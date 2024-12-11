# commands/student_employment_commands.py

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes
from commands.start_commands import exit_to_main_menu

from commands.states import COMPANY_NAME, SALARY, COMMISSION, CONFIRMATION
from student_management.student_management import update_student_data


async def edit_student_employment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает процесс добавления или редактирования занятости студента.
    """
    student = context.user_data.get("student")
    if not student:
        await update.message.reply_text("Ошибка: студент не выбран. Попробуйте снова.")
        return ConversationHandler.END

    # Если студент уже имеет данные о работе
    if student.get("Компания"):
        await update.message.reply_text(
            f"Студент уже устроился в {student['Компания']}. Хотите изменить данные?",
            reply_markup=ReplyKeyboardMarkup([["Да, изменить данные", "Отмена"]], one_time_keyboard=True)
        )
        return CONFIRMATION

    # Если данных о работе нет, начинаем ввод
    await update.message.reply_text("Введите название компании, куда устроился студент:")
    return COMPANY_NAME


async def handle_employment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает подтверждение редактирования занятости.
    """
    user_choice = update.message.text.strip()

    if user_choice == "Да, изменить данные":
        await update.message.reply_text("Введите новое название компании:")
        return COMPANY_NAME

    if user_choice == "Отмена":
        await update.message.reply_text(
            "Редактирование данных отменено.",
            reply_markup=ReplyKeyboardMarkup([["Редактировать данные студента"]], one_time_keyboard=True)
        )
        return ConversationHandler.END

    await update.message.reply_text("Пожалуйста, выберите один из вариантов: 'Да, изменить данные' или 'Отмена'.")
    return CONFIRMATION


async def handle_company_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод названия компании.
    """
    company_name = update.message.text.strip()
    if not company_name:
        await update.message.reply_text("Название компании не может быть пустым. Попробуйте снова.")
        return COMPANY_NAME

    context.user_data["company_name"] = company_name
    await update.message.reply_text("Введите зарплату студента (в числовом формате, например: 120000):")
    return SALARY


async def handle_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод зарплаты студента.
    """
    salary_text = update.message.text.strip()
    if not salary_text.isdigit():
        await update.message.reply_text("Зарплата должна быть числом. Попробуйте снова.")
        return SALARY

    context.user_data["salary"] = int(salary_text)
    await update.message.reply_text("Введите данные комиссии в формате: количество выплат, процент (например, 2, 50%):")
    return COMMISSION


async def handle_commission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ввод данных о комиссии.
    """
    commission_text = update.message.text.strip()
    try:
        payments, percentage = map(str.strip, commission_text.split(","))
        if not payments.isdigit() or not percentage.endswith("%") or not percentage[:-1].isdigit():
            raise ValueError("Некорректный формат комиссии.")

        context.user_data["commission"] = f"{payments}, {percentage}"
        student = context.user_data.get("student")

        # Обновляем данные студента
        update_student_data(student["ФИО"], "Компания", context.user_data["company_name"])
        update_student_data(student["ФИО"], "Зарплата", context.user_data["salary"])
        update_student_data(student["ФИО"], "Комиссия", context.user_data["commission"])

        await update.message.reply_text("Данные успешно обновлены! Возвращаемся в главное меню...")
        return await exit_to_main_menu(update, context)

    except ValueError:
        await update.message.reply_text(
            "Некорректный формат комиссии. Введите данные в формате: количество выплат, процент (например, 2, 50%)."
        )
        return COMMISSION
