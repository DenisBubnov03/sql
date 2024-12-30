from telegram import Update
from telegram.ext import CallbackContext

def start(update: Update, context: CallbackContext) -> None:
    """Обрабатывает команду /start."""
    update.message.reply_text("Добро пожаловать в систему управления студентами!")
