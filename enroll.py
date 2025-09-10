# enroll.py

import requests
import os
from Resize import process_and_resize_image

# --- CONFIGURE THIS SECTION FOR EACH OBJECT ---
SERVER_URL = "https://balanced-vaguely-mastodon.ngrok-free.app"
IMAGE_TO_ENROLL = process_and_resize_image("power_bank.png", 512)
OBJECT_DESCRIPTION = "a black MIXIO power bank"
# ---------------------------------------------

def enroll_object():
    """Sends a reference 'truth image' to the server to be saved and indexed."""
    enroll_url = f"{SERVER_URL}/enroll"

    if not os.path.exists(IMAGE_TO_ENROLL):
        print(f"Error: Image file not found at '{IMAGE_TO_ENROLL}'")
        return

    print(f"Enrolling '{IMAGE_TO_ENROLL}' as '{OBJECT_DESCRIPTION}'...")
    
    with open(IMAGE_TO_ENROLL, 'rb') as f:
        files = {'image': (IMAGE_TO_ENROLL, f, 'image/png')}
        payload = {'description': OBJECT_DESCRIPTION}
        
        try:
            response = requests.post(enroll_url, files=files, data=payload, timeout=20)
            response.raise_for_status()
            print("\n✅ Enrollment successful!")
            print("Server Response:", response.json())
        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error during enrollment: {e}")
            if e.response:
                print("Server Error Details:", e.response.text)

if __name__ == "__main__":
    enroll_object()