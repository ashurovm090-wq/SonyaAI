import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from google import generativeai as genai
from edge_tts import Communicate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_TOKEN = os.getenv("GEMINI_TOKEN")

genai.configure(api_key=GEMINI_TOKEN)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

SONYA_PROMPT = (
    "You are Elbrus, a sleek and futuristic AI voice assistant. "
    "Respond to the user's message in Russian, but keep your responses concise, "
    "natural, friendly and engaging. Use emojis appropriately."
)

@app.on_event("startup")
async def on_startup():
    # Удаляем вебхук и старые зависшие сообщения (drop_pending_updates), чтобы бот не тупил
    await bot.delete_webhook(drop_pending_updates=True)
    # Ставим вебхук заново автоматически при старте кода!
    await bot.set_webhook(url="https://sonyaai.onrender.com/webhook")
    logger.info("Эльбрус успешно запустилась, вебхук обновлен!")

@app.get("/")
async def index():
    return {"status": "Elbrus AI работает отлично"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    telegram_update = types.Update(**update)
    await dp.feed_update(bot, telegram_update)
    return {"ok": True}

# ТЕПЕРЬ /START РАБОТАЕТ НОРМАЛЬНО
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "Привет! Я твой голосово помощник **Elbrus AI** ✨\n\n"
        "Просто напиши мне любой текст, и я отвечу тебе голосом!",
        parse_mode="Markdown"
    )

# Обработка обычного текста
@dp.message(F.text)
async def process_text_message(message: types.Message):
    # Если вдруг проскочила команда, не обрабатываем её как обычный текст
    if message.text.startswith("/"):
        return

    status_msg = await message.answer("Sonya думает...")
    mp3_path = f"reply_{message.message_id}.mp3"
    
    try:
        prompt = f"{SONYA_PROMPT}\nUser message: {message.text}"
        response = ai_model.generate_content(prompt)
        sonya_response_text = response.text

        communicate = Communicate(sonya_response_text, "ru-RU-SvetlanaNeural")
        await communicate.save(mp3_path)
        
        await status_msg.delete()
        
        with open(mp3_path, "rb") as audio_reply:
            await message.answer_voice(
                voice=types.BufferedInputFile(audio_reply.read(), filename="sonya_voice.mp3"),
                caption=f"🤖 **Elbrus:** {sonya_response_text}",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await status_msg.edit_text(f"Произошла ошибка: {str(e)}")
    finally:
        if os.path.exists(mp3_path): 
            os.remove(mp3_path)
