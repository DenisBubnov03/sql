# admin_commission_manager.py
from sqlalchemy.orm import Session
from data_base.models import Student, CuratorCommission
import config

DIRECTOR_MANUAL_ID = 1
DIRECTOR_AUTO_ID = 3


class AdminCommissionManager:
    """
    Класс рассчитывает и фиксирует 'Потолок' (Общий Долг) перед менторами и директорами.
    Запускается 1 раз при трудоустройстве.
    """

    def calculate_and_save_debts(self, session: Session, student_id: int):
        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return "❌ Ошибка: Студент не найден."

        # 1. ОПРЕДЕЛЯЕМ БАЗУ ДЛЯ РАСЧЕТА (ЗП или Стоимость Курса)
        is_fullstack = (student.mentor_id is not None) and (student.auto_mentor_id is not None)

        # Логика выбора суммы:
        if not is_fullstack and student.total_cost and float(student.total_cost) > 0:
            # Если обычный студент и есть цена курса -> считаем от Цены Курса
            base_amount = float(student.total_cost)
            calculation_source = f"Стоимости курса ({base_amount})"
        elif student.salary and float(student.salary) > 0:
            # Иначе (Фуллстек или нет цены) -> считаем от Зарплаты
            base_amount = float(student.salary)
            calculation_source = f"Зарплаты ({base_amount})"
        else:
            return "❌ Ошибка: Не указана ни ЗП, ни Стоимость курса (total_cost)."

        debts_map = {}

        # ==========================================
        # 2. ЛОГИКА ФУЛЛСТЕК (Остается на базе ЗП, т.к. is_fullstack=True попадет в ветку salary)
        # ==========================================
        if is_fullstack:
            # ... (логика фуллстека без изменений, она обычно от ЗП) ...

            # А. Ручная часть
            if student.mentor_id:
                if student.mentor_id == DIRECTOR_MANUAL_ID:
                    self._add_debt(debts_map, DIRECTOR_MANUAL_ID, base_amount * 0.30)
                else:
                    self._add_debt(debts_map, student.mentor_id, base_amount * 0.15)
                    self._add_debt(debts_map, DIRECTOR_MANUAL_ID, base_amount * 0.06)  # 6% бонус

            # Б. Авто часть
            if student.auto_mentor_id:
                if student.auto_mentor_id == DIRECTOR_AUTO_ID:
                    self._add_debt(debts_map, DIRECTOR_AUTO_ID, base_amount * 0.30)
                else:
                    self._add_debt(debts_map, student.auto_mentor_id, base_amount * 0.15)
                    self._add_debt(debts_map, DIRECTOR_AUTO_ID, base_amount * 0.06)  # 6% бонус

        # ==========================================
        # 3. ЛОГИКА ОБЫЧНОГО ОБУЧЕНИЯ (Теперь может быть от total_cost)
        # ==========================================
        else:
            active_mentor_id = student.mentor_id or student.auto_mentor_id

            # Кто директор?
            if student.mentor_id:
                director_id = DIRECTOR_MANUAL_ID
            else:
                director_id = DIRECTOR_AUTO_ID

            if active_mentor_id:
                if active_mentor_id == director_id:
                    # Директор ведет сам -> 30%
                    self._add_debt(debts_map, director_id, base_amount * 0.30)
                else:
                    # Обычный ментор -> 20%
                    self._add_debt(debts_map, active_mentor_id, base_amount * 0.20)
                    # Бонус Директору -> 10%
                    self._add_debt(debts_map, director_id, base_amount * 0.10)

        # ==========================================
        # 4. ЗАПИСЬ В БД
        # ==========================================
        count = 0
        for m_id, amount in debts_map.items():
            if amount > 0:
                self._create_or_update_record(session, student_id, m_id, amount)
                count += 1

        return f"✅ Расчет выполнен от {calculation_source}. Создано записей: {count}"

    def _add_debt(self, debts_map, mentor_id, amount):
        if mentor_id in debts_map:
            debts_map[mentor_id] += amount
        else:
            debts_map[mentor_id] = amount

    def _create_or_update_record(self, session, student_id, mentor_id, total):
        rec = session.query(CuratorCommission).filter_by(
            student_id=student_id, curator_id=mentor_id
        ).first()

        if rec:
            rec.total_amount = total
        else:
            new_rec = CuratorCommission(
                student_id=student_id,
                curator_id=mentor_id,
                total_amount=total,
                paid_amount=0.0,
                payment_id=None
            )
            session.add(new_rec)