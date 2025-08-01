from datetime import datetime

from sqlalchemy import func

from commands.authorized_users import AUTHORIZED_USERS, NOT_ADMINS
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from commands.states import STATISTICS_MENU, COURSE_TYPE_MENU, START_PERIOD, END_PERIOD
from data_base.db import session
from data_base.models import Student, Payment
from data_base.operations import get_general_statistics, get_students_by_period, get_students_by_training_type
from commands.additional_expenses_commands import get_additional_expenses_for_period


async def show_statistics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает главное меню статистики.
    """
    user_id = update.message.from_user.id
    if user_id not in AUTHORIZED_USERS and user_id not in NOT_ADMINS:
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
    Отображает статистику для указанного типа обучения с указанием студентов и их оплаты.
    """
    students = get_students_by_training_type(course_type)

    response = (
        f"{emoji} Статистика по {course_type}:\n\n"
        f"👥 Всего студентов: {len(students)}\n"
    )

    if students:
        for student in students:
            response += (
                f"- {student.fio} ({student.telegram}) "
                f"  Оплачено: {student.payment_amount} из {student.total_cost}\n"
            )
    else:
        response += "Список студентов пуст."

    await update.message.reply_text(
        response,
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
        await update.message.reply_text("❌ Неверный формат даты! Введите дату в формате ДД.ММ.ГГГГ (например: 10.11.2024):")
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


# Вспомогательная функция, принимающая объекты date
def calc_total_salaries_for_dates(start_date, end_date, session) -> float:
    from data_base.models import Payment, Student

    mentor_salaries = {}

    detailed_payments = session.query(Payment).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
        Payment.status == "подтвержден",
        ~Payment.comment.ilike("%преми%")
    ).all()

    for p in detailed_payments:
        student = session.query(Student).get(p.student_id)
        if not student or not p.mentor_id:
            continue

        m_id = p.mentor_id
        mentor_salaries.setdefault(m_id, 0)

        if student.training_type == "Фуллстек":
            continue

        if m_id == 1 and student.training_type == "Ручное тестирование":
            pct = 0.3
        elif m_id == 3 and student.training_type == "Автотестирование":
            pct = 0.3
        else:
            pct = 0.2
        mentor_salaries[m_id] += float(p.amount) * pct

    for p in detailed_payments:
        student = session.query(Student).get(p.student_id)
        if not student or student.training_type == "Фуллстек":
            continue

        if p.mentor_id != 1 and student.training_type.lower().strip() == "ручное тестирование":
            mentor_salaries.setdefault(1, 0)
            mentor_salaries[1] += float(p.amount) * 0.1

        if p.mentor_id != 3 and student.training_type == "Автотестирование":
            mentor_salaries.setdefault(3, 0)
            mentor_salaries[3] += float(p.amount) * 0.1

    fs_students = session.query(Student).filter(
        Student.training_type == "Фуллстек",
        Student.total_cost >= 50000,
        Student.start_date >= start_date,
        Student.start_date <= end_date
    ).all()
    if fs_students:
        mentor_salaries.setdefault(1, 0)
        mentor_salaries[1] += len(fs_students) * 5000

    for p in detailed_payments:
        student = session.query(Student).get(p.student_id)
        if not student or student.training_type != "Фуллстек":
            continue

        amt = float(p.amount)
        m_id = p.mentor_id

        mentor_salaries.setdefault(m_id, 0)
        mentor_salaries.setdefault(3, 0)

        if m_id == 3:
            mentor_salaries[3] += amt * 0.3
        else:
            mentor_salaries[3] += amt * 0.1
            mentor_salaries[m_id] += amt * 0.2

    premium_payments = session.query(Payment).filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date,
        Payment.status == "подтвержден",
        Payment.comment.ilike("%преми%")
    ).all()

    for p in premium_payments:
        m_id = p.mentor_id
        mentor_salaries.setdefault(m_id, 0)
        mentor_salaries[m_id] += float(p.amount)

    return round(sum(mentor_salaries.values()), 2)


async def show_period_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает статистику по периоду с указанием количества студентов.
    """
    start_date = context.user_data.get("start_date")
    end_date = context.user_data.get("end_date")

    if not start_date or not end_date:
        await update.message.reply_text("❌ Ошибка: Даты периода отсутствуют. Попробуйте начать заново.")
        return STATISTICS_MENU

    if end_date < start_date:
        await update.message.reply_text("⚠ Конечная дата не может быть раньше начальной. Введите корректную дату.")
        return END_PERIOD

    # Получаем студентов, начавших обучение в период
    students = session.query(Student).filter(
        Student.start_date.between(start_date, end_date)
    ).all()

    student_count = len(students)

    # Получаем сумму всех платежей (включая первоначальные и доплаты), ИСКЛЮЧАЯ доп расходы
    total_paid = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        ~Payment.comment.ilike("%Доп расход%")  # Исключаем доп расходы из оборота
    ).scalar() or 0

    # Получаем сумму доплат (где comment = "Доплата")
    additional_payments = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.comment == "Доплата"
    ).scalar() or 0

    additional_commission = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.comment == "Комиссия"
    ).scalar() or 0

    # Общая стоимость обучения для найденных студентов
    total_cost = sum(student.total_cost for student in students)
    payment_amount = sum(student.payment_amount for student in students)

    # Остаток к оплате
    remaining_payment = total_cost - payment_amount

    # 📊 Формируем ответ в **старом формате**
    if student_count == 0:
        response = (
            f"📅 В период с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')} "
            f"студентов не найдено."
        )
    else:
        response = (
            f"📅 В период с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}:\n"
            f"👥 Найдено студентов: {student_count}\n\n"
        )

        for student in students:
            response += (
                f"- {student.fio} ({student.telegram}) "
                f"  Оплачено: {student.payment_amount} из {student.total_cost}\n"
            )

        # где-то в вашем хэндлере, после расчёта всех чисел
        total_salaries = calc_total_salaries_for_dates(start_date, end_date, session)
        
        # Получаем доп расходы за период
        additional_expenses = get_additional_expenses_for_period(start_date, end_date, session)
        
        # Чистая прибыль с учетом доп расходов
        net_profit = int(total_paid) - int(total_salaries) - int(additional_expenses)
        
        response += (
            f"\n💰 Оплачено за обучение: {int(payment_amount):,} руб.\n"
            f"📚 Общая стоимость обучения: {int(total_cost):,} руб.\n"
            f"➕ Общая сумма доплат: {int(additional_payments):,} руб.\n"
            f"💸 Общая сумма комиссии: {int(additional_commission):,} руб.\n"
            f"👥 Всего на зарплаты: {int(total_salaries):,} руб.\n"
            f"💵 Оборот: {int(total_paid):,} руб.\n"
            f"💸 Доп расходы: {int(additional_expenses):,} руб.\n"
            f"👥 Чистая прибыль: {net_profit:,} руб.\n"
            f"🧾 Осталось оплатить: {int(remaining_payment):,} руб."
        )

    await update.message.reply_text(response)
    return STATISTICS_MENU


