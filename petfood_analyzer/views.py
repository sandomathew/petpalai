from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
import threading
import json
import time
from django.core.files.storage import default_storage
from PIL import Image # Pillow library for image processing
import pytesseract # Python wrapper for Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract' # local machine path
import os # For path manipulation
# Import your model and form
from .models import FoodLabelScan
from .forms import FoodLabelScanForm

from PetPalAI.utils import get_food_label_collection, generate_pros_cons, parse_nutritional_data
import uuid # To generate unique IDs for documents


from django.contrib.auth.decorators import login_required

# A simple dictionary to store stream results.
# For production, use a proper cache (e.g., Redis)
# In-memory storage for stream data. NOT for production.
stream_data_store = {}

@login_required
def upload_label_view(request):
    """
    Handles image upload, OCR processing, and displays results.
    """
    # Initialize form outside the if/else to ensure it's always available for context
    form = FoodLabelScanForm()
    context = {
        'form': form,
    }
    return render(request, 'petfood_analyzer/upload.html', context)


@login_required
@csrf_exempt
def start_stream_analysis(request):
    """
    Receives the image via POST, saves it, and starts the background
    analysis process. Returns a task ID immediately.
    """
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            food_type = request.POST.get('food_type')

            task_id = str(uuid.uuid4())

            # Save file to a temporary location to pass to the thread
            file_path = default_storage.save(f'tmp/{task_id}_{image_file.name}', ContentFile(image_file.read()))

            # Initialize a placeholder for the stream data
            stream_data_store[task_id] = {'status': 'pending', 'data': []}

            # Start the background thread
            thread = threading.Thread(
                target=process_and_stream_data,
                args=(request.user, food_type, file_path, task_id)
            )
            thread.start()

            return JsonResponse({'status': 'processing', 'task_id': task_id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Failed to start analysis: {e}'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

# Helper function to generate events for the stream
def process_and_stream_data(user, food_type, file_path, task_id):
    """
    This function runs in a separate thread. It performs the OCR and LLM
    analysis and stores the results for streaming.
    """
    try:
        # Step 1: Initialize DB object and update status
        food_scan_instance = FoodLabelScan(user=user, food_type=food_type)
        food_scan_instance.image.name = file_path
        stream_data_store[task_id]['data'].append({"status": "processing", "message": "Starting OCR..."})


        # Step 2: Perform OCR and update status
        image = Image.open(food_scan_instance.image.path)
        raw_text = pytesseract.image_to_string(image.convert('RGB'))
        food_scan_instance.raw_text = raw_text.strip()
        stream_data_store[task_id]['data'].append({"status": "ocr_complete", "raw_text": food_scan_instance.raw_text})

        # --- 2. Parse and Analyze ---
        parsed_data_dict, kcal_per_kg_decimal, kcal_per_unit_str = parse_nutritional_data(food_scan_instance.raw_text)
        food_scan_instance.parsed_data = parsed_data_dict

        # 2. Simulate LLM Analysis
        if parsed_data_dict.get("ingredients"):
            stream_data_store[task_id]['data'].append({"status": "processing", "message": "Starting AI analysis..."})
            food_scan_instance.ai_analysis = generate_pros_cons(parsed_data_dict)

            # Add to VectorDB...
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

            stream_data_store[task_id]['data'].append(
                {"status": "llm_complete", "ai_analysis": food_scan_instance.ai_analysis})
        else:
            food_scan_instance.ai_analysis = "AI analysis skipped: No ingredient list found."
            stream_data_store[task_id]['data'].append(
                {"status": "llm_complete", "ai_analysis": food_scan_instance.ai_analysis})

        # Finalize and save to DB
        food_scan_instance.save()
        default_storage.delete(file_path)

        stream_data_store[task_id]['data'].append({"status": "completed"})
        stream_data_store[task_id]['status'] = 'completed'

    except Exception as e:
        stream_data_store[task_id]['status'] = 'error'
        stream_data_store[task_id]['message'] = str(e)


def event_stream(request, task_id):
    """
    Streams data from the temporary store to the client.
    """

    def event_generator():
        last_index = 0
        last_update = time.time()
        timeout_threshold = 20  # seconds
        while True:
            if task_id in stream_data_store:
                data = stream_data_store[task_id]['data']
                while last_index < len(data):
                    message = data[last_index]
                    yield f"data: {json.dumps(message)}\n\n"
                    last_index += 1
                    last_update = time.time()

                # Send a keep-alive message if no new data for a while
                if (time.time() - last_update) > timeout_threshold:
                    yield "event: keep-alive\ndata: {}\n\n"
                    last_update = time.time()  # Reset timer

                # Exit the loop when the process is complete or an error occurs
                if task_id in stream_data_store and stream_data_store[task_id]['status'] != 'pending':
                    break

            # Sleep to avoid high CPU usage
            time.sleep(1)

        if task_id in stream_data_store and stream_data_store[task_id]['status'] == 'completed':
            del stream_data_store[task_id]

    response = StreamingHttpResponse(event_generator(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response