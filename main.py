import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from google import generativeai as genai
from edge_tts import Communicate

# Настройка логов, чтобы видеть ошибки в панели Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токенов из настроек Render (Environment)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_TOKEN = os.getenv("GEMINI_TOKEN")

# Настройка нейросети Gemini
genai.configure(api_key=GEMINI_TOKEN)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

# Настройка Telegram бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройка веб-сервера FastAPI
app = FastAPI()

# Инструкция для ИИ (какой должна быть Соня)
SONYA_PROMPT = (
    "You are Sonya, a sleek and futuristic AI voice assistant. "
    "Respond to the user's message in Russian, but keep your responses concise, "
    "natural, friendly and engaging. Use emojis appropriately."
)

@app.on_event("startup")
async def on_startup():
    logger.info("Sonya AI успешно запустилась и готова к работе!")

# Просто заглушка для главной страницы сайта
@app.get("/")
async def index():
    return {"status": "Sonya AI работает в штатном режиме. Mini App отключен."}

# Вебхук, через который Телеграм передает сообщения на Render
@app.post("/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()
    telegram_update = types.Update(**update)
    await dp.feed_update(bot, telegram_update)
    return {"ok": True}

# Обработка команды /start (Простое приветствие без кнопок сайтов)
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "Привет! Я твоя голосовая помощница **Sonya** ✨\n\n"
        "Просто напиши мне любое сообщение или задай вопрос, и я отвечу тебе голосом!"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

# Обработчик текстовых сообщений от пользователя
@dp.message(F.text)
async def process_text_message(message: types.Message):
    # Если пользователь ввел старт, не обрабатываем его как обычный текст
    if message.text == "/start":
        return

    # Отправляем временный статус, чтобы пользователь видел, что бот не завис
    status_msg = await message.answer("Sonya думает...")
    mp3_path = f"reply_{message.message_id}.mp3"
    
    try:
        user_text = message.text

        # 1. Запрос к ИИ Gemini
        prompt = f"{SONYA_PROMPT}\nUser message: {user_text}"
        response = ai_model.generate_content(prompt)
        sonya_response_text = response.text

        # 2. Переводим текст ответа ИИ в аудио (Голос Светланы)
        communicate = Communicate(sonya_response_text, "ru-RU-SvetlanaNeural")
        await communicate.save(mp3_path)
        
        # Удаляем текст ожидания перед отправкой аудио
        await status_msg.delete()
        
        # 3. Отправляем голосовой ответ обратно в Телеграм
        with open(mp3_path, "rb") as audio_reply:
            await message.answer_voice(
                voice=types.BufferedInputFile(audio_reply.read(), filename="sonya_voice.mp3"),
                caption=f"🤖 **Sonya:** {sonya_response_text}",
                parse_mode="Markdown"
            )
            
        # Чистим за собой временный аудиофайл на сервере
        if os.path.exists(mp3_path): 
            os.remove(mp3_path)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке: {str(e)}")
        await status_msg.edit_text(f"Произошла ошибка: {str(e)}")
        if os.path.exists(mp3_path): 
            os.remove(mp3_path)
