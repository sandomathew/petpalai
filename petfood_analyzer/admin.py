from django.contrib import admin
from .models import FoodLabelScan

# Register your models here.
@admin.register(FoodLabelScan)
class FoodLabelScanAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'food_type', 'scanned_at', 'user') # Customize as you like
    # Add search_fields, list_filter etc. as discussed previously for convenience