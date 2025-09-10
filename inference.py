import os, re, cv2, torch
from typing import Union
from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, BitsAndBytesConfig
from qwen_vl_utils import process_vision_info

class SimpleInference:
    """
    A class for performing inference using Hugging Face models.
    """
    
    def __init__(self, model_id="BAAI/RoboBrain2.0-3B"):
        """
        Initialize the model and processor with 4-bit quantization.
        """
        print("Loading Checkpoint...")

        # Uncomment this section if you want to quantize
        #quantization_config = BitsAndBytesConfig(
        #    load_in_4bit=True,
        #    bnb_4bit_compute_dtype=torch.float16
        #)

        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_id,
            #quantization_config=quantization_config, # Uncomment if using quantization
            device_map="auto",
            torch_dtype="auto" # Remove if using quantization
        )
        
        self.processor = AutoProcessor.from_pretrained(model_id)
        
    def inference(self, text:str, image: Union[list,str], task="general", plot=False, enable_thinking=True, do_sample=True, temperature=0.5, **kwargs):
        """Perform inference with text and images input."""
        if isinstance(image, str):
            image = [image]

        # Add the new, explicit RAG tasks
        supported_tasks = ["general", "pointing", "affordance", "trajectory", "grounding", "verify", "object", "pointing_within_box", "pointing_based_on_reference", "verify_based_on_reference"]
        assert task in supported_tasks, f"Invalid task type: {task}. Supported tasks are {supported_tasks}"
        
        single_image_tasks = ["affordance", "trajectory", "grounding", "object", "pointing_within_box"]
        two_image_tasks = ["pointing_based_on_reference", "verify_based_on_reference"]
        
        # New assertion to check for correct number of images based on task
        assert (
            (task in single_image_tasks and len(image) == 1) or
            (task in two_image_tasks and len(image) == 2) or
            (task in ["general", "pointing", "verify"])
        ), f"Task '{task}' requires a specific number of images. Got {len(image)}."

        # Define prompts for the new tasks
        if task == "pointing":
            text = f"{text}. Your answer should be formatted as a list of tuples, i.e. [(x1, y1), (x2, y2), ...]."
        
        elif task == "pointing_based_on_reference":
            # The model will receive the user's image first, then the reference image.
            # The prompt instructs the model to use the second image as context for the first.
            text = f"The second image is the image of the feature you need to detect, using the second image as reference do the following task : {text} in the first image. Your answer should be formatted as a list of tuples, i.e. [(x1, y1), (x2, y2), ...]."

        elif task == "verify":
            # This is the non-RAG verification. It relies on the model's general knowledge.
            text = f"Please identify the object in the image. Compare the identified object with the object from the prompt: {text}. Your answer should be 'same' or 'different'."

        elif task == "verify_based_on_reference":
            # The model will receive the user's image first, then the reference image.
            # The prompt asks the model to compare them directly.
            text = "Is the object in the first image the same as the object in the second image? Answer 'same' or 'different'."

        elif task == "pointing_within_box":
            bbox = kwargs.get("bbox")
            if not bbox:
                raise ValueError("The 'pointing_within_box' task requires a 'bbox' keyword argument.")
            text = f"Within the bounding box {bbox}, find the feature described as: '{text}'. Your answer should be formatted as a list of tuples, i.e. [(x1, y1), (x2, y2), ...]."

        elif task == "affordance":
            text = f"You are a robot using the joint control. The task is \"{text}\". Please predict a possible affordance area of the end effector. Your answer MUST be only a bounding box in the format [x1, y1, x2, y2]."
        elif task == "trajectory":
            text = f"You are a robot using the joint control. The task is \"{text}\". Please predict up to 10 key trajectory points to complete the task. Your answer should be formatted as a list of tuples, i.e. [[x1, y1], [x2, y2], ...]."
        elif task == "grounding":
            text = f"Provide a bounding box for the area of the object identified as '{text}'. Your answer MUST be formatted as a list of bounding boxes in the format [[x1, y1, x2, y2], ...]."
        
        messages = [{"role": "user", "content": [{"type": "image", "image": path if path.startswith("http") else f"file://{os.path.abspath(path)}"} for path in image] + [{"type": "text", "text": f"{text}"}],}]
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        if enable_thinking:
            text = f"{text}<think>"
        else:
            text = f"{text}<think></think><answer>"

        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to("cuda")

        with torch.inference_mode():
            generated_ids = self.model.generate(**inputs, max_new_tokens=768, do_sample=do_sample, temperature=temperature)
        
        generated_ids_trimmed = [out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        output_text = self.processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)

        if enable_thinking:
            parts = output_text[0].split("</think>")
            thinking_text = parts[0].replace("<think>", "").strip()
            answer_text = parts[1].replace("<answer>", "").replace("</answer>", "").strip() if len(parts) > 1 else ""
        else:
            thinking_text = ""
            answer_text = output_text[0].replace("<answer>", "").replace("</answer>", "").strip()

        if not answer_text and thinking_text:
            answer_text = thinking_text
        
        return {"thinking": thinking_text, "answer": answer_text}
    
    def draw_on_image(self, image_path, points=None, boxes=None, trajectories=None, output_path=None):
        """Draw points, bounding boxes, and trajectories on an image"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise FileNotFoundError(f"Unable to read image: {image_path}")
            
            if points:
                for point in points:
                    cv2.circle(image, tuple(point), 10, (0, 0, 255), -1)
            
            if boxes:
                for box in boxes:
                    cv2.rectangle(image, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
            
            if trajectories:
                for trajectory in trajectories:
                    for i in range(1, len(trajectory)):
                        cv2.line(image, trajectory[i-1], trajectory[i], (255, 0, 0), 2)
                    cv2.circle(image, trajectory[-1], 7, (255, 0, 0), -1)
            
            if not output_path:
                name, ext = os.path.splitext(image_path)
                output_path = f"{name}_annotated{ext}"
            
            cv2.imwrite(output_path, image)
            print(f"Annotated image saved to: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error processing image: {e}")
            return None