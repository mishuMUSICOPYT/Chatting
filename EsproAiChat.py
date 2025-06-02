import asyncio
import base64
import mimetypes
import os
from typing import Union, Tuple

from pyrogram import Client, filters, types as t
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from lexica import AsyncClient
from lexica.constants import languageModels

# ======== ENV VARS ==========
def get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Missing environment variable: {name}")
    return value

API_ID = int(get_env_var("API_ID"))
API_HASH = get_env_var("API_HASH")
BOT_TOKEN = get_env_var("BOT_TOKEN")
START_PHOTO = get_env_var("START_PHOTO")

app = Client("AIChatBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ======== MEMORY ==========
user_model_memory = {}

# ======== AI CALL ==========
async def ChatCompletion(prompt, model) -> Union[Tuple[str, list], str]:
    try:
        modelInfo = getattr(languageModels, model)
        client = AsyncClient()
        output = await client.ChatCompletion(prompt, modelInfo)
        if model == "bard":
            return output['content'], output['images']
        return output['content']
    except Exception as e:
        raise Exception(f"API error: {e}")

# ======== VISION ==========
async def geminiVision(prompt, model, images) -> str:
    imageInfo = []
    for image in images:
        with open(image, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(image)
            imageInfo.append({"data": data, "mime_type": mime_type})
        os.remove(image)
    modelInfo = getattr(languageModels, model)
    client = AsyncClient()
    output = await client.ChatCompletion(prompt, modelInfo, json={"images": imageInfo})
    return output['content']['parts'][0]['text']

# ======== HELPERS ==========
def getMedia(message):
    media = message.media or (message.reply_to_message.media if message.reply_to_message else None)
    if media:
        target = message if message.media else message.reply_to_message
        if target.photo:
            return target.photo
        elif target.document and target.document.mime_type in ['image/png', 'image/jpeg'] and target.document.file_size < 5_242_880:
            return target.document
    return None

def getText(message):
    if message.text:
        return message.text.split(None, 1)[1] if " " in message.text else None
    return None

# ======== START COMMAND ==========
@app.on_message(filters.command("start") & filters.private)
async def start_command(_, m: t.Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Owner", url="https://t.me/ll_ksd_ll")],
        [InlineKeyboardButton("➕ Add Me To Group", url="https://t.me/PowerStudyChatgptBot?startgroup=s&admin=delete_messages+manage_video_chats+pin_messages+invite_users")]
    ])
    await m.reply_photo(
        photo=START_PHOTO,
        caption=(
            f"👋 Hello {m.from_user.mention}!\n\n"
            "Welcome to the AI chatbot.\n"
            "Just send a message (no command needed).\n\n"
            "ℹ️ For help, contact the owner."
        ),
        reply_markup=keyboard
    )

# ======== PING ==========
@app.on_message(filters.command("ping"))
async def ping(_, m): await m.reply_text("Pong! ✅ Bot is Alive.")

# ======== IMAGE HANDLER ==========
async def askAboutImage(_, m: t.Message, mediaFiles: list, prompt: str):
    images = []
    for media in mediaFiles:
        image = await _.download_media(media.file_id, file_name=f"./downloads/{m.from_user.id}_ask.jpg")
        images.append(image)
    output = await geminiVision(prompt or "What's this?", "gemini", images)
    await m.reply_text(output)

# ======== TEXT HANDLER (Private + Group + No Command) ==========
@app.on_message(filters.text & ~filters.command(["start", "ping"]))
async def auto_reply(_, m: t.Message):
    if m.chat.type not in ["private", "group", "supergroup"]:
        return

    # Ignore other bots
    if m.from_user is None or m.from_user.is_bot:
        return

    # Only respond in group if bot is mentioned or replied to
    if m.chat.type in ["group", "supergroup"]:
        if not (m.reply_to_message and m.reply_to_message.from_user.id == (await app.get_me()).id) and f"@{(await app.get_me()).username.lower()}" not in m.text.lower():
            return

    model = user_model_memory.get(m.from_user.id, "gpt")
    media = getMedia(m)

    if media:
        return await askAboutImage(_, m, [media], m.text)

    try:
        output = await ChatCompletion(m.text, model)
        text = output['parts'][0]['text'] if model == "gemini" else (output if isinstance(output, str) else output)
        await m.reply_text(text)
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Bot starting...")
    app.run()
