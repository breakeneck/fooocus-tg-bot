import logging
import io
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import FOOOCUS_BOT_TOKEN
from logic import FooocusLogic

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logic = FooocusLogic()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "Welcome to the Fooocus AI Bot!\n\n"
        "Commands:\n"
        "/models - Select a base model\n"
        "/image_count - Select number of images to generate\n"
        "/pure <prompt> - Generate with only positive safety filter\n"
        "/raw <prompt> - Generate without any safety filters\n\n"
        "Or simply send a text message to generate an image with full safety filters."
    )
    await update.message.reply_text(welcome_message)

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models_data = logic.get_models_keyboard_data()
    if not models_data:
        await update.message.reply_text("Could not fetch models from Fooocus API.")
        return

    # Store models in user_data is no longer strictly necessary if we fetch by index in logic, 
    # but logic.get_model_by_index fetches fresh list anyway.
    
    keyboard = []
    for model_name, callback_data in models_data:
        keyboard.append([InlineKeyboardButton(model_name, callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select a base model:", reply_markup=reply_markup)

async def model_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"DEBUG: Handler entered. Data: {query.data}")
    
    try:
        await query.answer()
        data = query.data
        if data.startswith("model:"):
            try:
                index = int(data.split("model:", 1)[1])
                selected_model = logic.get_model_by_index(index)
                
                if selected_model:
                    context.user_data["model"] = selected_model
                    logging.info(f"DEBUG: User selected model: {selected_model}")
                    await query.edit_message_text(text=f"Selected model: {selected_model}")
                else:
                    await query.edit_message_text(text="Error: Model selection invalid (list changed?). Please run /models again.")
            except (ValueError, IndexError) as e:
                logging.error(f"DEBUG: Error processing selection: {e}")
                await query.edit_message_text(text="Error processing selection.")
    except Exception as e:
        logging.error(f"DEBUG: Unexpected error in handler: {e}")

def is_english_prompt(text: str) -> bool:
    """Check if text contains primarily English characters (ASCII + common punctuation)"""
    if not text:
        return False
    
    # Count non-ASCII characters (excluding common punctuation and numbers)
    non_ascii_count = sum(1 for char in text if ord(char) > 127)
    total_chars = len(text.replace(' ', ''))  # Exclude spaces from count
    
    # Allow up to 10% non-ASCII characters (for emojis, special chars)
    if total_chars == 0:
        return False
    
    non_ascii_ratio = non_ascii_count / total_chars
    return non_ascii_ratio < 0.1

async def raw_generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide a prompt. Usage: /raw <prompt>")
        return
    
    if not is_english_prompt(prompt):
        await update.message.reply_text("⚠️ Please use English language only for prompts.")
        return
    
    await generate_image(update, context, prompt, use_safety_filter=False)

async def pure_generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Please provide a prompt. Usage: /pure <prompt>")
        return
    
    if not is_english_prompt(prompt):
        await update.message.reply_text("⚠️ Please use English language only for prompts.")
        return
    
    await generate_image(update, context, prompt, use_safety_filter='pure')

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    
    if not is_english_prompt(prompt):
        await update.message.reply_text("⚠️ Please use English language only for prompts.")
        return
    
    await generate_image(update, context, prompt, use_safety_filter=True)

async def image_count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard_data = logic.get_image_count_keyboard_data()
    keyboard = []
    for row_data in keyboard_data:
        row = [InlineKeyboardButton(label, callback_data=cb_data) for label, cb_data in row_data]
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select number of images to generate:", reply_markup=reply_markup)

async def image_count_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    try:
        await query.answer()
        data = query.data
        if data.startswith("img_count:"):
            count = int(data.split("img_count:", 1)[1])
            context.user_data["image_count"] = count
            await query.edit_message_text(text=f"Selected image count: {count}")
    except Exception as e:
        logging.error(f"DEBUG: Error in image count handler: {e}")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str, use_safety_filter: bool = True):
    user_model = context.user_data.get("model")
    image_count = context.user_data.get("image_count", 1)
    
    if use_safety_filter == 'pure':
        safety_status = "with positive safety filter only"
    elif use_safety_filter == True:
        safety_status = "with full safety filters"
    else:
        safety_status = "without safety filters (raw mode)"
    
    status_msg = await update.message.reply_text(f"Generating {image_count} image(s) for: '{prompt}'...\nModel: {user_model or 'Default'}\nMode: {safety_status}")

    try:
        async for event in logic.generate_image_stream(prompt, user_model, image_count, use_safety_filter):
            if event["type"] == "status":
                if status_msg.photo:
                     await status_msg.edit_caption(caption=event["text"])
                else:
                     await status_msg.edit_text(event["text"])
            
            elif event["type"] == "progress":
                status_text = event["text"]
                preview = event.get("preview")
                
                if preview and "base64" in preview and preview["base64"]:
                    preview_bytes = base64.b64decode(preview["base64"])
                    
                    if not status_msg.photo:
                        await status_msg.delete()
                        status_msg = await update.message.reply_photo(
                            photo=io.BytesIO(preview_bytes),
                            caption=status_text
                        )
                    else:
                        try:
                            await status_msg.edit_media(
                                media=InputMediaPhoto(media=io.BytesIO(preview_bytes), caption=status_text)
                            )
                        except Exception:
                            # Fallback if edit_media fails (e.g. rate limit or same media)
                            try:
                                await status_msg.edit_caption(caption=status_text)
                            except Exception:
                                pass
                else:
                    if status_msg.photo:
                        try:
                            await status_msg.edit_caption(caption=status_text)
                        except Exception:
                            pass
                    else:
                        try:
                            await status_msg.edit_text(status_text)
                        except Exception:
                            pass

            elif event["type"] == "image":
                try:
                    # Create caption with full prompt, negative prompt, and model name
                    full_prompt = event.get("prompt", prompt)
                    negative_prompt = event.get("negative_prompt", "")
                    model_name = event.get("model_name") or user_model or "Default"
                    
                    # Build caption
                    caption = f"{full_prompt}\n\n[{model_name}]"
                    if negative_prompt:
                        caption += f"\n\nNegative: {negative_prompt}"
                    
                    await update.message.reply_photo(
                        photo=io.BytesIO(event["data"]),
                        caption=caption
                    )
                except Exception as e:
                    logging.error(f"Failed to send image: {e}")
                    await update.message.reply_text(f"Error sending image: {e}")

            elif event["type"] == "error":
                await update.message.reply_text(f"Error: {event['message']}")

        # Cleanup status message
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Error during generation: {e}")
        await update.message.reply_text(f"An error occurred: {str(e)}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)

async def debug_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logging.info(f"DEBUG: Catch-all callback handler. Data: {query.data}")

async def raw_update_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"DEBUG: RAW UPDATE RECEIVED: {update}")

if __name__ == '__main__':
    if not FOOOCUS_BOT_TOKEN:
        print("Error: FOOOCUS_BOT_TOKEN not found in .env or config.py")
        exit(1)

    application = ApplicationBuilder().token(FOOOCUS_BOT_TOKEN).build()

    application.add_error_handler(error_handler)
    
    from telegram.ext import TypeHandler
    application.add_handler(TypeHandler(Update, raw_update_handler), group=-1)

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('models', models_command))
    application.add_handler(CommandHandler('image_count', image_count_command))
    application.add_handler(CommandHandler('images_count', image_count_command))
    application.add_handler(CommandHandler('pure', pure_generate_command))
    application.add_handler(CommandHandler('raw', raw_generate_command))
    
    application.add_handler(CallbackQueryHandler(model_selection_handler, pattern="^model:"))
    application.add_handler(CallbackQueryHandler(image_count_handler, pattern="^img_count:"))
    
    application.add_handler(CallbackQueryHandler(debug_callback_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), text_handler))

    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
