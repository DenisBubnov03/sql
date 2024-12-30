from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from bot.handlers.constants import (FIO, TELEGRAM, START_DATE, COURSE_TYPE, TOTAL_PAYMENT,
                           PAID_AMOUNT, COMMISSION, FIELD_TO_EDIT, FIO_OR_TELEGRAM,
                           WAIT_FOR_NEW_VALUE, SELECT_STUDENT)
from data_base.operations import add_student, get_student_by_fio, update_student

def add_student_start(update: Update, context: CallbackContext) -> int:
    """Начало диалога добавления студента."""
    update.message.reply_text("Введите ФИО студента:")
    return FIO

def add_student_fio(update: Update, context: CallbackContext) -> int:
    """Получение ФИО студента."""
    context.user_data["fio"] = update.message.text
    update.message.reply_text("Введите Telegram студента:")
    return TELEGRAM

# Аналогично добавляются другие функции, используя импортированные константы и операции.
