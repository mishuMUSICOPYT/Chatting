import asyncio
import base64
import mimetypes
import os
import logging
from typing import Union, Tuple

from pyrogram import Client, filters, types as t
from dotenv import load_dotenv
from lexica import AsyncClient
from lexica.constants import languageModels
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== LOAD ENV VARS ==========
load_dotenv()

def get_env_var(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value

API_ID = int(get_env_var("API_ID"))
API_HASH = get_env_var("API_HASH")
BOT_TOKEN = get_env_var("BOT_TOKEN")

# ========== INIT CLIENT ==========
app = Client("AIChatBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== IN-MEMORY MODEL SELECTION ==========
user_model_memory = {}

# ========== CHAT COMPLETION ==========
async def ChatCompletion(prompt, model) -> Union[Tuple[str, list], str]:
    try:
        modelInfo = getattr(languageModels, model)
        client = AsyncClient()
        output = await client.ChatCompletion(prompt, modelInfo)

        if model == "bard":
            return output['content'], output.get('images', [])
        elif model == "gemini":
            return output['content']['parts'][0]['text']
        else:
            return output['content']
    except Exception as E:
        raise Exception(f"API error: {E}")

# ========== GEMINI VISION ==========
async def geminiVision(prompt, model, images) -> str:
    imageInfo = []
    for image in images:
        with open(image, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(image)
            imageInfo.append({"data": data, "mime_type": mime_type})
        try:
            os.remove(image)
        except OSError:
            pass

    payload = {"images": imageInfo}
    modelInfo = getattr(languageModels, model)
    client = AsyncClient()
    output = await client.ChatCompletion(prompt, modelInfo, json=payload)
    return output['content']['parts'][0]['text']

# ========== MEDIA EXTRACTOR ==========
def getMedia(message):
    target = message if message.media else message.reply_to_message
    if not target:
        return None
    if target.photo:
        return target.photo
    if target.document and target.document.mime_type in ['image/png', 'image/jpg', 'image/jpeg'] and target.document.file_size < 5 * 1024 * 1024:
        return target.document
    return None

# ========== TEXT EXTRACTOR ==========
def getText(message):
    if not message.text:
        return None
    try:
        return message.text.split(None, 1)[1]
    except IndexError:
        return None


@app.on_message(filters.command("start") & filters.private)
async def start_command(_, m: t.Message):
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👤 Owner", url=f"https://t.me/Ur_Haiwan")],
            [InlineKeyboardButton("Add Me Your Group", url=f"http://t.me/ChatEsproBot?startgroup=true")]
        ]
    )

    await m.reply_text(
        f"👋 Hello {m.from_user.mention}!\n\n"
        "Welcome to the AI chatbot. Use commands like /gpt, /bard, /gemini to chat.\n\n"
        "For help or updates, contact the owner or join the channel below.",
        reply_markup=keyboard
    )

# ========== COMMAND HANDLER ==========
@app.on_message(filters.command(["gpt", "bard", "llama", "mistral", "palm", "gemini"]))
async def chatbots(_, m: t.Message):
    prompt = getText(m)
    media = getMedia(m)

    model = m.command[0].lower()
    user_model_memory[m.from_user.id] = model

    if media:
        return await askAboutImage(_, m, [media], prompt)

    if prompt is None:
        return await m.reply_text(f"✅ Model set to `{model}`. Now send a message without a command.")

    await m.chat.send_chat_action("typing")
    try:
        output = await ChatCompletion(prompt, model)

        if model == "bard":
            text, images = output
            if not images:
                return await m.reply_text(text)
            media_group = [t.InputMediaPhoto(img) for img in images]
            media_group[0] = t.InputMediaPhoto(images[0], caption=text)
            return await _.send_media_group(m.chat.id, media_group, reply_to_message_id=m.id)

        await m.reply_text(output)
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

# ========== AUTO-REPLY (NO COMMAND) ==========
@app.on_message(filters.private & filters.text & ~filters.command(["gpt", "bard", "llama", "mistral", "palm", "gemini"]))
async def smart_chat(_, m: t.Message):
    prompt = m.text
    model = user_model_memory.get(m.from_user.id, "gpt")
    await m.chat.send_chat_action("typing")
    try:
        output = await ChatCompletion(prompt, model)
        await m.reply_text(output)
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

# ========== GEMINI IMAGE HANDLER ==========
async def askAboutImage(_, m: t.Message, mediaFiles: list, prompt: str):
    images = []
    for media in mediaFiles:
        file_path = await _.download_media(media.file_id, file_name=f'./downloads/{m.from_user.id}_ask.jpg')
        images.append(file_path)

    prompt = prompt or "What's this?"
    await m.chat.send_chat_action("typing")
    try:
        output = await geminiVision(prompt, "geminiVision", images)
        await m.reply_text(f"🖼️ {prompt}\n\n{output}")
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

# ========== RUN ==========
if __name__ == "__main__":
    print("🤖 Bot is starting...")
    app.run()
