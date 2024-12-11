# commands/start_commands.py
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await start(update, context)  # Отображаем главное меню
    return ConversationHandler.END
