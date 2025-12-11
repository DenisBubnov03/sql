# admin_commission_manager.py
from sqlalchemy.orm import Session
from data_base.models import Student, CuratorCommission

# ID Директоров (проверьте, что они совпадают с реальными в БД)
DIRECTOR_MANUAL_ID = 1
DIRECTOR_AUTO_ID = 3


class AdminCommissionManager:
    """
    Класс рассчитывает и фиксирует 'Потолок' (Общий Долг) перед менторами и директорами.
    Запускается 1 раз при трудоустройстве.
    """

    def calculate_and_save_debts(self, session: Session, student_id: int):
        student = session.query(Student).filter_by(id=student_id).first()
        if not student or not student.salary:
            return "❌ Ошибка: Нет студента или не указана ЗП."

        salary = float(student.salary)

        # Определяем, фуллстек это или нет
        # (Простая логика: если есть оба ментора. Можете заменить на проверку training_type)
        is_fullstack = (student.mentor_id is not None) and (student.auto_mentor_id is not None)

        # Словарь для накопления долгов: {mentor_id: amount}
        debts_map = {}

        # ==========================================
        # 1. ЛОГИКА ФУЛЛСТЕК (FULLSTACK)
        # ==========================================
        if is_fullstack:

            # --- А. Ручная часть ---
            if student.mentor_id:
                if student.mentor_id == DIRECTOR_MANUAL_ID:
                    # Директор ведет сам -> 30%
                    self._add_debt(debts_map, DIRECTOR_MANUAL_ID, salary * 0.30)
                else:
                    # Обычный ментор -> 15% + Директор -> 7.5%
                    self._add_debt(debts_map, student.mentor_id, salary * 0.15)
                    self._add_debt(debts_map, DIRECTOR_MANUAL_ID, salary * 0.075)

            # --- Б. Авто часть ---
            if student.auto_mentor_id:
                if student.auto_mentor_id == DIRECTOR_AUTO_ID:
                    # Директор ведет сам -> 30%
                    self._add_debt(debts_map, DIRECTOR_AUTO_ID, salary * 0.30)
                else:
                    # Обычный ментор -> 15% + Директор -> 7.5%
                    self._add_debt(debts_map, student.auto_mentor_id, salary * 0.15)
                    self._add_debt(debts_map, DIRECTOR_AUTO_ID, salary * 0.075)

        # ==========================================
        # 2. ЛОГИКА ОБЫЧНОГО ОБУЧЕНИЯ
        # ==========================================
        else:
            # Определяем активного ментора (он будет либо в mentor_id, либо в auto_mentor_id)
            active_mentor_id = student.mentor_id or student.auto_mentor_id

            # Определяем, кто директор этого направления
            if student.mentor_id:
                director_id = DIRECTOR_MANUAL_ID
            else:
                director_id = DIRECTOR_AUTO_ID

            if active_mentor_id:
                if active_mentor_id == director_id:
                    # Директор ведет сам -> 30%
                    self._add_debt(debts_map, director_id, salary * 0.30)
                else:
                    # Обычный ментор -> 20%
                    self._add_debt(debts_map, active_mentor_id, salary * 0.20)
                    # Бонус Директору -> 10%
                    self._add_debt(debts_map, director_id, salary * 0.10)

        # ==========================================
        # 3. ЗАПИСЬ В БД
        # ==========================================
        count = 0
        for m_id, amount in debts_map.items():
            if amount > 0:
                self._create_or_update_record(session, student_id, m_id, amount)
                count += 1

        # session.commit() вызывается во внешнем коде
        return f"✅ Создано записей о долгах: {count}"

    def _add_debt(self, debts_map, mentor_id, amount):
        """Суммирует долг, если ID встречаются несколько раз"""
        if mentor_id in debts_map:
            debts_map[mentor_id] += amount
        else:
            debts_map[mentor_id] = amount

    def _create_or_update_record(self, session, student_id, mentor_id, total):
        """Пишет в таблицу CuratorCommission"""
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