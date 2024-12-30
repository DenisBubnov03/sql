from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from bot.handlers.constants import START_PERIOD, END_PERIOD, STATISTICS_MENU, COURSE_TYPE_MENU
from data_base.operations import get_students_by_period

def request_period_start(update: Update, context: CallbackContext) -> int:
    """Запрос начальной даты периода."""
    update.message.reply_text("Введите начальную дату (ДД.ММ.ГГГГ):")
    return START_PERIOD

def handle_period_start(update: Update, context: CallbackContext) -> int:
    """Обработка начальной даты периода."""
    context.user_data["start_date"] = update.message.text
    update.message.reply_text("Введите конечную дату (ДД.ММ.ГГГГ):")
    return END_PERIOD

