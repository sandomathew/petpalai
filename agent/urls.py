from django.urls import path
from .views import agent_core_view, resume_pending_agent_tasks, stream_agent_messages

urlpatterns = [
    path('stream/start/', agent_core_view, name='agent_core'),
    path('stream/resume/', resume_pending_agent_tasks, name='agent-resume'),
    path('stream/<str:task_id>/', stream_agent_messages, name='stream_agent_messages'),
]