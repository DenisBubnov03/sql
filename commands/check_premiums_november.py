from datetime import date
import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import func

# Добавляем корень проекта в sys.path, чтобы скрипт работал при прямом запуске
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_base.db import session
from data_base.models import Payment, Mentor, Student

# Жёстко фиксируем год для ноябрьских премий
NOVEMBER_YEAR = 2025
from data_base.db import engine
# print(engine.url)
# print(session.query(Payment).count())

# print(session.query(Payment).filter(Payment.comment.ilike('%преми%')).count())

def fetch_november_premiums(year: Optional[int] = None):
    """Возвращает список премий за ноябрь указанного года."""
    target_year = year or NOVEMBER_YEAR
    start = date(target_year, 11, 1)
    end = date(target_year, 11, 30)

    premium_comment = func.lower(func.coalesce(Payment.comment, ""))

    payments = (
        session.query(Payment)
        .filter(
            Payment.payment_date >= start,
            Payment.payment_date <= end,
            Payment.status == "подтвержден",
            # привели к нижнему регистру, поэтому ищем по нижнему
            premium_comment.like("%преми%"),
        )
        .order_by(Payment.payment_date.asc())
        .all()
    )
    return payments, target_year


def build_report(payments, year: int):
    """Формирует текстовый отчёт по найденным премиям."""
    if not payments:
        return f"🎁 Премии за ноябрь {year} не найдены."

    lines = [f"🎁 Премии за ноябрь {year}"]
    total = 0.0

    for p in payments:
        mentor = session.query(Mentor).filter(Mentor.id == p.mentor_id).first()
        student = (
            session.query(Student).filter(Student.id == p.student_id).first()
            if p.student_id
            else None
        )

        mentor_name = mentor.full_name if mentor else f"Mentor ID {p.mentor_id}"
        student_name = student.fio if student else "—"

        amount = float(p.amount)
        total += amount

        lines.append(
            f"- {p.payment_date}: {amount:.2f} руб. | Ментор: {mentor_name} | Студент: {student_name} | Комментарий: {p.comment or ''}"
        )

    lines.append(f"\nИтого премий: {total:.2f} руб.")
    return "\n".join(lines)


def main():
    payments, year = fetch_november_premiums()
    report = build_report(payments, year)
    print(report)


if __name__ == "__main__":
    main()
