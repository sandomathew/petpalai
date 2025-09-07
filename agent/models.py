from django.db import models
from django.contrib.auth.models import User
import uuid
# Create your models here.

class AgentCase(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
    ]

    case_id = models.CharField(max_length=50, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_cases')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    topic = models.CharField(max_length=100, blank=True)
    internal_notes = models.TextField(help_text="Detailed actions and decisions taken by PAAI")
    customer_notes = models.TextField(blank=True, help_text="Summary notes visible to user")
    resolved_by = models.CharField(max_length=100, blank=True, help_text="AI or human username")
    parsed_intents = models.JSONField(blank=True, null=True, help_text="All parsed intents")
    pending_intents = models.JSONField(null=True, blank=True,help_text="Pending intents")
    orchestrator_state = models.JSONField(default=dict, blank=True)
    ai_conversation_history = models.JSONField(blank=True, null=True, help_text="Case conversation history")

    def save(self, *args, **kwargs):
        if not self.case_id:
            self.case_id = f"{self.user.username.upper()}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.case_id} ({self.status})"


