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
    Рассчитывает ЗП всех участников фуллстек системы: директоров, кураторов + 10% бонусы за первые модули.
    
    ВАЖНО: 10% бонусы начисляются только за модули, сданные В ПЕРИОДЕ РАСЧЕТА (start_date - end_date).
    
    Бонусы директорам:
    - Ручной директор (ID=1): за сдачу "1 модуль" (ручное тестирование)
    - Авто директор (ID=3): за сдачу "Сдача 2 модуля" (автоматизация, начинаем со 2-го)
    - ВАЖНО: Бонус НЕ начисляется, если студент на самом директоре (избегаем дублирования)
    
    Args:
        start_date: Начальная дата периода расчета
        end_date: Конечная дата периода расчета
        
    Returns:
        dict: Словарь с ЗП для директоров и кураторов, логами и статистикой
    """
    logger.info(f"📊 Начинаем расчет ЗП директоров направления за фуллстек за период {start_date} - {end_date}")
    
    # Дата начала учета фуллстек студентов (с сентября 2025)
    september_start = date(2025, 9, 1)
    logger.info(f"📅 Учитываем только студентов, пришедших с {september_start}")
    
    # Получаем ВСЕ записи принятых тем за период (и от директоров, и от кураторов)
    # ВАЖНО: учитываем только студентов, которые пришли с сентября 2025
    topic_assignments = session.query(FullstackTopicAssign).join(Student).filter(
        Student.training_type == "Фуллстек",
        Student.start_date >= september_start,  # 🔥 НОВЫЙ ФИЛЬТР: только студенты с сентября
        func.date(FullstackTopicAssign.assigned_at) >= start_date,
        func.date(FullstackTopicAssign.assigned_at) <= end_date
    ).all()
    
    logger.info(f"📊 Найдено записей принятых тем за период: {len(topic_assignments)}")
    
    # Дополнительная статистика по фильтрации студентов
    all_fullstack_students = session.query(Student).filter(Student.training_type == "Фуллстек").count()
    september_fullstack_students = session.query(Student).filter(
        Student.training_type == "Фуллстек",
        Student.start_date >= september_start
    ).count()
    
    logger.info(f"📊 Всего фуллстек студентов в БД: {all_fullstack_students}")
    logger.info(f"📊 Фуллстек студентов с сентября: {september_fullstack_students}")
    logger.info(f"📊 Исключено студентов (до сентября): {all_fullstack_students - september_fullstack_students}")
    
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
    
    # Группируем по студентам и разделяем директоров/кураторов
    students_data = {}
    curator_students = {}  # Студенты, которых взяли кураторы
    
    for assignment in topic_assignments:
        student_id = assignment.student_id
        if student_id not in students_data:
            student = session.query(Student).filter(Student.id == student_id).first()
            students_data[student_id] = {
                'student': student,
                'manual_topics': 0,
                'auto_topics': 0,
                'is_curator_student': False,
                'curator_id': None,
                'curator_direction': None,
                'curators': {}  # Словарь всех кураторов: {curator_id: {'direction': 'auto/manual', 'assignments': [...]}}
            }
        
        # Определяем директор это или куратор
        if assignment.mentor_id in [1, 3]:  # Директор направления
            # Считаем темы по типам от директоров направления
            if assignment.mentor_id == 1 and assignment.topic_manual is not None:
                students_data[student_id]['manual_topics'] += 1
            if assignment.mentor_id == 3 and assignment.topic_auto is not None:
                students_data[student_id]['auto_topics'] += 1
        else:  # Куратор
            students_data[student_id]['is_curator_student'] = True
            
            # ВАЖНО: не перезаписываем curator_id, а собираем всех кураторов
            curator_id = assignment.mentor_id
            if curator_id not in students_data[student_id]['curators']:
                students_data[student_id]['curators'][curator_id] = {
                    'direction': None,
                    'assignments': []
                }
            
            # Определяем направление куратора
            if assignment.topic_manual is not None:
                if students_data[student_id]['curators'][curator_id]['direction'] is None:
                    students_data[student_id]['curators'][curator_id]['direction'] = 'manual'
            elif assignment.topic_auto is not None:
                if students_data[student_id]['curators'][curator_id]['direction'] is None:
                    students_data[student_id]['curators'][curator_id]['direction'] = 'auto'
            
            students_data[student_id]['curators'][curator_id]['assignments'].append(assignment)
            
            # Для обратной совместимости устанавливаем первого найденного куратора
            if students_data[student_id]['curator_id'] is None:
                students_data[student_id]['curator_id'] = curator_id
                students_data[student_id]['curator_direction'] = students_data[student_id]['curators'][curator_id]['direction']
            
            # Сохраняем информацию о кураторе для расчета ЗП
            if curator_id not in curator_students:
                curator_students[curator_id] = []
            if student_id not in [s['student_id'] for s in curator_students[curator_id]]:
                curator_students[curator_id].append({
                    'student_id': student_id,
                    'student': students_data[student_id]['student'],
                    'direction': students_data[student_id]['curators'][curator_id]['direction']
                })
    
    logger.info(f"📊 Найдено уникальных студентов с принятыми темами: {len(students_data)}")
    
    # Инициализируем ЗП кураторов и их логи
    curator_salaries = {}
    curator_detailed_logs = {}  # Детальные логи для кураторов
    
    for student_id, data in students_data.items():
        student = data['student']
        logger.info(f"📊 Обрабатываем студента: {student.fio} (ID {student.id})")
        
        # Получаем total_cost студента
        total_cost = float(student.total_cost) if student.total_cost else 0
        if total_cost == 0:
            logger.warning(f"⚠️ У студента {student.fio} total_cost = 0, пропускаем")
            continue
        
        if data['is_curator_student']:
            # === ОБРАБОТКА СТУДЕНТОВ КУРАТОРОВ ===
            # ВАЖНО: обрабатываем ВСЕХ кураторов для этого студента, а не только первого
            for curator_id, curator_info in data.get('curators', {}).items():
                curator_direction = curator_info['direction']
                
                if not curator_direction:
                    continue
                
                # Инициализируем ЗП куратора и его логи
                if curator_id not in curator_salaries:
                    curator_salaries[curator_id] = 0
                if curator_id not in curator_detailed_logs:
                    curator_detailed_logs[curator_id] = []
                
                if curator_direction == 'manual':
                    # === РУЧНОЙ КУРАТОР: как директор, но 10% вместо 30% ===
                    # Рассчитываем стоимость одного созвона (10% от total_cost)
                    call_cost = total_cost * 0.10
                    
                    # Считаем количество принятых тем куратором
                    manual_topics_count = len(TOPIC_FIELD_MAPPING)
                    manual_call_price = call_cost / manual_topics_count if manual_topics_count > 0 else 0
                    
                    # Подсчитываем принятые темы куратором для этого студента (из его assignments)
                    curator_manual_topics = sum(1 for a in curator_info['assignments'] if a.topic_manual is not None)
                    
                    curator_salary = curator_manual_topics * manual_call_price
                    curator_salaries[curator_id] += curator_salary
                    
                    # Добавляем детальный лог для куратора
                    curator_detailed_logs[curator_id].append(
                        f"💼 Ручной куратор за фуллстек студента {student.fio} {student.telegram} {student.id} | "
                        f"Принял {curator_manual_topics} тем по {round(manual_call_price, 2)} руб. | +{round(curator_salary, 2)} руб."
                    )
                    
                    # 10% ручному директору направления (только если студент НЕ на ручном директоре)
                    if student.mentor_id != 1:  # Студент НЕ на ручном директоре
                        director_salaries[1] += total_cost * 0.10
                        logger.info(f"📊 Ручной директор (ID 1): бонус +{round(total_cost * 0.10, 2)} руб. за студента {student.fio} (куратор {curator_id})")
                    else:
                        logger.debug(f"🚫 Ручному директору НЕ начислен бонус: студент {student.fio} на ручном директоре")
                    
                    logger.info(f"📊 Ручной куратор {curator_id}: принял {curator_manual_topics} тем у студента {student.fio}, ЗП +{round(curator_salary, 2)} руб.")
                    
                else:  # auto
                    # === АВТО КУРАТОР: как директор, но 20% вместо 30% ===
                    # Рассчитываем стоимость одного созвона (20% от total_cost)
                    call_cost = total_cost * 0.20
                    
                    # Считаем количество принятых модулей куратором
                    auto_modules_count = len(AUTO_MODULE_FIELD_MAPPING)
                    auto_call_price = call_cost / auto_modules_count if auto_modules_count > 0 else 0
                    
                    # Подсчитываем принятые модули куратором для этого студента (из его assignments)
                    curator_auto_topics = sum(1 for a in curator_info['assignments'] if a.topic_auto is not None)
                    
                    curator_salary = curator_auto_topics * auto_call_price
                    curator_salaries[curator_id] += curator_salary
                    
                    # Добавляем детальный лог для авто куратора
                    curator_detailed_logs[curator_id].append(
                        f"💼 Авто куратор за фуллстек студента {student.fio} {student.telegram} {student.id} | "
                        f"Принял {curator_auto_topics} модулей по {round(auto_call_price, 2)} руб. | +{round(curator_salary, 2)} руб."
                    )
                    
                    # 10% авто директору направления (только если студент НЕ на авто директоре)
                    if student.auto_mentor_id != 3:  # Студент НЕ на авто директоре
                        director_salaries[3] += total_cost * 0.10
                        logger.info(f"📊 Авто директор (ID 3): бонус +{round(total_cost * 0.10, 2)} руб. за студента {student.fio} (куратор {curator_id})")
                    else:
                        logger.debug(f"🚫 Авто директору НЕ начислен бонус: студент {student.fio} на авто директоре")
                    
                    logger.info(f"📊 Авто куратор {curator_id}: принял {curator_auto_topics} модулей у студента {student.fio}, ЗП +{round(curator_salary, 2)} руб.")
            
        else:
            # === ОБРАБОТКА СТУДЕНТОВ ДИРЕКТОРОВ НАПРАВЛЕНИЯ ===
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
    
    logger.info(f"📊 Итоговые ЗП кураторов:")
    for curator_id, salary in curator_salaries.items():
        logger.info(f"📊 Куратор (ID {curator_id}): {round(salary, 2)} руб.")
    
    # 🔹 НОВАЯ УПРОЩЕННАЯ ЛОГИКА: 10% ОТ СТОИМОСТИ КУРСА ПРИ СДАЧЕ ПЕРВОГО МОДУЛЯ
    logger.info("🔹 Обрабатываем 10% бонусы директорам за сдачу первых модулей")
    
    # Получаем всех фуллстек студентов, пришедших с сентября
    fullstack_students = session.query(Student).filter(
        Student.training_type == "Фуллстек",
        Student.start_date >= september_start
    ).all()
    
    module_bonuses_applied = 0
    
    for student in fullstack_students:
        if not student.total_cost:
            logger.debug(f"🚫 Пропускаем студента {student.fio}: нет данных о стоимости курса")
            continue
            
        # Проверяем, что студент НЕ на директоре (иначе не даем 10% бонус)
        is_on_manual_director = student.mentor_id == 1  # Ручной директор
        is_on_auto_director = student.auto_mentor_id == 3  # Авто директор
        
        logger.debug(f"🎯 Студент {student.fio}: mentor_id={student.mentor_id}, auto_mentor_id={student.auto_mentor_id}")
        logger.debug(f"🎯 На ручном директоре: {is_on_manual_director}, на авто директоре: {is_on_auto_director}")
        
        bonus_amount = float(student.total_cost) * 0.1
        bonuses_applied = []
        
        # Проверяем, сдал ли студент 1 модуль по ручному направлению В ПЕРИОДЕ РАСЧЕТА
        has_manual_module_1 = session.query(FullstackTopicAssign).filter(
            FullstackTopicAssign.student_id == student.id,
            FullstackTopicAssign.topic_manual == "1 модуль",
            FullstackTopicAssign.assigned_at >= start_date,
            FullstackTopicAssign.assigned_at <= end_date
        ).first() is not None
        
        # Проверяем, сдал ли студент 2 модуль по авто направлению В ПЕРИОДЕ РАСЧЕТА (начинаем со 2-го модуля)
        has_auto_module_2 = session.query(FullstackTopicAssign).filter(
            FullstackTopicAssign.student_id == student.id,
            FullstackTopicAssign.topic_auto == "Сдача 2 модуля",
            FullstackTopicAssign.assigned_at >= start_date,
            FullstackTopicAssign.assigned_at <= end_date
        ).first() is not None
        
        logger.debug(f"🎯 Студент {student.fio}: ручной модуль 1 = {has_manual_module_1}, авто модуль 2 = {has_auto_module_2}, стоимость курса = {student.total_cost}")
        
        # Бонус ручному директору (ID=1) только если сдан ручной 1 модуль И студент НЕ на ручном директоре
        if has_manual_module_1 and not is_on_manual_director:
            director_salaries[1] += bonus_amount
            detailed_logs[1].append(
                f"🎯 10% бонус за сдачу 1 модуля ручного В ПЕРИОДЕ: студент {student.fio} {student.telegram} (ID {student.id}) | "
                f"Стоимость курса: {student.total_cost} руб. | +{round(bonus_amount, 2)} руб."
            )
            bonuses_applied.append("ручной")
        elif has_manual_module_1 and is_on_manual_director:
            logger.debug(f"🚫 Ручному директору НЕ начислен бонус: студент {student.fio} на ручном директоре")
        
        # Бонус авто директору (ID=3) только если сдан авто 2 модуль И студент НЕ на авто директоре
        if has_auto_module_2 and not is_on_auto_director:
            director_salaries[3] += bonus_amount
            detailed_logs[3].append(
                f"🎯 10% бонус за сдачу 2 модуля авто В ПЕРИОДЕ: студент {student.fio} {student.telegram} (ID {student.id}) | "
                f"Стоимость курса: {student.total_cost} руб. | +{round(bonus_amount, 2)} руб."
            )
            bonuses_applied.append("авто")
        elif has_auto_module_2 and is_on_auto_director:
            logger.debug(f"🚫 Авто директору НЕ начислен бонус: студент {student.fio} на авто директоре")
        
        if bonuses_applied:
            logger.info(f"🔹 Фуллстек студент {student.fio} (ID {student.id}): сдал модули по направлениям {', '.join(bonuses_applied)}, бонус {round(bonus_amount, 2)} руб. каждому директору")
            module_bonuses_applied += len(bonuses_applied)
    
    # Статистика по новой упрощенной системе
    logger.info(f"📊 Статистика 10% бонусов директорам (упрощенная система, только студенты с {september_start}):")
    logger.info(f"📊 Всего фуллстек студентов с сентября: {len(fullstack_students)}")
    logger.info(f"📊 Всего бонусов начислено: {module_bonuses_applied}")
    logger.info(f"📊 Бонусы применены: {'✅ ДА' if module_bonuses_applied > 0 else '❌ НЕТ'}")
    logger.info(f"📅 ВАЖНО: Учитываются только студенты, пришедшие с {september_start} и позже")
    logger.info(f"🎯 НОВОЕ: 10% от стоимости курса при сдаче первого модуля В ПЕРИОДЕ РАСЧЕТА")
    logger.info(f"   • Ручной директор: бонус при сдаче 'ручной 1 модуль' в периоде {start_date} - {end_date}")
    logger.info(f"   • Авто директор: бонус при сдаче 'авто 2 модуль' (Сдача 2 модуля) в периоде {start_date} - {end_date}")
    logger.info(f"   • ВАЖНО: Бонус НЕ начисляется, если студент на самом директоре")
    logger.info(f"   • Каждый директор получает бонус за каждую сдачу первого модуля в периоде")
    
    return {
        'director_salaries': director_salaries,
        'curator_salaries': curator_salaries,
        'logs': detailed_logs,
        'curator_logs': curator_detailed_logs,  # Детальные логи кураторов
        'students_processed': len(students_data),
        'topics_processed': len(topic_assignments),
        'module_bonuses_applied': module_bonuses_applied,
        'fullstack_students_stats': {
            'total_students': len(fullstack_students),
            'bonuses_applied': module_bonuses_applied
        }
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
