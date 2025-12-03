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

def get_progress_bar(percentage, length=20):
    filled_length = int(length * percentage // 100)
    bar = '█' * filled_length + '░' * (length - filled_length)
    return f"[{bar}] {percentage}%"

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    user_model = context.user_data.get("model")
    image_count = context.user_data.get("image_count", 1)
    
    status_msg = await update.message.reply_text(f"Generating {image_count} image(s) for: '{prompt}'...\nModel: {user_model or 'Default'}")

    # Run blocking request in executor to avoid blocking the asyncio loop
    import asyncio
    loop = asyncio.get_running_loop()
    
    
    generated_images = []
    last_media_group_ids = []

    try:
        for i in range(image_count):
            # Start async generation
            current_status_text = f"Starting generation for image {i+1} of {image_count}..."
            if status_msg.photo:
                 await status_msg.edit_caption(caption=current_status_text)
            else:
                 await status_msg.edit_text(current_status_text)
            
            # Call generate_image with async_process=True
            initial_response = await loop.run_in_executor(
                None, 
                lambda: client.generate_image(prompt, model_name=user_model, image_number=1, async_process=True)
            )
            
            if not initial_response or "job_id" not in initial_response:
                await update.message.reply_text(f"Failed to start generation for image {i+1}. Check logs.")
                continue
                
            job_id = initial_response["job_id"]
            logging.info(f"DEBUG: Started job {job_id}")
            
            # Poll for progress
            last_progress = 0
            while True:
                await asyncio.sleep(1.0) # Poll every second
                
                job_status = await loop.run_in_executor(None, lambda: client.query_job(job_id))
                
                if not job_status:
                    logging.warning(f"DEBUG: Failed to query job {job_id}")
                    continue
                
                progress = job_status.get("job_progress", 0)
                stage = job_status.get("job_stage", "Unknown")
                
                # Update progress if changed
                if progress != last_progress:
                    last_progress = progress
                    # Check for preview
                    preview = job_status.get("job_step_preview")
                    
                    progress_bar = get_progress_bar(progress)
                    status_text = f"Generating image {i+1} of {image_count}...\n{progress_bar}\nStage: {stage}"
                    
                    if preview and "base64" in preview and preview["base64"]:
                        preview_bytes = base64.b64decode(preview["base64"])
                        
                        # If status_msg is text, delete it and send photo
                        if not status_msg.photo:
                            await status_msg.delete()
                            status_msg = await update.message.reply_photo(
                                photo=io.BytesIO(preview_bytes),
                                caption=status_text
                            )
                        else:
                            # Update existing photo message
                            # Telegram requires InputMediaPhoto for editing media
                            from telegram import InputMediaPhoto
                            try:
                                await status_msg.edit_media(
                                    media=InputMediaPhoto(media=io.BytesIO(preview_bytes), caption=status_text)
                                )
                            except Exception as e:
                                logging.warning(f"Failed to edit media (rate limit?): {e}")
                                # Fallback: just edit caption if media edit fails
                                try:
                                    await status_msg.edit_caption(caption=status_text)
                                except Exception:
                                    pass

                    else:
                        # No preview available yet or anymore
                        if status_msg.photo:
                            try:
                                await status_msg.edit_caption(caption=status_text)
                            except Exception:
                                pass
                        else:
                            try:
                                await status_msg.edit_text(status_text)
                            except Exception:
                                pass # Ignore edit errors (e.g. same content)

                if job_status.get("job_status") == "Finished":
                    break
            
            # Job finished, get result
            # The final result is in job_status['job_result']
            final_status = await loop.run_in_executor(None, lambda: client.query_job(job_id))
            result = final_status.get("job_result")
            
            new_image_bytes = None
            if result:
                images_data = []
                if isinstance(result, list):
                    images_data = result
                elif isinstance(result, dict):
                    images_data = [result]
                
                # We expect one image per generation call here because we loop image_count times
                # But just in case, take the last one if multiple are returned (though unlikely with image_number=1)
                for img_data in images_data:
                    if "base64" in img_data and img_data["base64"]:
                        img_bytes = base64.b64decode(img_data["base64"])
                        new_image_bytes = io.BytesIO(img_bytes)
                    elif "url" in img_data and img_data["url"]:
                        image_url = img_data["url"]
                        try:
                            from urllib.parse import urlparse, urljoin
                            parsed_img_url = urlparse(image_url)
                            parsed_base_url = urlparse(client.base_url)
                            final_image_url = parsed_img_url._replace(netloc=parsed_base_url.netloc, scheme=parsed_base_url.scheme).geturl()
                            
                            logging.info(f"Downloading image from: {final_image_url}")
                            
                            import requests
                            img_response = requests.get(final_image_url)
                            img_response.raise_for_status()
                            new_image_bytes = io.BytesIO(img_response.content)
                        except Exception as e:
                            logging.error(f"Failed to retrieve image: {e}")
                            await update.message.reply_text(f"Failed to retrieve image from {image_url}: {e}")
            else:
                await update.message.reply_text(f"Generation failed for image {i+1}. Please check logs.")

            # If we got a new image, update the media group
            if new_image_bytes:
                from telegram import InputMediaPhoto
                
                # If there was a previous media group message, delete it
                if last_media_group_ids:
                     for msg_id in last_media_group_ids:
                         try:
                            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
                         except Exception as e:
                            logging.warning(f"Failed to delete previous media group message {msg_id}: {e}")
                     last_media_group_ids = []

                # Prepare media group
                media_group = []
                
                # Add existing images using file_id
                for img_info in generated_images:
                    if 'file_id' in img_info:
                        media_group.append(InputMediaPhoto(media=img_info['file_id']))
                
                # Add new image using bytes
                media_group.append(InputMediaPhoto(media=new_image_bytes))
                
                # Send new media group
                try:
                    msgs = await update.message.reply_media_group(media=media_group)
                    
                    # The last message in the group corresponds to the last image we sent (the new one)
                    # We need to save its file_id for the next iteration
                    if msgs:
                        new_msg = msgs[-1]
                        # Get the largest photo size
                        new_file_id = new_msg.photo[-1].file_id
                        
                        generated_images.append({'file_id': new_file_id})
                        
                        # Store message IDs to delete next time
                        last_media_group_ids = [m.message_id for m in msgs]
                        
                except Exception as e:
                    logging.error(f"Failed to send media group: {e}")
                    await update.message.reply_text(f"Error sending image: {e}")

        # Cleanup status message
        await status_msg.delete()
            
    except Exception as e:
        logging.error(f"Error during generation: {e}")
        # If status_msg was deleted or invalid, we might not be able to edit it.
        # Try to send a new error message.
        await update.message.reply_text(f"An error occurred: {str(e)}")

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
    application.add_handler(CommandHandler('images_count', image_count_command)) # Alias
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
