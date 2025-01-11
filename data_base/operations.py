from data_base.db import session
from data_base.models import Student
from datetime import datetime, timedelta
from sqlalchemy import or_, func

# Добавление нового студента
def add_student(fio, telegram, start_date, training_type, total_cost, payment_amount, fully_paid, commission):
    try:
        student = Student(
            fio=fio,
            telegram=telegram,
            start_date=start_date,
            training_type=training_type,
            total_cost=total_cost,
            payment_amount=payment_amount,
            fully_paid=fully_paid,
            commission=commission
        )
        session.add(student)
        session.commit()
    except Exception as e:
        session.rollback()


# Получение всех студентов
def get_all_students():
    """Возвращает список всех студентов."""
    return session.query(Student).all()


# Поиск студента по ФИО или Telegram
def get_student_by_fio_or_telegram(value):
    """
    Ищет студента по ФИО или Telegram.
    """
    try:
        return session.query(Student).filter(
            (Student.fio == value) | (Student.telegram == value)
        ).first()
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
            func.to_date(Student.last_call_date, 'DD.MM.YYYY') < twenty_days_ago  # Студенты, звонившие более 20 дней назад
        )
    ).all()



# Проверка задолженностей по оплате
def get_students_with_unpaid_payment():
    """Возвращает студентов с неоплаченной комиссией."""
    return session.query(Student).filter(
        func.coalesce(Student.total_cost, 0) > func.coalesce(Student.payment_amount, 0)
    ).all()
def get_students_by_training_type(training_type):
    """
    Возвращает студентов по типу обучения.

    Args:
        training_type (str): Тип обучения (например, "Ручное тестирование", "Автотестирование", "Фуллстек").

    Returns:
        list: Список студентов с указанным типом обучения.
    """
    return session.query(Student).filter(Student.training_type == training_type).all()

