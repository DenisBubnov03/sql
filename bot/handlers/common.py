from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler

def exit_to_main_menu(update: Update, context: CallbackContext) -> int:
    """Возврат в главное меню."""
    update.message.reply_text("Возврат в главное меню.")
    return ConversationHandler.END
