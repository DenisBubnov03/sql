from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает главное меню пользователю.
    """
    user_id = update.message.from_user.id

    if user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return

    # Ограниченное меню для not_admin
    if user_id in NOT_ADMINS:
        reply_keyboard = [['Поиск ученика']]
    else:
        reply_keyboard = [
            ['Добавить студента', 'Премия куратору'],
            ['Редактировать данные студента', 'Проверить уведомления'],
            ['Поиск ученика', 'Статистика', "📊 Рассчитать зарплату"]
        ]

    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Привет! Выберите действие:", reply_markup=markup)


# Возврат в главное меню
async def exit_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Возврат в главное меню и завершение ConversationHandler.
    """
    reply_keyboard = [
        ["Добавить студента", "Премия куратору"],
        ["Редактировать данные студента", "Проверить уведомления"],
        ["Поиск ученика", "Статистика", "📊 Рассчитать зарплату"]

    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=markup
    )
    return ConversationHandler.END
