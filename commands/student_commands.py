# commands/student_commands.py

from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from commands.authorized_users import AUTHORIZED_USERS
from commands.logger import log_student_change
from commands.start_commands import exit_to_main_menu
from commands.states import FIELD_TO_EDIT, WAIT_FOR_NEW_VALUE, FIO_OR_TELEGRAM
from commands.student_info_commands import calculate_commission
from student_management.student_management import get_all_students, update_student_data


async def view_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает список студентов.
    """
    students = get_all_students()
    if not students:
        await update.message.reply_text("Список студентов пуст. Добавьте студентов через меню.")
        return

    response = "Список студентов:\n"
    for i, student in enumerate(students, start=1):
        response += f"{i}. {student['ФИО']} - {student['Telegram']} ({student['Тип обучения']})\n"
    await update.message.reply_text(response)

# Функция редактирования студента
async def edit_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало процесса редактирования студента.
    """
    await update.message.reply_text(
        "Введите ФИО или Telegram студента, данные которого вы хотите отредактировать:",
        reply_markup=ReplyKeyboardMarkup([["Главное меню"]], one_time_keyboard=True)
    )
    return FIO_OR_TELEGRAM


# Редактирование поля студента
async def edit_student_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return

    field_to_edit = update.message.text.strip()
    student = context.user_data.get("student")

    valid_fields = ["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты",
                    "Статус обучения", "Получил работу", "Комиссия выплачено"]

    if field_to_edit == "Назад":
        await update.message.reply_text(
            "Возврат к выбору студента. Введите ФИО или Telegram:",
            reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
        )
        return FIO_OR_TELEGRAM

    if field_to_edit in valid_fields:
        context.user_data["field_to_edit"] = field_to_edit

        if field_to_edit == "Дата последнего звонка":
            await update.message.reply_text(
                "Введите дату последнего звонка в формате ДД.ММ.ГГГГ или нажмите 'Сегодня':",
                reply_markup=ReplyKeyboardMarkup(
                    [["Сегодня"], ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return WAIT_FOR_NEW_VALUE

        if field_to_edit == "Статус обучения":
            await update.message.reply_text(
                "Выберите новый статус обучения:",
                reply_markup=ReplyKeyboardMarkup(
                    [["Не учится", "Учится", "Устроился"], ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return WAIT_FOR_NEW_VALUE

        await update.message.reply_text(
            f"Введите новое значение для '{field_to_edit}':",
            reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
        )
        return WAIT_FOR_NEW_VALUE

    await update.message.reply_text(
        "Некорректное поле. Выберите одно из предложенных:",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты",
                 "Статус обучения", "Получил работу", "Комиссия выплачено"],
                ["Назад"]
            ],
            one_time_keyboard=True
        )
    )
    return FIELD_TO_EDIT



async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student = context.user_data.get("student")
    field_to_edit = context.user_data.get("field_to_edit")
    new_value = update.message.text.strip()
    editor_tg = update.message.from_user.username

    if not student or not field_to_edit:
        await update.message.reply_text("Ошибка: данные для редактирования отсутствуют. Начните сначала.")
        return ConversationHandler.END

    old_value = student.get(field_to_edit)

    if field_to_edit == "Статус обучения":
        valid_statuses = ["Не учится", "Учится", "Устроился"]
        if new_value not in valid_statuses:
            await update.message.reply_text(
                "Некорректный статус. Выберите из предложенных: 'Не учится', 'Учится', 'Устроился'.",
                reply_markup=ReplyKeyboardMarkup(
                    [["Не учится", "Учится", "Устроился"], ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return WAIT_FOR_NEW_VALUE

        update_student_data(student["ФИО"], field_to_edit, new_value)
        log_student_change(editor_tg, student["ФИО"], {field_to_edit: (old_value, new_value)})
        await update.message.reply_text(
            f"Статус обучения успешно обновлён: {old_value} ➡ {new_value}."
        )
        return await exit_to_main_menu(update, context)

    elif field_to_edit == "Дата последнего звонка":
        if new_value.lower() == "сегодня":
            new_value = datetime.now().strftime("%d.%m.%Y")
        try:
            datetime.strptime(new_value, "%d.%m.%Y")
            update_student_data(student["ФИО"], field_to_edit, new_value)
            log_student_change(editor_tg, student["ФИО"], {field_to_edit: (old_value, new_value)})
            await update.message.reply_text(
                f"Дата последнего звонка успешно обновлена на '{new_value}'."
            )
        except ValueError:
            await update.message.reply_text("Некорректная дата. Введите в формате ДД.ММ.ГГГГ или нажмите 'Сегодня'.")
            return WAIT_FOR_NEW_VALUE

    elif field_to_edit == "Сумма оплаты":
        try:
            additional_payment = int(new_value)
            if additional_payment < 0:
                raise ValueError("Сумма не может быть отрицательной.")
            existing_payment = int(student.get("Сумма оплаты", 0))
            total_cost = int(student.get("Стоимость обучения", 0))
            updated_payment = existing_payment + additional_payment
            if updated_payment > total_cost:
                await update.message.reply_text(
                    f"Ошибка: общая сумма оплаты ({updated_payment}) превышает стоимость обучения ({total_cost})."
                )
                return WAIT_FOR_NEW_VALUE
            update_student_data(student["ФИО"], field_to_edit, updated_payment)
            log_student_change(editor_tg, student["ФИО"], {field_to_edit: (existing_payment, updated_payment)})
            await update.message.reply_text(
                f"Сумма оплаты успешно обновлена: {existing_payment} ➡ {updated_payment}."
            )
        except ValueError:
            await update.message.reply_text("Некорректная сумма. Введите числовое значение.")
            return WAIT_FOR_NEW_VALUE

    elif field_to_edit == "Комиссия выплачено":
        try:
            additional_commission = int(new_value)
            if additional_commission < 0:
                raise ValueError("Сумма не может быть отрицательной.")
            total_commission, paid_commission = calculate_commission(student)
            updated_commission = paid_commission + additional_commission
            if updated_commission > total_commission:
                await update.message.reply_text(
                    f"Ошибка: общая сумма комиссии ({updated_commission}) превышает расчётную ({total_commission})."
                )
                return WAIT_FOR_NEW_VALUE
            update_student_data(student["ФИО"], field_to_edit, updated_commission)
            log_student_change(editor_tg, student["ФИО"], {field_to_edit: (paid_commission, updated_commission)})
            await update.message.reply_text(
                f"Сумма комиссии успешно обновлена: {paid_commission} ➡ {updated_commission}."
            )
        except ValueError:
            await update.message.reply_text("Некорректная сумма. Введите числовое значение.")
            return WAIT_FOR_NEW_VALUE

    else:
        update_student_data(student["ФИО"], field_to_edit, new_value)
        log_student_change(editor_tg, student["ФИО"], {field_to_edit: (old_value, new_value)})
        await update.message.reply_text(f"Поле '{field_to_edit}' успешно обновлено на '{new_value}'.")

    return await exit_to_main_menu(update, context)





