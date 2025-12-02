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
    logging.info(f"DEBUG: Handler entered. Data: {query.data}")
    
    try:
        await query.answer()
        logging.info("DEBUG: Query answered")

        data = query.data
        if data.startswith("model:"):
            try:
                index = int(data.split("model:", 1)[1])
                logging.info(f"DEBUG: Parsed index: {index}")
                
                # Stateless approach: Fetch models again to resolve index
                # This avoids issues with user_data persistence
                models = client.get_models()
                logging.info(f"DEBUG: Fetched {len(models)} models")
                
                if 0 <= index < len(models):
                    selected_model = models[index]
                    context.user_data["model"] = selected_model
                    logging.info(f"DEBUG: User selected model: {selected_model}")
                    await query.edit_message_text(text=f"Selected model: {selected_model}")
                    logging.info("DEBUG: Message edited successfully")
                else:
                    logging.warning("DEBUG: Index out of range")
                    await query.edit_message_text(text="Error: Model selection invalid (list changed?). Please run /models again.")
            except (ValueError, IndexError) as e:
                logging.error(f"DEBUG: Error processing selection: {e}")
                await query.edit_message_text(text="Error processing selection.")
    except Exception as e:
        logging.error(f"DEBUG: Unexpected error in handler: {e}")
        import traceback
        logging.error(traceback.format_exc())

async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide a prompt. Usage: /generate <prompt>")
        return
    
    await generate_image(update, context, prompt)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    await generate_image(update, context, prompt)

async def image_count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    # Create rows of 5 buttons
    row = []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"img_count:{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select number of images to generate:", reply_markup=reply_markup)

async def image_count_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"DEBUG: Image count handler. Data: {query.data}")
    
    try:
        await query.answer()
        data = query.data
        if data.startswith("img_count:"):
            count = int(data.split("img_count:", 1)[1])
            context.user_data["image_count"] = count
            logging.info(f"DEBUG: User selected image count: {count}")
            await query.edit_message_text(text=f"Selected image count: {count}")
    except Exception as e:
        logging.error(f"DEBUG: Error in image count handler: {e}")
        import traceback
        logging.error(traceback.format_exc())

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    user_model = context.user_data.get("model")
    image_count = context.user_data.get("image_count", 1)
    
    status_msg = await update.message.reply_text(f"Generating {image_count} image(s) for: '{prompt}'...\nModel: {user_model or 'Default'}")

    # Run blocking request in executor to avoid blocking the asyncio loop
    import asyncio
    loop = asyncio.get_running_loop()
    
    try:
        result = await loop.run_in_executor(
            None, 
            lambda: client.generate_image(prompt, model_name=user_model, image_number=image_count)
        )
        
        if result:
            # Fooocus API returns a list of results. We usually get one image.
            # The result format from our client.generate_image (which calls text-to-image)
            # returns a list of objects with 'base64' or 'url'.
            
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

async def debug_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"DEBUG: Catch-all callback handler. Data: {query.data}")
    # We don't answer here, just log. The specific handler should answer.

async def raw_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"DEBUG: RAW UPDATE RECEIVED: {update}")

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env or config.py")
        exit(1)

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_error_handler(error_handler)
    
    # Log ALL updates before any other handler
    from telegram.ext import TypeHandler
    application.add_handler(TypeHandler(Update, raw_update_handler), group=-1)

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('models', models_command))
    application.add_handler(CommandHandler('image_count', image_count_command))
    application.add_handler(CommandHandler('generate', generate_command))
    
    # Specific handler first
    application.add_handler(CallbackQueryHandler(model_selection_handler, pattern="^model:"))
    application.add_handler(CallbackQueryHandler(image_count_handler, pattern="^img_count:"))
    
    # Catch-all for debugging (if the above doesn't match)
    application.add_handler(CallbackQueryHandler(debug_callback_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))

    print("Bot is running...")
    # Explicitly allow all updates to ensure we get callback queries
    application.run_polling(allowed_updates=Update.ALL_TYPES)
