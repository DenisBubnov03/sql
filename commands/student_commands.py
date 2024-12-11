# commands/student_commands.py

from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from commands.logger import log_student_change
from commands.start_commands import exit_to_main_menu
from commands.states import FIELD_TO_EDIT, WAIT_FOR_NEW_VALUE, FIO_OR_TELEGRAM
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
    """
    Обрабатывает выбор поля для редактирования.
    """
    field_to_edit = update.message.text.strip()
    student = context.user_data.get("student")

    valid_fields = ["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты", "Статус обучения", "Получил работу"]

    if field_to_edit == "Назад":
        await update.message.reply_text(
            "Возврат к выбору студента. Введите ФИО или Telegram:",
            reply_markup=ReplyKeyboardMarkup([["Назад"]], one_time_keyboard=True)
        )
        return FIO_OR_TELEGRAM

    if field_to_edit in valid_fields:
        context.user_data["field_to_edit"] = field_to_edit

        if field_to_edit == "Дата последнего звонка":
            # Добавляем кнопку "Сегодня" для установки текущей даты
            await update.message.reply_text(
                "Введите дату последнего звонка в формате ДД.ММ.ГГГГ или нажмите 'Сегодня':",
                reply_markup=ReplyKeyboardMarkup(
                    [["Сегодня"], ["Назад"]],
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
            [["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты", "Статус обучения", "Получил работу"],
             ["Назад"]],
            one_time_keyboard=True
        )
    )
    return FIELD_TO_EDIT



# Обработка нового значения
async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает новое значение, введенное пользователем.
    """
    student = context.user_data.get("student")
    field_to_edit = context.user_data.get("field_to_edit")
    new_value = update.message.text.strip()
    editor_tg = update.message.from_user.username  # Telegram пользователя для логирования

    if not student or not field_to_edit:
        await update.message.reply_text("Ошибка: данные для редактирования отсутствуют. Начните сначала.")
        return ConversationHandler.END

    old_value = student.get(field_to_edit)

    if field_to_edit == "Дата последнего звонка":
        if new_value == "Сегодня":
            new_value = datetime.now().strftime("%d.%m.%Y")
        try:
            datetime.strptime(new_value, "%d.%m.%Y")
            update_student_data(student["ФИО"], field_to_edit, new_value)
            log_student_change(editor_tg, student["ФИО"], {field_to_edit: (old_value, new_value)})
            await update.message.reply_text(f"Дата последнего звонка успешно обновлена: {new_value}.")
            # Возвращаем пользователя в главное меню
            return await exit_to_main_menu(update, context)
        except ValueError:
            await update.message.reply_text("Неверный формат даты. Попробуйте снова.")
            return WAIT_FOR_NEW_VALUE

    # Обновляем другие поля
    update_student_data(student["ФИО"], field_to_edit, new_value)
    log_student_change(editor_tg, student["ФИО"], {field_to_edit: (old_value, new_value)})
    await update.message.reply_text(f"Поле '{field_to_edit}' успешно обновлено на '{new_value}'.")
    # Возвращаем пользователя в главное меню
    return await exit_to_main_menu(update, context)
