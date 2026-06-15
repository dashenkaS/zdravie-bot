# Запуск: python -m bot.bot

import os
import asyncio
import aiohttp
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, ContextTypes, filters)

# Загружаем токен бота из .env файла
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Адрес нашего FastAPI-сервера
BACKEND_URL = "http://localhost:8000"

# Настройка логирования - будем видеть что происходит в консоли
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния ConversationHandler:
# Каждая константа это "шаг" диалога
FREQUENCY, TOPICS, HEALTH, CONSULTATION, SOCIAL, OTHER_SOCIAL = range(6)

# Варианты ответов:
FREQUENCY_OPTIONS = [
    ["Часто", "1-2 раза в неделю"],
    ["1 раз в месяц", "Напомните, что за канал"]
]

TOPICS_OPTIONS = [
    ["Психосоматика", "Телесная терапия"],
    ["Общие темы про здоровье", "Саморазвитие"]
]

HEALTH_OPTIONS = [
    ["100%", "75%"],
    ["50%", "Менее 50%"]
]

CONSULTATION_OPTIONS = [
    ["Ребалансинг", "Психологическая консультация"],
    ["Клуб «Свобода дышать»", "Собираюсь записаться"],
    ["Не планирую"]
]

SOCIAL_OPTIONS = [
    ["Всё равно Telegram", "MAX"],
    ["ВКонтакте", "BiP"],
    ["Другое"]
]


#  Вспомогательная функция

async def send_to_backend(data : dict):

    """
    Отправляем данные на наш FastAPI-сервер.
    aiohttp - асинхронный HTTP-клиент (как requests, но для async-кода).
    Обёртываем в try/except чтобы бот не падал если сервер недоступен.
    """

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BACKEND_URL}/save_response",
                json=data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Данные пользователя {data.get('user_id')} сохранены")
                else:
                    logger.warning(f"Бэкенд вернул статус {resp.status}")
    except Exception as e:
        logger.error(f"Не удалось отправить данные на бэкенд: {e}")


def get_user_data(update: Update) -> dict:

    """Извлекаем базовые данные пользователя из объекта Update"""

    user = update.effective_user
    return {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name
    }


# Обработка шагов

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """
    /start - начало диалога.
    Возвращаем FREQUENCY - переходим в состояние первого вопроса.
    """

    user = update.effective_user
    welcome = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я помогаю Галине лучше понять свою аудиторию.\n"
        "Пройди короткий опрос из 5 вопросов - это займёт меньше минуты.\n\n"
        "В качестве благодарности, за участие, вас ждёт подарок!\n"
        "Ваши ответы помогут сделать контент канала ещё полезнее!"
    )
    await update.message.reply_text(welcome)

    keyboard = ReplyKeyboardMarkup(
        FREQUENCY_OPTIONS,
        one_time_keyboard=True,
        resize_keyboard=True
    )
    await update.message.reply_text(
        "1️⃣ Как часто Вы читаете канал «PRO тело со Старшиновой»?",
        reply_markup=keyboard
    )
    return FREQUENCY


async def question_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """Получаем ответ на вопрос 1, сохраняем и задаём вопрос 2"""

    answer = update.message.text

    # context.user_data - словарь для хранения данных в рамках диалога
    context.user_data["visit_frequency"] = answer

    # Отправляем частичные данные на бэкенд, а не ждём конца опроса
    data = {**get_user_data(update), "visit_frequency": answer}

    await send_to_backend(data)

    keyboard = ReplyKeyboardMarkup(
        TOPICS_OPTIONS,
        one_time_keyboard=True,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "2️⃣ Какие темы Вам интереснее всего в канале?",
        reply_markup=keyboard
    )
    return TOPICS


async def question_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """Вопрос 2 → вопрос 3"""

    answer = update.message.text
    context.user_data["topics"] = answer

    data = {**get_user_data(update), "topics": answer}
    await send_to_backend(data)

    keyboard = ReplyKeyboardMarkup(
        HEALTH_OPTIONS,
        one_time_keyboard=True,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "3️⃣ Как бы Вы оценили своё самочувствие прямо сейчас?",
        reply_markup=keyboard,
    )
    return HEALTH


async def question_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """Вопрос 3 → вопрос 4"""

    answer = update.message.text
    context.user_data["health_satisfaction"] = answer

    data = {**get_user_data(update), "health_satisfaction": answer}
    await send_to_backend(data)

    keyboard = ReplyKeyboardMarkup(
        CONSULTATION_OPTIONS,
        one_time_keyboard=True,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "4️⃣ Пользовались ли Вы услугами Галины Старшиновой?",
        reply_markup=keyboard
    )
    return CONSULTATION


async def question_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """Вопрос 4 → вопрос 5"""

    answer = update.message.text
    context.user_data["consultation"] = answer

    data = {**get_user_data(update), "consultation": answer}
    await send_to_backend(data)

    keyboard = ReplyKeyboardMarkup(
        SOCIAL_OPTIONS,
        one_time_keyboard=True,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "5️⃣ Куда передёте в случае блокировки Telegram?",
        reply_markup=keyboard
    )
    return SOCIAL


async def question_social(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """
    Вопрос 5: если выбрали "Другое" — просим уточнить.
    Иначе — завершаем опрос.
    """

    answer = update.message.text
    context.user_data["social_network"] = answer

    if answer == "Другое":
        await update.message.reply_text(
            "Напишите какую социальную сеть/мессенджер вы используете",
            reply_markup=ReplyKeyboardRemove(),
        )
        return OTHER_SOCIAL

    # Сохраняем финальный ответ
    data = {**get_user_data(update), "social_network": answer}

    await send_to_backend(data)

    await send_final_message(update)
    return ConversationHandler.END


async def question_other_social(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатываем свободный текст для варианта "Другое" в вопросе 5"""
    answer = update.message.text
    context.user_data["social_network"] = f"Другое: {answer}"

    data = {**get_user_data(update), "social_network": f"Другое: {answer}"}
    await send_to_backend(data)

    await send_final_message(update)
    return ConversationHandler.END


async def send_final_message(update: Update):

    """
    Финальное сообщение - предложение от Галины.
    Отправляем после того как человек прошёл все 5 вопросов.
    """

    final_text = (
        "Спасибо большое за Ваши ответы! 💙\n\n"
        "Галина изучит их и сделает контент ещё более полезным для Вас.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎁 *Специально для участников опроса:*\n\n"
        "Галина приглашает тебя на *бесплатную 20-минутную диагностику*.\n"
        "Расскажи о своём запросе - и Галина покажет, "
        "как телесная терапия и ребалансинг могут помочь именно тебе.\n\n"
        "📩 Напиши в личные сообщения: @galastarshinova\n"
        "или нажми кнопку ниже 👇\n\n"
        "_Количество мест ограничено!_"
    )

    await update.message.reply_text(
        final_text,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """Команда /cancel - прекращает опрос в любой момент"""

    await update.message.reply_text(
        "Опрос отменён. Если захочешь пройти снова - напиши /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    """Команда /help"""

    await update.message.reply_text(
        "Этот бот проводит опрос для канала Галины Старшиновой.\n\n"
        "Команды:\n"
        "/start - начать опрос\n"
        "/cancel - отменить опрос\n"
        "/help - это сообщение"
    )


def main():

    """Точка входа, запуск бота в режиме long polling."""

    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан, проверь файл .env")

    # ApplicationBuilder создаёт и настраивает приложение бота
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ConversationHandler: главный обработчик диалога
    # entry_points: с чего начинается (команда /start)
    # states: что делать на каждом шаге
    # fallbacks: что делать при /cancel или непредвиденном вводе

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            FREQUENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_frequency)
            ],
            TOPICS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_topics)
            ],
            HEALTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_health)
            ],
            CONSULTATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_consultation)
            ],
            SOCIAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_social)
            ],
            OTHER_SOCIAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, question_other_social)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))

    logger.info("Бот запущен, нажмите Ctrl+C для остановки.")

    # run_polling - бот сам опрашивает серверы Telegram каждые несколько секунд
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()