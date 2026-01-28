from datetime import datetime, date, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.start_commands import exit_to_main_menu
from commands.states import NOTIFICATION_MENU, PAYMENT_NOTIFICATION_MENU
from data_base.operations import get_students_with_no_calls, get_students_with_unpaid_payment
from utils.security import restrict_to


async def send_long_message(update: Update, text: str):
    """Вспомогательная функция для разбивки сообщений."""
    if len(text) <= 4000:
        await update.message.reply_text(text)
        return
    parts = []
    current_part = ""
    for line in text.split('\n'):
        if len(current_part + line + '\n') > 4000:
            parts.append(current_part.strip())
            current_part = line + '\n'
        else:
            current_part += line + '\n'
    if current_part:
        parts.append(current_part.strip())
    for part in parts:
        await update.message.reply_text(part)


@restrict_to(['admin', 'mentor'])
async def show_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип уведомлений:",
        reply_markup=ReplyKeyboardMarkup(
            [["По звонкам"], ["По оплате"], ["Все"], ["🔙 Главное меню"]],
            one_time_keyboard=True
        )
    )
    return NOTIFICATION_MENU


async def check_call_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    students = get_students_with_no_calls()
    if students:
        notifications = [f"🔹 {s.fio} {s.telegram} давно не звонил!" for s in students]
        await send_long_message(update, "❗ Уведомления по звонкам:\n\n" + "\n".join(notifications))
    else:
        await update.message.reply_text("✅ Нет уведомлений по звонкам.")
    return await exit_to_main_menu(update, context)


async def check_payment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выберите тип уведомлений по оплате:",
        reply_markup=ReplyKeyboardMarkup(
            [["По предоплате"], ["По постоплате"], ["🔙 Назад"]],
            one_time_keyboard=True
        )
    )
    return PAYMENT_NOTIFICATION_MENU


async def check_prepayment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from data_base.db import session
    from data_base.models import Payment

    students = get_students_with_unpaid_payment()
    today = date.today()
    issues = []

    if students:
        for s in students:
            debt = s.total_cost - (s.payment_amount or 0)
            last_p = session.query(Payment).filter(
                Payment.student_id == s.id,
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.desc()).first()

            if last_p:
                days = (today - last_p.payment_date).days
                p_info = f"{last_p.payment_date.strftime('%d.%m.%Y')} ({days} дн. назад)"
            else:
                p_info = "платежей нет"

            issues.append(f"👤 {s.fio}\n💰 Долг: {debt}р | Посл. платеж: {p_info}")

        await send_long_message(update, "❗ Список должников (Предоплата):\n\n" + "\n\n".join(issues))
    else:
        await update.message.reply_text("✅ Нет задолженностей по предоплате.")
    return await exit_to_main_menu(update, context)


async def check_postpayment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from data_base.db import session
    from data_base.models import Student, Payment

    employed = session.query(Student).filter(Student.training_status == "Устроился").all()
    today = date.today()
    issues = []

    for s in employed:
        try:
            if not s.commission: continue
            c_data = s.commission.split(", ")
            num = int(c_data[0]) if c_data[0].isdigit() else 0
            perc = int(c_data[1].replace("%", "")) if len(c_data) > 1 else 0
            total = ((s.salary or 0) * perc / 100) * num
            paid = s.commission_paid or 0

            if total <= paid: continue

            last_p = session.query(Payment).filter(
                Payment.student_id == s.id,
                Payment.comment.ilike("%комисс%"),
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.desc()).first()

            p_info = f"{last_p.payment_date.strftime('%d.%m.%Y')}" if last_p else "нет"
            debt = total - paid
            issues.append(f"👤 {s.fio}\n💸 Комиссия: {debt}р | Посл. платеж: {p_info}")
        except:
            continue

    if issues:
        await send_long_message(update, "❗ Список по постоплате (Комиссии):\n\n" + "\n\n".join(issues))
    else:
        await update.message.reply_text("✅ Нет задолженностей по комиссиям.")
    return await exit_to_main_menu(update, context)


async def check_all_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Оригинальная краткая логика
    calls = get_students_with_no_calls()
    payments = get_students_with_unpaid_payment()
    msgs = []
    if payments:
        msgs.append("❗ ОПЛАТЫ:")
        msgs.extend([f"• {s.fio}: {s.total_cost - s.payment_amount}р" for s in payments])
    if calls:
        msgs.append("\n❗ ЗВОНКИ:")
        msgs.extend([f"• {s.fio} ({s.telegram})" for s in calls])

    if not msgs:
        await update.message.reply_text("✅ Уведомлений нет!")
    else:
        await send_long_message(update, "\n".join(msgs))
    return await exit_to_main_menu(update, context)