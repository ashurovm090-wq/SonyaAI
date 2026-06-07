import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Update
import google.generativeai as genai
from groq import Groq
from edge_tts import Communicate

# 1. Загружаем конфигурацию из переменных среды Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_TOKEN")

# Инициализация ИИ сервисов
genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
groq_client = Groq(api_key=GROQ_API_KEY)

# Инициализация Бота и Диспетчера (aiogram 3.x)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация FastAPI веб-сервера
app = FastAPI()

# Создаем папку для шаблонов, если её нет
os.makedirs("templates", exist_ok=True)


# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---

# Команда /start — выдает кнопку для открытия Mini App
@dp.message(F.text == "/start")
async def send_welcome(message: types.Message):
    webapp_url = "https://sonyaai.onrender.com" 
    
    kb = [
        [types.KeyboardButton(text="Открыть Sonya AI", web_app=types.WebAppInfo(url=webapp_url))]
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    await message.answer(
        "Привет! Я голосовой ассистент **Sonya**. \n"
        "Ты можешь общаться со мной прямо здесь, отправляя голосовые сообщения, "
        "или открыть моё графическое мини-приложение по кнопке ниже!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# Обработчик входящих голосовых сообщений
@dp.message(F.voice)
async def process_voice_message(message: types.Message):
    status_msg = await message.answer("Sonya думает...")
    
    try:
        ogg_path = f"{message.voice.file_id}.ogg"
        mp3_path = f"{message.voice.file_id}.mp3"
        
        file_info = await bot.get_file(message.voice.file_id)
        await bot.download_file(file_info.file_path, ogg_path)
        
        with open(ogg_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=(ogg_path, audio_file.read()),
                model="whisper-large-v3",
                language="ru",
                response_format="text"
            )
        user_text = transcription
        
        if not user_text.strip():
            await status_msg.edit_text("Мне показалось, или ты ничего не сказал? Повтори погромче.")
            return

        prompt = (
            "You are Sonya, a sleek and futuristic AI voice assistant. "
            "Respond to the user's message in Russian, but keep your responses concise, "
            "natural, and engaging, as they will be synthesized into voice format. "
            f"User message: {user_text}"
        )
        response = ai_model.generate_content(prompt)
        sonya_response_text = response.text

        communicate = Communicate(sonya_response_text, "ru-RU-SvetlanaNeural")
        await communicate.save(mp3_path)
        
        await status_msg.delete()
        
        with open(mp3_path, "rb") as audio_reply:
            await message.answer_voice(
                voice=types.BufferedInputFile(audio_reply.read(), filename="sonya_answer.mp3"),
                caption=f"🗣 **Вы:** _{user_text}_\n\n🤖 **Sonya:** {sonya_response_text}",
                parse_mode="Markdown"
            )
            
        if os.path.exists(ogg_path): os.remove(ogg_path)
        if os.path.exists(mp3_path): os.remove(mp3_path)
        
    except Exception as e:
        await status_msg.edit_text(f"Произошла ошибка в коде: {str(e)}")


# --- ЛОГИКА ВЕБ-СЕРВЕРА (FASTAPI) ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    telegram_update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}

@app.on_event("startup")
async def on_startup():
    RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "https://sonyaai.onrender.com")
    await bot.set_webhook(f"{RENDER_URL}/webhook")

@app.on_event("shutdown")
async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()
