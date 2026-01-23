from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from data_base.models import Mentor
from data_base.operations import get_career_consultant_by_telegram, get_mentor_by_telegram
from data_base.db import get_session, session


# --- Функция определения ролей (твоя логика) ---
async def get_user_role(user_id: int, username: str = None):
    if not username:
        return "admin" if user_id in AUTHORIZED_USERS else None

    formatted_username = f"@{username.replace('@', '')}"
    session = get_session()
    try:
        cc = get_career_consultant_by_telegram(formatted_username)
        if cc and cc.is_active:
            return "cc"

        mentor = get_mentor_by_telegram(formatted_username)
        if mentor:
            return "mentor"

        if user_id in AUTHORIZED_USERS:
            return "admin"

        return None
    finally:
        session.close()


# --- Твои списки кнопок (1 в 1 из функции start) ---
def get_reply_markup(role: str):
    if role == "mentor":
        reply_keyboard = [
            [KeyboardButton('Добавить студента')],
            [KeyboardButton('Подписание договора')],
            [KeyboardButton('Договор')],
            [KeyboardButton("📹 Создание встречи")],
            [KeyboardButton("📊 Рассчитать зарплату")],
            [KeyboardButton('Поиск ученика')],
            [KeyboardButton('Статистика')],
            [KeyboardButton('Редактировать данные студента')],
            [KeyboardButton('Доп расходы')]
        ]
    else:  # admin
        reply_keyboard = [
            [KeyboardButton('Добавить студента')],
            [KeyboardButton('Премия куратору')],
            [KeyboardButton('Подписание договора')],
            [KeyboardButton('Договор')],
            [KeyboardButton('Редактировать данные студента')],
            [KeyboardButton('Проверить уведомления')],
            [KeyboardButton('Поиск ученика')],
            [KeyboardButton('Статистика')],
            [KeyboardButton("📊 Рассчитать зарплату")],
            [KeyboardButton('Доп расходы')],
            [KeyboardButton('💼 Добавить КК')]
        ]
    return ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)


# --- Основные команды ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Форматируем username (добавляем @, если нужно), как в твоем примере
    formatted_username = f"@{username}" if username and not username.startswith("@") else username

    # --- ПРОВЕРКА И ДОБАВЛЕНИЕ В ТАБЛИЦУ MENTORS ---
    try:
        # Ищем ментора по chat_id (user_id)
        mentor = session.query(Mentor).filter(Mentor.chat_id == user_id).first()

        if not mentor:
            # Если по ID не нашли, проверяем по юзернейму (вдруг он уже был вбит вручную)
            mentor_by_username = session.query(Mentor).filter(Mentor.telegram == formatted_username).first()

            if mentor_by_username:
                # Привязываем ID к существующей записи
                mentor_by_username.chat_id = user_id
                session.commit()
            else:
                # Если вообще нет записи — создаем новую
                new_mentor = Mentor(
                    chat_id=user_id,
                    telegram=formatted_username,
                    full_name=update.effective_user.full_name
                )
                session.add(new_mentor)
                session.commit()
    except Exception as e:
        session.rollback()
        # Здесь можно добавить logger.error(f"Ошибка БД: {e}")
    # -----------------------------------------------

    role = await get_user_role(user_id, username)

    if role == "cc":
        from bot.handlers.career_consultant_handlers import career_consultant_start
        return await career_consultant_start(update, context)

    if role is None:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return

    markup = get_reply_markup(role)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает состояние и возвращает в меню."""
    context.user_data.clear()

    # Отрисовка меню через start
    await start(update, context)

    # ЭТО ОБЯЗАТЕЛЬНО для сброса состояния (ожидания ввода ТГ и т.д.)
    return ConversationHandler.END


async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в меню."""
    return await restart(update, context)