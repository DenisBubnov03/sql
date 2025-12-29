import logging
from decimal import Decimal
from datetime import date
from data_base.db import session
from data_base.models import Student, Salary, Payment

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Константы
DIRECTOR_MANUAL_ID = 1
DIRECTOR_AUTO_ID = 3


def audit_december_bonuses():
    logger.info("🔍 ЗАПУСК АУДИТА БОНУСОВ ЗА ДЕКАБРЬ 2025...")

    start_of_month = date(2025, 12, 1)
    end_of_month = date(2025, 12, 31)

    # 1. Ищем всех студентов, у которых есть подтвержденные платежи в ДЕКАБРЕ
    december_students_ids = session.query(Payment.student_id).filter(
        Payment.payment_date >= start_of_month,
        Payment.payment_date <= end_of_month,
        Payment.status == "подтвержден"
    ).distinct().all()

    student_ids = [s[0] for s in december_students_ids]

    missing_count = 0
    skipped_count = 0

    for s_id in student_ids:
        st = session.query(Student).filter_by(id=s_id).first()
        if not st or not st.total_cost or float(st.total_cost) <= 0:
            continue

        training_type = (st.training_type or "").lower()
        target_director_id = None
        current_mentor_id = None
        direction_label = ""

        # Определяем директора
        if "ручное" in training_type:
            target_director_id = DIRECTOR_MANUAL_ID
            current_mentor_id = st.mentor_id
            direction_label = "Ручное"
        elif "авто" in training_type:
            target_director_id = DIRECTOR_AUTO_ID
            current_mentor_id = st.auto_mentor_id
            direction_label = "Авто"

        # ЛОГИКА: Начисляем, если Директор НЕ является ментором этого студента
        if target_director_id and current_mentor_id != target_director_id:

            # Проверяем, нет ли уже начисления за этого студента (по Telegram в комменте)
            exists = session.query(Salary).filter(
                Salary.mentor_id == target_director_id,
                Salary.comment.ilike(f"%10% бонус%{st.telegram}%")
            ).first()

            if not exists:
                # Нам нужен ID декабрьского платежа для привязки
                pay = session.query(Payment).filter(
                    Payment.student_id == st.id,
                    Payment.status == "подтвержден",
                    Payment.payment_date >= start_of_month
                ).first()

                if pay:
                    bonus_amount = Decimal(str(st.total_cost)) * Decimal('0.10')

                    new_salary = Salary(
                        payment_id=pay.id,
                        mentor_id=target_director_id,
                        calculated_amount=bonus_amount.quantize(Decimal("0.01")),
                        is_paid=False,  # 🔥 Как ты и просил: к выплате
                        date_calculated=pay.payment_date,
                        comment=f"10% бонус за студента {st.telegram} ({direction_label})"
                    )
                    session.add(new_salary)
                    missing_count += 1
                    logger.info(f"✅ Добавлен бонус: {st.fio} (@{st.telegram}) — {bonus_amount} руб.")
            else:
                skipped_count += 1

    try:
        session.commit()
        logger.info(f"""
-------------------------------------------
📊 ИТОГИ ДЕКАБРЬСКОГО АУДИТА:
🆕 Новых бонусов создано: {missing_count}
🆗 Уже были в базе:       {skipped_count}
-------------------------------------------
""")
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    audit_december_bonuses()