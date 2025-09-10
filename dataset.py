# dataset.py
from Resize import process_and_resize_image

DATASET_IMAGES = {
    "black power bank" : process_and_resize_image("dataset/power_bank.png", 480),
    "power bank display": process_and_resize_image("dataset/power_bank_display.jpeg", 480),
    "stove": process_and_resize_image("dataset/electric stove.jpeg", 480),
    "timer button": process_and_resize_image("dataset/timer button.png", 480),
    "decrease button": process_and_resize_image("dataset/decrease button.png", 480),
    "increase button": process_and_resize_image("dataset/increase button.png", 480),
    "kettle rocker switch": process_and_resize_image("dataset/kettle rocker switch.png", 480),
    "kettle button": process_and_resize_image("dataset/kettle power button.png", 480),
    "kettle": process_and_resize_image("dataset/kettle.png", 480),
    "laptop": process_and_resize_image("dataset/laptop.png", 480),
    "On/Off Button": process_and_resize_image("dataset/power button.png", 480),
    "ac remote": process_and_resize_image("dataset/ac remote.png", 480),
    "cool button": process_and_resize_image("dataset/cool button.png", 480)
    # Add more entries as needed:
    # "your object description here": "dataset/your_image_file.extension",
}