import random

from typing import Optional

from data_base.db import session
from data_base.models import Student, Mentor, Payment, CareerConsultant, UnitEconomics
from datetime import datetime, timedelta
from sqlalchemy import or_, func
from sqlalchemy import desc


# Функции для работы с карьерными консультантами
def get_all_career_consultants():
    """Возвращает список всех активных карьерных консультантов."""
    return session.query(CareerConsultant).filter(CareerConsultant.is_active == True).all()


def get_career_consultant_by_telegram(telegram):
    """Находит карьерного консультанта по Telegram."""
    return session.query(CareerConsultant).filter(
        CareerConsultant.telegram == telegram,
        CareerConsultant.is_active == True
    ).first()


def get_students_by_career_consultant(consultant_id):
    """Возвращает всех студентов, закрепленных за карьерным консультантом."""
    return session.query(Student).filter(
        Student.career_consultant_id == consultant_id
    ).all()


def assign_student_to_career_consultant(student_id, consultant_id):
    """Закрепляет студента за карьерным консультантом."""
    from datetime import date
    
    student = session.query(Student).get(student_id)
    if not student:
        raise ValueError("Студент не найден.")
    
    consultant = session.query(CareerConsultant).get(consultant_id)
    if not consultant:
        raise ValueError("Карьерный консультант не найден.")
    
    student.career_consultant_id = consultant_id
    # Устанавливаем дату взятия студента в работу, если она еще не установлена
    if not student.consultant_start_date:
        student.consultant_start_date = date.today()
    session.commit()
    return student


def calculate_base_income_and_salary(payment_amount, commission_string, curator_percent):
    """
    Рассчитывает базовый доход (100% ЗП ученика) и зарплату куратора/КК от комиссионного платежа.
    
    Алгоритм:
    1. Извлекает X (количество месяцев) и Y (процент от ЗП) из commission_string
    2. Вычисляет общий процент долга: X * Y
    3. Находит базовый доход: Платеж / (X * Y / 100)
    4. Рассчитывает зарплату: Базовый доход * curator_percent
    
    Args:
        payment_amount: Фактическая сумма платежа (включает наценку бизнеса)
        commission_string: Строка в формате "X, Y" или "X,Y" (X - количество месяцев, Y - процент от ЗП)
        curator_percent: Процент куратора/КК (0.20 для кураторов, 0.10 или 0.20 для КК)
    
    Returns:
        tuple: (базовый_доход, зарплата_куратора) или (None, None) при ошибке
    """
    try:
        if not commission_string:
            return None, None
        
        # Обрабатываем формат "X, Y" или "X,Y" (с пробелом или без)
        commission_string = commission_string.strip()
        if ", " in commission_string:
            parts = commission_string.split(", ")
        elif "," in commission_string:
            parts = commission_string.split(",")
        else:
            return None, None
        
        if len(parts) != 2:
            return None, None
        
        # Извлекаем X (количество месяцев) и Y (процент от ЗП)
        X = int(parts[0].strip())
        Y_str = parts[1].strip().replace("%", "").replace(" ", "")
        Y = int(Y_str)
        
        # Шаг 1: Рассчитываем общий процент долга
        total_percent = X * Y
        
        # Шаг 1.3: Конвертируем в долю
        percent_share = total_percent / 100.0
        
        if percent_share == 0:
            return None, None
        
        # Шаг 2: Находим базовый доход (100% ЗП)
        base_income = float(payment_amount) / percent_share
        
        # Шаг 3: Рассчитываем зарплату куратора/КК
        curator_salary = base_income * curator_percent
        
        return round(base_income, 2), round(curator_salary, 2)
        
    except (ValueError, ZeroDivisionError, AttributeError) as e:
        return None, None


def calculate_career_consultant_salary(consultant_id, start_date, end_date):
    """
    Рассчитывает зарплату карьерного консультанта.
    10% или 20% от базового дохода (100% ЗП ученика) платежей со статусом "Комиссия".
    """
    # Получаем всех студентов, закрепленных за консультантом
    students = get_students_by_career_consultant(consultant_id)
    student_ids = [student.id for student in students]
    
    if not student_ids:
        return 0
    
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
    
    salary = 0
    for payment in commission_payments:
        student = session.query(Student).filter(Student.id == payment.student_id).first()
        if not student:
            continue
        
        # Определяем процент КК
        if student and student.consultant_start_date:
            # Если КК взял студента после 18.11.2025 и КК с ID=1, то 20%, иначе 10%
            if student.consultant_start_date >= COMMISSION_CHANGE_DATE and student.career_consultant_id == 1:
                consultant_percent = 0.2
            else:
                consultant_percent = 0.1
        else:
            # Если дата не установлена, используем старую ставку 10%
            consultant_percent = 0.1
        
        # Используем новую формулу расчета от базового дохода
        base_income, curator_salary = calculate_base_income_and_salary(
            float(payment.amount),
            student.commission,
            consultant_percent
        )
        
        if curator_salary is not None:
            salary += curator_salary
        else:
            # Fallback на старую формулу, если не удалось рассчитать по новой
            salary += float(payment.amount) * consultant_percent
    
    return round(salary, 2)


def get_latest_unit_economics(product_code: str = "default") -> Optional[UnitEconomics]:
    return (
        session.query(UnitEconomics)
        .filter(UnitEconomics.product_code == product_code)
        .order_by(desc(UnitEconomics.period_end), desc(UnitEconomics.period_start), desc(UnitEconomics.id))
        .first()
    )


def get_unit_economics(period_start, period_end, product_code: str = "default") -> Optional[UnitEconomics]:
    return (
        session.query(UnitEconomics)
        .filter(
            UnitEconomics.period_start == period_start,
            UnitEconomics.period_end == period_end,
            UnitEconomics.product_code == product_code,
        )
        .first()
    )


# Добавление нового студента
# def add_student(fio, telegram, start_date, training_type, total_cost, payment_amount, fully_paid, commission):
#     mentor_id = assign_mentor(training_type)
#     try:
#
#         student = Student(
#             fio=fio,
#             telegram=telegram,
#             start_date=start_date,
#             training_type=training_type,
#             total_cost=total_cost,
#             payment_amount=payment_amount,
#             fully_paid=fully_paid,
#             commission=commission,
#             mentor_id=mentor_id
#         )
#         session.add(student)
#         session.commit()
#     except Exception as e:
#         session.rollback()


# Получение всех студентов
def get_all_students():
    """Возвращает список всех студентов."""
    return session.query(Student).all()


def get_student_by_fio_or_telegram(value):
    """
    Ищет студента по ФИО или Telegram.
    """
    try:
        student = session.query(Student).filter(
            (Student.fio == value) | (Student.telegram == value)
        ).first()
        if not student:
            return None
        return student
    except Exception as e:
        return None


# Обновление данных студента
def update_student(student_id, updates):
    student = session.query(Student).get(student_id)
    if not student:
        raise ValueError("Студент не найден.")
    for key, value in updates.items():
        setattr(student, key, value)
    session.commit()


# Удаление студента
def delete_student(student_id):
    """Удаляет студента из базы данных."""
    student = session.query(Student).get(student_id)
    if student:
        session.delete(student)
        session.commit()


# Получение статистики
def get_general_statistics():
    """Возвращает общую статистику."""
    students = session.query(Student).all()
    total_students = len(students)
    fully_paid = sum(1 for student in students if student.fully_paid == "Да")
    training_types = {}

    for student in students:
        training_types[student.training_type] = training_types.get(student.training_type, 0) + 1

    return {
        "total_students": total_students,
        "fully_paid": fully_paid,
        "training_types": training_types
    }


# Получение студентов по периоду
def get_students_by_period(start_date, end_date):
    """Возвращает студентов, зарегистрированных в определённый период."""
    return session.query(Student).filter(
        Student.start_date.between(start_date, end_date)
    ).all()


# Проверка уведомлений по звонкам
def get_students_with_no_calls():
    """Возвращает студентов, которые давно не звонили."""
    twenty_days_ago = datetime.now() - timedelta(days=20)
    # Фильтр студентов без звонков и с последним звонком более 20 дней назад
    return session.query(Student).filter(
        or_(
            Student.last_call_date == None,  # Студенты без даты звонка
            func.to_date(Student.last_call_date, 'DD.MM.YYYY') < twenty_days_ago
            # Студенты, звонившие более 20 дней назад
        )
    ).all()


# Проверка задолженностей по оплате
def get_students_with_unpaid_payment():
    """Возвращает студентов, которые обучаются больше месяца, не оплатили полностью курс и не делали доплат за последний месяц."""

    # Дата месяц назад
    one_month_ago = datetime.now() - timedelta(days=30)

    # Запрос студентов, удовлетворяющих условиям
    students = session.query(Student).filter(
        Student.start_date <= one_month_ago,  # Обучаются больше месяца
        Student.training_status.in_(["Учится", "Устроился"]),  # Статус обучения
        Student.fully_paid == "Нет"  # Не полностью оплачено
    ).all()

    # Фильтруем тех, кто **не делал доплат за последний месяц**
    unpaid_students = []
    for student in students:
        last_payment = session.query(func.max(Payment.payment_date)).filter(
            Payment.student_id == student.id,
            Payment.comment == "Доплата",
            Payment.payment_date >= one_month_ago  # Ищем доплаты за последний месяц
        ).scalar()

        if not last_payment:  # Если доплат за последний месяц **не было**, добавляем в список
            unpaid_students.append(student)

    return unpaid_students


def get_students_by_training_type(training_type):
    """
    Возвращает студентов по типу обучения.

    Args:
        training_type (str): Тип обучения (например, "Ручное тестирование", "Автотестирование", "Фуллстек").

    Returns:
        list: Список студентов с указанным типом обучения.
    """
    return session.query(Student).filter(Student.training_type == training_type).all()


def count_completed_modules(student_id, direction):
    """
    Подсчитывает количество сданных модулей для студента фуллстек по направлению.
    
    Args:
        student_id: ID студента
        direction: "manual" для ручного направления или "auto" для авто
        
    Returns:
        int: Количество уникальных сданных модулей
    """
    from data_base.models import FullstackTopicAssign
    from sqlalchemy import func
    
    if direction == "manual":
        # Считаем уникальные ручные темы
        count = session.query(func.count(func.distinct(FullstackTopicAssign.topic_manual))).filter(
            FullstackTopicAssign.student_id == student_id,
            FullstackTopicAssign.topic_manual.isnot(None)
        ).scalar() or 0
    elif direction == "auto":
        # Считаем уникальные авто темы
        count = session.query(func.count(func.distinct(FullstackTopicAssign.topic_auto))).filter(
            FullstackTopicAssign.student_id == student_id,
            FullstackTopicAssign.topic_auto.isnot(None)
        ).scalar() or 0
    else:
        return 0
    
    return count


def calculate_held_amount(student_id, direction, mentor_id=None, is_director=False):
    """
    Рассчитывает холдирование для студента фуллстек по направлению.
    
    Args:
        student_id: ID студента
        direction: "manual" или "auto"
        mentor_id: ID куратора или директора (может быть None)
        is_director: True если это директор направления, False если куратор
        
    Returns:
        dict: {
            'potential_amount': потенциальная сумма,
            'paid_amount': выплаченная сумма,
            'held_amount': холдирование,
            'modules_completed': количество сданных модулей,
            'total_modules': всего модулей
        }
    """
    from config import Config
    from data_base.models import Student
    
    student = session.query(Student).filter(Student.id == student_id).first()
    if not student or student.training_type != "Фуллстек":
        return None
    
    # Для директоров - 30% от total_cost студента
    if is_director:
        potential_amount = float(student.total_cost) * Config.DIRECTOR_RESERVE_PERCENT
        # Для директоров выплата не зависит от модулей (пока считаем как 0)
        paid_amount = 0.0
        held_amount = potential_amount
        modules_completed = 0
        total_modules = 0
    else:
        # Для кураторов - 20% от стоимости направления
        if direction == "manual":
            potential_amount = Config.FULLSTACK_MANUAL_COURSE_COST * Config.MANUAL_CURATOR_RESERVE_PERCENT
            total_modules = Config.MANUAL_MODULES_TOTAL
        elif direction == "auto":
            potential_amount = Config.FULLSTACK_AUTO_COURSE_COST * Config.AUTO_CURATOR_RESERVE_PERCENT
            total_modules = Config.AUTO_MODULES_TOTAL
        else:
            return None
        
        # Считаем сданные модули
        modules_completed = count_completed_modules(student_id, direction)
        
        # Рассчитываем выплаченную сумму
        if total_modules > 0:
            paid_amount = (modules_completed / total_modules) * potential_amount
        else:
            paid_amount = 0.0
        
        # Холдирование
        held_amount = max(0.0, potential_amount - paid_amount)  # Не может быть отрицательным
    
    return {
        'potential_amount': round(potential_amount, 2),
        'paid_amount': round(paid_amount, 2),
        'held_amount': round(held_amount, 2),
        'modules_completed': modules_completed,
        'total_modules': total_modules
    }


# def assign_mentor(training_type):
#     """
#     Назначает ментора в зависимости от направления:
#     - Фуллстек → Всегда ментор с ID = 1
#     - Автотестирование → 30% ID = 3, 70% другие менторы с этим направлением
#     - Ручное тестирование → 30% ID = 1, 70% другие менторы с этим направлением
#     """
#     print(f"📌 Назначение ментора для курса: {training_type}")
#
#     # Фуллстек всегда получает ментора с ID = 1
#     if training_type == "Фуллстек":
#         print("💼 Назначен ментор для Фуллстек (ID: 1)")
#         return 1
#
#     # Загружаем всех менторов для других направлений
#     mentors = session.query(Mentor).all()
#     print(f"👥 Все менторы: {[m.id for m in mentors]}")
#
#     if training_type == "Автотестирование":
#         direction = "Автотестирование"
#         main_mentor_id = 3  # Главный ментор для автотестирования
#     else:
#         direction = "Ручное тестирование"
#         main_mentor_id = 1  # Главный ментор для ручного тестирования
#
#     # Фильтруем менторов по направлению
#     mentors_in_direction = [m for m in mentors if m.direction == direction]
#
#     # Если нет менторов в этом направлении, возвращаем None
#     if len(mentors_in_direction) == 0:
#         print("❌ Нет менторов для этого направления!")
#         return None
#
#     main_mentor = next((m for m in mentors_in_direction if m.id == main_mentor_id), None)
#     other_mentors = [m for m in mentors_in_direction if m.id != main_mentor_id]
#
#     print(f"💼 Главный ментор (ID: {main_mentor.id if main_mentor else 'None'})")
#     print(f"💼 Остальные менторы: {[m.id for m in other_mentors]}")
#
#     # Если только один ментор — возвращаем его
#     if not main_mentor or len(mentors_in_direction) == 1:
#         return mentors_in_direction[0].id
#
#     # 30% главный ментор, 70% распределяем между остальными
#     mentor_id = random.choices(
#         population=[main_mentor.id] + [m.id for m in other_mentors],
#         weights=[30] + [70 / len(other_mentors)] * len(other_mentors),
#         k=1
#     )[0]
#
#     print(f"🎯 Назначен ментор (ID: {mentor_id})")
#     return mentor_id
# data_base/operations.py

def get_mentor_by_telegram(telegram: str):
    """Находит активного ментора по Telegram."""
    # Убедитесь, что формат (с @ или без) совпадает с тем, как вы записываете их в базу
    return session.query(Mentor).filter(Mentor.telegram == telegram).first()