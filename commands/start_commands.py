# commands/start_commands.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.authorized_users import AUTHORIZED_USERS


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    """
    Отображает главное меню пользователю.
    """
    reply_keyboard = [
        ['Добавить студента', 'Просмотреть студентов'],
        ['Редактировать данные студента', 'Проверить уведомления'],
        ['Поиск ученика', 'Статистика']
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)


# Возврат в главное меню
async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Возврат в главное меню и завершение ConversationHandler.
    """
    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            [["Добавить студента", "Просмотреть студентов"],
             ["Редактировать данные студента", "Проверить уведомления"],
             ["Поиск ученика", "Статистика"]],
            one_time_keyboard=True
        )
    )
    return ConversationHandler.END
