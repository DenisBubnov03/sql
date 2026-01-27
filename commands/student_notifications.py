from datetime import datetime, date, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.start_commands import exit_to_main_menu
from commands.states import NOTIFICATION_MENU, PAYMENT_NOTIFICATION_MENU
from data_base.operations import get_students_with_no_calls, get_students_with_unpaid_payment
from utils.security import restrict_to


async def send_long_message(update: Update, text: str):
    """Вспомогательная функция для разбивки и отправки длинных сообщений."""
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
        notifications = [f"{s.fio} {s.telegram} давно не звонил!" for s in students]
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
    """
    Проверяет уведомления по предоплате (должники).
    """
    from data_base.db import session
    from data_base.models import Student, Payment
    from data_base.operations import get_students_with_unpaid_payment

    students = get_students_with_unpaid_payment()
    today = date.today()

    if students:
        notif_list = []
        for s in students:
            # Ищем самый свежий подтвержденный платеж (не обязательно комиссию)
            last_p = session.query(Payment).filter(
                Payment.student_id == s.id,
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.desc()).first()

            if last_p and last_p.payment_date:
                days = (today - last_p.payment_date).days
                p_info = f"📅 Последний платеж: {last_p.payment_date.strftime('%d.%m.%Y')} ({days} дн. назад)"
            else:
                p_info = "📅 Платежей еще не было"

            debt = s.total_cost - (s.payment_amount or 0)

            txt = (f"👤 {s.fio} ({s.telegram})\n"
                   f"{p_info}\n"
                   f"💰 Долг: {debt} руб. (из {s.total_cost})\n")
            notif_list.append(txt)

        await send_long_message(update, "❗ Уведомления по предоплате (должники):\n\n" + "\n".join(notif_list))
    else:
        await update.message.reply_text("✅ Нет уведомлений по предоплате.")
    return await exit_to_main_menu(update, context)


async def check_postpayment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from data_base.db import session
    from data_base.models import Student, Payment

    employed_students = session.query(Student).filter(Student.training_status == "Устроился").all()
    issues = []
    today = date.today()
    one_month_ago = today - timedelta(days=30)

    for student in employed_students:
        try:
            if not student.commission:
                continue

            # Парсим комиссию: "количество_платежей, процент%"
            comm_data = [item.strip() for item in student.commission.split(",")]
            num_payments = int(comm_data[0]) if comm_data and comm_data[0].isdigit() else 0
            percentage = int(comm_data[1].replace("%", "")) if len(comm_data) > 1 else 0

            salary = student.salary or 0
            total_expected = (salary * percentage / 100) * num_payments
            paid_so_far = student.commission_paid or 0

            if total_expected == 0 or paid_so_far >= total_expected:
                continue

            # ПОИСК ПЛАТЕЖА: изменен фильтр на %комисс% для надежности
            last_p = session.query(Payment).filter(
                Payment.student_id == student.id,
                Payment.comment.ilike("%Комисс%"),
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.desc()).first()

            last_date = last_p.payment_date if last_p else None
            reasons = []

            if paid_so_far < total_expected:
                reasons.append(f"Неполная выплата: {paid_so_far}/{total_expected} руб.")

            # Обработка даты трудоустройства
            emp_date = None
            if student.employment_date:
                if isinstance(student.employment_date, str):
                    try:
                        emp_date = datetime.strptime(student.employment_date, "%d.%m.%Y").date()
                    except:
                        pass
                else:
                    emp_date = student.employment_date

            if not last_date and emp_date and emp_date < one_month_ago:
                reasons.append("Нет платежей комиссии (устроился > 30 дней назад)")
            elif last_date and last_date < one_month_ago:
                reasons.append("Последний платеж комиссии был более 30 дней назад")

            if reasons:
                issues.append({
                    'name': student.fio,
                    'tg': student.telegram,
                    'paid': paid_so_far,
                    'total': total_expected,
                    'last_date': last_date,
                    'reasons': reasons
                })
        except:
            continue

    if issues:
        notif_list = []
        for iss in issues:
            if iss['last_date']:
                days = (today - iss['last_date']).days
                p_info = f"📅 Последний платеж: {iss['last_date'].strftime('%d.%m.%Y')} ({days} дн. назад)"
            else:
                p_info = "📅 Платежей по комиссии не найдено"

            txt = (f"👤 {iss['name']} ({iss['tg']})\n"
                   f"{p_info}\n"
                   f"💰 Выплачено {iss['paid']} из {iss['total']} руб.\n"
                   f"⚠️ " + "; ".join(iss['reasons']))
            notif_list.append(txt)

        await send_long_message(update, "❗ Уведомления по постоплате:\n\n" + "\n\n".join(notif_list))
    else:
        await update.message.reply_text("✅ Нет уведомлений по постоплате.")
    return await exit_to_main_menu(update, context)


async def check_all_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сборная солянка по всем типам уведомлений (кратко)."""
    calls = get_students_with_no_calls()
    prepayments = get_students_with_unpaid_payment()

    msgs = []
    if prepayments:
        msgs.append("❗ ЗАДОЛЖЕННОСТИ:")
        msgs.extend([f"• {s.fio}: {s.total_cost - s.payment_amount}р" for s in prepayments])
        msgs.append("")

    if calls:
        msgs.append("❗ ПРОПУЩЕННЫЕ ЗВОНКИ:")
        msgs.extend([f"• {s.fio} {s.telegram}" for s in calls])

    if not msgs:
        await update.message.reply_text("✅ Уведомлений нет!")
    else:
        await send_long_message(update, "\n".join(msgs))
    return await exit_to_main_menu(update, context)