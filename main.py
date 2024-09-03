import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import openai
from PIL import Image
from io import BytesIO
import base64
import requests
import os
from dotenv import load_dotenv 

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение токенов из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('GDZ_TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('GDZ_OPENAI_API_KEY')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Задайте свой токен для OpenAI
openai.api_key = OPENAI_API_KEY

# Функция для регистрации пользователя
async def register_user(user_id):
    # добавить регистрацию пользователя в базу данных, если еще не был
    # TODO предначисление кристаллов для бесплатных запросов
    # Проверка реферальной ссылки
    pass

# Команда start - приветствие и регистрация
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    await register_user(user.id)

    greeting_message = (
        f"Привет, {user.first_name}!\n"
        f"Ваш логин: @{user.username}\n"
        f"Ваше полное имя: {user.full_name}\n"
        f"Ваш ID: {user.id}\n"
        f"Ваш язык: {user.language_code}"
    )

    await update.message.reply_text(greeting_message)

# Обработка изображений (считывание из чата, сжатие, прогресс-бар)
async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    file = await update.message.photo[-1].get_file()
    file_bytes = BytesIO(await file.download_as_bytearray())

    image = Image.open(file_bytes)
    image = image.resize((512, 512))
    output = BytesIO()
    image.save(output, format="JPEG")
    compressed_image = output.getvalue()

    keyboard = [[InlineKeyboardButton("Отменить запрос", callback_data='cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    progress_message = await update.message.reply_text("Обработка: ░░░░░░░░░░", reply_markup=reply_markup)

    task = asyncio.create_task(process_image_with_openai(compressed_image, update, progress_message))

    last_progress_bar = ""
    while not task.done():
        for i in range(10):
            await asyncio.sleep(0.5)
            progress_bar = '█' * (i + 1) + '░' * (9 - i)
            if progress_bar != last_progress_bar:
                try:
                    await progress_message.edit_text(f"Обработка: {progress_bar}", reply_markup=reply_markup)
                    last_progress_bar = progress_bar
                except Exception as e:
                    logging.error(f"Error updating progress bar: {e}")

    result = await task
    await progress_message.delete()
    await update.message.reply_text(f"Результат: {result}")

# Обработка отмены запроса
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Запрос отменен.")
    await query.message.edit_text("Запрос был отменен.")

# Вызов OpenAI API для обработки изображения
async def process_image_with_openai(image_data: bytes, update: Update, progress_message) -> str:
    image_b64 = base64.b64encode(image_data).decode('utf-8')

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Изучи изображение. Если в нем содержится задача, определи для кого она возраста, реши её как школьник соответствующего возраста и дай ответ по шагам, но в пределах нескольких предложений. Если на изображении не задача, просто дай его короткое описание."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }
        ],
        "max_tokens": 300
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    result_text = response.json()["choices"][0]["message"]["content"]

    return result_text

# Обработка любых текстовых сообщений и файлов
async def handle_text_or_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверяем, есть ли фото в сообщении
    if update.message.photo:
        await handle_image(update, context)
    else:
        # Если файл не фото или неразрешенное вложение, отправляем сообщение
        await update.message.reply_text("Пришли фотку с домашним заданием и я решу его.")
        await update.message.reply_text("🤖")


def main() -> None:
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.TEXT | filters.ATTACHMENT, handle_text_or_file))
    application.add_handler(CallbackQueryHandler(cancel, pattern='^cancel$'))

    application.run_polling()

if __name__ == '__main__':
    main()
