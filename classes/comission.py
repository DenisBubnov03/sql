import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session
from data_base.models import Student, CuratorCommission, ManualProgress, AutoProgress, Payout, SalaryKK

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DIRECTOR_MANUAL_ID = 1
DIRECTOR_AUTO_ID = 3


class AdminCommissionManager:
    # 1. СТАВКИ ДЛЯ SOLO (Обычный ученик)
    SOLO_CURATOR_RATE = 0.20  # 20%
    SOLO_DIRECTOR_PASSIVE = 0.10  # 10% (Фикса)
    SOLO_DIRECTOR_ACTIVE = 0.30  # 30% (За темы)

    # 2. СТАВКИ ДЛЯ FULLSTACK
    FULL_CURATOR_RATE = 0.15  # 15%
    FULL_DIRECTOR_PASSIVE = 0.075  # 7.5% (Фикса)
    FULL_DIRECTOR_ACTIVE = 0.30  # 30% (За темы)

    MANUAL_FIELDS = [
        'm1_mentor_id', 'm2_1_2_2_mentor_id', 'm2_3_3_1_mentor_id',
        'm3_2_mentor_id', 'm3_3_mentor_id', 'm4_1_mentor_id',
        'm4_2_4_3_mentor_id', 'm4_mock_exam_mentor_id'
    ]

    AUTO_FIELDS = [
        'm2_exam_mentor_id', 'm3_exam_mentor_id', 'm4_topic_mentor_id',
        'm5_topic_mentor_id', 'm6_topic_mentor_id', 'm7_topic_mentor_id'
    ]

    def calculate_and_save_debts(self, session: Session, student_id: int):
        logger.info(f"🏁 --- РАСЧЕТ КОМИССИИ: Студент ID {student_id} ---")

        student = session.query(Student).filter_by(id=student_id).first()
        if not student:
            return "❌ Студент не найден."

        # Проверка наличия зарплаты
        if not student.salary or float(student.salary) <= 0:
            return "❌ Ошибка: Не указана ЗП (salary)."

        base_amount = float(student.salary)

        # ОПРЕДЕЛЯЕМ РЕЖИМ (Fullstack или Solo)
        # Если у студента заполнены оба ментора в профиле — это Fullstack
        is_fullstack = (student.mentor_id is not None) and (student.auto_mentor_id is not None)

        if is_fullstack:
            rates = {
                'curator': self.FULL_CURATOR_RATE,
                'passive': self.FULL_DIRECTOR_PASSIVE,  # 7.5%
                'active': self.FULL_DIRECTOR_ACTIVE
            }
            mode = "FULLSTACK"
        else:
            rates = {
                'curator': self.SOLO_CURATOR_RATE,
                'passive': self.SOLO_DIRECTOR_PASSIVE,  # 10%
                'active': self.SOLO_DIRECTOR_ACTIVE
            }
            mode = "SOLO"

        logger.info(f"💰 База: {base_amount} | Режим: {mode}")
        debts_map = {}

        # РАСЧЕТ MANUAL
        m_progress = session.query(ManualProgress).filter_by(student_id=student_id).first()
        if m_progress:
            self._process_direction(debts_map, m_progress, self.MANUAL_FIELDS, DIRECTOR_MANUAL_ID, base_amount, rates,
                                    "Manual")

        # РАСЧЕТ AUTO
        a_progress = session.query(AutoProgress).filter_by(student_id=student_id).first()
        if a_progress:
            self._process_direction(debts_map, a_progress, self.AUTO_FIELDS, DIRECTOR_AUTO_ID, base_amount, rates,
                                    "Auto")

        # СОХРАНЕНИЕ
        for m_id, amount in debts_map.items():
            if amount > 0:
                self._create_or_update_record(session, student_id, m_id, amount)
                logger.info(f"   ➕ Итог Ментор ID {m_id}: {amount:.2f}")

        return "✅ Расчет завершен."

    def _process_direction(self, debts_map, progress_obj, fields, director_id, base_amount, rates, label):
        total_steps = len(fields)

        # 1. Анализируем, кто принимал темы
        accepted_by_mentor = {}  # {mentor_id: count}
        any_work_done = False

        for f in fields:
            mid = getattr(progress_obj, f)
            if mid:
                accepted_by_mentor[mid] = accepted_by_mentor.get(mid, 0) + 1
                any_work_done = True

        if not any_work_done:
            return

        director_is_active = director_id in accepted_by_mentor

        # 2. НАЧИСЛЕНИЕ ДИРЕКТОРУ
        if not director_is_active:
            # ПАССИВНЫЙ РЕЖИМ: Фикса 10% или 7.5% от всей ЗП
            passive_income = base_amount * rates['passive']
            self._add_debt(debts_map, director_id, passive_income)
            logger.info(f"   [{label}] Директор {director_id} ПАССИВЕН: +{passive_income:.2f} (Фикса)")
        else:
            # АКТИВНЫЙ РЕЖИМ: Только за свои темы по ставке 30%
            count = accepted_by_mentor[director_id]
            active_income = base_amount * rates['active'] * (count / total_steps)
            self._add_debt(debts_map, director_id, active_income)
            logger.info(f"   [{label}] Директор {director_id} АКТИВЕН: +{active_income:.2f} (за {count} тем)")

        # 3. НАЧИСЛЕНИЕ КУРАТОРАМ (за работу)
        for m_id, count in accepted_by_mentor.items():
            if m_id == director_id:
                continue  # Пропускаем, так как уже посчитали его выше как активного директора

            # Формула: ЗП * Ставка * (Принято / Всего)
            work_income = base_amount * rates['curator'] * (count / total_steps)
            self._add_debt(debts_map, m_id, work_income)
            logger.info(f"   [{label}] Куратор {m_id}: +{work_income:.2f} (за {count} тем)")

    def _add_debt(self, debts_map, mentor_id, amount):
        debts_map[mentor_id] = debts_map.get(mentor_id, 0) + amount

    def _create_or_update_record(self, session, student_id, mentor_id, total):
        rec = session.query(CuratorCommission).filter_by(
            student_id=student_id, curator_id=mentor_id
        ).first()
        if rec:
            rec.total_amount = total
        else:
            session.add(CuratorCommission(
                student_id=student_id, curator_id=mentor_id,
                total_amount=total, paid_amount=0.0
            ))

    @staticmethod
    def process_kk_payout(session, kk_id: int, start_date: datetime, end_date: datetime, method: str = 'card'):
        """
        Проводит фактическую выплату для КК:
        1. Находит все неоплаченные записи в salary_kk за период.
        2. Помечает их как is_paid = True.
        3. Создает запись в таблице payouts.
        """
        # 1. Ищем неоплаченные начисления КК за указанный период
        unpaid_records = session.query(SalaryKK).filter(
            and_(
                SalaryKK.kk_id == kk_id,
                SalaryKK.is_paid == False,
                SalaryKK.date_calculated >= start_date,
                SalaryKK.date_calculated <= end_date
            )
        ).all()

        if not unpaid_records:
            return None, "Нет начислений для выплаты за этот период."

        # 2. Считаем итоговую сумму к выплате
        total_payout_amount = sum(Decimal(str(rec.calculated_amount)) for rec in unpaid_records)

        # 3. Создаем запись в общем реестре выплат (Payouts)
        new_payout = Payout(
            kk_id=kk_id,  # Используем новое поле
            mentor_id=None, # Для КК mentor_id пустой
            period_start=start_date.date(),
            period_end=end_date.date(),
            total_amount=total_payout_amount,
            payout_status='completed', # Или 'pending_transfer'
            payout_method=method,
            date_processed=datetime.now(),
            date_created=datetime.now()
        )
        session.add(new_payout)
        session.flush() # Получаем ID новой выплаты

        # 4. Помечаем все записи в salary_kk как оплаченные
        for rec in unpaid_records:
            rec.is_paid = True
            rec.comment = f"{rec.comment or ''} | Оплачено в выплате #{new_payout.payout_id}".strip()

        return new_payout, f"Успешно выплачено {total_payout_amount} руб."