import logging
from datetime import date
from decimal import Decimal
from sqlalchemy import func
from data_base.db import session
from data_base.models import Student, Payment, Salary, SalaryKK, CuratorCommission
# Импортируй свой класс здесь
from classes.comission import AdminCommissionManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_commissions_by_themes():
    logger.info("💰 ЗАПУСК МИГРАЦИИ КОМИССИЙ (с учетом сданных тем)...")

    manager = AdminCommissionManager()
    start_period = date(2025, 11, 1)
    end_period = date(2025, 12, 31)

    # 1. Сначала ПЕРЕСЧИТЫВАЕМ ПОТОЛКИ для всех, у кого есть ЗП
    # Это гарантирует, что CuratorCommission.total_amount актуален и учитывает темы
    students_with_job = session.query(Student).filter(Student.salary > 0).all()
    for st in students_with_job:
        manager.calculate_and_save_debts(session, st.id)
    session.commit()
    logger.info(f"✅ Потолки обновлены для {len(students_with_job)} студентов.")

    # 2. Обрабатываем платежи
    payments = session.query(Payment).filter(
        Payment.payment_date >= start_period,
        Payment.payment_date <= end_period,
        Payment.comment.ilike("%Комиссия%"),
        Payment.status == "подтвержден"
    ).all()

    stats = {"salary": 0, "kk": 0}

    for p in payments:
        student = session.query(Student).filter_by(id=p.student_id).first()
        if not student or not student.salary or float(student.salary) <= 0:
            continue

        # --- КУРАТОРЫ И ДИРЕКТОРА ---
        # Берем долги, которые МЫ ТОЛЬКО ЧТО пересчитали по темам
        debts = session.query(CuratorCommission).filter_by(student_id=student.id).all()

        for d in debts:
            # Вычисляем, какую долю от каждого платежа должен получать этот ментор
            # (total_amount уже рассчитан пропорционально темам внутри AdminCommissionManager)
            mentor_payout_rate = float(d.total_amount) / float(student.salary)

            amt_to_add = Decimal(str(float(p.amount) * mentor_payout_rate)).quantize(Decimal("0.01"))

            if amt_to_add > 0:
                # Проверка на дубль
                exists = session.query(Salary).filter_by(payment_id=p.id, mentor_id=d.curator_id).first()
                if not exists:
                    session.add(Salary(
                        payment_id=p.id,
                        mentor_id=d.curator_id,
                        calculated_amount=amt_to_add,
                        is_paid=False,  # Ноябрь-Декабрь: к выплате
                        date_calculated=p.payment_date,  # Дата платежа
                        comment=f"Комиссия ({int(mentor_payout_rate * 100)}%) от платежа #{p.id} (Темы учтены)"
                    ))
                    stats["salary"] += 1

        # --- КАРЬЕРНЫЕ КОНСУЛЬТАНТЫ ---
        if student.career_consultant_id:
            kk_id = student.career_consultant_id
            total_kk_cap = Decimal(str(student.salary)) * Decimal('0.10')

            # Считаем, сколько уже начислили КК по этому студенту
            already_billed = session.query(func.sum(SalaryKK.calculated_amount)).filter_by(
                student_id=student.id, kk_id=kk_id
            ).scalar() or Decimal('0')

            if already_billed < total_kk_cap:
                kk_amt = Decimal(str(p.amount)) * Decimal('0.10')
                kk_final = min(kk_amt, total_kk_cap - already_billed).quantize(Decimal("0.01"))

                if not session.query(SalaryKK).filter_by(payment_id=p.id).first():
                    session.add(SalaryKK(
                        payment_id=p.id,
                        kk_id=kk_id,
                        student_id=student.id,
                        calculated_amount=kk_final,
                        total_potential=total_kk_cap,
                        remaining_limit=total_kk_cap - (already_billed + kk_final),
                        is_paid=False,
                        date_calculated=p.payment_date,
                        comment=f"10% от платежа #{p.id}"
                    ))
                    stats["kk"] += 1

    try:
        session.commit()
        logger.info(f"🏁 Успешно! Создано начислений: Менторы: {stats['salary']}, КК: {stats['kk']}")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    migrate_commissions_by_themes()