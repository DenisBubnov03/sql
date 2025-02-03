from data_base import Session
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


from datetime import datetime

def update_student_data(identifier, new_payment, payment_date):
    """
    Обновляет данные студента, учитывая доплату и дату платежа.

    Args:
        identifier (str | int): ID, ФИО или Telegram студента.
        new_payment (float): Сумма доплаты.
        payment_date (datetime.date): Дата платежа.

    Returns:
        bool: True, если обновление успешно, иначе False.
    """
    try:
        # Определяем, является ли идентификатор числом (ID) или строкой (ФИО/Telegram)
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            student = session.query(Student).filter(Student.id == int(identifier)).first()
        else:
            student = session.query(Student).filter(
                (Student.fio == identifier) | (Student.telegram == identifier)
            ).first()

        if not student:
            return False

        # Проверяем, был ли платеж в этом же месяце
        if student.extra_payment_date and student.extra_payment_date.strftime("%m.%Y") == payment_date.strftime("%m.%Y"):
            # Если платеж в этом месяце, суммируем доплату
            student.extra_payment_amount += new_payment
        else:
            # Если новый месяц, заменяем сумму доплаты и дату
            student.extra_payment_amount = new_payment
            student.extra_payment_date = payment_date

        # Обновляем общую сумму оплат
        updated_payment = student.payment_amount + new_payment

        # Проверяем, не превышает ли оплата стоимость курса
        if updated_payment > student.total_cost:
            session.rollback()
            raise ValueError(
                f"Ошибка: общая сумма оплаты ({updated_payment:.2f} руб.) "
                f"превышает стоимость обучения ({student.total_cost:.2f} руб.)."
            )

        student.payment_amount = updated_payment

        # Проверяем, полностью ли оплачен курс
        student.fully_paid = "Да" if student.payment_amount >= student.total_cost else "Нет"

        session.commit()
        return True
    except Exception as e:
        session.rollback()
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
