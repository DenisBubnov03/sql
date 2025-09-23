import json
import asyncio
import os
from datetime import datetime, timedelta
from sqlalchemy import desc
from telegram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from data_base.db import session
from data_base.models import Student, Payment

# ADMIN_CHAT_ID = 325531224
ADMIN_CHAT_ID = 1257163820
DEBT_DAYS_THRESHOLD = 30
STATE_FILE = "prev_debtors.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


def get_current_debtors():
    """Возвращает список Telegram-должников, у которых последний платёж был более 30 дней назад."""
    cutoff_date = datetime.now().date() - timedelta(days=DEBT_DAYS_THRESHOLD)
    debtors = []

    students = session.query(Student).filter(
        Student.total_cost > Student.payment_amount,
        Student.training_status != "не учится"
    ).all()

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
    if not TELEGRAM_TOKEN or not ADMIN_CHAT_ID:
        print("⚠️ Не настроены параметры Telegram бота")
        return
        
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = "❗️ Новые должники:\n" + "\n".join(new_debtors)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        print(f"📤 Отправлено уведомление о {len(new_debtors)} новых должниках")
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления: {e}")

async def notify_resolved_debtors(resolved_debtors):
    """Уведомляет о решенных проблемах с должниками."""
    if not resolved_debtors:
        return
    
    if not TELEGRAM_TOKEN or not ADMIN_CHAT_ID:
        print("⚠️ Не настроены параметры Telegram бота")
        return
        
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = "✅ Решены проблемы с должниками:\n" + "\n".join(resolved_debtors)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        print(f"📤 Отправлено уведомление о {len(resolved_debtors)} решенных проблемах")
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления о решенных проблемах: {e}")

async def notify_cron_job_completed():
    """Отправляет уведомление о выполнении cron job."""
    if not TELEGRAM_TOKEN:
        return
        
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = "✅ Cron job выполнена: проверка должников"
        await bot.send_message(chat_id=1257163820, text=message)
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомления о завершении: {e}")


async def check_new_debtors():
    current_debtors = get_current_debtors()
    previous_debtors = load_previous_debtors()

    # Находим новых должников
    new_debtors = [d for d in current_debtors if d not in previous_debtors]
    
    # Находим решенные проблемы (были в списке, но больше нет)
    resolved_debtors = [d for d in previous_debtors if d not in current_debtors]

    # Уведомляем о новых должниках
    if new_debtors:
        await notify_new_debtors(new_debtors)
    
    # Уведомляем о решенных проблемах
    if resolved_debtors:
        await notify_resolved_debtors(resolved_debtors)

    # Сохраняем состояние, если есть изменения
    if sorted(current_debtors) != sorted(previous_debtors):
        save_current_debtors(current_debtors)
        print(f"📊 Состояние обновлено: {len(current_debtors)} должников")
        if resolved_debtors:
            print(f"✅ Решено проблем: {len(resolved_debtors)}")
    
    # Отправляем уведомление о выполнении cron job
    await notify_cron_job_completed()


if __name__ == "__main__":
    asyncio.run(check_new_debtors())
