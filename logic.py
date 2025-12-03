import logging
import base64
import io
import asyncio
from client import FooocusClient
from config import SAFETY_POSITIVE_PROMPT, SAFETY_NEGATIVE_PROMPT

class FooocusLogic:
    def __init__(self):
        self.client = FooocusClient()

    def get_welcome_message(self):
        return (
            "Welcome to the Fooocus AI Bot!\n\n"
            "Commands:\n"
            "/models - Select a base model\n"
            "/generate <prompt> - Generate an image\n"
            "Or simply send a text message to generate an image."
        )

    def get_models_keyboard_data(self):
        models = self.client.get_models()
        if not models:
            return None
        
        # Return list of (model_name, callback_data) tuples
        return [(model, f"model:{i}") for i, model in enumerate(models)]

    def get_model_by_index(self, index):
        models = self.client.get_models()
        if 0 <= index < len(models):
            return models[index]
        return None

    def get_image_count_keyboard_data(self):
        # Returns a list of rows, where each row is a list of (label, callback_data)
        keyboard_data = []
        row = []
        for i in range(1, 11):
            row.append((str(i), f"img_count:{i}"))
            if len(row) == 5:
                keyboard_data.append(row)
                row = []
        if row:
            keyboard_data.append(row)
        return keyboard_data

    def get_progress_bar(self, percentage, length=20):
        filled_length = int(length * percentage // 100)
        bar = '█' * filled_length + '░' * (length - filled_length)
        return f"[{bar}] {percentage}%"

    async def generate_image_stream(self, prompt, model_name, image_count, use_safety_filter=True):
        """
        Async generator that yields updates during image generation.
        Yields dicts with type: 'status', 'preview', 'image', 'error'
        
        Args:
            prompt: User's image generation prompt
            model_name: Selected model name
            image_count: Number of images to generate
            use_safety_filter: If True, add full safety prompts; if 'pure', add only positive prompt; if False, no filters
        """
        loop = asyncio.get_running_loop()
        
        # Apply safety filters based on mode
        final_prompt = prompt
        final_negative_prompt = ""
        
        if use_safety_filter == True:
            # Full safety mode: positive + negative prompts
            final_prompt = f"{prompt}, {SAFETY_POSITIVE_PROMPT}"
            final_negative_prompt = SAFETY_NEGATIVE_PROMPT
        elif use_safety_filter == 'pure':
            # Pure mode: only positive prompt, no negative
            final_prompt = f"{prompt}, {SAFETY_POSITIVE_PROMPT}"
            final_negative_prompt = ""

        for i in range(image_count):
            yield {
                "type": "status", 
                "text": f"Starting generation for image {i+1} of {image_count}...",
                "current_index": i + 1,
                "total_count": image_count
            }

            # Start generation
            initial_response = await loop.run_in_executor(
                None, 
                lambda: self.client.generate_image(
                    final_prompt, 
                    model_name=model_name, 
                    negative_prompt=final_negative_prompt,
                    image_number=1, 
                    async_process=True
                )
            )

            if not initial_response or "job_id" not in initial_response:
                yield {"type": "error", "message": f"Failed to start generation for image {i+1}. Check logs."}
                continue

            job_id = initial_response["job_id"]
            logging.info(f"DEBUG: Started job {job_id}")

            last_progress = 0
            while True:
                await asyncio.sleep(1.0)
                
                job_status = await loop.run_in_executor(None, lambda: self.client.query_job(job_id))
                
                if not job_status:
                    continue

                progress = job_status.get("job_progress", 0)
                stage = job_status.get("job_stage", "Unknown")

                if progress != last_progress:
                    last_progress = progress
                    preview = job_status.get("job_step_preview")
                    
                    progress_bar = self.get_progress_bar(progress)
                    status_text = f"Generating image {i+1} of {image_count}...\n{progress_bar}\nStage: {stage}"
                    
                    yield {
                        "type": "progress",
                        "text": status_text,
                        "preview": preview, # Pass the raw preview dict
                        "progress": progress
                    }

                if job_status.get("job_status") == "Finished":
                    break
            
            # Job finished, get result
            final_status = await loop.run_in_executor(None, lambda: self.client.query_job(job_id))
            result = final_status.get("job_result")

            if result:
                images_data = []
                if isinstance(result, list):
                    images_data = result
                elif isinstance(result, dict):
                    images_data = [result]
                
                for img_data in images_data:
                    img_bytes = None
                    if "base64" in img_data and img_data["base64"]:
                        img_bytes = base64.b64decode(img_data["base64"])
                    elif "url" in img_data and img_data["url"]:
                        # Handle URL download logic here or in client? 
                        # Keeping it here for now as it was in bot.py, but maybe cleaner in client?
                        # For now, let's keep the logic close to where it was, but inside this class.
                        image_url = img_data["url"]
                        try:
                            from urllib.parse import urlparse
                            parsed_img_url = urlparse(image_url)
                            parsed_base_url = urlparse(self.client.base_url)
                            final_image_url = parsed_img_url._replace(netloc=parsed_base_url.netloc, scheme=parsed_base_url.scheme).geturl()
                            
                            import requests
                            img_response = requests.get(final_image_url)
                            img_response.raise_for_status()
                            img_bytes = img_response.content
                        except Exception as e:
                            logging.error(f"Failed to retrieve image: {e}")
                            yield {"type": "error", "message": f"Failed to retrieve image from URL: {e}"}
                    
                    if img_bytes:
                        yield {
                            "type": "image", 
                            "data": img_bytes,
                            "prompt": prompt,  # Original user prompt
                            "model_name": model_name
                        }
            else:
                yield {"type": "error", "message": f"Generation failed for image {i+1}."}
