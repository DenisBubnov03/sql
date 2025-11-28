from uuid import uuid4
from urllib.parse import urlencode
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ConversationHandler, ContextTypes
import requests

from commands.start_commands import exit_to_main_menu
from data_base.db import session
from data_base.models import Mentor
from commands.states import MEETING_TYPE_SELECTION
from utils.request_logger import log_request, log_conversation_handler


def generate_meeting_url(creator_telegram: str, meeting_type: str) -> str:
    """
    Генерирует ссылку на Jitsi встречу с параметрами создателя и типа встречи

    Args:
        creator_telegram: Telegram создателя встречи (например, @username)
        meeting_type: Тип встречи ("зачет" или "мок")

    Returns:
        URL встречи Jitsi с параметрами
    """
    room = uuid4().hex[:10]  # случайное имя комнаты

    # Параметры для URL
    params = {
        "creator": creator_telegram.replace("@", ""),  # убираем @ для URL
        "type": meeting_type
    }

    # Формируем URL с параметрами
    base_url = f"https://meet.coconutjitsi.ru/{room}"
    query_string = urlencode(params)
    return f"{base_url}?{query_string}"


@log_request("create_meeting_entry")
async def create_meeting_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс создания встречи"""
    user_id = update.message.from_user.id
    username = "@" + update.message.from_user.username if update.message.from_user.username else None

    # Проверяем, является ли пользователь ментором или админом
    mentor = session.query(Mentor).filter(Mentor.chat_id == str(user_id)).first()

    if not mentor:
        await update.message.reply_text("❌ Эта функция доступна только для кураторов и админов.")
        return ConversationHandler.END

    # Сохраняем telegram создателя
    context.user_data["creator_telegram"] = username

    # Предлагаем выбрать тип встречи
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("✅ Зачет")],
            [KeyboardButton("📝 Мок")],
            [KeyboardButton("🔙 В главное меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "📅 Создание встречи\n\n"
        "Выберите тип встречи:",
        reply_markup=keyboard
    )

    return MEETING_TYPE_SELECTION


API_BASE_URL = "http://91.229.11.119:8000"  # пример, подставь свой IP/домен


def create_backend_meeting(room, creator_telegram, meeting_type):
    try:
        resp = requests.post(
            f"{API_BASE_URL}/api/meetings",
            params={
                "room_name": room,
                "creator": creator_telegram,
                "type": meeting_type
            },
            timeout=3
        )
        print("Backend responded:", resp.text)
    except Exception as e:
        print("Failed to call backend:", e)


@log_conversation_handler("select_meeting_type")
async def select_meeting_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meeting_type_text = update.message.text.strip()
    meeting_type = None

    if meeting_type_text == "✅ Зачет":
        meeting_type = "зачет"
    elif meeting_type_text == "📝 Мок":
        meeting_type = "мок"
    else:
        keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("✅ Зачет")],
                [KeyboardButton("📝 Мок")],
                [KeyboardButton("🔙 В главное меню")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(
            "❌ Пожалуйста, выберите тип встречи из списка:",
            reply_markup=keyboard
        )
        return MEETING_TYPE_SELECTION

    creator_telegram = context.user_data.get("creator_telegram")
    if not creator_telegram:
        username = update.message.from_user.username
        creator_telegram = "@" + username if username else "unknown"

    # генерируем имя комнаты
    room = uuid4().hex[:10]

    # вызываем API
    create_backend_meeting(room, creator_telegram, meeting_type)

    # генерируем ссылку
    meeting_url = f"https://meet.coconutjitsi.ru/{room}?{urlencode({'creator': creator_telegram.replace('@', ''), 'type': meeting_type})}"

    await update.message.reply_text(
        f"✅ Встреча создана!\n\n"
        f"📅 Тип: {meeting_type_text}\n"
        f"👤 Создатель: {creator_telegram}\n\n"
        f"🔗 Ссылка на встречу:\n{meeting_url}"
    )

    await exit_to_main_menu(update, context)
    return ConversationHandler.END

