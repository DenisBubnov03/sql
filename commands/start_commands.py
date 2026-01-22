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


from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler


# Общая функция для логики сброса и отрисовки меню
async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Полностью сбрасывает состояние пользователя и возвращает в главное меню.
    Вызывается командами /start и /restart.
    """
    # 1. Сброс данных
    context.user_data.clear()

    # 2. Остановка фоновых задач пользователя (если есть)
    user_id = update.effective_user.id
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs:
        job.schedule_removal()

    username = update.effective_user.username

    # 3. Проверка ролей (ваша логика)
    if await is_career_consultant(user_id, username):
        from bot.handlers.career_consultant_handlers import career_consultant_start
        return await career_consultant_start(update, context)

    if user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

    # 4. Выбор клавиатуры
    if user_id in NOT_ADMINS:
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
        # Ваше стандартное админ-меню
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

    await update.message.reply_text(
        "🔄 Состояние сброшено. Все процессы остановлены.\nВыберите действие:",
        reply_markup=markup
    )

    # Возвращаем END, чтобы выйти из любого ConversationHandler
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
