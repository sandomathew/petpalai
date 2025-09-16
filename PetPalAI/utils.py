# --- Initialize the Ollama Client with a timeout ---
# You can do this once when your Django app starts up,
# or in the function if you prefer. Doing it here makes it reusable.
# Adjust the timeout (in seconds) as needed. 120 seconds (2 minutes) is a good start.
import json
import re
import ollama # Make sure you have 'ollama' installed: pip install ollama
from ollama import Client

ollama_client = Client(host='http://localhost:11434', timeout=120)

import chromadb
from chromadb.utils import embedding_functions
# Embedding function that is compatible with your LLM (e.g., Llama 3)
# Ollama provides a hostable embedding model like "nomic-embed-text" or "mxbai-embed-large"
# Make sure your Ollama instance is running with this model.
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    model_name="nomic-embed-text",
    url="http://localhost:11434"
)


def get_food_label_collection():
    client = chromadb.Client()
    collection = client.get_or_create_collection(
        name="food_label_collection",
        embedding_function=ollama_ef
    )
    return collection

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