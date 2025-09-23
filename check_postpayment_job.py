#!/usr/bin/env python3
"""
Джоба для проверки постоплаты (комиссий) студентов со статусом "Устроился".
Проверяет различные условия и отправляет уведомления о необходимости доплаты.
"""

import os
import sys
import json
import asyncio
from datetime import datetime, date, timedelta
from sqlalchemy import func
from telegram import Bot
from telegram.error import TelegramError

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_base.db import session
from data_base.models import Student, Payment
from commands.logger import custom_logger

logger = custom_logger

# Настройки Telegram бота
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')  # ID чата для отправки уведомлений
STATE_FILE = "prev_postpayment_issues.json"

# Загружаем переменные из .env файла
from dotenv import load_dotenv
load_dotenv()

# Переопределяем после загрузки .env
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

def calculate_commission(student):
    """
    Вычисляет общую комиссию и уже выплаченную сумму для студента.
    """
    try:
        if not student.commission:
            return 0, 0
            
        # Разделяем данные комиссии (количество выплат, процент)
        commission_info = student.commission.split(", ")
        payments = int(commission_info[0]) if len(commission_info) > 0 and commission_info[0].isdigit() else 0
        percentage = int(commission_info[1].replace("%", "")) if len(commission_info) > 1 else 0

        # Зарплата
        salary = student.salary or 0

        # Расчёт общей комиссии
        total_commission = (salary * percentage / 100) * payments

        # Выплаченная комиссия
        paid_commission = student.commission_paid or 0

        return total_commission, paid_commission
    except Exception as e:
        logger.error(f"Ошибка при расчёте комиссии для студента {student.id}: {e}")
        return 0, 0

def get_last_commission_payment_date(student_id):
    """
    Получает дату последнего платежа с комментарием "Комиссия" для студента.
    """
    try:
        last_payment = session.query(Payment).filter(
            Payment.student_id == student_id,
            Payment.comment.ilike("%комисси%"),
            Payment.status == "подтвержден"
        ).order_by(Payment.payment_date.desc()).first()
        
        return last_payment.payment_date if last_payment else None
    except Exception as e:
        logger.error(f"Ошибка при получении последнего платежа комиссии для студента {student_id}: {e}")
        return None

def get_employment_date(student):
    """
    Получает дату трудоустройства студента.
    """
    try:
        # Предполагаем, что дата трудоустройства хранится в поле employment_date
        # Если такого поля нет, можно использовать другое поле или логику
        if hasattr(student, 'employment_date') and student.employment_date:
            # Проверяем, что это объект date, а не строка
            if isinstance(student.employment_date, str):
                try:
                    return datetime.strptime(student.employment_date, "%Y-%m-%d").date()
                except:
                    return None
            return student.employment_date
        
        # Альтернативная логика: ищем последний платеж "Комиссия" как дату трудоустройства
        last_commission_date = get_last_commission_payment_date(student.id)
        if last_commission_date:
            return last_commission_date
            
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении даты трудоустройства для студента {student.id}: {e}")
        return None

def get_current_postpayment_issues():
    """
    Получает текущий список студентов с проблемами постоплаты.
    """
    logger.info("🔍 Начинаем проверку условий постоплаты...")
    
    # Получаем всех студентов со статусом "Устроился"
    employed_students = session.query(Student).filter(
        Student.training_status == "Устроился"
    ).all()
    
    logger.info(f"📊 Найдено студентов со статусом 'Устроился': {len(employed_students)}")
    
    issues = []
    current_date = date.today()
    one_month_ago = current_date - timedelta(days=30)
    
    for student in employed_students:
        try:
            # Получаем общую и выплаченную комиссию
            total_commission, paid_commission = calculate_commission(student)
            
            if total_commission == 0:
                continue  # Пропускаем студентов без комиссии
            
            # Проверяем, выплачена ли вся комиссия
            if paid_commission >= total_commission:
                continue  # Комиссия полностью выплачена
            
            # Получаем дату трудоустройства
            employment_date = get_employment_date(student)
            
            # Получаем дату последнего платежа комиссии
            last_commission_date = get_last_commission_payment_date(student.id)
            
            # Проверяем различные условия
            issue_reasons = []
            
            # Условие 1: Сумма оплаченной комиссии не равна сумме полной комиссии
            if paid_commission < total_commission:
                issue_reasons.append(f"Неполная выплата комиссии: {paid_commission}/{total_commission} руб.")
            
            # Условие 2: Нет платежей "Комиссия" + устроился больше месяца назад
            if (not last_commission_date and employment_date and 
                employment_date < one_month_ago):
                issue_reasons.append("Нет платежей 'Комиссия' + устроился больше месяца назад")
            
            # Условие 3: Последний платеж "Комиссия" был больше месяца назад и не все выплатил
            if (last_commission_date and last_commission_date < one_month_ago and 
                paid_commission < total_commission):
                issue_reasons.append("Последний платеж 'Комиссия' больше месяца назад + неполная выплата")
            
            # Если есть проблемы, добавляем в список
            if issue_reasons:
                issues.append({
                    'student_id': student.id,
                    'student_name': student.fio,
                    'student_telegram': student.telegram,
                    'total_commission': total_commission,
                    'paid_commission': paid_commission,
                    'employment_date': str(employment_date) if employment_date else None,
                    'last_commission_date': str(last_commission_date) if last_commission_date else None,
                    'reasons': issue_reasons
                })
                
        except Exception as e:
            logger.error(f"Ошибка при проверке студента {student.id}: {e}")
            continue
    
    logger.info(f"📊 Найдено студентов с проблемами постоплаты: {len(issues)}")
    return issues

def load_previous_issues():
    """Загружает предыдущий список проблем из файла."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_current_issues(issues):
    """Сохраняет текущий список проблем в файл."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(issues, f, ensure_ascii=False, indent=2)

async def notify_new_issues(new_issues):
    """Уведомляет о новых проблемах с постоплатой."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("⚠️ Не настроены параметры Telegram бота")
        logger.info("📋 Новые проблемы с постоплатой:")
        for issue in new_issues:
            logger.info(f"  • {issue['student_name']} ({issue['student_telegram']})")
            logger.info(f"    💰 Комиссия: {issue['paid_commission']}/{issue['total_commission']} руб.")
            if issue['last_commission_date']:
                logger.info(f"    💳 Последний платеж комиссии: {issue['last_commission_date']}")
            else:
                logger.info(f"    💳 Платежей комиссии: НЕТ")
            for reason in issue['reasons']:
                logger.info(f"    ⚠️ {reason}")
        return
    
    if not new_issues:
        return
    
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        message = "🚨 Новые проблемы с постоплатой:\n\n"
        
        for i, issue in enumerate(new_issues, 1):
            message += f"{i}. {issue['student_name']} (@{issue['student_telegram']})\n"
            message += f"   💰 Комиссия: {issue['paid_commission']}/{issue['total_commission']} руб.\n"
            
            if issue['employment_date']:
                message += f"   📅 Устроился: {issue['employment_date']}\n"
            
            if issue['last_commission_date']:
                message += f"   💳 Последний платеж комиссии: {issue['last_commission_date']}\n"
            else:
                message += f"   💳 Платежей комиссии: НЕТ\n"
            
            message += f"   ⚠️ Проблемы:\n"
            for reason in issue['reasons']:
                message += f"      • {reason}\n"
            
            message += "\n"
        
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        logger.info(f"📤 Отправлено уведомление о {len(new_issues)} новых проблемах")
        
    except TelegramError as e:
        logger.error(f"❌ Ошибка при отправке уведомления в Telegram: {e}")
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при отправке уведомления: {e}")

async def notify_cron_job_completed():
    """Отправляет уведомление о выполнении cron job."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        return
        
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        message = "✅ Cron job выполнена: проверка постоплаты"
        await bot.send_message(chat_id=1257163820, text=message)
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления о завершении: {e}")

async def check_new_issues():
    """
    Проверяет новые проблемы с постоплатой и уведомляет об изменениях.
    """
    current_issues = get_current_postpayment_issues()
    previous_issues = load_previous_issues()
    
    # Создаем словари для сравнения по student_id
    current_dict = {issue['student_id']: issue for issue in current_issues}
    previous_dict = {issue['student_id']: issue for issue in previous_issues}
    
    # Находим новые проблемы
    new_issues = []
    for student_id, issue in current_dict.items():
        if student_id not in previous_dict:
            new_issues.append(issue)
    
    # Уведомляем о новых проблемах
    if new_issues:
        await notify_new_issues(new_issues)
    
    # Сохраняем текущее состояние, если есть изменения
    if sorted(current_issues, key=lambda x: x['student_id']) != sorted(previous_issues, key=lambda x: x['student_id']):
        save_current_issues(current_issues)
        logger.info(f"📊 Состояние обновлено: {len(current_issues)} проблем")
    
    # Отправляем уведомление о завершении
    await notify_cron_job_completed()

async def main():
    """
    Основная функция джобы.
    """
    try:
        logger.info("🚀 Запуск джобы проверки постоплаты...")
        
        # Проверяем новые проблемы
        await check_new_issues()
        
        logger.info("✅ Джоба проверки постоплаты завершена успешно")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в джобе проверки постоплаты: {e}")
        raise
    finally:
        # Закрываем сессию
        try:
            session.close()
        except Exception as e:
            logger.error(f"❌ Ошибка при закрытии сессии: {e}")

if __name__ == "__main__":
    asyncio.run(main())
