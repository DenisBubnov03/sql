# commands/student_info_commands.py
from commands.authorized_users import AUTHORIZED_USERS
from commands.states import FIO_OR_TELEGRAM

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from student_management.student_management import get_all_students


async def search_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    """
    Запрашивает ввод для поиска студента по ФИО или Telegram.
    """
    await update.message.reply_text(
        "Введите ФИО или Telegram ученика, информацию о котором хотите посмотреть:"
    )
    return FIO_OR_TELEGRAM


def calculate_commission(student):
    """
    Вычисляет общую комиссию и уже выплаченную сумму для студента.
    """
    commission_info = student.get("Комиссия", "0, 0%").split(", ")
    payments = int(commission_info[0]) if len(commission_info) > 0 and commission_info[0].isdigit() else 0
    percentage = int(commission_info[1].replace("%", "")) if len(commission_info) > 1 else 0

    salary_raw = student.get("Зарплата", 0)
    salary = int(salary_raw) if isinstance(salary_raw, int) else int(salary_raw.strip()) if isinstance(salary_raw, str) else 0

    paid_commission_raw = student.get("Комиссия выплачено", 0)
    paid_commission = int(paid_commission_raw) if isinstance(paid_commission_raw, int) else int(
        paid_commission_raw.strip()) if isinstance(paid_commission_raw, str) else 0

    total_commission = (salary * percentage // 100) * payments

    return total_commission, paid_commission


async def display_student_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ищет информацию о студенте и выводит её.
    """
    search_query = update.message.text.lower()
    students = get_all_students()

    matching_students = [
        student for student in students
        if search_query in student["ФИО"].lower() or search_query in student["Telegram"].lower()
    ]

    if not matching_students:
        await update.message.reply_text("Ученик не найден. Попробуйте ещё раз.")
        return FIO_OR_TELEGRAM

    if len(matching_students) > 1:
        response = "Найдено несколько учеников. Уточните запрос:\n"
        for student in matching_students:
            response += f"{student['ФИО']} - {student['Telegram']}\n"
        await update.message.reply_text(response)
        return FIO_OR_TELEGRAM

    student = matching_students[0]
    context.user_data["student"] = student

    total_commission, paid_commission = calculate_commission(student)
    commission_info = f"{paid_commission} из {total_commission}"

    info = "\n".join([
        f"{key}: {value}" if key != "Комиссия выплачено" else f"Комиссия выплачено: {commission_info}"
        for key, value in student.items()
    ])

    await update.message.reply_text(
        f"Информация об ученике:\n\n{info}",
        reply_markup=ReplyKeyboardMarkup(
            [
                ['Добавить студента', 'Просмотреть студентов'],
                ['Редактировать данные студента', 'Проверить уведомления'],
                ['Поиск ученика', 'Статистика']
            ],
            one_time_keyboard=True
        )
    )
    return ConversationHandler.END
