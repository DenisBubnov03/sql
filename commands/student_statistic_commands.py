# commands/student_statistic_commands.py
import re
from datetime import datetime

from commands.authorized_users import AUTHORIZED_USERS
from student_management.student_management import get_all_students
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from commands.states import STATISTICS_MENU, COURSE_TYPE_MENU, START_PERIOD, END_PERIOD


async def show_statistics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return
    """
    Отображает главное меню статистики.
    """
    await update.message.reply_text(
        "📊 Статистика:\nВыберите тип статистики:",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["📈 Общая статистика", "📚 По типу обучения"],
                ["📅 По периоду", "🔙 Вернуться в меню"]
            ],
            one_time_keyboard=True
        )
    )
    return STATISTICS_MENU


async def show_general_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает общую статистику по всем студентам.
    """
    students = get_all_students()
    total_students = len(students)
    fully_paid = sum(1 for s in students if s.get("Полностью оплачено") == "Да")
    not_fully_paid = total_students - fully_paid

    await update.message.reply_text(
        f"📋 Общая статистика:\n\n"
        f"👥 Всего студентов: {total_students}\n"
        f"✅ Полностью оплатили: {fully_paid}\n"
        f"❌ Не оплатили полностью: {not_fully_paid}",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Вернуться в меню"]],
            one_time_keyboard=True
        )
    )
    return STATISTICS_MENU


async def show_course_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает меню выбора типа обучения для статистики.
    """
    await update.message.reply_text(
        "📚 Выберите тип обучения для статистики:",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["👨‍💻 Ручное тестирование", "🤖 Автотестирование", "💻 Фуллстек"],
                ["🔙 Назад"]
            ],
            one_time_keyboard=True
        )
    )
    return COURSE_TYPE_MENU


def filter_students_by_course(students, course_type):
    """
    Фильтрует студентов по типу обучения.

    Args:
        students (list): Список студентов.
        course_type (str): Тип обучения.

    Returns:
        list: Список студентов с указанным типом обучения.
    """
    return [s for s in students if s.get("Тип обучения") == course_type]


async def show_course_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE, course_type, emoji):
    """
    Отображает статистику для указанного типа обучения.

    Args:
        update (Update): Объект Telegram Update.
        context (ContextTypes.DEFAULT_TYPE): Контекст команды.
        course_type (str): Тип обучения.
        emoji (str): Эмодзи для заголовка.
    """
    students = get_all_students()
    filtered_students = filter_students_by_course(students, course_type)

    await update.message.reply_text(
        f"{emoji} Статистика по {course_type}:\n\n"
        f"👥 Всего студентов: {len(filtered_students)}",
        reply_markup=ReplyKeyboardMarkup(
            [["🔙 Назад"]],
            one_time_keyboard=True
        )
    )
    return COURSE_TYPE_MENU


async def show_manual_testing_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает статистику по ручному тестированию.
    """
    return await show_course_statistics(update, context, "Ручное тестирование", "👨‍💻")


async def show_automation_testing_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает статистику по автотестированию.
    """
    return await show_course_statistics(update, context, "Автотестирование", "🤖")


async def show_fullstack_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает статистику по Фуллстек.
    """
    return await show_course_statistics(update, context, "Фуллстек", "💻")

async def request_period_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Запрашивает начальную дату периода.
    """
    await update.message.reply_text("Введите начальную дату периода в формате ДД.ММ.ГГГГ:")
    return START_PERIOD


async def handle_period_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает начальную дату периода.
    """
    try:
        start_date_text = update.message.text.strip()  # Удаляем лишние пробелы
        start_date = datetime.strptime(start_date_text, "%d.%m.%Y")
        context.user_data["start_date"] = start_date
        await update.message.reply_text("Введите конечную дату периода в формате ДД.ММ.ГГГГ:")
        return END_PERIOD
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат даты! Введите дату в формате **ДД.ММ.ГГГГ** (например: 10.11.2024):")
        return START_PERIOD


def parse_date(date_text):
    """
    Преобразует дату из любого распространённого формата в формат ДД.ММ.ГГГГ.
    """
    try:
        # Попытка распознать дату в формате ДД.ММ.ГГГГ
        return datetime.strptime(date_text, "%d.%m.%Y")
    except ValueError:
        pass

    try:
        # Попытка распознать дату в формате ГГГГ-ММ-ДД
        return datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError:
        pass

    # Если дата не распознаётся
    raise ValueError(f"Неподдерживаемый формат даты: {date_text}")


async def handle_period_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает конечную дату периода и фильтрует учеников.
    """
    try:
        end_date_text = update.message.text.strip()
        end_date = parse_date(end_date_text)  # Используем универсальный парсер

        start_date = context.user_data.get("start_date")
        if start_date and end_date < start_date:
            await update.message.reply_text("❌ Конечная дата не может быть раньше начальной. Попробуйте снова:")
            return END_PERIOD

        context.user_data["end_date"] = end_date

        # Получаем всех студентов
        students = get_all_students()
        filtered_students = []

        for student in students:
            if "Дата начала обучения" in student:
                try:
                    student_date = parse_date(student["Дата начала обучения"])
                    if start_date <= student_date <= end_date:
                        filtered_students.append(student)
                except ValueError:
                    print(f"Ошибка формата у студента {student['ФИО']}: {student['Дата начала обучения']}")

        if not filtered_students:
            await update.message.reply_text("😔 Не найдено учеников в заданный период.")
        else:
            response = "📅 Ученики, устроившиеся в заданный период:\n\n"
            for student in filtered_students:
                response += f"{student['ФИО']} - {student['Telegram']} (Начало: {student['Дата начала обучения']})\n"
            await update.message.reply_text(response)

        return STATISTICS_MENU

    except ValueError as e:
        print(f"Ошибка формата даты: {e}")
        await update.message.reply_text("❌ Неверный формат даты! Введите дату в формате **ДД.ММ.ГГГГ** (например: 10.12.2024):")
        return END_PERIOD