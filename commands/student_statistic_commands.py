import logging
from datetime import datetime

from sqlalchemy import func
from classes.salary import SalaryManager
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from commands.states import STATISTICS_MENU, COURSE_TYPE_MENU, START_PERIOD, END_PERIOD
from data_base.db import session
from data_base.models import Student, Payment
from data_base.operations import get_general_statistics, get_students_by_period, get_students_by_training_type
from commands.additional_expenses_commands import get_additional_expenses_for_period
from utils.security import restrict_to

logger = logging.getLogger(__name__)

@restrict_to(['admin', 'mentor']) # Разрешаем доступ обеим ролям
async def show_statistics_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отображает главное меню статистики.
    """

    await update.message.reply_text(
        "📊 Статистика:\nВыберите тип статистики:",
        reply_markup=ReplyKeyboardMarkup(
            [
                ["📈 Общая статистика", "📚 По типу обучения"],
                ["📅 По периоду", "💰 Холдирование"],
                ["💹 Юнит экономика"],
                ["🔙 Вернуться в меню"]
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
            await update.message.reply_text("❌ Дата не должна быть пустой. Введите дату в формате ДД.ММ.ГГГГ (например: 01.10.2025):")
            return END_PERIOD

        # Преобразуем конечную дату
        try:
            end_date = datetime.strptime(end_date_text, "%d.%m.%Y")
        except ValueError as e:
            # Проверяем, может быть это невалидная дата (например, 31 сентября)
            error_msg = str(e).lower()
            if "day" in error_msg or "day is out of range" in error_msg or "invalid day" in error_msg:
                await update.message.reply_text(
                    f"❌ Неверная дата! Вы ввели: '{end_date_text}'\n"
                    "Эта дата не существует (например, в месяце недостаточно дней).\n"
                    "Проверьте правильность даты и введите снова в формате ДД.ММ.ГГГГ (например: 30.09.2025):"
                )
            else:
                await update.message.reply_text(
                    f"❌ Неверный формат даты! Вы ввели: '{end_date_text}'\n"
                    "Используйте формат ДД.ММ.ГГГГ (например: 01.10.2025):"
                )
            return END_PERIOD

        # Получаем начальную дату из context.user_data
        start_date = context.user_data.get("start_date")

        # Проверяем, что начальная дата сохранена и является объектом datetime
        if not start_date:
            await update.message.reply_text("❌ Начальная дата отсутствует. Попробуйте начать сначала.")
            return START_PERIOD
        
        # Преобразуем start_date в datetime, если это строка
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, "%d.%m.%Y")
            except ValueError:
                await update.message.reply_text("❌ Ошибка в начальной дате. Попробуйте начать сначала.")
                return START_PERIOD

        # Проверяем, что конечная дата не раньше начальной
        if end_date < start_date:
            await update.message.reply_text(
                f"❌ Конечная дата ({end_date.strftime('%d.%m.%Y')}) не может быть раньше начальной ({start_date.strftime('%d.%m.%Y')}). "
                "Введите корректную дату:"
            )
            return END_PERIOD

        # Сохраняем конечную дату в context
        context.user_data["end_date"] = end_date

        # Переходим к отображению статистики
        return await show_period_statistics(update, context)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Произошла ошибка при обработке даты: {str(e)}\n"
            "Попробуйте ввести дату в формате ДД.ММ.ГГГГ (например: 01.10.2025):"
        )
        return END_PERIOD


# Вспомогательная функция, принимающая объекты date
def calc_total_salaries_for_dates(start_date, end_date, session) -> tuple:
    from data_base.models import Payment, Student, CareerConsultant

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

    # fs_students = session.query(Student).filter(
    #     Student.training_type == "Фуллстек",
    #     Student.total_cost >= 50000,
    #     Student.start_date >= start_date,
    #     Student.start_date <= end_date
    # ).all()
    # if fs_students:
    #     mentor_salaries.setdefault(1, 0)
    #     mentor_salaries[1] += len(fs_students) * 5000

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

    # Расчет зарплат карьерных консультантов
    career_consultant_salaries = {}
    all_consultants = session.query(CareerConsultant).filter(CareerConsultant.is_active == True).all()
    
    for consultant in all_consultants:
        # Получаем всех студентов, закрепленных за консультантом
        students = session.query(Student).filter(Student.career_consultant_id == consultant.id).all()
        student_ids = [student.id for student in students]
        
        if not student_ids:
            continue
        
        # Получаем все подтвержденные платежи с комментарием "Комиссия" за период
        commission_payments = session.query(Payment).filter(
            Payment.student_id.in_(student_ids),
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status == "подтвержден",
            Payment.comment.ilike("%комисси%")
        ).all()
        
        # Рассчитываем комиссию: 20% если КК с ID=1 взял студента после 18.11.2025, иначе 10%
        from datetime import date
        COMMISSION_CHANGE_DATE = date(2025, 11, 18)
        
        total_commission = 0
        salary = 0
        for payment in commission_payments:
            student = session.query(Student).filter(Student.id == payment.student_id).first()
            if student and student.consultant_start_date:
                # Если КК взял студента после 18.11.2025 и КК с ID=1, то 20%, иначе 10%
                if student.consultant_start_date >= COMMISSION_CHANGE_DATE and student.career_consultant_id == 1:
                    salary += float(payment.amount) * 0.2
                else:
                    salary += float(payment.amount) * 0.1
            else:
                # Если дата не установлена, используем старую ставку 10%
                salary += float(payment.amount) * 0.1
            total_commission += float(payment.amount)
        career_consultant_salaries[consultant.id] = round(salary, 2)
        
        # Подробное логирование для карьерных консультантов
        if commission_payments:
            logger.info(f"📘 Карьерный консультант: {consultant.full_name} ({consultant.telegram})")
            # Расчет с учетом НДФЛ 6%
            salary_with_tax = round(salary * 1.06, 2)
            logger.info(f"💼 Карьерный консультант {consultant.full_name} | Комиссии: {total_commission} руб. | Итого: {salary} руб. (с НДФЛ {salary_with_tax})")
            
            # Логируем каждый платеж комиссии отдельно
            for payment in commission_payments:
                student = session.query(Student).filter(Student.id == payment.student_id).first()
                if student:
                    logger.info(f"  📄 Студент {student.fio} ({student.telegram}) | Платеж: {payment.amount} руб. | Дата: {payment.payment_date} | Комментарий: {payment.comment}")
            logger.info(f"Итог: {salary} руб. (с НДФЛ {salary_with_tax})")

    # Вычисляем общую зарплату менторов (исключая карьерных консультантов)
    total_mentor_salary = sum(mentor_salaries.values())
    total_career_consultant_salary = sum(career_consultant_salaries.values())

    return (round(total_mentor_salary, 2), round(total_career_consultant_salary, 2))


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
        Payment.status == "подтвержден",
        ~Payment.comment.ilike("%Системное восстановление%"),  # Исключаем доп расходы из оборота
        ~Payment.comment.ilike("%Доп расход%")  # Исключаем доп расходы из оборота
    ).scalar() or 0

    # Получаем сумму доплат (где comment = "Доплата")
    additional_payments = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.status == "подтвержден",
        Payment.comment == "Доплата"
    ).scalar() or 0

    additional_commission = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.status == "подтвержден",
        Payment.comment == "Комиссия"
    ).scalar() or 0

    # Общая стоимость обучения для найденных студентов
    total_cost = sum(student.total_cost for student in students)
    payment_amount = session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date.between(start_date, end_date),
        Payment.status == "подтвержден",
        Payment.comment == "Первоначальный платёж при регистрации"
    ).scalar() or 0

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
        # mentor_salaries, career_consultant_salaries = calc_total_salaries_for_dates(start_date, end_date, session)
        mentor_salaries, career_consultant_salaries = SalaryManager.get_total_turnover(session, start_date, end_date)
        total_salaries = mentor_salaries + career_consultant_salaries

        # Получаем доп расходы за период
        additional_expenses = get_additional_expenses_for_period(start_date, end_date)
        
        # Чистая прибыль с учетом доп расходов
        net_profit = int(total_paid) - int(total_salaries) - int(additional_expenses)
        
        # Расчет с учетом НДФЛ 6%
        mentor_salaries_with_tax = round(mentor_salaries * 1.06, 2)
        career_consultant_salaries_with_tax = round(career_consultant_salaries * 1.06, 2)
        total_salaries_with_tax = round(total_salaries * 1.06, 2)
        
        response += (
            f"\n💰 Оплачено за обучение: {int(payment_amount):,} руб.\n"
            f"📚 Общая стоимость обучения: {int(total_cost):,} руб.\n"
            f"➕ Общая сумма доплат: {int(additional_payments):,} руб.\n"
            f"💸 Общая сумма комиссии: {int(additional_commission):,} руб.\n"
            f"👥 Зарплаты менторов: {int(mentor_salaries):,} руб. (с НДФЛ {int(mentor_salaries_with_tax):,})\n"
            f"👥 Зарплаты КК: {int(career_consultant_salaries):,} руб. (с НДФЛ {int(career_consultant_salaries_with_tax):,})\n"
            f"👥 Всего на зарплаты: {int(total_salaries):,} руб. (с НДФЛ {int(total_salaries_with_tax):,})\n"
        )
        
        
        response += (
            f"💵 Оборот: {int(total_paid):,} руб.\n"
            f"💸 Доп расходы: {int(additional_expenses):,} руб.\n"
            f"👥 Чистая прибыль: {net_profit:,} руб.\n"
            f"🧾 Осталось оплатить: {int(remaining_payment):,} руб."
        )

    await update.message.reply_text(response)
    return STATISTICS_MENU

@restrict_to(['admin', 'mentor']) # Разрешаем доступ обеим ролям
async def show_held_amounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает общую сумму активного холдирования с 1 сентября 2025 по текущую дату.
    """
    import logging
    import traceback
    
    # Базовый логгер для отладки
    logger = logging.getLogger(__name__)
    
    try:
        user_id = update.message.from_user.id
        logger.info(f"💰 Запрос холдирования от пользователя {user_id}")

        
        from config import Config
        from data_base.models import HeldAmount, Mentor
        from datetime import date as date_class
        
        logger.info(f"💰 HELD_AMOUNTS_ENABLED = {Config.HELD_AMOUNTS_ENABLED}")
        
        if not Config.HELD_AMOUNTS_ENABLED:
            await update.message.reply_text(
                "💰 Система холдирования отключена.",
                reply_markup=ReplyKeyboardMarkup(
                    [["🔙 Вернуться в меню"]],
                    one_time_keyboard=True
                )
            )
            return STATISTICS_MENU
        
        # Настраиваем логгер для холдирования
        held_logger = logging.getLogger('held_amounts')
        held_logger.setLevel(logging.INFO)
        if not held_logger.handlers:
            try:
                held_file_handler = logging.FileHandler('held_amounts.log', encoding='utf-8')
                held_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                held_logger.addHandler(held_file_handler)
                logger.info("✅ Логгер held_amounts настроен успешно")
            except Exception as e:
                logger.error(f"❌ Ошибка при создании логгера held_amounts: {e}")
                await update.message.reply_text(
                    f"❌ Ошибка при настройке логирования: {e}",
                    reply_markup=ReplyKeyboardMarkup(
                        [["🔙 Вернуться в меню"]],
                        one_time_keyboard=True
                    )
                )
                return STATISTICS_MENU
        
        held_logger.info("=" * 80)
        held_logger.info("💰 НАЧАЛО ОБРАБОТКИ ЗАПРОСА ХОЛДИРОВАНИЯ")
        logger.info("💰 Начинаем обработку запроса холдирования")
        
        # Дата начала действия системы холдирования
        held_amounts_start_date = date_class(2025, 9, 1)
        current_date = date_class.today()
        
        # 📝 ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
        held_logger.info("=" * 80)
        held_logger.info(f"💰 ЗАПРОС ХОЛДИРОВАНИЯ - {current_date.strftime('%d.%m.%Y %H:%M:%S')}")
        held_logger.info(f"Период: с 01.09.2025 по {current_date.strftime('%d.%m.%Y')}")
        held_logger.info("=" * 80)
        
        # 🔄 СОЗДАНИЕ/ОБНОВЛЕНИЕ ЗАПИСЕЙ ХОЛДИРОВАНИЯ
        from data_base.operations import calculate_held_amount
        from datetime import date
        
        held_logger.info("🔄 Начинаем создание/обновление записей холдирования...")
        
        # 🔄 ПРОВЕРЯЕМ И ОБНОВЛЯЕМ СТАТУСЫ ЗАПИСЕЙ В held_amounts
        # Если у студента training_status = "Не учится" или "Отчислен", 
        # помечаем все его записи как released
        held_logger.info("🔄 Проверяем статусы студентов в held_amounts...")
        all_held_records = session.query(HeldAmount).all()
        students_to_deactivate = set()
        
        for held_record in all_held_records:
            student = session.query(Student).filter(Student.id == held_record.student_id).first()
            if student and student.training_status in ["Не учится", "Отчислен"]:
                students_to_deactivate.add(student.id)
                if held_record.status == "active":
                    held_record.status = "released"
                    held_logger.info(f"🔴 Помечено как released: студент ID {student.id} ({student.fio}), training_status={student.training_status}")
        
        if students_to_deactivate:
            session.commit()
            held_logger.info(f"✅ Обновлено записей для {len(students_to_deactivate)} студентов со статусом 'Не учится' или 'Отчислен'")
        
        # Получаем активных студентов фуллстек, которые начали обучение с 1 сентября 2025
        # Исключаем студентов с training_status = "Не учится" или "Отчислен"
        from sqlalchemy import and_, not_
        
        fullstack_students = session.query(Student).filter(
            Student.training_type == "Фуллстек",
            Student.start_date >= held_amounts_start_date,
            Student.training_status != "Отчислен",
            Student.training_status != "Не учится"
        ).all()
        
        # Дополнительная фильтрация в Python для надежности
        fullstack_students = [
            s for s in fullstack_students 
            if s.training_status not in ["Отчислен", "Не учится"]
        ]
        
        held_logger.info(f"💰 Найдено активных студентов фуллстек для обработки: {len(fullstack_students)}")
        
        total_created_updated = 0.0
        
        for student in fullstack_students:
            try:
                # 🔍 РУЧНОЕ НАПРАВЛЕНИЕ: проверяем, кто назначен куратором
                if student.mentor_id == Config.DIRECTOR_MANUAL_ID:
                    manual_result = calculate_held_amount(student.id, "manual", Config.DIRECTOR_MANUAL_ID, is_director=True)
                    is_director_manual = True
                elif student.mentor_id:
                    manual_result = calculate_held_amount(student.id, "manual", student.mentor_id, is_director=False)
                    is_director_manual = False
                else:
                    manual_result = calculate_held_amount(student.id, "manual", None, is_director=False)
                    is_director_manual = False
                
                if manual_result:
                    held_amount = manual_result['held_amount']
                    potential_amount = manual_result['potential_amount']
                    paid_amount = manual_result['paid_amount']
                    modules_completed = manual_result['modules_completed']
                    total_modules = manual_result['total_modules']
                    mentor_id_for_db = student.mentor_id if student.mentor_id else Config.DIRECTOR_MANUAL_ID if is_director_manual else None
                    
                    held_record = session.query(HeldAmount).filter(
                        HeldAmount.student_id == student.id,
                        HeldAmount.direction == "manual"
                    ).first()
                    
                    if held_record:
                        held_record.mentor_id = mentor_id_for_db
                        held_record.held_amount = held_amount
                        held_record.potential_amount = potential_amount
                        held_record.paid_amount = paid_amount
                        held_record.modules_completed = modules_completed
                        held_record.total_modules = total_modules
                        held_record.updated_at = date.today()
                        if held_record.status == "released":
                            held_record.status = "active"
                        total_created_updated += held_amount
                    else:
                        held_record = HeldAmount(
                            student_id=student.id,
                            mentor_id=mentor_id_for_db,
                            direction="manual",
                            held_amount=held_amount,
                            potential_amount=potential_amount,
                            paid_amount=paid_amount,
                            modules_completed=modules_completed,
                            total_modules=total_modules,
                            status="active",
                            created_at=date.today(),
                            updated_at=date.today()
                        )
                        session.add(held_record)
                        total_created_updated += held_amount
                
                # 🔍 АВТО НАПРАВЛЕНИЕ: проверяем, кто назначен куратором
                if student.auto_mentor_id == Config.DIRECTOR_AUTO_ID:
                    auto_result = calculate_held_amount(student.id, "auto", Config.DIRECTOR_AUTO_ID, is_director=True)
                    is_director_auto = True
                elif student.auto_mentor_id:
                    auto_result = calculate_held_amount(student.id, "auto", student.auto_mentor_id, is_director=False)
                    is_director_auto = False
                else:
                    auto_result = calculate_held_amount(student.id, "auto", None, is_director=False)
                    is_director_auto = False
                
                if auto_result:
                    held_amount = auto_result['held_amount']
                    potential_amount = auto_result['potential_amount']
                    paid_amount = auto_result['paid_amount']
                    modules_completed = auto_result['modules_completed']
                    total_modules = auto_result['total_modules']
                    mentor_id_for_db = student.auto_mentor_id if student.auto_mentor_id else Config.DIRECTOR_AUTO_ID if is_director_auto else None
                    
                    held_record = session.query(HeldAmount).filter(
                        HeldAmount.student_id == student.id,
                        HeldAmount.direction == "auto"
                    ).first()
                    
                    if held_record:
                        held_record.mentor_id = mentor_id_for_db
                        held_record.held_amount = held_amount
                        held_record.potential_amount = potential_amount
                        held_record.paid_amount = paid_amount
                        held_record.modules_completed = modules_completed
                        held_record.total_modules = total_modules
                        held_record.updated_at = date.today()
                        if held_record.status == "released":
                            held_record.status = "active"
                        total_created_updated += held_amount
                    else:
                        held_record = HeldAmount(
                            student_id=student.id,
                            mentor_id=mentor_id_for_db,
                            direction="auto",
                            held_amount=held_amount,
                            potential_amount=potential_amount,
                            paid_amount=paid_amount,
                            modules_completed=modules_completed,
                            total_modules=total_modules,
                            status="active",
                            created_at=date.today(),
                            updated_at=date.today()
                        )
                        session.add(held_record)
                        total_created_updated += held_amount
                
                session.commit()
                
            except Exception as e:
                held_logger.error(f"❌ Ошибка при обработке студента {student.fio} (ID {student.id}): {e}")
                session.rollback()
    
        held_logger.info(f"✅ Создано/обновлено записей холдирования. Итого: {round(total_created_updated, 2)} руб.")
    
        # Получаем все активные холдирования для студентов, начавших обучение с 1 сентября 2025
        active_held_amounts = session.query(HeldAmount).join(
            Student, HeldAmount.student_id == Student.id
        ).filter(
            HeldAmount.status == "active",
            Student.start_date >= held_amounts_start_date
        ).all()
    
        # Логируем количество найденных записей
        held_logger.info(f"🔍 Найдено активных холдирований после обновления: {len(active_held_amounts)}")
    
        total_held_amount = sum(float(held.held_amount) for held in active_held_amounts)
    
        # Подсчитываем количество студентов с холдированием
        student_ids_with_held = set(held.student_id for held in active_held_amounts)
        students_count = len(student_ids_with_held)
    
        # Группируем по типам получателей
        manual_curators = {}  # {mentor_id: {'name': str, 'total': float, 'students': []}}
        auto_curators = {}
        director_manual_info = {'total': 0.0, 'students': []}
        director_auto_info = {'total': 0.0, 'students': []}
    
        # Логируем каждую найденную запись для отладки
        if active_held_amounts:
            held_logger.info("")
            held_logger.info("📋 НАЙДЕННЫЕ ЗАПИСИ ХОЛДИРОВАНИЯ:")
            for idx, held in enumerate(active_held_amounts, 1):
                student = session.query(Student).filter(Student.id == held.student_id).first()
                student_name = student.fio if student else f"ID {held.student_id} (не найден)"
                student_date = student.start_date.strftime('%d.%m.%Y') if student and student.start_date else "нет даты"
                held_logger.info(
                    f"  {idx}. Студент: {student_name} (ID {held.student_id}, дата начала: {student_date}) | "
                    f"Направление: {held.direction} | "
                    f"Ментор ID: {held.mentor_id} | "
                    f"Холдировано: {float(held.held_amount):.2f} руб. | "
                    f"Статус: {held.status}"
                )
            held_logger.info("")
        
        for held in active_held_amounts:
            student = session.query(Student).filter(Student.id == held.student_id).first()
            if not student:
                continue
            
            mentor_name = "не назначен"
            is_director_manual = False
            is_director_auto = False
            
            if held.mentor_id:
                mentor = session.query(Mentor).filter(Mentor.id == held.mentor_id).first()
                if mentor:
                    mentor_name = mentor.full_name
                
                # Проверяем, является ли директором
                if held.mentor_id == Config.DIRECTOR_MANUAL_ID and held.direction == "manual":
                    is_director_manual = True
                elif held.mentor_id == Config.DIRECTOR_AUTO_ID and held.direction == "auto":
                    is_director_auto = True
            
            held_amount = float(held.held_amount)
            
            if held.direction == "manual":
                if is_director_manual:
                    # Это директор ручного направления
                    director_manual_info['total'] += held_amount
                    director_manual_info['students'].append({
                        'student': student.fio,
                        'student_id': student.id,
                        'amount': held_amount,
                        'total_cost': float(student.total_cost)
                    })
                    
                    held_logger.info(
                        f"💼 РУЧНОЕ (ДИРЕКТОР): Студент {student.fio} (ID {student.id}) | "
                        f"Директор: {mentor_name} (ID {held.mentor_id}) | "
                        f"30% от total_cost {float(student.total_cost):.2f} руб. | "
                        f"Холдировано: {held_amount:.2f} руб."
                    )
                else:
                    # Это обычный куратор ручного направления
                    if held.mentor_id not in manual_curators:
                        manual_curators[held.mentor_id] = {
                            'name': mentor_name,
                            'total': 0.0,
                            'students': []
                        }
                    manual_curators[held.mentor_id]['total'] += held_amount
                    manual_curators[held.mentor_id]['students'].append({
                        'student': student.fio,
                        'student_id': student.id,
                        'amount': held_amount,
                        'modules': f"{held.modules_completed}/{held.total_modules}",
                        'paid': float(held.paid_amount)
                    })
                    
                    held_logger.info(
                        f"📋 РУЧНОЕ (КУРАТОР): Студент {student.fio} (ID {student.id}) | "
                        f"Куратор: {mentor_name} (ID {held.mentor_id or 'не назначен'}) | "
                        f"Модулей: {held.modules_completed}/{held.total_modules} | "
                        f"Выплачено: {float(held.paid_amount):.2f} руб. | "
                        f"Холдировано: {held_amount:.2f} руб."
                    )
            
            elif held.direction == "auto":
                if is_director_auto:
                    # Это директор авто направления
                    director_auto_info['total'] += held_amount
                    director_auto_info['students'].append({
                        'student': student.fio,
                        'student_id': student.id,
                        'amount': held_amount,
                        'total_cost': float(student.total_cost)
                    })
                    
                    held_logger.info(
                        f"💼 АВТО (ДИРЕКТОР): Студент {student.fio} (ID {student.id}) | "
                        f"Директор: {mentor_name} (ID {held.mentor_id}) | "
                        f"30% от total_cost {float(student.total_cost):.2f} руб. | "
                        f"Холдировано: {held_amount:.2f} руб."
                    )
                else:
                    # Это обычный куратор авто направления
                    if held.mentor_id not in auto_curators:
                        auto_curators[held.mentor_id] = {
                            'name': mentor_name,
                            'total': 0.0,
                            'students': []
                        }
                    auto_curators[held.mentor_id]['total'] += held_amount
                    auto_curators[held.mentor_id]['students'].append({
                        'student': student.fio,
                        'student_id': student.id,
                        'amount': held_amount,
                        'modules': f"{held.modules_completed}/{held.total_modules}",
                        'paid': float(held.paid_amount)
                    })
                    
                    held_logger.info(
                        f"📋 АВТО (КУРАТОР): Студент {student.fio} (ID {student.id}) | "
                        f"Куратор: {mentor_name} (ID {held.mentor_id or 'не назначен'}) | "
                        f"Модулей: {held.modules_completed}/{held.total_modules} | "
                        f"Выплачено: {float(held.paid_amount):.2f} руб. | "
                        f"Холдировано: {held_amount:.2f} руб."
                    )
        
        # Подсчитываем по направлениям и типам
        manual_held = sum(info['total'] for info in manual_curators.values())
        auto_held = sum(info['total'] for info in auto_curators.values())
        director_manual_held = director_manual_info['total']
        director_auto_held = director_auto_info['total']
        
        # Проверка суммы
        calculated_total = manual_held + auto_held + director_manual_held + director_auto_held
        
        # Логируем итоги по кураторам
        held_logger.info("")
        held_logger.info("📊 ИТОГИ ПО КУРАТОРАМ РУЧНОГО НАПРАВЛЕНИЯ:")
        for mentor_id, info in sorted(manual_curators.items(), key=lambda x: x[1]['total'], reverse=True):
            held_logger.info(
                f"  👤 {info['name']} (ID {mentor_id or 'не назначен'}): "
                f"{len(info['students'])} студентов, "
                f"Итого холдировано: {info['total']:.2f} руб."
            )
            for stud_info in info['students']:
                held_logger.info(
                    f"    └─ {stud_info['student']} (ID {stud_info['student_id']}): "
                    f"{stud_info['amount']:.2f} руб. (модулей {stud_info['modules']}, выплачено {stud_info['paid']:.2f})"
                )
        
        held_logger.info("")
        held_logger.info("📊 ИТОГИ ПО КУРАТОРАМ АВТО НАПРАВЛЕНИЯ:")
        for mentor_id, info in sorted(auto_curators.items(), key=lambda x: x[1]['total'], reverse=True):
            held_logger.info(
                f"  👤 {info['name']} (ID {mentor_id or 'не назначен'}): "
                f"{len(info['students'])} студентов, "
                f"Итого холдировано: {info['total']:.2f} руб."
            )
            for stud_info in info['students']:
                held_logger.info(
                    f"    └─ {stud_info['student']} (ID {stud_info['student_id']}): "
                    f"{stud_info['amount']:.2f} руб. (модулей {stud_info['modules']}, выплачено {stud_info['paid']:.2f})"
                )
        
        # Логируем итоги по директорам
        if director_manual_info['total'] > 0:
            held_logger.info("")
            held_logger.info(f"💼 ИТОГИ ПО ДИРЕКТОРАМ РУЧНОГО НАПРАВЛЕНИЯ:")
            held_logger.info(f"  Итого холдировано: {director_manual_info['total']:.2f} руб. за {len(director_manual_info['students'])} студентов")
            for stud_info in director_manual_info['students']:
                held_logger.info(
                    f"    └─ {stud_info['student']} (ID {stud_info['student_id']}): "
                    f"{stud_info['amount']:.2f} руб. (30% от {stud_info['total_cost']:.2f} руб.)"
                )
        
        if director_auto_info['total'] > 0:
            held_logger.info("")
            held_logger.info(f"💼 ИТОГИ ПО ДИРЕКТОРАМ АВТО НАПРАВЛЕНИЯ:")
            held_logger.info(f"  Итого холдировано: {director_auto_info['total']:.2f} руб. за {len(director_auto_info['students'])} студентов")
            for stud_info in director_auto_info['students']:
                held_logger.info(
                    f"    └─ {stud_info['student']} (ID {stud_info['student_id']}): "
                    f"{stud_info['amount']:.2f} руб. (30% от {stud_info['total_cost']:.2f} руб.)"
                )
        
        held_logger.info("")
        held_logger.info(f"💰 ОБЩАЯ СУММА ХОЛДИРОВАНИЯ: {total_held_amount:.2f} руб.")
        held_logger.info(f"👥 КОЛИЧЕСТВО СТУДЕНТОВ: {students_count}")
        held_logger.info("=" * 80)
        
        response = (
            f"💰 Холдирование (резерв)\n\n"
            f"📅 Период: с 01.09.2025 по {current_date.strftime('%d.%m.%Y')}\n\n"
            f"📊 Общая сумма холдирования: {int(total_held_amount):,} руб.\n"
            f"👥 Количество студентов: {students_count}\n\n"
            f"📋 По направлениям:\n"
            f"  • Ручное направление (кураторы): {int(manual_held):,} руб.\n"
            f"  • Авто направление (кураторы): {int(auto_held):,} руб.\n"
        )
        
        # Добавляем директоров, если есть
        if director_manual_held > 0 or director_auto_held > 0:
            response += (
                f"  • Ручное направление (директора): {int(director_manual_held):,} руб.\n"
                f"  • Авто направление (директора): {int(director_auto_held):,} руб.\n"
            )
        
        # Проверка на расхождение
        if abs(calculated_total - total_held_amount) > 0.01:
            response += f"\n⚠️ Внимание: обнаружено расхождение!\n"
            response += f"   Сумма по направлениям: {int(calculated_total):,} руб.\n"
            response += f"   Общая сумма: {int(total_held_amount):,} руб.\n"
            response += f"   Разница: {int(abs(calculated_total - total_held_amount)):,} руб.\n"
        
        response += f"\n📝 Подробная информация записана в лог-файл held_amounts.log"
        
        await update.message.reply_text(
            response,
            reply_markup=ReplyKeyboardMarkup(
                [["🔙 Вернуться в меню"]],
                one_time_keyboard=True
            )
        )
        held_logger.info("✅ Запрос холдирования успешно обработан")
        logger.info("✅ Запрос холдирования успешно обработан")
        return STATISTICS_MENU
    
    except Exception as e:
        error_msg = f"❌ Критическая ошибка при обработке запроса холдирования: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Пытаемся записать в лог-файл, если он доступен
        try:
            held_logger = logging.getLogger('held_amounts')
            held_logger.error(error_msg)
            held_logger.error(traceback.format_exc())
        except:
            pass
        
        await update.message.reply_text(
            f"❌ Произошла ошибка при обработке запроса. Проверьте логи.\nОшибка: {str(e)}",
            reply_markup=ReplyKeyboardMarkup(
                [["🔙 Вернуться в меню"]],
                one_time_keyboard=True
            )
        )
        return STATISTICS_MENU
