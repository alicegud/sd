import logging
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Загружаем переменные из .env (или из переменных окружения на Railway)
load_dotenv()

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not BOT_TOKEN or not ADMIN_CHAT_ID:
    raise ValueError("Не заданы BOT_TOKEN или ADMIN_CHAT_ID в .env или переменных окружения")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Хранилище состояний (в памяти)
user_states = {}

# ---------- КОМАНДА /start ----------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    user = message.from_user
    text = (
        f"🍸 Добро пожаловать в бар «Последний шанс», {user.first_name}.\n\n"
        "Я – Бармен. Здесь каждый гость может повлиять на судьбу участников шоу.\n"
        "Твоя идея для доната (задания) может быть использована в прямом эфире.\n"
        "Просто предложи, что они должны сделать, – мы выберем лучшие.\n\n"
        "Хочешь остаться инкогнито или готов раскрыть имя?"
    )
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🥸 Анонимно", callback_data="anon"),
        InlineKeyboardButton("😎 С именем", callback_data="not_anon")
    )
    bot.send_message(chat_id, text, reply_markup=keyboard)
    user_states[chat_id] = {'state': 'waiting_choice'}
    logger.info(f"Пользователь {user.first_name} (ID: {chat_id}) начал диалог.")

# ---------- ОБРАБОТКА КНОПОК ВЫБОРА ----------
@bot.callback_query_handler(func=lambda call: call.data in ['anon', 'not_anon'])
def process_choice(call):
    chat_id = call.message.chat.id
    if chat_id not in user_states:
        return
    user_states[chat_id]['is_anon'] = (call.data == 'anon')
    user_states[chat_id]['state'] = 'waiting_message'
    bot.edit_message_text(
        "Отлично. Теперь напиши свою идею для доната.\n"
        "Опиши задание так, чтобы у нас пошли мурашки по коже…",
        chat_id, call.message.message_id
    )
    bot.answer_callback_query(call.id)
    logger.info(f"Пользователь {chat_id} выбрал анонимность: {call.data}")

# ---------- ПРИЁМ СООБЩЕНИЯ С ИДЕЕЙ ----------
@bot.message_handler(func=lambda message: user_states.get(message.chat.id, {}).get('state') == 'waiting_message')
def forward_idea(message):
    chat_id = message.chat.id
    data = user_states.get(chat_id, {})
    is_anon = data.get('is_anon', True)

    user = message.from_user
    user_full_info = f"ID: {user.id}, Имя: {user.full_name}"
    if user.username:
        user_full_info += f", Username: @{user.username}"

    if is_anon:
        sender_info_admin = f"🍸 Анонимная идея (реально: {user_full_info})"
        user_reply = "✅ Твоя идея доставлена Бармену анонимно. Если она окажется лучшей – мы свяжемся."
    else:
        sender_info_admin = f"🍸 Идея от {user.full_name}" + (f" (@{user.username})" if user.username else "")
        user_reply = "✅ Твоя идея доставлена Бармену. Если она окажется лучшей – мы свяжемся."

    try:
        if message.text:
            bot.send_message(ADMIN_CHAT_ID, f"{sender_info_admin}\n\n{message.text}")
        elif message.caption:
            bot.send_message(ADMIN_CHAT_ID, f"{sender_info_admin}\n\n{message.caption}")
        else:
            bot.send_message(ADMIN_CHAT_ID, sender_info_admin)

        bot.send_message(chat_id, user_reply)
        logger.info(f"Идея от {chat_id} отправлена админу. Анонимно: {is_anon}")
    except Exception as e:
        logger.error(f"Ошибка отправки админу от {chat_id}: {e}")
        bot.send_message(chat_id, "❌ Что-то пошло не так. Попробуй ещё раз позже.")
    finally:
        if chat_id in user_states:
            del user_states[chat_id]

# ---------- АВТООТВЕТЧИК ----------
@bot.message_handler(func=lambda message: True)
def auto_reply(message):
    chat_id = message.chat.id
    if user_states.get(chat_id, {}).get('state') in ('waiting_choice', 'waiting_message'):
        return

    text = message.text.lower() if message.text else ""
    user_name = message.from_user.first_name

    answers = {
        "привет": f"🍸 Привет, {user_name}. Заходи, присаживайся. Есть что предложить для шоу?",
        "здравствуйте": f"🍸 Здравствуй, путник. Не хочешь оставить своё пожелание участникам?",
        "кто ты": "Я – Бармен. Хранитель тайн этого заведения и посредник между зрителями и шоу.",
        "что ты умеешь": "Принимаю идеи для донатов. Напиши /start и предложи задание.",
        "спасибо": "Это тебе спасибо. Заходи ещё.",
        "пока": "Прощай, но помни: дверь в «Последний шанс» всегда открыта.",
    }

    for key in answers:
        if key in text:
            bot.send_message(chat_id, answers[key])
            return

    bot.send_message(chat_id, "🍸 Я всего лишь бармен. Если хочешь предложить идею, нажми /start.")

# ---------- ЗАПУСК БОТА ----------
if __name__ == '__main__':
    logger.info("Бот запускается в режиме long polling...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Бот остановлен с ошибкой: {e}")
        