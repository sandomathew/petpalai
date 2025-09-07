from django import forms
from .models import FoodLabelScan

class FoodLabelScanForm(forms.ModelForm):
    """
    A form for uploading a pet food label image.
    """
    class Meta:
        model = FoodLabelScan
        # Only include the 'image' field for now for simplicity.
        # We'll populate 'raw_text', 'parsed_data', 'ai_analysis' in the view.
        # You could also add 'product_name' and 'food_type' here if you want user input for them immediately.
        fields = ['image', 'pet_type', 'product_name', 'food_type']

        # Optional: Add help text or labels for clarity in the form
        labels = {
            'image': 'Upload Pet Food Label Image',
            'pet_type': 'Enter you Pet Species',
            'product_name': 'Product Name (Optional)',
            'food_type': 'Food Type',
        }
        help_texts = {
            'image': 'Upload a clear image of the nutritional information on the label.',
            'pet_type': 'Select the pet species from the list.',
            'product_name': 'Enter the common name of the product (e.g., "Wellness Core Dog Food").',
            'food_type': 'Select the type of food from the list.',
        }
