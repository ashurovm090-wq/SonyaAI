import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from google import generativeai as genai
from edge_tts import Communicate

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токены
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_TOKEN = os.getenv("GEMINI_TOKEN")

# Настройка ИИ
genai.configure(api_key=GEMINI_TOKEN)
ai_model = genai.GenerativeModel("gemini-1.5-flash")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SONYA_PROMPT = (
    "You are Sonya, a sleek and futuristic AI voice assistant. "
    "Respond to the user's message in Russian, but keep your responses concise, "
    "natural, friendly and engaging. Use emojis appropriately."
)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "Привет! Я твоя голосовая помощница **Sonya** ✨\n\n"
        "Просто напиши мне любой текст, и я отвечу тебе голосом!",
        parse_mode="Markdown"
    )

@dp.message(F.text)
async def process_text_message(message: types.Message):
    if message.text == "/start":
        return

    status_msg = await message.answer("Sonya думает...")
    mp3_path = f"reply_{message.message_id}.mp3"
    
    try:
        # Запрос к Gemini
        prompt = f"{SONYA_PROMPT}\nUser message: {message.text}"
        response = ai_model.generate_content(prompt)
        sonya_response_text = response.text

        # Озвучка
        communicate = Communicate(sonya_response_text, "ru-RU-SvetlanaNeural")
        await communicate.save(mp3_path)
        
        await status_msg.delete()
        
        # Отправка ГС
        with open(mp3_path, "rb") as audio_reply:
            await message.answer_voice(
                voice=types.BufferedInputFile(audio_reply.read(), filename="sonya_voice.mp3"),
                caption=f"🤖 **Sonya:** {sonya_response_text}",
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await status_msg.edit_text(f"Произошла ошибка: {str(e)}")
    finally:
        if os.path.exists(mp3_path): 
            os.remove(mp3_path)

async def main():
    logger.info("Бот Sonya AI запущен через Polling!")
    # Удаляем вебхук, чтобы он не мешал обычному соединению
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
