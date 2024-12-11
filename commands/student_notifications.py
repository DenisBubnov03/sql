# commands/student_notifications.py

from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.authorized_users import AUTHORIZED_USERS
from commands.start_commands import exit_to_main_menu
from commands.states import NOTIFICATION_MENU
from student_management.student_management import get_all_students


def calculate_due_payments(students):
    """
    Вычисляет задолженности студентов по оплатам.
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


async def show_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Вызвана функция show_notifications_menu")
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
    print("Вызвана функция check_call_notifications")  # Для отладки
    students = get_all_students()
    call_notifications = calculate_call_notifications(students)

    if call_notifications:
        await update.message.reply_text("❗ Уведомления по звонкам:\n" + "\n".join(call_notifications))
    else:
        await update.message.reply_text("✅ Нет уведомлений по звонкам.")
    return await exit_to_main_menu(update, context)



async def check_payment_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Вызвана функция check_payment_notifications")  # Для отладки
    students = get_all_students()
    payment_notifications = calculate_due_payments(students)

    if payment_notifications:
        await update.message.reply_text("❗ Уведомления по оплате:\n" + "\n".join(payment_notifications))
    else:
        await update.message.reply_text("✅ Нет уведомлений по оплате.")
    return await exit_to_main_menu(update, context)



async def check_all_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Проверяет все уведомления.
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
    return await exit_to_main_menu(update, context)
