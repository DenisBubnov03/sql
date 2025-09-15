"""
Модуль для расчета ЗП директоров направления фуллстек курса по новой системе.
"""
from datetime import datetime, date
from sqlalchemy import func
from data_base.db import session
from data_base.models import Student, FullstackTopicAssign, Mentor
from commands.fullstack_constants import TOPIC_FIELD_MAPPING, AUTO_MODULE_FIELD_MAPPING
from commands.logger import custom_logger

logger = custom_logger

def calculate_fullstack_salary(start_date: date, end_date: date):
    """
    Рассчитывает ЗП директоров направления (менторов ID 1 и 3) за фуллстек курсы.
    
    Args:
        start_date: Начальная дата периода
        end_date: Конечная дата периода
        
    Returns:
        dict: Словарь с ЗП для каждого директора и подробными логами
    """
    logger.info(f"📊 Начинаем расчет ЗП директоров направления за фуллстек за период {start_date} - {end_date}")
    
    # Получаем все записи принятых тем за период ТОЛЬКО от директоров направления (ID 1 и 3)
    topic_assignments = session.query(FullstackTopicAssign).join(Student).filter(
        Student.training_type == "Фуллстек",
        FullstackTopicAssign.mentor_id.in_([1, 3]),  # Только директора направления
        func.date(FullstackTopicAssign.assigned_at) >= start_date,
        func.date(FullstackTopicAssign.assigned_at) <= end_date
    ).all()
    
    logger.info(f"📊 Найдено записей принятых тем за период: {len(topic_assignments)}")
    
    # Отладочная информация - показываем все найденные записи
    logger.info("🔍 DEBUG: Найденные записи принятых тем:")
    for assignment in topic_assignments:
        topic_info = f"Ручная: {assignment.topic_manual}" if assignment.topic_manual else f"Авто: {assignment.topic_auto}"
        logger.info(f"  • ID {assignment.id}: Студент {assignment.student_id}, Ментор {assignment.mentor_id} | {topic_info} | {assignment.assigned_at}")
    
    # Инициализируем результаты
    director_salaries = {
        1: 0.0,  # Ручной директор
        3: 0.0   # Авто директор
    }
    detailed_logs = {
        1: [],
        3: []
    }
    
    # Группируем по студентам
    students_data = {}
    for assignment in topic_assignments:
        student_id = assignment.student_id
        if student_id not in students_data:
            student = session.query(Student).filter(Student.id == student_id).first()
            students_data[student_id] = {
                'student': student,
                'manual_topics': 0,
                'auto_topics': 0
            }
        
        # Считаем темы по типам ТОЛЬКО от директоров направления
        if assignment.mentor_id == 1 and assignment.topic_manual is not None:
            students_data[student_id]['manual_topics'] += 1
        if assignment.mentor_id == 3 and assignment.topic_auto is not None:
            students_data[student_id]['auto_topics'] += 1
    
    logger.info(f"📊 Найдено уникальных студентов с принятыми темами: {len(students_data)}")
    
    for student_id, data in students_data.items():
        student = data['student']
        logger.info(f"📊 Обрабатываем студента: {student.fio} (ID {student.id})")
        
        # Получаем total_cost студента
        total_cost = float(student.total_cost) if student.total_cost else 0
        if total_cost == 0:
            logger.warning(f"⚠️ У студента {student.fio} total_cost = 0, пропускаем")
            continue
            
        # Рассчитываем стоимость одного созвона (30% от total_cost)
        call_cost = total_cost * 0.3
        
        # === РАСЧЕТ ДЛЯ РУЧНОГО ДИРЕКТОРА (ID = 1) ===
        manual_topics_count = len(TOPIC_FIELD_MAPPING)
        manual_call_price = call_cost / manual_topics_count if manual_topics_count > 0 else 0
        
        # Используем уже подсчитанные ручные темы
        manual_accepted_topics = data['manual_topics']
        
        # Отладочная информация
        logger.info(f"🔍 DEBUG: Студент {student.fio} (ID {student.id})")
        logger.info(f"🔍 DEBUG: Ручных тем для этого студента: {manual_accepted_topics}")
        logger.info(f"🔍 DEBUG: Авто тем для этого студента: {data['auto_topics']}")
        
        manual_salary = manual_accepted_topics * manual_call_price
        director_salaries[1] += manual_salary
        
        # Логируем для ручного директора
        if manual_accepted_topics > 0:
            detailed_logs[1].append(
                f"💼 Ручной директор принял {manual_accepted_topics} тем у студента {student.fio} (ID {student.id}) | "
                f"Стоимость созвона: {round(manual_call_price, 2)} руб. | "
                f"ЗП: +{round(manual_salary, 2)} руб."
            )
            logger.info(f"📊 Ручной директор: {manual_accepted_topics} тем, ЗП +{round(manual_salary, 2)} руб.")
        
        # === РАСЧЕТ ДЛЯ АВТО ДИРЕКТОРА (ID = 3) ===
        auto_modules_count = len(AUTO_MODULE_FIELD_MAPPING)
        auto_call_price = call_cost / auto_modules_count if auto_modules_count > 0 else 0
        
        # Используем уже подсчитанные авто темы
        auto_accepted_topics = data['auto_topics']
        
        auto_salary = auto_accepted_topics * auto_call_price
        director_salaries[3] += auto_salary
        
        # Логируем для авто директора
        if auto_accepted_topics > 0:
            detailed_logs[3].append(
                f"💼 Авто директор принял {auto_accepted_topics} модулей у студента {student.fio} (ID {student.id}) | "
                f"Стоимость созвона: {round(auto_call_price, 2)} руб. | "
                f"ЗП: +{round(auto_salary, 2)} руб."
            )
            logger.info(f"📊 Авто директор: {auto_accepted_topics} модулей, ЗП +{round(auto_salary, 2)} руб.")
    
    # Итоговое логирование
    logger.info(f"📊 Итоговые ЗП директоров направления:")
    logger.info(f"📊 Ручной директор (ID 1): {round(director_salaries[1], 2)} руб.")
    logger.info(f"📊 Авто директор (ID 3): {round(director_salaries[3], 2)} руб.")
    
    return {
        'salaries': director_salaries,
        'logs': detailed_logs,
        'students_processed': len(students_data),
        'topics_processed': len(topic_assignments)
    }


def get_fullstack_salary_summary(start_date: date, end_date: date):
    """
    Возвращает краткую сводку по ЗП директоров направления за фуллстек.
    
    Args:
        start_date: Начальная дата периода
        end_date: Конечная дата периода
        
    Returns:
        str: Текстовая сводка
    """
    result = calculate_fullstack_salary(start_date, end_date)
    
    summary = f"📊 ЗП директоров направления за фуллстек ({start_date} - {end_date}):\n\n"
    summary += f"👨‍🏫 Ручной директор (ID 1): {round(result['salaries'][1], 2)} руб.\n"
    summary += f"🤖 Авто директор (ID 3): {round(result['salaries'][3], 2)} руб.\n\n"
    summary += f"📈 Итого: {round(result['salaries'][1] + result['salaries'][3], 2)} руб.\n"
    summary += f"👥 Обработано студентов: {result['students_processed']}\n"
    
    return summary
