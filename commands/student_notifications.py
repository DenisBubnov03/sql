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

            issues.append(f"👤 {s.telegram}\n💰 Стоимость обучения: {s.total_cost} Долг: {debt}р | Посл. платеж: {p_info}")

        await send_long_message(update, "❗ Список должников (Предоплата):\n\n" + "\n\n".join(issues))
    else:
        await update.message.reply_text("✅ Нет задолженностей по предоплате.")
    return await exit_to_main_menu(update, context)


async def check_postpayment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from data_base.db import session
    from data_base.models import Student, Payment
    from datetime import date, timedelta, datetime
    from sqlalchemy import or_

    # Изменяем фильтр: берем тех, кто "Устроился" ИЛИ у кого есть дата устройства
    employed = session.query(Student).filter(
        or_(
            Student.training_status == "Устроился",
            Student.employment_date.isnot(None)
        )
    ).all()

    today = date.today()
    month_ago = today - timedelta(days=30)
    issues = []

    for s in employed:
        try:
            # Пропускаем, если нет условий комиссии
            if not s.commission or s.commission.strip() == "":
                continue

            # Парсинг условий (num, perc)
            c_parts = [p.strip() for p in s.commission.split(",")]
            num = int(c_parts[0]) if c_parts[0].isdigit() else 0
            perc = int(c_parts[1].replace("%", "")) if len(c_parts) > 1 else 0

            salary = float(s.salary or 0)
            total = (salary * perc / 100) * num
            paid = float(s.commission_paid or 0)

            # Если всё выплачено — пропускаем
            if total > 0 and paid >= total:
                continue

            # Обработка даты устройства (в БД это TEXT, формат 10.12.2025)
            emp_date = s.employment_date
            if isinstance(emp_date, str):
                try:
                    # Твой формат из БД: DD.MM.YYYY
                    emp_date = datetime.strptime(emp_date.strip(), "%d.%m.%Y").date()
                except:
                    try:
                        emp_date = datetime.strptime(emp_date.strip(), "%Y-%m-%d").date()
                    except:
                        emp_date = None

            # Поиск последнего платежа
            last_p = session.query(Payment).filter(
                Payment.student_id == s.id,
                Payment.comment.ilike("%Комисс%"),
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.desc()).first()

            should_add = False

            # Условие 1: Денег 0, работает больше месяца
            if paid == 0:
                if emp_date and emp_date < month_ago:
                    should_add = True

            # Условие 2: Оплаты были, но последняя больше месяца назад
            else:
                if not last_p or last_p.payment_date < month_ago:
                    should_add = True

            if should_add:
                p_info = f"{last_p.payment_date.strftime('%d.%m.%Y')}" if last_p else "нет"
                e_info = emp_date.strftime('%d.%m.%Y') if emp_date else "не указана"
                debt = total - paid
                issues.append(f"👤 {s.telegram}\n📅 Устроился: {e_info} Должен {total}\n💸 Осталось оплатить: {debt}р | Посл. платеж: {p_info}")

        except Exception as e:
            print(f"Ошибка на студенте ID {s.id}: {e}")
            continue

    if issues:
        await send_long_message(update, "❗ Список по постоплате (Комиссии):\n\n" + "\n\n".join(issues))
    else:
        await update.message.reply_text("✅ Нет задолженностей по комиссиям.")
    return await exit_to_main_menu(update, context)
