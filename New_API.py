import os
import shutil
import uvicorn
import uuid
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pyngrok import ngrok, conf
from typing import Union

# Import your custom class from the inference.py file
from inference import SimpleInference

# --- Import your mini-dataset from a separate file ---
# Assuming dataset.py contains DATASET_IMAGES dictionary
from dataset import DATASET_IMAGES 

# --- Global Settings & Setup ---
VERIFIED_DIR = "verified_images"
os.makedirs(VERIFIED_DIR, exist_ok=True)
os.makedirs("dataset", exist_ok=True) # Ensure your dataset directory exists

app = FastAPI(
    title="RoboBrain Stateful API",
    description="A two-step API with RAG: 1. Verify an image. 2. Use the ID to send prompts.",
    version="4.0.0"
)

# --- Model Loading ---
print("Initializing server and loading model...")
model = SimpleInference("BAAI/RoboBrain2.0-3B")
print("Model loaded. Server is ready.")

# --- API Endpoints ---
@app.get("/")
def root():
    return {"message": "Welcome to the Stateful RoboBrain API. Use /verify and /prompt endpoints."}

@app.post("/verify")
async def verify_image_and_get_id(
    object_id: str = Form(..., description="A description of the object to verify in the image."),
    image: UploadFile = File(...)
):
    """
    Verifies an object using RAG if a keyword is detected, otherwise uses the foundation model only.
    """
    temp_upload_path = os.path.join(VERIFIED_DIR, f"temp_{image.filename}")
    
    try:
        with open(temp_upload_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        # Check if the object ID is a keyword in your mini-dataset
        reference_image_path = DATASET_IMAGES.get(object_id.lower())
        
        if reference_image_path:
            # --- KEYWORD DETECTED: USE RAG ---
            print(f"Keyword '{object_id}' detected. Running RAG verification.")
            images_for_inference = [os.path.abspath(temp_upload_path), reference_image_path]
            task_for_inference = "verify_based_on_reference"
        else:
            # --- KEYWORD NOT DETECTED: USE FOUNDATION MODEL ONLY ---
            print(f"Keyword '{object_id}' not found. Running verification with foundation model only.")
            images_for_inference = [os.path.abspath(temp_upload_path)]
            task_for_inference = "verify"

        # Run Verification with the selected images and task
        verification_result = model.inference(
            text=object_id,
            image=images_for_inference,
            task=task_for_inference,
            plot=False,
            enable_thinking=False,
            do_sample=True
        )

        if verification_result.get("answer") == "same":
            # Verification successful, save image and return ID
            image_id = str(uuid.uuid4())
            file_extension = os.path.splitext(image.filename)[1]
            permanent_path = os.path.join(VERIFIED_DIR, f"{image_id}{file_extension}")
            os.rename(temp_upload_path, permanent_path)
            
            print(f"Verification successful. Image saved as {image_id}{file_extension}")
            return {"status": "verified", "image_id": image_id}
        else:
            # Verification failed
            os.remove(temp_upload_path)
            print("Verification failed. Sending comedic error.")
            raise HTTPException(
                status_code=404, 
                detail="YOU DARE LIE TO ROBOBRAIN????"
            )
            
    except Exception as e:
        if os.path.exists(temp_upload_path):
            os.remove(temp_upload_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")


@app.post("/prompt")
async def run_prompt_on_verified_image(
    image_id: str = Form(..., description="The unique ID of the previously verified image."),
    prompt: str = Form(..., description="The pointing instruction for the model.")
):
    """
    Runs a pointing task on an image that has already been verified,
    using its unique image_id. RAG is enabled if a keyword from the
    mini-dataset is detected in the prompt.
    """
    # Find the image file by its ID, checking common extensions
    image_path = None
    for ext in ['.png', '.jpg', '.jpeg', '.webp']:
        potential_path = os.path.join(VERIFIED_DIR, f"{image_id}{ext}")
        if os.path.exists(potential_path):
            image_path = potential_path
            break
    
    if not image_path:
        raise HTTPException(status_code=404, detail=f"Image with ID '{image_id}' not found. Please verify the image first.")

    try:
        # --- NEW LOGIC: Check if the prompt contains a keyword for RAG ---
        found_keyword = None
        for keyword in DATASET_IMAGES.keys():
            # Check for keyword existence in the lowercase prompt
            if keyword in prompt.lower():
                found_keyword = keyword
                break
        
        if found_keyword:
            # --- KEYWORD DETECTED: USE RAG for pointing ---
            print(f"Keyword '{found_keyword}' detected in prompt. Running RAG pointing task.")
            images_for_inference = [os.path.abspath(image_path), DATASET_IMAGES.get(found_keyword)]
            task_for_inference = "pointing_based_on_reference"
        else:
            # --- KEYWORD NOT DETECTED: USE FOUNDATION MODEL ONLY ---
            print("Keyword not found in prompt. Running pointing with foundation model only.")
            images_for_inference = [os.path.abspath(image_path)]
            task_for_inference = "pointing"

        # Run Pointing Task with the selected images and task
        pointing_result = model.inference(
            text=prompt,
            image=images_for_inference,
            task=task_for_inference,
            plot=True,
            enable_thinking=False,
            do_sample=True
        )
        print("Pointing task complete.")
        return pointing_result

    except Exception as e:
        print(f"An error occurred during the pointing task: {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")

# --- Main execution block to start the server and ngrok tunnel ---
if __name__ == "__main__":
    NGROK_AUTHTOKEN = os.environ.get("NGROK_AUTHTOKEN")
    if NGROK_AUTHTOKEN is None:
        NGROK_AUTHTOKEN = input("Please enter your ngrok authtoken: ")
    
    try:
        conf.get_default().auth_token = NGROK_AUTHTOKEN
        public_url = ngrok.connect(8000, domain="balanced-vaguely-mastodon.ngrok-free.app")
        
        print("====================================================================")
        print(f"✅ Your server is live!")
        print(f"✅ Public URL: {public_url}")
        print("You can now use this URL in your client script from any network.")
        print("====================================================================")

        uvicorn.run(app, host="0.0.0.0", port=8000)

    except Exception as e:
        print(f"❌ An error occurred with ngrok: {e}")
        print("Please ensure your ngrok authtoken is correct and that ngrok is not already running.")
