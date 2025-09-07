from django.shortcuts import render, redirect
from django.conf import settings # To access MEDIA_ROOT
from PIL import Image # Pillow library for image processing
import pytesseract # Python wrapper for Tesseract OCR

import json
import re
import ollama # Make sure you have 'ollama' installed: pip install ollama
from ollama import Client
import os # For path manipulation
# Import your model and form
from .models import FoodLabelScan
from .forms import FoodLabelScanForm

from PetPalAI.utils import get_food_label_collection
import uuid # To generate unique IDs for documents


from django.contrib.auth.decorators import login_required

# --- Initialize the Ollama Client with a timeout ---
# You can do this once when your Django app starts up,
# or in the function if you prefer. Doing it here makes it reusable.
# Adjust the timeout (in seconds) as needed. 120 seconds (2 minutes) is a good start.
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract' # local machine path
ollama_client = Client(host='http://localhost:11434', timeout=120)


def parse_nutritional_data(raw_text):
    """
    Parses raw OCR text to extract structured nutritional data.
    """
    data = {
        "product_name": None,
        "guaranteed_analysis": {},
        "ingredients": [],
        "feeding_guide": None,
        "other_info": {}
    }
    extracted_kcal_per_kg = None
    extracted_kcal_per_unit = None
    # Product_name
    pattern = r"Animal feeding tests using AAFCO procedures substantiate that (.*?) provides complete and balanced nutrition for .*"

    match_product_name = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)  # re.DOTALL allows . to match newlines

    if match_product_name:
        data["product_name"] = match_product_name.group(1).strip()  # .strip() to remove any leading/trailing whitespace


    # Extracting Guaranteed Analysis (simplified) ---
    # Crude Protein
    match_protein = re.search(r'Crude Protein,\s*Min.\s*([\d.]+%)', raw_text, re.IGNORECASE)
    if match_protein:
        data["guaranteed_analysis"]["crude_protein"] = match_protein.group(1)

    # Crude Fat
    match_fat = re.search(r'Crude Fat,\s*Min.\s*([\d.]+%)', raw_text, re.IGNORECASE)
    if match_fat:
        data["guaranteed_analysis"]["crude_fat"] = match_fat.group(1)

    # Moisture
    match_moisture = re.search(r'Moisture,\s*Max.\s*([\d.]+%)', raw_text, re.IGNORECASE)
    if match_moisture:
        data["guaranteed_analysis"]["moisture"] = match_moisture.group(1)

    # Calorie Content
    # Regex to capture "816 kcal ME/kg" AND "67 kcal ME/can" (or similar)
    calorie_match = re.search(
        r'Calorie Content \(calculated\):\s*([\d.]+)\s*kcal ME/kg(?:;\s*([\d.]+)\s*kcal ME/(?:can|cup|treat))?',
        raw_text, re.IGNORECASE
    )

    if calorie_match:
        # First group is always kcal ME/kg
        kcal_per_kg_str = calorie_match.group(1)
        try:
            extracted_kcal_per_kg = float(kcal_per_kg_str)  # Convert to float
        except ValueError:
            extracted_kcal_per_kg = None  # Handle cases where conversion fails

        # Second group is optional (kcal per can/cup)
        if calorie_match.group(2):
            unit_type_match = re.search(r'kcal ME/(can|cup|treat)', raw_text, re.IGNORECASE)
            unit_type = unit_type_match.group(1) if unit_type_match else 'unit'
            extracted_kcal_per_unit = f"{calorie_match.group(2)} kcal ME/{unit_type}"

    # ... (your existing regex for ingredients list, etc.) ...
    ingredients_match = re.search(
        r'(?:Ingredients|Inaredients):\s*(.*?)(?=\s*Guaranteed Analysis:|Calorie Content:|DAILY FEEDING GUIDE:|AFCO Statement:|Ingredients : Bouillon|$)',
        raw_text, re.IGNORECASE | re.DOTALL)
    if ingredients_match:
        ingredients_string = ingredients_match.group(1).strip()
        ingredients_string = ingredients_string.replace('Inaredients:', 'Ingredients:')
        ingredients_string = ingredients_string.replace(':', '')
        ingredients_list = [item.strip() for item in re.split(r'[,;]', ingredients_string) if item.strip()]
        data["ingredients"] = ingredients_list

    # Return the data dict, kcal_per_kg, and kcal_per_unit
    return data, extracted_kcal_per_kg, extracted_kcal_per_unit

def generate_pros_cons(nutritional_data):
    """
    Generates AI-powered pros and cons for pet food based on parsed nutritional data.
    """
    if not nutritional_data or not isinstance(nutritional_data, dict):
        return "No valid nutritional data to analyze."

    # Convert the dictionary to a string for the LLM prompt
    nutritional_data_str = json.dumps(nutritional_data, indent=2)

    prompt = f"""
    Analyze the following pet food nutritional data and provide a concise list of pros and cons for a typical cat or dog owner.
    Focus on common concerns like protein content, fat content, moisture, ingredients (e.g., common allergens, quality of protein sources, fillers), and calorie content.
    Do not make medical recommendations. If data is incomplete or unclear, mention it in 'Notes'. Keep it to about 3-5 pros and 3-5 cons. Alert any recalls in last 2 years.

    Nutritional Data:
    {nutritional_data_str}

    Format your response as:
    Pros:
    - [Pro 1]
    - [Pro 2]
    ...
    Cons:
    - [Con 1]
    - [Con 2]
    ...
    Notes:
    - ...
    """

    try:
        # Assuming your Ollama server is running locally (default: http://localhost:11434)
        # Increase the timeout for the Ollama API call
        # Set to a value in seconds (e.g., 120 seconds = 2 minutes)
        # You might need to adjust this based on your system's performance.
        response = ollama_client.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': 'You are an AI assistant that analyzes pet food labels.'},
                {'role': 'user', 'content': prompt}
            ],
            options={'temperature': 0.7}
        )
        return response['message']['content']
    except ollama.ResponseError as e:  # Catch specific Ollama API errors
        print(f"Ollama API Error: {e}")
        return f"AI analysis failed due to Ollama API error: {e}"
    except Exception as e:
        print(f"General AI analysis error: {e}")
        return f"AI analysis failed: An unexpected error occurred. Error: {e}"


@login_required
def upload_label_view(request):
    """
    Handles image upload, OCR processing, and displays results.
    """
    # Initialize form outside the if/else to ensure it's always available for context
    form = FoodLabelScanForm()
    food_scan_instance = None # To hold the FoodLabelScan object if successfully processed
    error_message = None

    if request.method == 'POST':
        form = FoodLabelScanForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # Create a FoodLabelScan instance but don't save to DB yet (commit=False)
                # This allows us to modify it with OCR/AI results before final save.
                food_scan_instance = form.save(commit=False)

                # Set user if authenticated (optional for MVP)
                if request.user.is_authenticated:
                    food_scan_instance.user = request.user
                else:
                    food_scan_instance.user = None # Or link to a default/anonymous user if you set one up

                # Save the image file to MEDIA_ROOT
                food_scan_instance.save() # Saves the image to disk and creates a DB entry

                # --- 1. Perform OCR using pytesseract ---
                # Get the full path to the saved image file
                image_path = food_scan_instance.image.path
                try:
                    # Open the image using Pillow and pass to pytesseract
                    image = Image.open(image_path)
                    # convert to RGB to ensure a common mode, then grayscale.
                    image = image.convert('RGB')
                    #image = image.convert('L')  # Convert to grayscale
                    # OPTIONAL: Save the processed image for inspection
                    # This helps verify what Tesseract is actually receiving
                    # debug_image_path = os.path.join(settings.MEDIA_ROOT, 'debug_processed_image.png')
                    # image.save(debug_image_path)
                    raw_text = pytesseract.image_to_string(image)
                    food_scan_instance.raw_text = raw_text.strip()
                except pytesseract.TesseractNotFoundError:
                    raw_text = "ERROR: Tesseract OCR engine not found. Please ensure it's installed and in your PATH."
                    food_scan_instance.raw_text = raw_text
                    error_message = raw_text # Store error to display
                except Exception as e:
                    raw_text = f"ERROR during OCR: {e}"
                    food_scan_instance.raw_text = raw_text
                    error_message = raw_text

                # --- 2. Plug in your parsing logic ---
                # Pass the raw_text to your parsing function
                parsed_data_dict, kcal_per_kg_decimal, kcal_per_unit_str = parse_nutritional_data(food_scan_instance.raw_text)
                food_scan_instance.parsed_data = parsed_data_dict
                food_scan_instance.calorie_content_kcal_per_kg = kcal_per_kg_decimal
                food_scan_instance.calorie_content_per_unit = kcal_per_unit_str

                print("food_scan_instance.parsed_data ", parsed_data_dict)
                # --- 3. Plug in your AI analysis logic ---
                # Pass the parsed_data to your LLM function
                if parsed_data_dict.get("ingredients"):
                    food_scan_instance.ai_analysis = generate_pros_cons(parsed_data_dict)
                    # Add parsed data to the Vector Database
                    collection = get_food_label_collection()
                    # Count the number of items before adding
                    initial_count = collection.count()

                    # Create a string representation of the parsed data
                    doc_content = f"Product Name: {parsed_data_dict.get('product_name')}\n" \
                                  f"Ingredients: {', '.join(parsed_data_dict.get('ingredients', []))}\n" \
                                  f"Analysis: {parsed_data_dict.get('guaranteed_analysis')}"

                    # Add the document to the collection
                    collection.add(
                        documents=[doc_content],
                        metadatas=[{"product_name": parsed_data_dict.get('product_name')}],
                        ids=[str(uuid.uuid4())]
                    )

                    # Count the number of items after adding
                    final_count = collection.count()

                    # Print the result to your terminal
                    print(f"ChromaDB Status: Initial count was {initial_count}, Final count is {final_count}.")
                    if final_count > initial_count:
                        print("✅ Document successfully added to the vector database.")
                    else:
                        print("❌ Document was NOT added to the vector database. Check for errors.")

                else:
                    food_scan_instance.ai_analysis = "AI analysis skipped: No ingredient list found in the label."


                # Save the FoodLabelScan instance again with the processed data
                food_scan_instance.save()

                # At this point, food_scan_instance contains all the data.
                # It will be passed to the template for display.

            except Exception as e:
                error_message = f"An unexpected error occurred during processing: {e}"
                food_scan_instance = None # Clear instance if processing failed

        else:
            # Form is not valid, error messages will be in form.errors
            pass # Form will be rendered again with errors

    context = {
        'form': form,
        'food_scan': food_scan_instance, # Pass the processed scan or None
        'error_message': error_message,
    }
    return render(request, 'petfood_analyzer/upload.html', context)