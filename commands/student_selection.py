from commands.states import FIO_OR_TELEGRAM, SELECT_STUDENT, FIELD_TO_EDIT
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from data_base.operations import get_all_students, get_student_by_fio_or_telegram


# Поиск студента
async def find_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Поиск студента в базе данных.
    """
    search_query = update.message.text.strip()
    # Если пользователь нажал "Главное меню", возвращаем в главное меню
    if search_query == "Главное меню":
        await update.message.reply_text(
            "Возвращаемся в главное меню:",
            reply_markup=ReplyKeyboardMarkup(
                [['Добавить студента', 'Премия куратору'],
        ['Редактировать данные студента', 'Проверить уведомления'],
        ['Поиск ученика', 'Статистика', "📊 Рассчитать зарплату"]],
                one_time_keyboard=True
            )
        )
        return ConversationHandler.END
    students = get_all_students()  # Получение списка студентов из базы данных

    matching_students = [
        student for student in students
        if search_query.lower() in student.fio.lower() or search_query.lower() in student.telegram.lower()
    ]

    if not matching_students:  # Если студенты не найдены
        await update.message.reply_text(
            "Студент не найден. Попробуйте снова ввести ФИО или Telegram:",
            reply_markup=ReplyKeyboardMarkup([["Главное меню"]], one_time_keyboard=True)
        )
        return FIO_OR_TELEGRAM

    if len(matching_students) > 1:  # Если найдено несколько студентов
        response = "Найдено несколько студентов. Укажите номер:\n"
        for i, student in enumerate(matching_students, start=1):
            response += f"{i}. {student.fio} - {student.telegram}\n"

        context.user_data["matching_students"] = matching_students
        await update.message.reply_text(
            response,
            reply_markup=ReplyKeyboardMarkup(
                [[str(i) for i in range(1, len(matching_students) + 1)], ["Назад"]],
                one_time_keyboard=True
            )
        )
        return SELECT_STUDENT

    # Если найден только один студент
    student = matching_students[0]
    context.user_data["student"] = student
    await update.message.reply_text(
        f"Вы выбрали студента: {student.fio} ({student.telegram}).\n"
        "Что вы хотите отредактировать?",
        reply_markup=ReplyKeyboardMarkup(
            [["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты", "Статус обучения", "Получил работу",
              "Комиссия выплачено", "Удалить ученика"],
             ["Назад"]],
            one_time_keyboard=True
        )
    )
    return FIELD_TO_EDIT


# Обработка выбора из нескольких студентов
async def handle_multiple_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор студента из списка.
    """
    selected_option = update.message.text
    matching_students = context.user_data.get("matching_students")

    if not matching_students:
        await update.message.reply_text("Ошибка: список студентов отсутствует.")
        return FIO_OR_TELEGRAM

    try:
        index = int(selected_option) - 1
        if 0 <= index < len(matching_students):
            context.user_data["student"] = matching_students[index]
            await update.message.reply_text(
                f"Вы выбрали студента: {matching_students[index].fio}.",
                reply_markup=ReplyKeyboardMarkup(
                    [["ФИО", "Telegram", "Дата последнего звонка", "Сумма оплаты", "Статус обучения", "Получил работу",
                      "Комиссия выплачено", "Удалить ученика"],
                     ["Назад"]],
                    one_time_keyboard=True
                )
            )
            return FIELD_TO_EDIT
        else:
            raise ValueError("Выбран некорректный номер.")
    except ValueError:
        await update.message.reply_text("Некорректный выбор. Попробуйте снова.")
        return SELECT_STUDENT
