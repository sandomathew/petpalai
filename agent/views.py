import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .orchestrator import AgentOrchestrator


@csrf_exempt
def agent_core_view(request):
    """
    Core API endpoint for the agent chatbot.
    Receives user messages and delegates to the AgentOrchestrator.
    """
    if request.method != 'POST':
        return JsonResponse({"reply": "❌ Invalid method"}, status=405)

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        user = request.user if request.user.is_authenticated else None

        # The orchestrator handles all the logic: parsing, state management,
        # tool execution, and response generation.
        orchestrator = AgentOrchestrator(request, user)
        response_data = orchestrator.handle_message(message)

        return JsonResponse(response_data)

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
    """
    user = request.user

    try:
        orchestrator = AgentOrchestrator(request, user)
        response_data = orchestrator.resume_pending_tasks()
        #print("response_data ", response_data)

        return JsonResponse(response_data)

    except Exception as e:
        print(f"Error in resume_pending_agent_tasks: {e}")
        return JsonResponse({"reply": f"❌ Failed to resume tasks: {str(e)}"}, status=500)