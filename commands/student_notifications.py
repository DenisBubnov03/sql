from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.authorized_users import AUTHORIZED_USERS
from commands.start_commands import exit_to_main_menu
from commands.states import NOTIFICATION_MENU
from data_base.operations import get_all_students, get_students_with_no_calls, get_students_with_unpaid_payment


async def show_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает меню для выбора уведомлений.
    """
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Выберите тип уведомлений:",
        reply_markup=ReplyKeyboardMarkup(
            [["По звонкам", "По оплате", "Все"], ["🔙 Главное меню"]],
            one_time_keyboard=True
        )
    )
    return NOTIFICATION_MENU


async def check_call_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет уведомления по звонкам.
    """
    students = get_students_with_no_calls()

    if students:
        notifications = [
            f"Студент {student.fio} {student.telegram} давно не звонил!" for student in students
        ]
        await update.message.reply_text("❗ Уведомления по звонкам:\n" + "\n".join(notifications))
    else:
        await update.message.reply_text("✅ Нет уведомлений по звонкам.")
    return await exit_to_main_menu(update, context)


async def check_payment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет уведомления по оплате.
    """
    students = get_students_with_unpaid_payment()

    if students:
        notifications = [
            f"Студент {student.fio} {student.telegram} задолжал {student.total_cost - student.payment_amount} рублей."
            for student in students
        ]
        await update.message.reply_text("❗ Уведомления по оплате:\n" + "\n".join(notifications))
    else:
        await update.message.reply_text("✅ Нет уведомлений по оплате.")
    return await exit_to_main_menu(update, context)


async def check_all_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет все уведомления.
    """
    call_notifications = get_students_with_no_calls()
    payment_notifications = get_students_with_unpaid_payment()

    messages = []

    if payment_notifications:
        messages.append("❗ Уведомления по оплатам:")
        messages.extend([
            f"Студент {student.fio} {student.telegram} задолжал {student.total_cost - student.payment_amount} рублей."
            for student in payment_notifications
        ])

    if call_notifications:
        messages.append("❗ Уведомления по звонкам:")
        messages.extend([
            f"Студент {student.fio} {student.telegram} давно не звонил!" for student in call_notifications
        ])

    if not messages:
        await update.message.reply_text("✅ Все в порядке, уведомлений нет!")
    else:
        await update.message.reply_text("\n".join(messages))
    return await exit_to_main_menu(update, context)
