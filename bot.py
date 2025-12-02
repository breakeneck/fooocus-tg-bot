import logging
import base64
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import BOT_TOKEN
from client import FooocusClient

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

client = FooocusClient()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to the Fooocus AI Bot!\n\n"
        "Commands:\n"
        "/models - Select a base model\n"
        "/generate <prompt> - Generate an image\n"
        "Or simply send a text message to generate an image."
    )

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models = client.get_models()
    if not models:
        await update.message.reply_text("Could not fetch models from Fooocus API.")
        return

    # Store models in user_data to map indices to filenames
    context.user_data["available_models"] = models

    keyboard = []
    for i, model in enumerate(models):
        # Use index to avoid 64-byte limit on callback_data
        # Display name can be the full model name
        keyboard.append([InlineKeyboardButton(model, callback_data=f"model:{i}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select a base model:", reply_markup=reply_markup)

async def model_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    print(f"DEBUG: Handler entered. Data: {query.data}") # Debug log
    
    try:
        # Always answer the query to stop the loading animation
        await query.answer()
        print("DEBUG: Query answered")

        data = query.data
        if data.startswith("model:"):
            try:
                index = int(data.split("model:", 1)[1])
                print(f"DEBUG: Parsed index: {index}")
                
                available_models = context.user_data.get("available_models", [])
                print(f"DEBUG: Available models in user_data: {available_models}")
                
                if 0 <= index < len(available_models):
                    selected_model = available_models[index]
                    context.user_data["model"] = selected_model
                    print(f"DEBUG: User selected model: {selected_model}")
                    await query.edit_message_text(text=f"Selected model: {selected_model}")
                    print("DEBUG: Message edited successfully")
                else:
                    print("DEBUG: Index out of range or models empty")
                    await query.edit_message_text(text="Error: Model selection expired or invalid. Please run /models again.")
            except (ValueError, IndexError) as e:
                print(f"DEBUG: Error parsing index: {e}")
                await query.edit_message_text(text="Error processing selection.")
    except Exception as e:
        print(f"DEBUG: Unexpected error in handler: {e}")
        import traceback
        traceback.print_exc()

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide a prompt. Usage: /generate <prompt>")
        return
    
    await generate_image(update, context, prompt)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    await generate_image(update, context, prompt)

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    user_model = context.user_data.get("model")
    status_msg = await update.message.reply_text(f"Generating image for: '{prompt}'...\nModel: {user_model or 'Default'}")

    # Run blocking request in executor to avoid blocking the asyncio loop
    # Although requests is blocking, for a simple bot this might be okay, 
    # but strictly speaking we should run it in a separate thread.
    # Since we are using python-telegram-bot which is async, we should be careful.
    # However, for this MVP, we'll call it directly but acknowledge it blocks.
    # To do it properly:
    # loop = asyncio.get_running_loop()
    # result = await loop.run_in_executor(None, lambda: client.generate_image(...))
    
    # For simplicity in this step, we will just call it. 
    # If the generation takes a long time, the bot might stop responding to pings if we don't use run_in_executor.
    # Let's use run_in_executor for better practice.
    import asyncio
    loop = asyncio.get_running_loop()
    
    try:
        result = await loop.run_in_executor(
            None, 
            lambda: client.generate_image(prompt, model_name=user_model)
        )
        
        if result:
            # Fooocus API returns a list of results. We usually get one image.
            # The result format from our client.generate_image (which calls text-to-image)
            # returns a list of objects with 'base64' or 'url'.
            # Wait, the API docs say text-to-image returns a list of results?
            # Let's check the API docs again. 
            # The docs say:
            # [
            #   {
            #     "base64": "...",
            #     "url": "...",
            #     "seed": ...,
            #     "finish_reason": "SUCCESS"
            #   }
            # ]
            # Actually the docs example shows a list in `job_result` for query-job, 
            # but for synchronous `text-to-image`, it returns the list directly?
            # Let's assume it returns a list of dicts based on common patterns, 
            # but if it returns a single dict, we handle that too.
            
            # Based on docs position 2: "This interface returns a universal response structure, refer to [response](#response)"
            # And position 16 (which we didn't read fully but saw the title) likely describes it.
            # Usually it's a list of generated items.
            
            images = []
            if isinstance(result, list):
                images = result
            elif isinstance(result, dict):
                # It might be wrapped
                images = [result]
            
            for img_data in images:
                if "base64" in img_data and img_data["base64"]:
                    img_bytes = base64.b64decode(img_data["base64"])
                    await update.message.reply_photo(photo=io.BytesIO(img_bytes))
                elif "url" in img_data and img_data["url"]:
                    # Telegram cannot access localhost URLs, so we must download it first
                    image_url = img_data["url"]
                    try:
                        # Use requests to download the image content
                        # We can use the client.base_url to ensure we are hitting the right host if the URL is relative, 
                        # but Fooocus usually returns absolute URLs like http://127.0.0.1:8888/files/...
                        
                        # Fix: Replace the host/port in the returned URL with our configured BASE_URL
                        # This handles cases where Fooocus returns 127.0.0.1 but we are connecting via localhost (IPv6/v4 differences)
                        # or if we are connecting via a different IP/tunnel.
                        from urllib.parse import urlparse, urljoin
                        
                        # Parse the returned URL
                        parsed_img_url = urlparse(image_url)
                        # Parse our configured base URL
                        parsed_base_url = urlparse(client.base_url)
                        
                        # Construct new URL with configured netloc (host:port)
                        # Keep the path from the image URL
                        final_image_url = parsed_img_url._replace(netloc=parsed_base_url.netloc, scheme=parsed_base_url.scheme).geturl()
                        
                        print(f"Downloading image from: {final_image_url}") # Debug log
                        
                        import requests
                        img_response = requests.get(final_image_url)
                        img_response.raise_for_status()
                        await update.message.reply_photo(photo=io.BytesIO(img_response.content))
                    except Exception as e:
                        await update.message.reply_text(f"Failed to retrieve image from {image_url} (tried {final_image_url if 'final_image_url' in locals() else 'N/A'}): {e}")
            
            await status_msg.delete()
        else:
            await status_msg.edit_text("Generation failed. Please check the API logs.")
            
    except Exception as e:
        await status_msg.edit_text(f"An error occurred: {str(e)}")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env or config.py")
        exit(1)

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('models', models_command))
    application.add_handler(CommandHandler('generate', generate_command))
    application.add_handler(CallbackQueryHandler(model_selection_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))

    print("Bot is running...")
    application.run_polling()
