from django.urls import path
from .views import agent_core_view, resume_pending_agent_tasks

urlpatterns = [
    path('', agent_core_view, name='agent_core'),
    path('resume/', resume_pending_agent_tasks, name='agent-resume'),
]