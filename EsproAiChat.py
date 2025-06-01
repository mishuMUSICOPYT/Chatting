import os
import base64
import mimetypes
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto
from lexica import AsyncClient
from lexica.constants import languageModels
from typing import Union, Tuple

# ========== BOT TOKEN ==========
API_ID = int(os.environ.get("API_ID", "123456"))  # replace 123456 with your id if env not set
API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")

# Ensure downloads folder exists
os.makedirs("./downloads", exist_ok=True)

# ========== START CLIENT ==========
app = Client("AIChatBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🧠 Chat Completion for Text
async def ChatCompletion(prompt, model) -> Union[Tuple[str, list], str]:
    try:
        modelInfo = getattr(languageModels, model)
        client = AsyncClient()
        output = await client.ChatCompletion(prompt, modelInfo)
        if model == "bard":
            return output['content'], output['images']
        return output['content']
    except Exception as E:
        return f"API error: {E}"

# 🧠 Image + Prompt -> Gemini Vision
async def geminiVision(prompt, model, images) -> Union[str, None]:
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
    payload = { "images": imageInfo }
    modelInfo = getattr(languageModels, model)
    client = AsyncClient()
    output = await client.ChatCompletion(prompt, modelInfo, json=payload)
    return output['content']['parts'][0]['text']

# 📸 Get media (photo or image document)
def getMedia(message: Message):
    if message.photo:
        return message.photo
    if message.document and message.document.mime_type in ['image/png', 'image/jpg', 'image/jpeg'] and message.document.file_size < 5 * 1024 * 1024:
        return message.document
    return None

# 🚀 Main handler: works in both groups & DMs
@app.on_message(filters.text & ~filters.edited)
async def ai_chat(_, m: Message):
    text = m.text
    media = getMedia(m)
    model = "gemini"  # Change to "gpt", "bard", etc. if you prefer

    # 🖼️ If image present
    if media:
        file_path = await m.download(file_name=f"./downloads/{m.from_user.id}_img.jpg")
        reply = await geminiVision(text or "What's in this image?", "geminiVision", [file_path])
        await m.reply_text(reply)
        return

    # 🧠 If only text
    if not text:
        return

    output = await ChatCompletion(text, model)

    # Handle Gemini or Bard output formatting
    if model == "gemini" and isinstance(output, dict):
        await m.reply_text(output['parts'][0]['text'])
    elif model == "bard" and isinstance(output, tuple):
        text_out, images = output
        if not images:
            await m.reply_text(text_out)
            return
        media_group = [InputMediaPhoto(i) for i in images]
        media_group[0] = InputMediaPhoto(images[0], caption=text_out)
        await _.send_media_group(m.chat.id, media_group, reply_to_message_id=m.id)
    else:
        await m.reply_text(output)

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
