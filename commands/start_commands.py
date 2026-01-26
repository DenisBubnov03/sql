from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from data_base.models import Mentor
from data_base.operations import get_career_consultant_by_telegram, get_mentor_by_telegram
from data_base.db import get_session, session
from utils.security import get_user_role


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
    role = await get_user_role(user_id, username)
    if role in ["mentor", "admin"] and username:
        session = get_session()
        try:
            from data_base.models import Mentor
            # Ищем ментора по username (убираем лишние @ для чистоты поиска)
            formatted_username = f"@{username.replace('@', '')}"
            mentor = session.query(Mentor).filter(Mentor.telegram == formatted_username).first()

            # Если нашли ментора и у него не заполнен chat_id — записываем
            if mentor and not mentor.chat_id:
                mentor.chat_id = str(user_id)
                session.commit()
        except Exception as e:
            print(f"Ошибка при сохранении chat_id: {e}")
        finally:
            session.close()


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