from telegram import Update, ReplyKeyboardMarkup
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
        reply_keyboard = [['Добавить студента', 'Подписание договора', 'Договор',"📹 Создание встречи", "📊 Рассчитать зарплату", 'Поиск ученика', 'Статистика', 'Редактировать данные студента', 'Доп расходы']]
    else:
        reply_keyboard = [
            ['Добавить студента', 'Премия куратору', 'Подписание договора', 'Договор'],
            ['Редактировать данные студента', 'Проверить уведомления'],
            ['Поиск ученика', 'Статистика', "📊 Рассчитать зарплату", 'Доп расходы'],
            ['💼 Добавить КК']  # Добавляем кнопки для управления КК
        ]

    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)


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
        reply_keyboard = [['Добавить студента','Подписание договора', 'Договор',"📹 Создание встречи",
 "📊 Рассчитать зарплату", 'Поиск ученика', 'Статистика', 'Редактировать данные студента', 'Доп расходы']]
    else:
        reply_keyboard = [
            ['Добавить студента', 'Премия куратору', 'Подписание договора', 'Договор'],
            ['Редактировать данные студента', 'Проверить уведомления'],
            ['Поиск ученика', 'Статистика', "📊 Рассчитать зарплату", 'Доп расходы'],
            ['💼 Добавить КК']  # Добавляем кнопки для управления КК
        ]

    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=markup)
    return ConversationHandler.END
