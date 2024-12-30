from data_base.db import session
from data_base.models import Student


def add_student(fio, telegram, start_date, course_type, total_payment, paid_amount, fully_paid, commission):
    """
    Добавляет нового студента в базу данных.

    Args:
        fio (str): ФИО студента.
        telegram (str): Telegram студента.
        start_date (str): Дата начала обучения.
        course_type (str): Тип обучения.
        total_payment (float): Стоимость курса.
        paid_amount (float): Оплаченная сумма.
        fully_paid (str): Полностью оплачено ("Да"/"Нет").
        commission (str): Информация о комиссии.

    Returns:
        None
    """
    try:
        student = Student(
            fio=fio,
            telegram=telegram,
            start_date=start_date,
            training_type=course_type,
            total_cost=total_payment,
            payment_amount=paid_amount,
            fully_paid=fully_paid,
            commission=commission,
            commission_paid=0,
            training_status="Учится"
        )
        session.add(student)
        session.commit()
    except Exception as e:
        raise RuntimeError(f"Ошибка добавления студента: {e}")


def delete_student(identifier):
    """
    Удаляет студента по ФИО или Telegram из базы данных.

    Args:
        identifier (str): ФИО или Telegram студента.

    Returns:
        bool: True, если студент удалён, иначе False.
    """
    try:
        student = session.query(Student).filter((Student.fio == identifier) | (Student.telegram == identifier)).first()
        if student:
            session.delete(student)
            session.commit()
            return True
        return False
    except Exception as e:
        raise RuntimeError(f"Ошибка удаления студента: {e}")


def update_student_data(identifier, field, new_value):
    """
    Обновляет данные студента в базе данных.

    Args:
        identifier (str): ФИО или Telegram студента.
        field (str): Поле, которое нужно обновить.
        new_value (str): Новое значение.

    Returns:
        bool: True, если обновление успешно, иначе False.
    """
    try:
        student = session.query(Student).filter((Student.fio == identifier) | (Student.telegram == identifier)).first()
        if student and hasattr(student, field):
            setattr(student, field, new_value)
            session.commit()
            return True
        return False
    except Exception as e:
        raise RuntimeError(f"Ошибка обновления данных студента: {e}")


def get_all_students():
    """
    Возвращает список всех студентов.

    Returns:
        list: Список студентов в виде объектов.
    """
    try:
        return session.query(Student).all()
    except Exception as e:
        raise RuntimeError(f"Ошибка получения списка студентов: {e}")
