# commands/student_notifications.py

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from commands.authorized_users import AUTHORIZED_USERS
from student_management.student_management import get_all_students


def calculate_due_payments(students):
    """
    Вычисляет задолженности студентов по оплатам.

    Args:
        students (list): Список студентов.

    Returns:
        list: Список уведомлений по оплатам.
    """
    payment_notifications = []
    for student in students:
        if student.get("Полностью оплачено") == "Нет":
            try:
                due_amount = int(student.get("Стоимость обучения", 0)) - int(student.get("Сумма оплаты", 0))
                payment_notifications.append(
                    f"Студент {student['ФИО']} {student['Telegram']} должен {due_amount} рублей."
                )
            except (ValueError, TypeError):
                payment_notifications.append(
                    f"Ошибка в данных студента {student['ФИО']} {student['Telegram']} при расчёте задолженности."
                )
    return payment_notifications


def calculate_call_notifications(students):
    """
    Вычисляет студентов, которым необходимо позвонить.

    Args:
        students (list): Список студентов.

    Returns:
        list: Список уведомлений по звонкам.
    """
    call_notifications = []
    for student in students:
        if student.get("Статус обучения") == "Учится":
            last_call_date = student.get("Дата последнего звонка")
            if not last_call_date:
                call_notifications.append(
                    f"Студент {student['ФИО']} {student['Telegram']} не звонил."
                )
            else:
                try:
                    last_call = datetime.strptime(last_call_date, "%d.%m.%Y")
                    days_since_last_call = (datetime.now() - last_call).days
                    if days_since_last_call > 20:
                        call_notifications.append(
                            f"Студент {student['ФИО']} {student['Telegram']} не звонил {days_since_last_call} дней. Пора позвонить!"
                        )
                except ValueError:
                    call_notifications.append(
                        f"Некорректная дата звонка у студента {student['ФИО']} {student['Telegram']}: {last_call_date}."
                    )
    return call_notifications


async def check_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    """
    Проверяет уведомления для студентов и отправляет их пользователю.

    Args:
        update (Update): Объект Telegram Update.
        context (ContextTypes.DEFAULT_TYPE): Контекст команды.

    Returns:
        None
    """
    students = get_all_students()

    payment_notifications = calculate_due_payments(students)
    call_notifications = calculate_call_notifications(students)

    messages = []

    if payment_notifications:
        messages.append("❗ Уведомления по оплатам:")
        messages.extend(payment_notifications)

    if call_notifications:
        messages.append("❗ Уведомления по звонкам:")
        messages.extend(call_notifications)

    if not messages:
        await update.message.reply_text("✅ Все в порядке, уведомлений нет!")
    else:
        await update.message.reply_text("\n".join(messages))
