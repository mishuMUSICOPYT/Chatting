import asyncio
import base64
import mimetypes
import os
from pyrogram import Client, filters, types as t
from lexica import AsyncClient
from lexica.constants import languageModels
from typing import Union, Tuple

# ========== BOT TOKEN ==========
API_ID = os.environ.get("API_ID", "none") 
API_HASH = os.environ.get("API_HASH", "none") 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "none") 


# Ensure downloads folder exists
os.makedirs("./downloads", exist_ok=True)

# ========== START CLIENT ==========
app = Client("AIChatBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ========== AI Chat Completion ==========
# Use typing.Union for compatibility with Python versions < 3.10
async def ChatCompletion(prompt: str, model: str) -> Union[Tuple[str, list], str]:
    try:
        modelInfo = getattr(languageModels, model)
        client = AsyncClient()
        output = await client.ChatCompletion(prompt, modelInfo)
        if model == "bard":
            return output['content'], output['images']
        return output['content']
    except Exception as E:
        raise Exception(f"API error: {E}")

async def geminiVision(prompt: str, model: str, images: list) -> str:
    imageInfo = []
    for image in images:
        with open(image, "rb") as imageFile:
            data = base64.b64encode(imageFile.read()).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(image)
            imageInfo.append({
                "data": data,
                "mime_type": mime_type
            })
        os.remove(image)
    payload = {
        "images": imageInfo
    }
    modelInfo = getattr(languageModels, model)
    client = AsyncClient()
    output = await client.ChatCompletion(prompt, modelInfo, json=payload)
    return output['content']['parts'][0]['text']

def getMedia(message: t.Message):
    """Extract Media from message or reply."""
    media = None
    if message.media:
        if message.photo:
            media = message.photo
        elif message.document and message.document.mime_type in ['image/png', 'image/jpg', 'image/jpeg'] and message.document.file_size < 5242880:
            media = message.document
    elif message.reply_to_message and message.reply_to_message.media:
        if message.reply_to_message.photo:
            media = message.reply_to_message.photo
        elif message.reply_to_message.document and message.reply_to_message.document.mime_type in ['image/png', 'image/jpg', 'image/jpeg'] and message.reply_to_message.document.file_size < 5242880:
            media = message.reply_to_message.document
    return media

def getText(message: t.Message):
    """Extract text after command or full text if no command."""
    if message.text is None:
        return None
    if " " in message.text:
        try:
            return message.text.split(None, 1)[1]
        except IndexError:
            return None
    else:
        return message.text

# ========== Auto AI Chat Handler ==========
@app.on_message(filters.text & ~filters.command)
async def auto_chat(_, m: t.Message):
    if m.from_user.is_bot:
        return

    prompt = getText(m)
    media = getMedia(m)

    if media is not None:
        return await askAboutImage(_, m, [media], prompt)

    if not prompt:
        return await m.reply_text("Hello, How can I assist you today?")

    model = "gemini"  # Default model for auto chat

    try:
        output = await ChatCompletion(prompt, model)
        if isinstance(output, tuple):
            # For models like bard returning (text, images)
            content, images = output
            if not images:
                return await m.reply_text(content)
            media_group = [t.InputMediaPhoto(img) for img in images]
            media_group[0] = t.InputMediaPhoto(images[0], caption=content)
            await _.send_media_group(m.chat.id, media_group, reply_to_message_id=m.id)
        else:
            await m.reply_text(output)
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

async def askAboutImage(_, m: t.Message, mediaFiles: list, prompt: str):
    images = []
    for media in mediaFiles:
        image = await _.download_media(media.file_id, file_name=f'./downloads/{m.from_user.id}_ask.jpg')
        images.append(image)
    output = await geminiVision(prompt if prompt else "What's this?", "geminiVision", images)
    await m.reply_text(output)

# ========== Run the Bot ==========
if __name__ == "__main__":
    print("Starting AI Chat Bot...")
    app.run()
