import asyncio
import base64
import mimetypes
import os
import re
import pathlib
from typing import Union, Tuple

from pyrogram import Client, filters, types as t
from lexica import AsyncClient
from lexica.constants import languageModels

# === CONFIGURATION ===
API_ID = os.environ.get("API_ID", "none") 
API_HASH = os.environ.get("API_HASH", "none") 
BOT_TOKEN = os.environ.get("BOT_TOKEN", "none") 
# Create downloads directory if not exists
DOWNLOAD_DIR = pathlib.Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Initialize Pyrogram Client
app = Client(
    "my_bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Initialize Lexica AsyncClient once
client = AsyncClient()


async def ChatCompletion(prompt, model) -> Union[Tuple[str, list], str]:
    try:
        modelInfo = getattr(languageModels, model)
        output = await client.ChatCompletion(prompt, modelInfo)
        if model == "bard":
            return output['content'], output['images']
        return output['content']
    except Exception as E:
        raise Exception(f"API error: {E}")


async def geminiVision(prompt, model, images) -> Union[Tuple[str, list], str]:
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
    output = await client.ChatCompletion(prompt, modelInfo, json=payload)
    return output['content']['parts'][0]['text']


def getMedia(message):
    """Extract media (photo or small image document) from message or its reply."""
    target = message if message.media else (
        message.reply_to_message if message.reply_to_message and message.reply_to_message.media else None
    )
    if not target:
        return None

    if target.photo:
        return target.photo
    if target.document and target.document.mime_type in ['image/png', 'image/jpg', 'image/jpeg'] and target.document.file_size < 5_242_880:
        return target.document
    return None


@app.on_message(filters.text & ~filters.edited)
async def chatbots(_, m: t.Message):
    prompt = m.text
    media = getMedia(m)

    try:
        if media is not None:
            return await askAboutImage(_, m, [media], prompt)

        if not prompt:
            return await m.reply_text("Hello, How can I assist you today?")

        model = "gpt"

        output = await ChatCompletion(prompt, model)

        if model == "bard":
            output, images = output
            if len(images) == 0:
                return await m.reply_text(output)
            media_group = []
            for i in images:
                media_group.append(t.InputMediaPhoto(i))
            media_group[0] = t.InputMediaPhoto(images[0], caption=output)
            await _.send_media_group(
                m.chat.id,
                media_group,
                reply_to_message_id=m.id
            )
            return

        if model == "gemini":
            # gemini model output may differ, safe access
            text = output.get('parts', [{}])[0].get('text', output)
            await m.reply_text(text)
        else:
            await m.reply_text(output)

    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")


async def askAboutImage(_, m: t.Message, mediaFiles: list, prompt: str):
    images = []
    for media in mediaFiles:
        image = await _.download_media(media.file_id, file_name=str(DOWNLOAD_DIR / f'{m.from_user.id}_ask.jpg'))
        images.append(image)
    output = await geminiVision(prompt if prompt else "What's this?", "geminiVision", images)
    await m.reply_text(output)


if __name__ == "__main__":
    print("Starting bot...")
    app.run()
