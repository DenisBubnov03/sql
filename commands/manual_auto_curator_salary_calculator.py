"""
Модуль для расчета ЗП ручных и авто кураторов по системе принятых тем/модулей.
"""
from datetime import date
from data_base.db import session
from data_base.models import Student, ManualProgress, AutoProgress, Mentor
from commands.logger import custom_logger
from config import Config

logger = custom_logger

# Маппинг полей для ручных кураторов (8 тем)
MANUAL_TOPIC_FIELDS = [
    "m1_submission_date",
    "m2_1_2_2_submission_date",
    "m2_3_3_1_submission_date",
    "m3_2_submission_date",
    "m3_3_submission_date",
    "m4_1_submission_date",
    "m4_2_4_3_submission_date",
    "m4_mock_exam_passed_date",
]

# Маппинг полей для авто кураторов (6 модулей)
AUTO_MODULE_FIELDS = [
    "m2_exam_passed_date",
    "m3_exam_passed_date",
    "m4_topic_passed_date",
    "m5_topic_passed_date",
    "m6_topic_passed_date",
    "m7_topic_passed_date",
]


def calculate_manual_auto_curator_salary(start_date: date, end_date: date):
    """
    Рассчитывает ЗП ручных и авто кураторов по системе принятых тем/модулей.
    
    ВАЖНО: Эта функция рассчитывает зарплату ТОЛЬКО для студентов, пришедших ПОСЛЕ december_start.
    Студенты, пришедшие ДО december_start, рассчитываются по старой системе (20% от платежей)
    и НЕ должны получать зарплату по темам/модулям.
    
    Ручные кураторы:
    - 20% от total_cost студента
    - Делим на 8 тем
    - Учитываем только темы, сданные в периоде расчета
    
    Авто кураторы:
    - 20% от total_cost студента
    - Делим на 6 модулей
    - Учитываем только модули, сданные в периоде расчета
    
    ВАЖНО: Стоимость рассчитывается индивидуально для каждого студента на основе его total_cost.
    
    Args:
        start_date: Начальная дата периода расчета
        end_date: Конечная дата периода расчета
        
    Returns:
        dict: Словарь с ЗП для кураторов, логами и статистикой
    """
    logger.info(f"📊 Начинаем расчет ЗП ручных и авто кураторов за период {start_date} - {end_date}")
    
    # Дата начала учета студентов (из конфига)
    from config import Config
    december_start = Config.NEW_PAYMENT_SYSTEM_START_DATE
    logger.info(f"📅 Учитываем только студентов, пришедших с {december_start}")
    
    # Инициализируем результаты
    curator_salaries = {}
    curator_detailed_logs = {}
    
    # === РАСЧЕТ ДЛЯ РУЧНЫХ КУРАТОРОВ ===
    logger.info("📊 Обрабатываем ручных кураторов...")
    
    # Получаем студентов с типом "Ручное тестирование", пришедших с декабря 2025
    manual_students = session.query(Student).filter(
        Student.training_type == "Ручное тестирование",
        Student.start_date >= december_start
    ).all()
    
    logger.info(f"📊 Найдено ручных студентов с {december_start}: {len(manual_students)}")
    
    # Логируем всех найденных студентов для отладки
    for s in manual_students:
        logger.info(f"🔍 Ручной студент: {s.fio} (ID {s.id}), start_date={s.start_date}, mentor_id={s.mentor_id}, total_cost={s.total_cost}")
    
    manual_topics_count = len(MANUAL_TOPIC_FIELDS)  # 8 тем
    
    for student in manual_students:
        if not student.mentor_id:
            logger.debug(f"🚫 Студент {student.fio} (ID {student.id}) не имеет назначенного куратора (mentor_id)")
            continue
        
        # Проверяем наличие total_cost
        if not student.total_cost or float(student.total_cost) == 0:
            logger.debug(f"🚫 У студента {student.fio} (ID {student.id}) нет total_cost или он равен 0")
            continue
        
        # Получаем прогресс студента
        progress = session.query(ManualProgress).filter(
            ManualProgress.student_id == student.id
        ).first()
        
        if not progress:
            logger.debug(f"🚫 У студента {student.fio} (ID {student.id}) нет записи в ManualProgress")
            continue
        
        curator_id = student.mentor_id
        
        # Инициализируем ЗП куратора и его логи
        if curator_id not in curator_salaries:
            curator_salaries[curator_id] = 0
        if curator_id not in curator_detailed_logs:
            curator_detailed_logs[curator_id] = []
        
        # Рассчитываем стоимость одной темы для этого студента (20% от total_cost / 8 тем)
        student_total_cost = float(student.total_cost)
        manual_call_cost = student_total_cost * 0.20  # 20% от стоимости курса студента
        manual_topic_price = manual_call_cost / manual_topics_count if manual_topics_count > 0 else 0
        
        # Подсчитываем сданные темы в периоде
        completed_topics = 0
        topic_details = []
        
        logger.info(f"🔍 Проверяем темы для студента {student.fio} (ID {student.id}), период: {start_date} - {end_date}")
        for field_name in MANUAL_TOPIC_FIELDS:
            field_value = getattr(progress, field_name, None)
            if field_value:
                logger.info(f"  • {field_name}: {field_value} (в периоде: {start_date <= field_value <= end_date})")
            if field_value and start_date <= field_value <= end_date:
                completed_topics += 1
                topic_details.append(f"{field_name}: {field_value}")
        
        if completed_topics > 0:
            curator_salary = completed_topics * manual_topic_price
            curator_salaries[curator_id] += curator_salary
            
            # Добавляем детальный лог для куратора
            curator_detailed_logs[curator_id].append(
                f"💼 За студента ручное направление {student.fio} {student.telegram} (ID {student.id}) | "
                f"Стоимость курса: {student_total_cost} руб. | Сдано {completed_topics} тем в периоде по {round(manual_topic_price, 2)} руб. | +{round(curator_salary, 2)} руб."
            )
            
            logger.info(f"📊 Ручной куратор {curator_id}: студент ручник {student.fio}, стоимость курса {student_total_cost} руб., сдано {completed_topics} тем, ЗП +{round(curator_salary, 2)} руб.")
    
    # === РАСЧЕТ ДЛЯ АВТО КУРАТОРОВ ===
    logger.info("📊 Обрабатываем авто кураторов...")
    
    # Получаем студентов с типом "Автотестирование", пришедших с декабря 2025
    auto_students = session.query(Student).filter(
        Student.training_type == "Автотестирование",
        Student.start_date >= december_start
    ).all()
    
    logger.info(f"📊 Найдено авто студентов с {december_start}: {len(auto_students)}")
    
    # Логируем всех найденных студентов для отладки
    for s in auto_students:
        logger.info(f"🔍 Авто студент: {s.fio} (ID {s.id}), start_date={s.start_date}, auto_mentor_id={s.auto_mentor_id}, total_cost={s.total_cost}")
    
    auto_modules_count = len(AUTO_MODULE_FIELDS)  # 6 модулей
    
    for student in auto_students:
        if not student.auto_mentor_id:
            logger.debug(f"🚫 Студент {student.fio} (ID {student.id}) не имеет назначенного авто куратора (auto_mentor_id)")
            continue
        
        # Проверяем наличие total_cost
        if not student.total_cost or float(student.total_cost) == 0:
            logger.debug(f"🚫 У студента {student.fio} (ID {student.id}) нет total_cost или он равен 0")
            continue
        
        # Получаем прогресс студента
        progress = session.query(AutoProgress).filter(
            AutoProgress.student_id == student.id
        ).first()
        
        if not progress:
            logger.debug(f"🚫 У студента {student.fio} (ID {student.id}) нет записи в AutoProgress")
            continue
        
        curator_id = student.auto_mentor_id
        
        # Инициализируем ЗП куратора и его логи
        if curator_id not in curator_salaries:
            curator_salaries[curator_id] = 0
        if curator_id not in curator_detailed_logs:
            curator_detailed_logs[curator_id] = []
        
        # Рассчитываем стоимость одного модуля для этого студента (20% от total_cost / 6 модулей)
        student_total_cost = float(student.total_cost)
        auto_call_cost = student_total_cost * 0.20  # 20% от стоимости курса студента
        auto_module_price = auto_call_cost / auto_modules_count if auto_modules_count > 0 else 0
        
        # Подсчитываем сданные модули в периоде
        completed_modules = 0
        module_details = []
        
        logger.info(f"🔍 Проверяем модули для студента {student.fio} (ID {student.id}), период: {start_date} - {end_date}")
        for field_name in AUTO_MODULE_FIELDS:
            field_value = getattr(progress, field_name, None)
            if field_value:
                logger.info(f"  • {field_name}: {field_value} (в периоде: {start_date <= field_value <= end_date})")
            if field_value and start_date <= field_value <= end_date:
                completed_modules += 1
                module_details.append(f"{field_name}: {field_value}")
        
        if completed_modules > 0:
            curator_salary = completed_modules * auto_module_price
            curator_salaries[curator_id] += curator_salary
            
            # Добавляем детальный лог для куратора
            curator_detailed_logs[curator_id].append(
                f"💼 За студента авто направление {student.fio} {student.telegram} (ID {student.id}) | "
                f"Стоимость курса: {student_total_cost} руб. | Сдано {completed_modules} модулей в периоде по {round(auto_module_price, 2)} руб. | +{round(curator_salary, 2)} руб."
            )
            
            logger.info(f"📊 Авто куратор {curator_id}: студент {student.fio}, стоимость курса {student_total_cost} руб., сдано {completed_modules} модулей, ЗП +{round(curator_salary, 2)} руб.")
    
    # Итоговое логирование
    logger.info(f"📊 Итоговые ЗП кураторов:")
    for curator_id, salary in curator_salaries.items():
        curator = session.query(Mentor).filter(Mentor.id == curator_id).first()
        curator_name = curator.full_name if curator else f"ID {curator_id}"
        logger.info(f"📊 Куратор {curator_name} (ID {curator_id}): {round(salary, 2)} руб.")
    
    # Статистика
    total_manual_students = len(manual_students)
    total_auto_students = len(auto_students)
    total_curators = len(curator_salaries)
    
    logger.info(f"📊 Статистика расчета:")
    logger.info(f"📊 Ручных студентов обработано: {total_manual_students}")
    logger.info(f"📊 Авто студентов обработано: {total_auto_students}")
    logger.info(f"📊 Всего кураторов получили ЗП: {total_curators}")
    logger.info(f"📅 ВАЖНО: Учитываются только студенты, пришедшие с {december_start} и позже")
    logger.info(f"📅 ВАЖНО: Учитываются только темы/модули, сданные в периоде {start_date} - {end_date}")
    
    # Округляем итоговые зарплаты
    rounded_salaries = {curator_id: round(salary, 2) for curator_id, salary in curator_salaries.items()}
    
    return {
        'curator_salaries': rounded_salaries,
        'logs': curator_detailed_logs,
        'students_processed': {
            'manual': total_manual_students,
            'auto': total_auto_students,
            'total': total_manual_students + total_auto_students
        },
        'curators_count': total_curators
    }

