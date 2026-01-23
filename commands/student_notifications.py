from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.start_commands import exit_to_main_menu
from commands.states import NOTIFICATION_MENU, PAYMENT_NOTIFICATION_MENU
from data_base.operations import get_all_students, get_students_with_no_calls, get_students_with_unpaid_payment
from utils.security import restrict_to


@restrict_to(['admin', 'mentor']) # Разрешаем доступ обеим ролям
async def show_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает меню для выбора уведомлений.
    """

    await update.message.reply_text(
        "Выберите тип уведомлений:",
        reply_markup=ReplyKeyboardMarkup(
            [["По звонкам"], ["По оплате"], ["Все"], ["🔙 Главное меню"]],
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
    Показывает подменю для выбора типа уведомлений по оплате.
    """
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
    students = get_students_with_unpaid_payment()

    if students:
        notifications = [
            f"Студент {student.fio} {student.telegram} задолжал {student.total_cost - student.payment_amount} рублей."
            for student in students
        ]
        
        # Разбиваем длинное сообщение на части
        full_message = "❗ Уведомления по предоплате:\n" + "\n".join(notifications)
        
        if len(full_message) > 4000:
            # Разбиваем на части
            parts = []
            current_part = "❗ Уведомления по предоплате:\n"
            
            for notification in notifications:
                if len(current_part + notification + "\n") > 4000:
                    parts.append(current_part.strip())
                    current_part = notification + "\n"
                else:
                    current_part += notification + "\n"
            
            if current_part.strip():
                parts.append(current_part.strip())
            
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(full_message)
    else:
        await update.message.reply_text("✅ Нет уведомлений по предоплате.")
    return await exit_to_main_menu(update, context)


async def check_postpayment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет уведомления по постоплате (комиссии).
    """
    from data_base.db import session
    from data_base.models import Student, Payment
    from datetime import date, timedelta
    
    # Получаем студентов со статусом "Устроился"
    employed_students = session.query(Student).filter(
        Student.training_status == "Устроился"
    ).all()
    
    issues = []
    current_date = date.today()
    one_month_ago = current_date - timedelta(days=30)
    
    for student in employed_students:
        try:
            # Получаем общую и выплаченную комиссию
            if not student.commission:
                continue
                
            commission_info = student.commission.split(", ")
            payments = int(commission_info[0]) if len(commission_info) > 0 and commission_info[0].isdigit() else 0
            percentage = int(commission_info[1].replace("%", "")) if len(commission_info) > 1 else 0
            salary = student.salary or 0
            total_commission = (salary * percentage / 100) * payments
            paid_commission = student.commission_paid or 0
            
            if total_commission == 0 or paid_commission >= total_commission:
                continue
                
            # Получаем дату последнего платежа комиссии
            last_commission = session.query(Payment).filter(
                Payment.student_id == student.id,
                Payment.comment.ilike("%комисси%"),
                Payment.status == "подтвержден"
            ).order_by(Payment.payment_date.desc()).first()
            
            last_commission_date = last_commission.payment_date if last_commission else None
            
            # Проверяем условия
            issue_reasons = []
            
            if paid_commission < total_commission:
                issue_reasons.append(f"Неполная выплата: {paid_commission}/{total_commission} руб.")
            
            # Обрабатываем employment_date как строку
            employment_date = None
            if student.employment_date:
                try:
                    if isinstance(student.employment_date, str):
                        from datetime import datetime
                        employment_date = datetime.strptime(student.employment_date, "%d.%m.%Y").date()
                    else:
                        employment_date = student.employment_date
                except:
                    employment_date = None
            
            if (not last_commission_date and employment_date and 
                employment_date < one_month_ago):
                issue_reasons.append("Нет платежей комиссии + устроился > месяца назад")
            
            if (last_commission_date and last_commission_date < one_month_ago and 
                paid_commission < total_commission):
                issue_reasons.append("Последний платеж комиссии > месяца назад")
            
            if issue_reasons:
                issues.append({
                    'student_id': student.id,
                    'student_name': student.fio,
                    'student_telegram': student.telegram,
                    'total_commission': total_commission,
                    'paid_commission': paid_commission,
                    'employment_date': student.employment_date,
                    'last_commission_date': last_commission_date,
                    'reasons': issue_reasons
                })
                
        except Exception as e:
            continue
    
    if issues:
        notifications = []
        for issue in issues:
            # Определяем статус платежей более точно
            if issue['last_commission_date']:
                last_payment = f" (последний платеж: {issue['last_commission_date']})"
            elif issue['paid_commission'] and issue['paid_commission'] > 0:
                last_payment = " (есть выплаты, но нет платежей комиссии)"
            else:
                last_payment = " (нет платежей)"
            
            notifications.append(
                f"Студент {issue['student_name']} {issue['student_telegram']}{last_payment}:\n" +
                "\n".join([f"  • {reason}" for reason in issue['reasons']])
            )
        
        # Разбиваем длинное сообщение на части
        full_message = "❗ Уведомления по постоплате:\n\n" + "\n\n".join(notifications)
        
        if len(full_message) > 4000:
            # Разбиваем на части
            parts = []
            current_part = "❗ Уведомления по постоплате:\n\n"
            
            for notification in notifications:
                if len(current_part + notification + "\n\n") > 4000:
                    parts.append(current_part.strip())
                    current_part = notification + "\n\n"
                else:
                    current_part += notification + "\n\n"
            
            if current_part.strip():
                parts.append(current_part.strip())
            
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(full_message)
    else:
        await update.message.reply_text("✅ Нет уведомлений по постоплате.")
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
        full_message = "\n".join(messages)
        
        if len(full_message) > 4000:
            # Разбиваем на части
            parts = []
            current_part = ""
            
            for message in messages:
                if len(current_part + message + "\n") > 4000:
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = message + "\n"
                else:
                    current_part += message + "\n"
            
            if current_part.strip():
                parts.append(current_part.strip())
            
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(full_message)
    return await exit_to_main_menu(update, context)
