from datetime import datetime
from commands.authorized_users import AUTHORIZED_USERS
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from commands.states import STATISTICS_MENU, COURSE_TYPE_MENU, START_PERIOD, END_PERIOD
from data_base.db import session
from data_base.models import Student
from data_base.operations import get_general_statistics, get_students_by_period, get_students_by_training_type


async def show_statistics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает главное меню статистики.
    """
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("Извините, у вас нет доступа.")
        return

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
    statistics = get_general_statistics()
    total_students = statistics.get("total_students", 0)
    fully_paid = statistics.get("fully_paid", 0)
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


async def show_course_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE, course_type, emoji):
    """
    Отображает статистику для указанного типа обучения.
    """
    students = get_students_by_training_type(course_type)

    await update.message.reply_text(
        f"{emoji} Статистика по {course_type}:\n\n"
        f"👥 Всего студентов: {len(students)}",
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
        start_date_text = update.message.text.strip()
        start_date = datetime.strptime(start_date_text, "%d.%m.%Y")
        context.user_data["start_date"] = start_date
        await update.message.reply_text("Введите конечную дату периода в формате ДД.ММ.ГГГГ:")
        return END_PERIOD
    except ValueError:
        await update.message.reply_text("❌ Неверный формат даты! Введите дату в формате **ДД.ММ.ГГГГ** (например: 10.11.2024):")
        return START_PERIOD


async def handle_period_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает конечную дату периода и фильтрует учеников.
    """
    try:
        # Получаем текст конечной даты
        end_date_text = update.message.text.strip()

        # Проверяем, что текст даты не пуст
        if not end_date_text:
            await update.message.reply_text("Дата не должна быть пустой. Введите дату в формате ДД.ММ.ГГГГ.")
            return END_PERIOD

        # Преобразуем конечную дату только если это строка
        if isinstance(end_date_text, str):
            end_date = datetime.strptime(end_date_text, "%d.%m.%Y")
        else:
            end_date = end_date_text

        # Получаем начальную дату из context.user_data
        start_date = context.user_data.get("start_date")

        # Проверяем, что начальная дата сохранена и является объектом datetime
        if not start_date:
            await update.message.reply_text("Начальная дата отсутствует. Попробуйте начать сначала.")
            return START_PERIOD
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%d.%m.%Y")

        # Проверяем, что конечная дата не раньше начальной
        if end_date < start_date:
            await update.message.reply_text("Конечная дата не может быть раньше начальной. Введите корректную дату.")
            return END_PERIOD

        # Сохраняем конечную дату в context
        context.user_data["end_date"] = end_date

        # Переходим к отображению статистики
        return await show_period_statistics(update, context)

    except ValueError:
        await update.message.reply_text("Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ.")
        return END_PERIOD
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {e}")
        return END_PERIOD



async def show_period_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает статистику по периоду с указанием количества студентов.
    """
    start_date = context.user_data.get("start_date")
    end_date = context.user_data.get("end_date")

    # Проверяем, что даты существуют и являются объектами datetime
    if not start_date or not end_date:
        await update.message.reply_text("Даты периода отсутствуют. Попробуйте начать заново.")
        return STATISTICS_MENU
    if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
        raise ValueError("Одна из дат не является объектом datetime.")

    # Получаем студентов из базы
    students = session.query(Student).filter(
        Student.start_date.between(start_date, end_date)
    ).all()

    # Формируем сообщение
    student_count = len(students)
    if student_count == 0:
        response = f"📅 В период с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} студентов не найдено."
    else:
        response = (
            f"📅 В период с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}:\n"
            f"👥 Найдено студентов: {student_count}\n\n"
        )
        for student in students:
            response += f"- {student.fio} ({student.telegram})\n"

    await update.message.reply_text(response)
    return STATISTICS_MENU

