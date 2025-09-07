# PetPalAI/agent/orchestrator.py

import json
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.timezone import now
from datetime import datetime

# Import LLM and rule-based parsers
from .llm_parser import try_llm_parser, llm_one_shot
from .rule_parser import fallback_regex_parser
from .models import AgentCase

# Import business logic "tools"
from pet_manager.utils import create_pet_via_agent
from user_profile.utils import register_user_via_agent
from PetPalAI.utils import get_food_label_collection

class PetSlots:
    def __init__(self, name=None, species=None, breed=None, gender=None, weight_lbs=None, birth_date=None):
        self.name = name
        self.species = species
        self.breed = breed
        self.gender = gender
        self.weight_lbs = weight_lbs
        self.birth_date = birth_date

    def as_dict(self):
        # Returns a dictionary of all filled slots
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def is_complete(self):
        # Checks if all required fields are filled
        required = [self.name, self.species, self.breed]
        return all(required)

    def get_missing_field(self):
        # Returns the name of the first missing required field
        if not self.name: return "name"
        if not self.species: return "species"
        if not self.breed: return "breed"
        return None

class AgentOrchestrator:
    def __init__(self, request, user):
        self.request = request
        self.user = user
        # Get or create an active case for the session
        self.case = self._get_or_create_active_case()

    def _get_or_create_active_case(self):
        """
        Retrieves an active case from the session or creates a new one.
        Handles re-assignment if a guest user logs in mid-conversation.
        """
        case_id = self.request.session.get("active_case_id")
        case = None
        if case_id:
            case = AgentCase.objects.filter(case_id=case_id).first()

        if not case:
            # Create a guest user if the request is unauthenticated
            guest_user, _ = User.objects.get_or_create(username="guest")
            case = AgentCase.objects.create(
                user=self.user if self.user else guest_user,
                topic="Agent session"
            )
            self.request.session["active_case_id"] = case.case_id

        # If the user logs in later, associate the case with their account
        if self.user and case.user.username == "guest":
            case.user = self.user
            case.save(update_fields=["user"])

        return case

    def _add_to_conversation_history(self, role, content):
        """Logs a conversation turn to the database using the ConversationTurn model."""
        """
            Appends a new conversation turn to the JSONField history.
            Args:
                case_instance: The Django model instance (e.g., AgentCase)
                role (str): The role of the speaker (e.g., "User", "AI")
                message (str): The content of the message
            """
        # 1. Retrieve the existing history.
        # Use .json() to get a copy or default to an empty list.
        case = self.case
        history = case.ai_conversation_history
        if not isinstance(history, list):
            history = []

        # 2. Append the new message dictionary.
        new_turn = {"role": role, "message": content}
        history.append(new_turn)

        # 3. Save the updated list back to the field.
        case.ai_conversation_history = history
        case.save()

    def _execute_intent(self, intent, params):

        """Dispatches to the correct business logic "tool" based on the intent."""
        tool_registry = {
            "register_user": register_user_via_agent,
            "create_pet": create_pet_via_agent,
            "analyze_food": lambda user, params: (
            "📸 Please upload the food label on the main page.", "Requested food analysis"),
            "food_query": self._handle_food_query  # Your RAG handler
        }

        tool_func = tool_registry.get(intent)
        if not tool_func:
            return "🤔 Sorry, I didn’t understand that.", f"Unknown intent: {intent}"

        try:
            # Execute the tool
            if intent == "register_user":
                result, new_user = tool_func(params.get("name"), params.get("email"))
                if new_user and self.case.user.username == "guest":
                    self.case.user = new_user
                    self.case.save(update_fields=['user'])

            # Add a specific check for "food_query" if its handler has a different signature
            elif intent == "food_query":
                result = tool_func(params.get('query'))
                print("food query tool func result - ", result)
                internal_log = result["log"]
            else:
                result = tool_func(self.user, params)

            if result["success"]:
                internal_log = f"✅ Executed `{intent}` with `{params}` successfully."
            else:
                internal_log = f" Unable to process `{intent}` with `{params}`."

            return result , internal_log

        except Exception as e:
            # Re-raise the exception to allow the atomic block to fail
            # this is crucial for the transaction to be rolled back.
            raise e

    @transaction.atomic
    def handle_message(self, message):
        """Main orchestration method for a single user message."""
        self._add_to_conversation_history("user", message)

        replies, deferred_intents = [], []

        # Handle "provide_followup" intent first if a conversation is in progress
        state = self.case.orchestrator_state or {}
        last_question = state.get("last_question")

        if last_question:
            print("last_question - ",last_question)
            return self._handle_follow_up(message, last_question)

        # 1. Parse the message for intents
        # ... (parsing logic) ...
        parsed_intents = try_llm_parser(message)
        print("inside handle_message")
        print("message - ", message)
        print("parsed_intents - ", parsed_intents)
        if parsed_intents:
            self.case.parsed_intents = parsed_intents
            self.case.updated_at = datetime.now()
            self.case.save()
        else:
            # If LLM fails, use the rule-based parser as a fallback
            _, regex_intent = fallback_regex_parser(message)
            parsed_intents = [regex_intent]
            print("regex_intent - ", regex_intent)

        # 2. Iterate through parsed intents and execute them
        for intent_data in parsed_intents:
            try:

                intent = intent_data.get("intent")
                params = intent_data.get("params", {})

                # 🔒 Defer if login is required and the user isn't authenticated
                if intent != "register_user" and not self.user:
                    deferred_intents.append(intent_data)
                    continue

                # 🐾 Special handling for "create_pet"
                if intent == "create_pet":
                    slots = PetSlots(
                        name=params.get("name"),
                        species=params.get("species"),
                        breed=params.get("breed"),
                        gender=params.get("gender"),
                        weight_lbs=params.get("weight_lbs"),
                        birth_date=params.get("birth_date"),
                    )

                    if not slots.is_complete():
                        missing_field = slots.get_missing_field()
                        question = self._get_follow_up_question(missing_field, slots)
                        self._save_state_and_ask(slots, question)
                        replies.append(question)
                        continue  # 🚫 Don't call the tool yet

                # ✅ Execute the intent and get the reply
                result, internal_log = self._execute_intent(intent_data.get("intent"), intent_data.get("params", {}))
                reply = result["message"]
                replies.append(reply)
                self.case.internal_notes += f"\n- {internal_log}"
                self.case.customer_notes += f"\n- {reply}"
            except Exception as e:
                # Catch the exception, add a user-friendly message, and then break
                # The outer transaction.atomic block will handle the rollback.
                deferred_intents.append(intent_data)
                replies.append(f"❌ Failed to complete your request. Please try again or rephrase.")
                self.case.internal_notes += f"\n- ❌ Transaction failed due to an unhandled error: {e}"
                break

        # 3. Handle deferred intents
        if deferred_intents:
            self.case.pending_intents = deferred_intents
            self.case.internal_notes += "\n- 💾 Saved deferred intents."
            replies.append("\n🔐 Please [log in](/login/) to complete the remaining tasks.")
        else:
            self.case.status = "resolved"

        # 4. Finalize the case
        self.case.updated_at = datetime.now()
        self.case.save()

        reply_text = "\n".join(replies) if replies else "✅ Noted."
        self._add_to_conversation_history("agent", reply_text)

        return {"reply": reply_text}

    @transaction.atomic
    def resume_pending_tasks(self):
        """Method to resume pending tasks for a logged-in user."""
        print("inside resume_pending_tasks")
        # Get the latest case with pending intents for the user
        self.case = AgentCase.objects.filter(user=self.user,status="open",pending_intents__isnull=False).order_by(
            '-updated_at').first()



        if not self.case or not self.case.pending_intents:
            return {"history":[],
                    "reply": "👋 Hi! I'm PAAI – your PetPalAI Agent. <br> Please note: your interactions may be reviewed for quality and improvement purposes."}
            #return {"reply": "👋 Hi! I'm PAAI – your PetPalAI Agent. <br> Please note: your interactions may be reviewed for quality and improvement purposes."}

                    # ✅ fetch old conversation from case
        history = getattr(self.case, "ai_conversation_history", [])
        if not history:
            # fallback to conversation turns table if you’re using that model
            history = [
                {"role": t.role, "message": t.content}
                for t in self.case.conversation.all().order_by("created_at")
            ]

        self._add_to_conversation_history("agent", "Resuming pending tasks.")
        replies = []
        pending = list(self.case.pending_intents)  # Create a copy to iterate

        for intent_data in pending:
            intent = intent_data.get("intent")
            params = intent_data.get("params", {})
            result, internal_log = self._execute_intent(intent, params)
            reply = result["message"]
            replies.append(reply)
            self.case.internal_notes += f"\n- 🔁 Resumed: {internal_log}"
            self.case.customer_notes += f"\n- {reply}"

        # Clear the pending intents after successful execution
        self.case.pending_intents = []
        self.case.updated_at = now()
        self.case.status = "resolved"
        reply_text = "\n".join(replies)
        self._add_to_conversation_history("agent", reply_text)
        self.case.save()

        return {"history":history,
                "reply": reply_text}

    def _handle_food_query(self, user_query):
        """Performs a RAG search on the vector database and generates a response."""
        if not user_query:
            return {"success": False,
                "message": "Please provide a query about pet food.",
                "log": "No query provided for food_query intent."
                }

        # 1. Retrieval: Query the vector database
        collection = get_food_label_collection()
        results = collection.query(
            query_texts=[user_query],
            n_results=5  # Get the top 5 most relevant documents
        )

        # 2. Format the retrieved context for the LLM
        retrieved_docs = results['documents'][0]
        #print("retrieved_docs ", retrieved_docs)
        if not retrieved_docs:
            return {"success": True,
                "message": "I couldn't find any food labels matching that query.",
                "log": f"No documents found in vector DB for user query - {user_query}."
                }

        retrieved_context = "\n---\n".join(retrieved_docs)

        # 3. Generation: Use the LLM to generate a final answer
        prompt = f"""
        You are an expert on pet food analysis. Use the following scanned food label data to answer the user's question. 
        Focus only on the provided context. If the context does not contain the answer, state that you do not have enough information.

        Context from scanned labels:
        {retrieved_context}

        User's Question:
        {user_query}
        """

        llm_response = llm_one_shot(messages=[
            {'role': 'system', 'content': 'You are a helpful pet food analyst.'},
            {'role': 'user', 'content': prompt}
        ])

        return {"success": True,
                "message": llm_response,
                "log": "RAG-powered analysis completed."
                }

    def _handle_follow_up(self, message, last_question):
        print("inside _handle_follow_up")
        state = self.case.orchestrator_state
        slots = PetSlots(**state.get("slots", {}))

        # Check for example/clarification requests
        if message.lower() in ["examples", "give me examples", "not sure", "sample"]:
            reply = self._get_clarifying_examples(last_question)
            self._add_to_conversation_history("agent", reply)
            return {"reply": reply}

        # If not an example request, update the slots
        updated_slots = self._update_slots_with_reply(slots, last_question, message)

        if not updated_slots.is_complete():
            missing_field = updated_slots.get_missing_field()
            question = self._get_follow_up_question(missing_field, updated_slots)
            self._save_state_and_ask(updated_slots, question)
            return {"reply": question}

        # All slots are filled, so execute the tool
        result = create_pet_via_agent(self.user, updated_slots.as_dict())
        self._clear_state()
        self._add_to_conversation_history("agent", result["message"])
        return {"reply": result["message"]}

    def _get_clarifying_examples(self, question):
        if "breed" in question.lower():
            return "Sure! Examples of breeds include: Domestic shorthair, Labrador, German Shepherd, Siamese, Poodle."
        if "species" in question.lower():
            return "I can help with dogs, cats, birds, and more! What species is your pet?"
        return "I can help you add a pet, create a user account, and more!"

    def _save_state_and_ask(self, slots, question):
        state = self.case.orchestrator_state or {}
        state['slots'] = slots.as_dict()
        state['last_question'] = question
        self.case.orchestrator_state = state
        self.case.save()
        self._add_to_conversation_history("agent", question)

    def _clear_state(self):
        self.case.orchestrator_state = {}
        self.case.save(update_fields=["orchestrator_state"])

    # You'll also need a new helper to process the user's reply
    def _update_slots_with_reply(self, slots, last_question, reply):
        if "what is your pet's name" in last_question.lower():
            slots.name = reply
        elif "what species is" in last_question.lower():
            slots.species = reply
        elif "what is the breed" in last_question.lower():
            slots.breed = reply
        # Add more `elif` statements for other fields
        return slots

    def _get_follow_up_question(self, missing_field, slots):
        if missing_field == "name":
            return "🐾 What is your pet's name?"
        if missing_field == "species":
            return f"🐾 What species is {slots.name or 'your pet'}? (e.g., Dog, Cat, Bird)"
        if missing_field == "breed":
            return f"🐾 What is the breed of {slots.name or 'your pet'}?"
        return f"🐾 Could you provide the {missing_field} of your pet?"

