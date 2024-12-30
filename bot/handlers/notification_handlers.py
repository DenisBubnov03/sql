from telegram import Update
from telegram.ext import CallbackContext
from bot.handlers.constants import NOTIFICATION_MENU
from data_base.operations import get_students_with_no_calls, get_students_with_unpaid_commissions

def check_call_notifications(update: Update, context: CallbackContext) -> None:
    """Проверка уведомлений по звонкам."""
    students = get_students_with_no_calls()
    if students:
        response = "\n".join([f"{s.fio} давно не звонил!" for s in students])
    else:
        response = "Все звонки в порядке."
    update.message.reply_text(response)

def check_payment_notifications(update: Update, context: CallbackContext) -> None:
    """Проверка уведомлений по оплатам."""
    students = get_students_with_unpaid_commissions()
    if students:
        response = "\n".join([f"{s.fio} задолжал {s.commission - s.commission_paid}." for s in students])
    else:
        response = "Все оплаты в порядке."
    update.message.reply_text(response)
