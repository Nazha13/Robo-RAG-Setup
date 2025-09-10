import os
import requests
import time
import ast
from tkinter import Tk, filedialog
from PIL import Image, ImageDraw
from io import BytesIO
from rich.console import Console

# --- Configuration ---
# 💡 IMPORTANT: Replace this with your actual ngrok public URL from the server
SERVER_URL = "https://balanced-vaguely-mastodon.ngrok-free.app" 
RESULTS_DIR = "test_results"

# --- Setup ---
console = Console()
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- Helper Functions ---

def select_image_file():
    """Opens a file dialog to select an image and returns its path."""
    console.print("Opening file dialog to select an image...", style="yellow")
    root = Tk()
    root.withdraw()  # Hide the main tkinter window
    filepath = filedialog.askopenfilename(
        title="Select Test Image",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
    )
    if not filepath:
        console.print("No file selected. Aborting test.", style="bold red")
        return None
    console.print(f"Selected image: [cyan]{os.path.basename(filepath)}[/cyan]")
    return filepath

def verify_image(image_path: str, object_id: str) -> str | None:
    """Sends image to /verify endpoint and returns the image_id on success."""
    verify_url = f"{SERVER_URL}/verify"
    console.print(f"Step 1: Verifying '{object_id}'...", style="bold blue")

    try:
        with open(image_path, "rb") as image_file:
            files = {"image": (os.path.basename(image_path), image_file)}
            data = {"object_id": object_id}
            
            response = requests.post(verify_url, files=files, data=data, timeout=120)

            if response.status_code == 200:
                result = response.json()
                image_id = result.get("image_id")
                console.print(f"✅ Verification successful! Image ID: [bold green]{image_id}[/bold green]")
                return image_id
            else:
                console.print(f"❌ Verification failed (HTTP {response.status_code})", style="bold red")
                console.print(f"Server says: {response.text}")
                return None
                
    except requests.exceptions.RequestException as e:
        console.print(f"❌ A network error occurred: {e}", style="bold red")
        return None

def run_prompt(image_id: str, prompt: str, original_image_path: str):
    """
    Sends prompt to server, gets coordinates, draws a dot on the original image,
    and saves/displays the result.
    """
    prompt_url = f"{SERVER_URL}/prompt"
    console.print(f"Step 2: Running prompt '{prompt}'...", style="bold blue")

    try:
        data = {"image_id": image_id, "prompt": prompt}
        response = requests.post(prompt_url, data=data, timeout=180)

        if response.status_code == 200:
            result_data = response.json()
            console.print("✅ Task complete. Received JSON response:", style="green")
            console.print(result_data)

            # --- UPDATED DRAWING LOGIC ---
            coordinates = None
            answer_string = result_data.get('answer') # Get the string from the 'answer' key

            if answer_string:
                try:
                    # Safely convert the string '[(343, 526)]' into a Python list [(343, 526)]
                    parsed_list = ast.literal_eval(answer_string)
                    
                    # Check if we got a list with at least one coordinate tuple inside
                    if isinstance(parsed_list, list) and len(parsed_list) > 0:
                        coordinates = parsed_list[0] # Grab the first tuple, e.g., (343, 526)
                        
                except (ValueError, SyntaxError):
                    console.print(f"Could not parse coordinates from the server's answer string: {answer_string}", style="yellow")

            # Now, check if we successfully got the coordinates before drawing
            if coordinates and len(coordinates) == 2:
                # Open the original image to draw on
                image = Image.open(original_image_path).convert("RGB")
                draw = ImageDraw.Draw(image)

                # Define dot properties
                x, y = coordinates
                radius = 15  # Dot size
                color = "green"
                
                # Calculate bounding box for the circle
                bounding_box = [x - radius, y - radius, x + radius, y + radius]
                draw.ellipse(bounding_box, fill=color, outline=color)

                # Save the modified image
                timestamp = int(time.time())
                filename = f"result_{timestamp}_{image_id}.png"
                save_path = os.path.join(RESULTS_DIR, filename)
                image.save(save_path)
                
                console.print(f"Dot drawn at ({x},{y}). Result saved to: [cyan]{save_path}[/cyan]")
                
                # Display the image with the dot
                image.show()
            else:
                console.print("Could not find point coordinates in the server response.", style="yellow")

        else:
            console.print(f"❌ Prompt failed (HTTP {response.status_code})", style="bold red")
            console.print(f"Server says: {response.text}")

    except requests.exceptions.RequestException as e:
        console.print(f"❌ A network error occurred: {e}", style="bold red")

def run_full_test_flow() -> dict | None:
    """Orchestrates the entire test flow from file selection to prompt."""
    image_path = select_image_file()
    if not image_path:
        return None
    
    return run_reprompt_flow(image_path)

def run_reprompt_flow(image_path: str) -> dict | None:
    """
    Takes an existing image path, asks for a new object_id and prompt,
    and runs the verification and pointing steps.
    """
    try:
        object_id = console.input("Enter the [bold]Object ID[/bold] for verification (e.g., 'kettle'): ")
        prompt = console.input("Enter the [bold]Prompt[/bold] for pointing (e.g., 'point to the power switch'): ")
    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user.", style="yellow")
        return None

    if not all([object_id, prompt]):
        console.print("Object ID and Prompt cannot be empty. Aborting.", style="bold red")
        return None

    image_id = verify_image(image_path, object_id)
    if image_id:
        run_prompt(image_id, prompt, image_path)
        # Return the data so it becomes the new "last run"
        return {"image_path": image_path, "object_id": object_id, "prompt": prompt}
    
    return None

# --- Main Execution Loop ---
if __name__ == "__main__":
    last_run_data = {}

    while True:
        console.print("\n" + "="*60, style="dim")
        
        # Build the menu options string
        menu = "[bold](N)[/bold]ew Test"
        if last_run_data:
            menu += " | [bold](P)[/bold]epeat Last"
            menu += " | [bold](R)[/bold]epeat with New Inputs"
        menu += " | [bold](Q)[/bold]uit"
        
        console.print(menu, justify="center")
        
        try:
            choice = console.input("Choose an option: ").lower().strip()
        except KeyboardInterrupt:
            choice = 'q'

        if choice == 'n':
            new_run_data = run_full_test_flow()
            if new_run_data:
                last_run_data = new_run_data
        
        elif choice == 'p':
            if not last_run_data:
                console.print("No previous test to repeat. Please run a new test first.", style="bold red")
                continue
            
            console.print("--- Repeating Last Test ---", style="bold magenta")
            console.print(f"Image: [cyan]{os.path.basename(last_run_data['image_path'])}[/cyan]")
            console.print(f"Object ID: [cyan]{last_run_data['object_id']}[/cyan]")
            console.print(f"Prompt: [cyan]{last_run_data['prompt']}[/cyan]")
            
            image_id = verify_image(last_run_data['image_path'], last_run_data['object_id'])
            if image_id:
                run_prompt(image_id, last_run_data['prompt'], last_run_data['image_path'])

        elif choice == 'r':
            if not last_run_data:
                console.print("No previous test to repeat. Please run a new test first.", style="bold red")
                continue
            
            console.print("--- Re-prompting on Last Image ---", style="bold magenta")
            console.print(f"Re-using image: [cyan]{os.path.basename(last_run_data['image_path'])}[/cyan]")
            
            reprompt_data = run_reprompt_flow(last_run_data['image_path'])
            if reprompt_data:
                last_run_data = reprompt_data

        elif choice == 'q':
            console.print("Exiting client. Goodbye!", style="bold")
            break
            
        else:
            console.print(f"Invalid option: '{choice}'. Please try again.", style="bold red")