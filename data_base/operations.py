import random

from data_base.db import session
from data_base.models import Student, Mentor, Payment
from datetime import datetime, timedelta
from sqlalchemy import or_, func


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
    Возвращает None, если студент не найден или произошла ошибка.
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


