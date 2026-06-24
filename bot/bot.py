# bot/bot.py
# Бот для канала
# Запуск: python -m bot.bot

import os
import json
import aiohttp
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler, ContextTypes, filters
)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = "http://localhost:8000"

logging.basicConfig(format="%(asctime)s — %(levelname)s — %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Файл с администраторами
ADMINS_FILE = "admins.json"

def load_admins():
    try:
        with open(ADMINS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_admins(data):
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

admins = load_admins()

# Состояния диалога
(CHOOSE_ACTION, BOOK_NAME, LEAVE_CONTACT,
 FREQUENCY, NOT_READING_WHY, TOPICS, HEALTH,
 CONSULTATION_BEEN, FEEDBACK_TYPE, FEEDBACK_TEXT,
 NOT_BEEN_WHY, SOCIAL, AFTER_SURVEY, BOOK_NAME_AFTER) = range(14)

# Кнопки для каждого вопроса
FREQ_KB = [["Несколько раз в неделю", "Несколько раз в месяц"], ["Не читаю"]]
WHY_KB = [["Нет времени"], ["Не интересно"], ["Я здесь, чтобы не терять контакт специалиста"]]
TOPICS_KB = [["Психосоматика", "Телесная терапия"], ["Нутрициология", "О личном"]]
HEALTH_KB = [["100%", "75%"], ["50%", "Менее 50%"]]
CONSULT_KB = [["Была / Был", "Не был(а)"]]
FEEDBACK_KB = [["Всё понравилось 🌿", "Есть что улучшить 🌱"], ["Поделиться впечатлением..."]]
NOT_BEEN_KB = [["Пока нет времени"], ["Нужна дополнительная информация"]]
SOCIAL_KB = [["Всё равно Telegram", "MAX"], ["ВКонтакте", "BiP"], ["Другое"]]

# Допустимые ответы чтобы не принимать произвольный текст
VALID = {
    CHOOSE_ACTION:     ["Пройти опрос", "Записаться на приём"],
    FREQUENCY:         ["Несколько раз в неделю", "Несколько раз в месяц", "Не читаю"],
    NOT_READING_WHY:   ["Нет времени", "Не интересно", "Я здесь, чтобы не терять контакт специалиста"],
    TOPICS:            ["Психосоматика", "Телесная терапия", "Нутрициология", "О личном"],
    HEALTH:            ["100%", "75%", "50%", "Менее 50%"],
    CONSULTATION_BEEN: ["Была / Был", "Не был(а)"],
    FEEDBACK_TYPE:     ["Всё понравилось 🌿", "Есть что улучшить 🌱", "Поделиться впечатлением..."],
    NOT_BEEN_WHY:      ["Пока нет времени", "Нужна дополнительная информация"],
    SOCIAL:            ["Всё равно Telegram", "MAX", "ВКонтакте", "BiP", "Другое"],
}

def kb(options):
    return ReplyKeyboardMarkup(options, one_time_keyboard=True, resize_keyboard=True)

def user_info(update):
    u = update.effective_user
    return {"user_id": u.id, "username": u.username, "first_name": u.first_name}

async def send_to_backend(data):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BACKEND_URL}/save_response", json=data,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status != 200:
                    logger.warning(f"Бэкенд вернул {r.status}")
    except Exception as e:
        logger.error(f"Ошибка отправки на бэкенд: {e}")

async def notify_admins(context, text):
    for uid, settings in admins.items():
        if settings.get("notify", True):
            try:
                await context.bot.send_message(int(uid), text)
            except Exception as e:
                logger.warning(f"Не удалось уведомить {uid}: {e}")



# ========= /start ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    user = update.effective_user

    await update.message.reply_text(
        f"Здравствуйте, {user.first_name}! 👋\n\n"
        "Я бот-помощник Галины Старшиновой.\n\n"
        "Большое спасибо, что проявляете интерес к каналу! "
        "Хотим задать Вам пару вопросов - это займёт буквально минуту. "
        "В благодарность за уделённое время Вас ждёт небольшой подарок 🎁"
    )
    await update.message.reply_text(
        "Что Вас интересует?",
        reply_markup=kb([["Пройти опрос", "Записаться на приём"]])
    )
    return CHOOSE_ACTION


async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[CHOOSE_ACTION]:
        await update.message.reply_text(
            "Пожалуйста, выберите один из вариантов 👇",
            reply_markup=kb([["Пройти опрос", "Записаться на приём"]])
        )
        return CHOOSE_ACTION

    if answer == "Записаться на приём":
        await update.message.reply_text(
            "Хорошо! Напишите, пожалуйста, Ваше имя:",
            reply_markup=ReplyKeyboardRemove()
        )
        return BOOK_NAME

    # Начинаем опрос
    await update.message.reply_text(
        "1️⃣ Как часто Вы читаете канал «PRO тело со Старшиновой»?",
        reply_markup=kb(FREQ_KB)
    )
    return FREQUENCY


# ========== Запись на приём  ============

async def book_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["book_name"] = name
    user = update.effective_user

    if user.username:
        await notify_admins(
            context,
            f"📋 Новая запись на приём!\nИмя: {name}\nTelegram: @{user.username}"
        )
        await update.message.reply_text(
            f"Спасибо, {name}! Ваша заявка принята.\n"
            "Галина скоро с Вами свяжется 😊"
        )
        return ConversationHandler.END

    # Если никнейма нет, просим контакт
    await update.message.reply_text(
        "У Вас не указан Telegram-никнейм, поэтому оставьте контакт для связи: "
        "ник в Telegram, номер телефона или другой мессенджер (напишите какой):"
    )
    return LEAVE_CONTACT


async def leave_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact = update.message.text.strip()
    name = context.user_data.get("book_name", "")

    await notify_admins(
        context,
        f"📋 Новая запись!\nИмя: {name}\nКонтакт: {contact}"
    )

    await update.message.reply_text(
        f"Спасибо, {name}! Ваша заявка принята.\n"
        "Галина скоро с Вами свяжется 😊"
    )

    return ConversationHandler.END


# ===========  Вопросы  ==========

async def question_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[FREQUENCY]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(FREQ_KB))
        return FREQUENCY

    context.user_data["visit_frequency"] = answer
    await send_to_backend({**user_info(update), "visit_frequency": answer})

    if answer == "Не читаю":
        await update.message.reply_text("Можете сказать почему?", reply_markup=kb(WHY_KB))
        return NOT_READING_WHY

    await update.message.reply_text("2️⃣ Какие темы Вам нравятся?", reply_markup=kb(TOPICS_KB))
    return TOPICS


async def question_not_reading(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[NOT_READING_WHY]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(WHY_KB))
        return NOT_READING_WHY

    full = f"Не читаю - {answer}"
    context.user_data["visit_frequency"] = full
    await send_to_backend({**user_info(update), "visit_frequency": full})

    await update.message.reply_text("2️⃣ Какие темы Вам нравятся?", reply_markup=kb(TOPICS_KB))
    return TOPICS


async def question_topics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[TOPICS]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(TOPICS_KB))
        return TOPICS

    context.user_data["topics"] = answer
    await send_to_backend({**user_info(update), "topics": answer})

    await update.message.reply_text(
        "3️⃣ Как бы Вы оценили своё самочувствие прямо сейчас?",
        reply_markup=kb(HEALTH_KB)
    )
    return HEALTH


async def question_health(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[HEALTH]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(HEALTH_KB))
        return HEALTH

    context.user_data["health_satisfaction"] = answer
    await send_to_backend({**user_info(update), "health_satisfaction": answer})

    await update.message.reply_text(
        "4️⃣ Если Вы были на консультации или сессии у Галины, поделитесь, как это было для Вас?",
        reply_markup=kb(CONSULT_KB)
    )
    return CONSULTATION_BEEN


async def question_consultation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[CONSULTATION_BEEN]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(CONSULT_KB))
        return CONSULTATION_BEEN

    context.user_data["consultation"] = answer

    if answer == "Была / Был":
        await update.message.reply_text(
            "Здорово! Поделитесь впечатлениями - это очень важно для нас 🙏",
            reply_markup=kb(FEEDBACK_KB)
        )
        return FEEDBACK_TYPE

    await update.message.reply_text(
        "Понятно. Может, что-то останавливает или нужна дополнительная информация об услугах?",
        reply_markup=kb(NOT_BEEN_KB)
    )
    return NOT_BEEN_WHY


async def question_feedback_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[FEEDBACK_TYPE]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(FEEDBACK_KB))
        return FEEDBACK_TYPE

    if answer == "Расскажу подробнее...":
        await update.message.reply_text(
            "Будем рады услышать! Напишите, что думаете:",
            reply_markup=ReplyKeyboardRemove()
        )
        return FEEDBACK_TEXT

    val = f"Была / Был — {answer}"
    context.user_data["consultation"] = val
    await send_to_backend({**user_info(update), "consultation": val})

    await update.message.reply_text(
        "5️⃣ Куда перейдёте в случае блокировки Telegram?",
        reply_markup=kb(SOCIAL_KB)
    )
    return SOCIAL


async def question_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    val = f"Была / Был — отзыв: {text}"
    context.user_data["consultation"] = val
    await send_to_backend({**user_info(update), "consultation": val})

    await update.message.reply_text(
        "5️⃣ Куда перейдёте в случае блокировки Telegram?",
        reply_markup=kb(SOCIAL_KB)
    )
    return SOCIAL


async def question_not_been(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[NOT_BEEN_WHY]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(NOT_BEEN_KB))
        return NOT_BEEN_WHY

    val = f"Не был(а) - {answer}"
    context.user_data["consultation"] = val
    await send_to_backend({**user_info(update), "consultation": val})

    await update.message.reply_text(
        "5️⃣ Куда перейдёте в случае блокировки Telegram?",
        reply_markup=kb(SOCIAL_KB)
    )
    return SOCIAL


async def question_social(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    answer = update.message.text

    if answer not in VALID[SOCIAL]:
        await update.message.reply_text("Выберите один из вариантов 👇", reply_markup=kb(SOCIAL_KB))
        return SOCIAL

    context.user_data["social_network"] = answer
    await send_to_backend({**user_info(update), "social_network": answer})


    # Финальное сообщение и подарок
    await update.message.reply_text(
        "Большое спасибо за Ваши ответы! 💙\n\n"
        "Галина обязательно учтёт их при работе над контентом.\n\n"
        "🎁 В знак благодарности - бесплатная 30-минутная консультация. "
        "Если хотите записаться, нажмите кнопку ниже.",
        reply_markup=ReplyKeyboardRemove()
    )
    inline_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Записаться на консультацию 📝", callback_data="book_after")
    ]])
    await update.message.reply_text("👇", reply_markup=inline_kb)

    return AFTER_SURVEY



# ============= Запись на консультацию после опроса ==============

async def handle_book_after(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Напишите, пожалуйста, Ваше имя:")
    return BOOK_NAME_AFTER


async def book_name_after(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["book_name"] = name
    user = update.effective_user

    if user.username:
        await notify_admins(
            context,
            f"📋 Запись на консультацию!\nИмя: {name}\nTelegram: @{user.username}"
        )
        await update.message.reply_text(
            f"Готово, {name}! Ваша заявка принята.\n"
            "Галина скоро с Вами свяжется 😊"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "У Вас не указан Telegram-никнейм. Оставьте контакт для связи:"
    )
    return LEAVE_CONTACT



# =========== Служебные команды ==========

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Опрос отменён. Напишите /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start - начать\n"
        "/cancel - отменить опрос\n"
        "/help - это сообщение\n"
        "/admin - войти как администратор\n"
        "/notifications - включить/отключить уведомления о записях (только для администраторов)\n"
        "/result - статистика ответов (только для администраторов)"
    )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0] != BOT_TOKEN:
        await update.message.reply_text("Неверный пароль.")
        return

    uid = str(update.effective_user.id)
    if uid in admins:
        await update.message.reply_text("Вы уже администратор.")
        return

    admins[uid] = {"notify": True}
    save_admins(admins)
    await update.message.reply_text(
        "✅ Готово! Теперь Вы администратор.\n"
        "Будете получать уведомления о новых записях.\n\n"
        "Чтобы отключить /notifications"
    )


async def notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in admins:
        await update.message.reply_text("Эта команда только для администраторов.")
        return

    current = admins[uid].get("notify", True)
    admins[uid]["notify"] = not current
    save_admins(admins)

    status = "включены ✅" if not current else "отключены ❌"
    await update.message.reply_text(f"Уведомления {status}")


async def result_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in admins:
        await update.message.reply_text("Эта команда только для администраторов.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BACKEND_URL}/stats",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as r:
                if r.status != 200:
                    await update.message.reply_text("Не удалось получить данные с сервера.")
                    return
                data = await r.json()
    except Exception as e:
        await update.message.reply_text(f"Ошибка подключения к серверу: {e}")
        return

    total = data.get("total_users", 0)

    def fmt_block(predefined, counts):
        lines = []
        for opt in predefined:
            n = counts.get(opt, 0)
            lines.append(f"  • {opt} — {n}")
        for k, v in counts.items():
            if k not in predefined:
                lines.append(f"  • {k} — {v}")
        return "\n".join(lines) if lines else "  нет ответов"

    freq_opts    = ["Несколько раз в неделю", "Несколько раз в месяц", "Не читаю"]
    topics_opts  = ["Психосоматика", "Телесная терапия", "Нутрициология", "О личном"]
    health_opts  = ["100%", "75%", "50%", "Менее 50%"]
    consult_opts = ["Была / Был", "Не был(а)"]
    social_opts  = ["Всё равно Telegram", "MAX", "ВКонтакте", "BiP", "Другое"]

    msg = (
        f"📊 Статистика опроса\n"
        f"Всего участников: {total}\n\n"
        f"1️⃣ Как часто читаете канал?\n"
        f"{fmt_block(freq_opts, data.get('visit_frequency', {}))}\n\n"
        f"2️⃣ Какие темы нравятся?\n"
        f"{fmt_block(topics_opts, data.get('topics', {}))}\n\n"
        f"3️⃣ Самочувствие прямо сейчас\n"
        f"{fmt_block(health_opts, data.get('health_satisfaction', {}))}\n\n"
        f"4️⃣ Были на консультации?\n"
        f"{fmt_block(consult_opts, data.get('consultation', {}))}\n\n"
        f"5️⃣ Куда при блокировке Telegram?\n"
        f"{fmt_block(social_opts, data.get('social_network', {}))}"
    )

    await update.message.reply_text(msg)



# ========== Запуск ==========

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан. Проверь .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            BOOK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, book_name)],
            LEAVE_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, leave_contact)],
            FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_frequency)],
            NOT_READING_WHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_not_reading)],
            TOPICS: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_topics)],
            HEALTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_health)],
            CONSULTATION_BEEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_consultation)],
            FEEDBACK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_feedback_type)],
            FEEDBACK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_feedback_text)],
            NOT_BEEN_WHY: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_not_been)],
            SOCIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, question_social)],
            AFTER_SURVEY: [CallbackQueryHandler(handle_book_after, pattern="^book_after$")],
            BOOK_NAME_AFTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, book_name_after)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("notifications", notifications_command))
    app.add_handler(CommandHandler("result", result_command))

    logger.info("Бот запущен, нажмите Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
