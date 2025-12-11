from data_base import Session
from data_base.models import Student

DIRECTOR_ID_MANUAL = 1
DIRECTOR_ID_AUTO = 3


class SalaryManager:
# =======================================================================
    # 3. ЛОГИКА ИНИЦИАЛИЗАЦИИ 10% БОНУСА ДИРЕКТОРА
    # =======================================================================

    def init_director_bonus_commission(self, session: Session, student: Student):
        """
        Создает запись о 10% долге перед Директором при добавлении нового студента.
        Применяется только для Ручного и Автотестирования, если Директор не является куратором.
        """
        # 1. Проверка типа обучения и директора
        training_type = student.training_type.strip().lower() if student.training_type else ""
        director_id = None
        mentor_id_field = None
        direction_name = None

        if training_type == "ручное тестирование":
            director_id = DIRECTOR_ID_MANUAL  # ID = 1
            mentor_id_field = student.mentor_id
            direction_name = "Ручное тестирование"
        elif training_type == "автотестирование":
            director_id = DIRECTOR_ID_AUTO  # ID = 3
            mentor_id_field = student.auto_mentor_id
            direction_name = "Автотестирование"
        elif training_type == "фуллстек":
            # Для фуллстека бонус не начисляется при добавлении (по условию)
            return None
        else:
            return None  # Неизвестный тип

        # 2. Проверка, что Директор не является куратором студента
        if director_id == mentor_id_field:
            print(
                f"Warn: Director {director_id} is also the curator for student {student.telegram}. Skipping 10% bonus init.")
            return None

        # 3. Проверка стоимости
        if not student.total_cost or float(student.total_cost) <= 0:
            print(f"Warn: Student {student.telegram} has no total_cost. Skipping 10% bonus init.")
            return None

        # 4. Расчет 10% комиссии
        bonus_percent = 0.10
        total_commission_value = float(student.total_cost) * bonus_percent

        # 5. Проверка: нет ли уже такой записи
        from data_base.models import CuratorCommission
        existing_debt = session.query(CuratorCommission).filter_by(
            student_id=student.id,
            curator_id=director_id
        ).first()

        if existing_debt:
            print(
                f"Warn: Director bonus already exists for student {student.telegram} and director {director_id}. Skipping init.")
            return existing_debt

        # 6. Создаем новую запись в CuratorCommission
        new_commission = CuratorCommission(
            student_id=student.id,
            curator_id=director_id,
            payment_id=None,
            total_amount=total_commission_value,
            paid_amount=0.0
        )
        session.add(new_commission)
        print(
            f"Info: Initialized 10% director bonus ({total_commission_value:.2f}₽) for student {student.telegram} ({direction_name})")
        return new_commission
