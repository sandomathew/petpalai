# agent/llm_parser.py
import json
import re
import ollama # Make sure you have 'ollama' installed: pip install ollama
from ollama import Client
ollama_client = Client(host='http://localhost:11434', timeout=120)


def extract_json_block(text):
    """Extract JSON block from the LLM output using regex."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    return match.group(0) if match else "[]"

def try_llm_parser(message):
    prompt = f"""
You are a smart assistant for PetPalAI that turns natural language commands into structured JSON.

Your job is to extract **intent(s)** from the user's message and return a JSON list with each intent as an object.

Supported intents:
- register_user (params: name, email)
- create_pet (params: name, species, breed, birth_date, gender, weight_lbs)
- food_query (params: query)
- analyze_food (no params)
- provide_followup (params: user message)

example species are dog, cat, bird etc.,example breed are poodle, short haired domestic, exotic etc..

If the message does not contain above Supported intents (register user, create pet, analyze_food, etc.),
return an empty list [].
Do not guess.

Respond ONLY with valid JSON array. Example:
[
  {{
    "intent": "register_user",
    "params": {{
      "name": "Sam",
      "email": "sam@email.com"
    }}
  }},
  {{
    "intent": "create_pet",
    "params": {{
      "name": "Luna",
      "species": "cat",
      "breed": "short haired domestic",
      "gender": "neutered male",
      "weight_lbs": 12
    }}
  }},
  {{
    "intent": "create_pet",
    "params": {{
      "name": "Tommy",
      "species": "dog",
      "breed": "poodle",
      "gender": "neutered male",
      "weight_lbs": 80,
      "age": 2
    }}
  }},
  {{
    "intent": "food_query",
    "params": {{
      "query": "<user message>"
    }}
  }},
  {{"intent": "provide_followup", 
  "params": {{
    "text": "<user message>"
    }}
  }}
]

User message: {message}
"""

    try:
        response = ollama_client.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': 'You are an AI assistant that extracts intent from pet-related user requests.'},
                {'role': 'user', 'content': prompt}
            ],
            options={'temperature': 0.2}
        )

        raw = response['message']['content'].strip()
        #print("🧪 LLM raw output:\n", raw)

        json_text = extract_json_block(raw)
        return json.loads(json_text)

    except Exception as e:
        print("❌ LLM parse failed:", e)
        return []


def llm_one_shot(messages):
    """
    Generic helper for single-turn LLM queries with chat history.
    messages = list of { "role": "system"/"user"/"assistant", "content": "..." }
    """
    response = ollama_client.chat(
        model='llama3.2',
        messages=messages,
        options={'temperature': 0.2}
    )

    return response['message']['content'].strip()


def llm_summarize(conversation_history):
    """
    Summarize long conversations into a compact form.
    Useful for persistence in AgentCase.internal_notes.
    """
    summary_prompt = [
        {"role": "system", "content": "You are an assistant that summarizes conversations."},
        {"role": "user", "content": f"Summarize this conversation in under 200 words:\n{conversation_history}"}
    ]

    return llm_one_shot(summary_prompt)
