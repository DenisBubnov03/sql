import json
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import desc
from telegram import Bot


from data_base.db import session
from data_base.models import Student, Payment

ADMIN_CHAT_ID = 1257163820
DEBT_DAYS_THRESHOLD = 30
STATE_FILE = "prev_debtors.json"


def get_current_debtors():
    """Возвращает список Telegram-должников, у которых последний платёж был более 30 дней назад."""
    cutoff_date = datetime.now().date() - timedelta(days=DEBT_DAYS_THRESHOLD)
    debtors = []

    students = session.query(Student).filter(Student.total_cost > Student.payment_amount).all()

    for student in students:
        last_payment = session.query(Payment.payment_date).filter(
            Payment.student_id == student.id,
            Payment.comment != "Комиссия"
        ).order_by(desc(Payment.payment_date)).first()

        if not last_payment or last_payment[0] <= cutoff_date:
            debtors.append(student.telegram)

    return sorted(debtors)


def load_previous_debtors():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_current_debtors(debtors):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(debtors), f, ensure_ascii=False, indent=2)


async def notify_new_debtors(new_debtors):
    bot = Bot(token="7581276969:AAFcFbSt5F2XpVq3yCKDjhLP7tv1cs8TK8Q")
    message = "❗️ Новые должники:\n" + "\n".join(new_debtors)
    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)


async def check_new_debtors():
    current_debtors = get_current_debtors()
    previous_debtors = load_previous_debtors()

    new_debtors = [d for d in current_debtors if d not in previous_debtors]

    if new_debtors:
        await notify_new_debtors(new_debtors)

    if sorted(current_debtors) != sorted(previous_debtors):
        save_current_debtors(current_debtors)


if __name__ == "__main__":
    asyncio.run(check_new_debtors())
