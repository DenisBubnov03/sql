from commands.start_commands import exit_to_main_menu
from commands.states import FIO_OR_TELEGRAM, SELECT_STUDENT, FIELD_TO_EDIT
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from data_base.operations import get_all_students, get_student_by_fio_or_telegram
from utils.security import get_user_role


def get_edit_menu_keyboard(role: str):
    """Генерирует кнопки редактирования студента в зависимости от роли."""
    if role == "mentor":
        keyboard = [
            [KeyboardButton("ФИО")],
            [KeyboardButton("Telegram")],
            [KeyboardButton("Статус обучения")],
            [KeyboardButton("Получил работу")],
            [KeyboardButton("Возврат")],
            [KeyboardButton("Куратор")],
            [KeyboardButton("Назад")]
        ]
    else:  # admin
        keyboard = [
            [KeyboardButton("ФИО")],
            [KeyboardButton("Telegram")],
            [KeyboardButton("Сумма оплаты")],
            [KeyboardButton("Статус обучения")],
            [KeyboardButton("Получил работу")],
            [KeyboardButton("Комиссия выплачено")],
            [KeyboardButton("Возврат")],
            [KeyboardButton("Куратор")],
            [KeyboardButton("Удалить ученика")],
            [KeyboardButton("Назад")]
        ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# Поиск студента
async def find_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text.strip()

    if search_query == "Главное меню":
        return await exit_to_main_menu(update, context)

    students = get_all_students()

    matching_students = [
        student for student in students
        if search_query.lower() in student.fio.lower() or search_query.lower() in student.telegram.lower()
    ]

    if not matching_students:
        await update.message.reply_text(
            "Студент не найден. Попробуйте снова ввести ФИО или Telegram:",
            reply_markup=ReplyKeyboardMarkup([["Главное меню"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return FIO_OR_TELEGRAM

    if len(matching_students) > 1:
        response = "Найдено несколько студентов. Укажите номер:\n"
        for i, student in enumerate(matching_students, start=1):
            response += f"{i}. {student.fio} - {student.telegram}\n"

        context.user_data["matching_students"] = matching_students
        await update.message.reply_text(
            response,
            reply_markup=ReplyKeyboardMarkup(
                [[str(i)] for i in range(1, len(matching_students) + 1)] + [["Назад"]],
                one_time_keyboard=True, resize_keyboard=True
            )
        )
        return SELECT_STUDENT

    # Если найден один студент
    student = matching_students[0]
    context.user_data["student"] = student

    # ОПРЕДЕЛЯЕМ РОЛЬ И ДАЕМ МЕНЮ
    role = await get_user_role(update.effective_user.id, update.effective_user.username)
    markup = get_edit_menu_keyboard(role)

    await update.message.reply_text(
        f"Вы выбрали студента: {student.fio} ({student.telegram}).\n"
        "Что вы хотите отредактировать?",
        reply_markup=markup
    )
    return FIELD_TO_EDIT


async def handle_multiple_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_option = update.message.text
    matching_students = context.user_data.get("matching_students")

    if not matching_students:
        await update.message.reply_text("Ошибка: список студентов отсутствует.")
        return FIO_OR_TELEGRAM

    try:
        index = int(selected_option) - 1
        if 0 <= index < len(matching_students):
            student = matching_students[index]
            context.user_data["student"] = student

            # ОПРЕДЕЛЯЕМ РОЛЬ И ДАЕМ МЕНЮ
            role = await get_user_role(update.effective_user.id, update.effective_user.username)
            markup = get_edit_menu_keyboard(role)

            await update.message.reply_text(
                f"Вы выбрали студента: {student.fio}.",
                reply_markup=markup
            )
            return FIELD_TO_EDIT
        else:
            raise ValueError("Выбран некорректный номер.")
    except ValueError:
        await update.message.reply_text("Некорректный выбор. Попробуйте снова.")
        return SELECT_STUDENT
