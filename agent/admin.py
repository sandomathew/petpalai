from django.contrib import admin
from .models import AgentCase
# Register your models here.

@admin.register(AgentCase)
class AgentCaseAdmin(admin.ModelAdmin):
    list_display = ('case_id', 'user', 'status', 'created_at', 'updated_at', 'resolved_by')
    list_filter = ('status', 'created_at', 'resolved_by')
    search_fields = ('case_id', 'user__username', 'internal_notes', 'customer_notes')
    readonly_fields = ('case_id', 'created_at', 'updated_at')


