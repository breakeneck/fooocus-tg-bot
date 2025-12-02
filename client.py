import requests
import json
from config import BASE_URL

class FooocusClient:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url

    def ping(self):
        try:
            response = requests.get(f"{self.base_url}/ping", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_models(self):
        try:
            response = requests.get(f"{self.base_url}/v1/engines/all-models", timeout=10)
            response.raise_for_status()
            return response.json().get("model_filenames", [])
        except requests.RequestException as e:
            print(f"Error fetching models: {e}")
            return []

    def generate_image(self, prompt, model_name=None, negative_prompt="", style_selections=None, 
                       performance_selection="Speed", aspect_ratios_selection="1152*896", 
                       image_number=1, image_seed=-1, sharpness=2.0, guidance_scale=4.0):
        
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "style_selections": style_selections or [],
            "performance_selection": performance_selection,
            "aspect_ratios_selection": aspect_ratios_selection,
            "image_number": image_number,
            "image_seed": image_seed,
            "sharpness": sharpness,
            "guidance_scale": guidance_scale,
            "async_process": False 
        }

        if model_name:
            payload["base_model_name"] = model_name

        try:
            response = requests.post(f"{self.base_url}/v1/generation/text-to-image", 
                                     json=payload, timeout=300) # Long timeout for generation
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error generating image: {e}")
            return None
