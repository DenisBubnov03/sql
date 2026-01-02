from datetime import datetime, date, time

from sqlalchemy import func

from data_base.db import session as db_session  # Или просто session, зависит от вашего импорта
from data_base.models import Student, CuratorCommission, Salary, Mentor, SalaryKK  # Добавили Salary

DIRECTOR_ID_MANUAL = 1
DIRECTOR_ID_AUTO = 3


class SalaryManager:
    # ... (здесь могут быть другие методы класса, если они есть) ...

    # =======================================================================
    # ЛОГИКА ИНИЦИАЛИЗАЦИИ 10% БОНУСА ДИРЕКТОРА (ДОЛГ + ЗАПИСЬ В SALARY)
    # =======================================================================

    def init_director_bonus_commission(self, session, student: Student, payment_id: int):
        """
        1. Создает запись о 10% долге перед Директором (CuratorCommission).
        2. Создает запись в таблице начислений (Salary).

        ВАЖНО: payment_id обязателен, так как в таблице salary это поле NOT NULL.
        """
        # 1. Проверка типа обучения и определение директора
        training_type = student.training_type.strip().lower() if student.training_type else ""
        director_id = None
        mentor_id_field = None
        direction_name = None

        if "ручное" in training_type:
            director_id = DIRECTOR_ID_MANUAL  # ID = 1
            mentor_id_field = student.mentor_id
            direction_name = "Ручное тестирование"
        elif "авто" in training_type:
            director_id = DIRECTOR_ID_AUTO  # ID = 3
            mentor_id_field = student.auto_mentor_id
            direction_name = "Автотестирование"
        elif "фуллстек" in training_type:
            # Для фуллстека можно добавить логику здесь, если нужно
            return None
        else:
            return None

            # 2. Проверка: Директор не должен получать бонус за самого себя (если он сам куратор студента)
        if director_id == mentor_id_field:
            print(f"Warn: Director {director_id} is also the curator. Skipping bonus.")
            return None

        # 3. Проверка стоимости курса
        if not student.total_cost or float(student.total_cost) <= 0:
            print(f"Warn: Student has no total_cost. Skipping bonus.")
            return None

        # 4. Проверка наличия payment_id (критично для таблицы Salary)
        if not payment_id:
            print(f"Error: payment_id is required for creating Salary record! Skipping bonus init.")
            return None

        # 5. Расчет 10% суммы
        bonus_percent = 0.10
        total_commission_value = float(student.total_cost) * bonus_percent

        # 6. Проверка дублей (чтобы не начислить дважды за одного студента)
        # Проверяем по таблице долгов
        existing_debt = session.query(CuratorCommission).filter_by(
            student_id=student.id,
            curator_id=director_id
        ).first()

        if existing_debt:
            print(f"Warn: Bonus debt already exists for student {student.id}. Skipping.")
            return existing_debt

        # # 7. Создаем запись об ОБЩЕМ ДОЛГЕ (CuratorCommission)
        # new_commission_debt = CuratorCommission(
        #     student_id=student.id,
        #     curator_id=director_id,
        #     payment_id=payment_id,
        #     total_amount=total_commission_value,
        #     paid_amount=0.0
        # )
        # session.add(new_commission_debt)

        # 8. Создаем запись в НАЧИСЛЕНИЯХ (Salary)
        # Используем вашу модель Salary
        new_salary_record = Salary(
            payment_id=payment_id,
            mentor_id=director_id,
            calculated_amount=total_commission_value,
            is_paid=False,
            comment=f"10% бонус за студента {student.telegram} ({direction_name})"
        )
        session.add(new_salary_record)

        return new_salary_record

    def get_total_turnover(session, start_val, end_val):
        """
        Считает общую сумму начислений, гарантированно захватывая весь последний день.
        """
        # 1. Гарантируем, что у нас объекты datetime с правильным временем
        if isinstance(start_val, date) and not isinstance(start_val, datetime):
            start_dt = datetime.combine(start_val, time.min)
        else:
            start_dt = start_val

        if isinstance(end_val, date) and not isinstance(end_val, datetime):
            end_dt = datetime.combine(end_val, time.max)
        else:
            # Если это уже datetime, но время 00:00:00, лучше тоже сделать time.max
            end_dt = datetime.combine(end_val.date(), time.max)

        # 2. Считаем сумму по менторам
        mentors_total = session.query(func.sum(Salary.calculated_amount)).filter(
            Salary.date_calculated >= start_dt,
            Salary.date_calculated <= end_dt
        ).scalar() or 0.0

        # 3. Считаем сумму по КК
        kk_total = session.query(func.sum(SalaryKK.calculated_amount)).filter(
            SalaryKK.date_calculated >= start_dt,
            SalaryKK.date_calculated <= end_dt
        ).scalar() or 0.0

        return float(mentors_total), float(kk_total)