from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from data_base.operations import get_career_consultant_by_telegram
from data_base.db import get_session


async def is_career_consultant(user_id: int, username: str = None) -> bool:
    """Проверяет, является ли пользователь карьерным консультантом."""
    if not username:
        return False
    
    session = get_session()
    try:
        consultant = get_career_consultant_by_telegram(f"@{username}")
        return consultant is not None and consultant.is_active
    except Exception:
        return False
    finally:
        session.close()


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает главное меню пользователю.
    """
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # Проверяем доступ для карьерных консультантов в БД
    if await is_career_consultant(user_id, username):
        # Сразу отправляем в меню карьерного консультанта
        from bot.handlers.career_consultant_handlers import career_consultant_start
        return await career_consultant_start(update, context)
    elif user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    # Ограниченное меню для not_admin
    elif user_id in NOT_ADMINS:
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
    else:
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

    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)


# Общая функция для логики сброса и отрисовки меню
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import logging

# Предполагаем, что импорты ролей и клавиатур уже есть
# from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Полностью сбрасывает состояние пользователя и возвращает в главное меню.
    """
    # 1. Сброс данных сессии
    context.user_data.clear()

    user_id = update.effective_user.id
    username = update.effective_user.username

    # 2. Безопасная остановка фоновых задач
    if context.job_queue:
        current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
        for job in current_jobs:
            job.schedule_removal()
    else:
        logging.warning(f"JobQueue не настроен. Пропускаем удаление задач для {user_id}")

    # 3. Проверка ролей
    # Проверка на карьерного консультанта
    if await is_career_consultant(user_id, username):
        from bot.handlers.career_consultant_handlers import career_consultant_start
        return await career_consultant_start(update, context)

    # Проверка на доступ (если не КК и не в списках доступа)
    if user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа к этой системе.")
        return ConversationHandler.END

    # 4. Формирование меню (выбор кнопок)
    if user_id in NOT_ADMINS:
        reply_keyboard = [
            [KeyboardButton('Добавить студента')],
            [KeyboardButton('Подписание договора'), KeyboardButton('Договор')],
            [KeyboardButton("📹 Создание встречи"), KeyboardButton("📊 Рассчитать зарплату")],
            [KeyboardButton('Поиск ученика'), KeyboardButton('Статистика')],
            [KeyboardButton('Редактировать данные студента')],
            [KeyboardButton('Доп расходы')]
        ]
    else:
        # Админ-меню (добавлены кнопки, которые были в твоем списке)
        reply_keyboard = [
            [KeyboardButton('Добавить студента')],
            [KeyboardButton('Премия куратору'), KeyboardButton('Подписание договора')],
            [KeyboardButton('Договор'), KeyboardButton('Редактировать данные студента')],
            [KeyboardButton('Проверить уведомления'), KeyboardButton('Поиск ученика')],
            [KeyboardButton('Статистика'), KeyboardButton("📊 Рассчитать зарплату")],
            [KeyboardButton('Доп расходы'), KeyboardButton('💼 Добавить КК')]
        ]

    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    # 5. Ответ пользователю
    # Если команда вызвана как /start, текст может быть другим
    text = "🔄 Состояние сброшено. Вы в главном меню.\nВыберите действие:"
    if update.message.text == '/start':
        text = f"Добро пожаловать, {update.effective_user.first_name}! 👋\nВыберите действие:"

    await update.message.reply_text(text, reply_markup=markup)

    return ConversationHandler.END
# Возврат в главное меню
async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Возврат в главное меню и завершение ConversationHandler.
    """
    user_id = update.message.from_user.id

    username = update.message.from_user.username

    # Проверяем доступ для карьерных консультантов в БД
    if await is_career_consultant(user_id, username):
        # Сразу отправляем в меню карьерного консультанта
        from bot.handlers.career_consultant_handlers import career_consultant_start
        return await career_consultant_start(update, context)
    elif user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    # Ограниченное меню для not_admin
    elif user_id in NOT_ADMINS:
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
    else:
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

    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=markup)
    return ConversationHandler.END
