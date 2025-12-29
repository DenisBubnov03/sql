import logging
from datetime import date
from data_base.db import session
from data_base.models import Student, ManualProgress, AutoProgress, Salary

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def deep_audit_submissions():
    logger.info("🔍 ЗАПУСК ТОЧНОГО АУДИТА (сверка по текстовым логам)...")

    start_date = date(2025, 12, 1)
    end_date = date(2025, 12, 31)

    # Маппинг для поиска в текстовых комментариях (из вашего скриншота)
    manual_search = [
        ('m1_submission_date', 'm1_mentor_id', '1 модуль'),
        ('m2_1_2_2_submission_date', 'm2_1_2_2_mentor_id', 'Тема 2.1 + 2.2'),
        ('m2_3_3_1_submission_date', 'm2_3_3_1_mentor_id', 'Тема 2.3 + 3.1'),
        ('m3_2_submission_date', 'm3_2_mentor_id', 'Тема 3.2'),
        ('m3_3_submission_date', 'm3_3_mentor_id', 'Тема 3.3'),
        ('m4_mock_exam_passed_date', 'm4_mock_exam_mentor_id', 'экзамен')
    ]

    stats = {"total_found_in_progress": 0, "verified": 0, "missing": 0}

    # Получаем всех студентов
    students = session.query(Student).all()

    for st in students:
        # 1. Проверка ManualProgress
        mp = session.query(ManualProgress).filter_by(student_id=st.id).first()
        if mp:
            for date_col, mentor_col, search_text in manual_search:
                p_date = getattr(mp, date_col)
                m_id = getattr(mp, mentor_col)

                if p_date and start_date <= p_date <= end_date:
                    stats["total_found_in_progress"] += 1

                    # Ищем запись в Salary по ментору и упоминанию ника или текста темы
                    # На скриншоте видно формат: "Принял Тема ... у @username"
                    exists = session.query(Salary).filter(
                        Salary.mentor_id == m_id,
                        Salary.comment.ilike(f"%{search_text}%"),
                        Salary.comment.ilike(f"%{st.telegram}%")
                    ).first()

                    if exists:
                        stats["verified"] += 1
                    else:
                        logger.warning(f"❌ ПРОПУЩЕНО: {st.fio} (@{st.telegram}){st.id} | {search_text} | Дата: {p_date}")
                        stats["missing"] += 1

    logger.info(f"""
-------------------------------------------
📊 ИТОГИ ПРОВЕРКИ (Ноябрь-Декабрь):
✅ Темы подтверждены в Salary: {stats['verified']}
❌ Темы отсутствуют в Salary:   {stats['missing']}
🔎 Всего проанализировано дат: {stats['total_found_in_progress']}
-------------------------------------------
""")


if __name__ == "__main__":
    deep_audit_submissions()