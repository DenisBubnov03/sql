import json
import asyncio
import os
from datetime import datetime, date, timedelta
from sqlalchemy import desc, or_
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

from data_base.db import session
from data_base.models import Student, Payment

# Настройки
SPECIAL_USER_ID = 1257163820
ADMIN_CHAT_ID = 1257163820
DEBT_DAYS_THRESHOLD = 30
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
STUDENT_BOT = os.getenv("STUDENT_BOT_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "prev_debtors.json")
HISTORY_FILE = os.path.join(BASE_DIR, "notification_history.json")


def can_send_to_student(student_id, type_suffix, history):
    key = f"{student_id}_{type_suffix}"
    last_date_str = history.get(key)
    if not last_date_str: return True
    last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
    return (date.today() - last_date).days >= 4


async def check_new_debtors(bot):
    """Оригинальный функционал для админа."""
    cutoff = datetime.now().date() - timedelta(days=DEBT_DAYS_THRESHOLD)
    students = session.query(Student).filter(Student.total_cost > Student.payment_amount,
                                             Student.training_status != "Не учится").all()
    current_debtors = []
    for s in students:
        last_p = session.query(Payment.payment_date).filter(Payment.student_id == s.id,
                                                            Payment.comment != "Комиссия").order_by(
            desc(Payment.payment_date)).first()
        if not last_p or last_p[0] <= cutoff:
            current_debtors.append(s.telegram or s.fio)

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            prev_debtors = json.load(f)
    else:
        prev_debtors = []

    new = [d for d in current_debtors if d not in prev_debtors]
    resolved = [d for d in prev_debtors if d not in current_debtors]

    if new: await bot.send_message(chat_id=ADMIN_CHAT_ID, text="❗️ Новые должники:\n" + "\n".join(new))
    if resolved: await bot.send_message(chat_id=ADMIN_CHAT_ID,
                                        text="✅ Решены проблемы с должниками:\n" + "\n".join(resolved))

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(current_debtors), f, ensure_ascii=False, indent=2)


async def notify_students_logic(bot):
    """Рассылка с учетом интервала в 1 месяц от платежа и 4 дня от уведомления."""
    today = date.today()
    month_ago = today - timedelta(days=30)

    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
    else:
        history = {}

    delivered, stub = [], []

    # 1. ПРЕДОПЛАТА (Первоначальный платёж или Доплата)
    prepaid = session.query(Student).filter(Student.total_cost > Student.payment_amount,
                                            Student.training_status != "Не учится").all()
    for s in prepaid:
        # Ищем последний платеж по предоплате
        last_p = session.query(Payment).filter(
            Payment.student_id == s.id,
            Payment.status == "подтвержден",
            or_(Payment.comment.ilike("%платёж%"), Payment.comment.ilike("%доплата%"))
        ).order_by(Payment.payment_date.desc()).first()

        # УСЛОВИЕ: Прошло больше месяца с платежа И кулдаун 4 дня
        if last_p and last_p.payment_date > month_ago:
            continue  # Слишком рано напоминать, он платил меньше месяца назад

        if can_send_to_student(s.id, "pre", history):
            debt = s.total_cost - (s.payment_amount or 0)
            msg = f"Здравствуйте, {s.fio}! Напоминаем об оплате обучения. Остаток: {debt}р."
            sent = False
            if s.chat_id:
                try:
                    await bot.send_message(chat_id=s.chat_id, text=msg)
                    sent = True
                except:
                    pass

            history[f"{s.id}_pre"] = today.strftime('%Y-%m-%d')
            (delivered if sent else stub).append(f"{s.telegram} (предоплата, {debt}р)")

    # 2. ПОСТОПЛАТА (Комиссия)
    employed = session.query(Student).filter(Student.training_status == "Устроился").all()
    for s in employed:
        if s.commission:
            try:
                # Ищем последний платеж комиссии
                last_p = session.query(Payment).filter(
                    Payment.student_id == s.id,
                    Payment.comment.ilike("%комисс%"),
                    Payment.status == "подтвержден"
                ).order_by(Payment.payment_date.desc()).first()

                # УСЛОВИЕ: Прошло больше месяца с платежа
                if last_p and last_p.payment_date > month_ago:
                    continue

                if can_send_to_student(s.id, "post", history):
                    c = [i.strip() for i in s.commission.split(",")]
                    num, perc = int(c[0]), int(c[1].replace("%", ""))
                    debt = ((s.salary or 0) * perc / 100) * num - (s.commission_paid or 0)

                    if debt > 0:
                        msg = f"Здравствуйте, {s.fio}! Напоминаем о выплате комиссии. Долг: {debt}р."
                        sent = False
                        if s.chat_id:
                            try:
                                await bot.send_message(chat_id=s.chat_id, text=msg)
                                sent = True
                            except:
                                pass
                        history[f"{s.id}_post"] = today.strftime('%Y-%m-%d')
                        (delivered if sent else stub).append(f"{s.telegram} (комиссия, {debt}р)")
            except:
                continue

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

    report = []
    if delivered: report.append("📩 Доставлено ученикам:\n" + "\n".join(delivered))
    if stub: report.append("⏸ Заглушка (не в боте):\n" + "\n".join(stub))
    if report: await bot.send_message(chat_id=SPECIAL_USER_ID, text="\n\n".join(report))


async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    student_bot = Bot(token=STUDENT_BOT)
    await check_new_debtors(bot)
    await notify_students_logic(student_bot)


if __name__ == "__main__":
    asyncio.run(main())