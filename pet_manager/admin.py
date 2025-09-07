
from django.contrib import admin
from .models import Pet

@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'gender', 'weight_lbs', 'user')
    search_fields = ('name', 'species', 'owner__nickname')
    list_filter = ('species', 'gender')