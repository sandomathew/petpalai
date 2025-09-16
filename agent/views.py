import json
import threading
import uuid
import time
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .orchestrator import AgentOrchestrator, STREAM_DATA_STORE


@csrf_exempt
def agent_core_view(request):
    """
    Core API endpoint for the agent chatbot.
    Receives user messages, delegates to the AgentOrchestrator and returns a task ID.
    """
    if request.method != 'POST':
        return JsonResponse({"reply": "❌ Invalid method"}, status=405)

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        task_id = str(uuid.uuid4())
        user = request.user if request.user.is_authenticated else None

        # The orchestrator handles all the logic: parsing, state management,
        # tool execution, and response generation.
        # Offload the orchestration logic to a separate thread
        thread = threading.Thread(
            target=lambda: AgentOrchestrator(request, user , task_id).handle_message(message)
        )
        thread.start()
        # orchestrator = AgentOrchestrator(request, user)
        # response_data = orchestrator.handle_message(message)

        return JsonResponse({"task_id": task_id})

    except json.JSONDecodeError:
        return JsonResponse({"reply": "❌ Invalid JSON payload."}, status=400)
    except Exception as e:
        # Generic error handling to prevent crashes
        print(f"Error in agent_core_view: {e}")
        return JsonResponse({"reply": f"❌ An unexpected error occurred: {str(e)}"}, status=500)


@csrf_exempt
@login_required
def resume_pending_agent_tasks(request):
    """
    API endpoint to resume any pending tasks for a logged-in user.
    Kicks off the resume process in a background thread and returns a task ID.
    """
    print("inside resume_pending_agent_tasks")

    try:

        if request.method == 'GET':
            user = request.user
            task_id = str(uuid.uuid4())
            # Initialize the stream store for the new task
            STREAM_DATA_STORE[task_id] = {'status': 'pending', 'data': []}
            # The orchestrator handles all the logic: parsing, state management,
            # tool execution, and response generation.
            # Offload the orchestration logic to a separate thread
            thread = threading.Thread(
                target=lambda: AgentOrchestrator(request, user, task_id).resume_pending_tasks()
            )
            thread.start()
            #print("response_data ", response_data)

            return JsonResponse({"task_id": task_id})

    except Exception as e:
        print(f"Error in resume_pending_agent_tasks: {e}")
        return JsonResponse({"reply": f"❌ Failed to resume tasks: {str(e)}"}, status=500)


@csrf_exempt
def stream_agent_messages(request, task_id):
    """Streams messages from the agent to the client."""

    def event_generator():
        last_index = 0
        last_update = time.time()
        timeout_threshold = 20  # Keep-alive timeout

        while True:
            if task_id in STREAM_DATA_STORE:
                messages = STREAM_DATA_STORE[task_id]['data']
                while last_index < len(messages):
                    message = messages[last_index]
                    yield f"data: {json.dumps(message)}\n\n"
                    last_index += 1
                    last_update = time.time()

                if STREAM_DATA_STORE[task_id]['status'] == 'completed':
                    del STREAM_DATA_STORE[task_id]
                    break

            # Send a keep-alive message if no new data for a while
            if (time.time() - last_update) > timeout_threshold:
                yield "event: keep-alive\ndata: {}\n\n"
                last_update = time.time()

            time.sleep(1)

    return StreamingHttpResponse(event_generator(), content_type="text/event-stream")