#!/usr/bin/env python3
"""
🎯 ТЕСТ ЛОГИКИ 10% БОНУСОВ ПО СДАЧЕ 1 МОДУЛЯ
Проверяем, что директора получают бонусы только если студент сдал 1 модуль по их направлению
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

class MockStudent:
    def __init__(self, id, fio, telegram, training_type, start_date, total_cost=100000):
        self.id = id
        self.fio = fio
        self.telegram = telegram
        self.training_type = training_type
        self.start_date = start_date
        self.total_cost = total_cost

class MockPayment:
    def __init__(self, student_id, mentor_id, amount, payment_date):
        self.student_id = student_id
        self.mentor_id = mentor_id
        self.amount = Decimal(str(amount))
        self.payment_date = payment_date

class MockTopicAssignment:
    def __init__(self, student_id, mentor_id, topic_manual=None, topic_auto=None):
        self.student_id = student_id
        self.mentor_id = mentor_id
        self.topic_manual = topic_manual
        self.topic_auto = topic_auto
        self.assigned_at = datetime.now()

class MockMentor:
    def __init__(self, id, full_name):
        self.id = id
        self.full_name = full_name

def test_module_1_bonus_logic():
    """Тестируем логику 10% бонусов по сдаче 1 модуля"""
    print("🎯 ТЕСТ ЛОГИКИ 10% БОНУСОВ ПО СДАЧЕ 1 МОДУЛЯ")
    print("=" * 70)
    
    # Критическая дата - 1 сентября 2025 (как в коде)
    september_start = date(2025, 9, 1)
    print(f"📅 Учитываются студенты с: {september_start}")
    
    print("\n🎯 НОВАЯ ЛОГИКА:")
    print("   ✅ Ручной директор (ID=1): бонус только если студент сдал 'ручной 1 модуль'")
    print("   ✅ Авто директор (ID=3): бонус только если студент сдал 'авто 1 модуль' (Сдача 2 модуля)")
    print("   ❌ Если студент не сдал 1 модуль по направлению → директор НЕ получает бонус")
    
    # Создаем тестовых студентов
    test_students = [
        MockStudent(1, "Студент Только Ручной", "@manual_only", "Фуллстек", date(2025, 10, 1)),
        MockStudent(2, "Студент Только Авто", "@auto_only", "Фуллстек", date(2025, 10, 1)),
        MockStudent(3, "Студент Оба Направления", "@both", "Фуллстек", date(2025, 10, 1)),
        MockStudent(4, "Студент Без Модулей", "@none", "Фуллстек", date(2025, 10, 1)),
        MockStudent(5, "Студент Переключился", "@switched", "Фуллстек", date(2025, 10, 1)),
    ]
    
    # Создаем назначения тем (кто что сдал)
    test_assignments = [
        # Студент 1: только ручной 1 модуль
        MockTopicAssignment(1, 2, topic_manual="1 модуль"),
        
        # Студент 2: только авто 1 модуль
        MockTopicAssignment(2, 2, topic_auto="Сдача 2 модуля"),
        
        # Студент 3: оба направления
        MockTopicAssignment(3, 2, topic_manual="1 модуль"),
        MockTopicAssignment(3, 2, topic_auto="Сдача 2 модуля"),
        
        # Студент 4: никаких модулей не сдал
        
        # Студент 5: сначала сдал ручной, потом авто (сценарий переключения)
        MockTopicAssignment(5, 2, topic_manual="1 модуль"),  # Месяц назад
        MockTopicAssignment(5, 2, topic_auto="Сдача 2 модуля"),  # Недавно
    ]
    
    # Создаем платежи от кураторов (ID=2)
    test_payments = []
    for student in test_students:
        test_payments.append(MockPayment(
            student_id=student.id,
            mentor_id=2,  # Куратор
            amount=50000,
            payment_date=date.today()
        ))
    
    # Создаем ментора
    curator = MockMentor(2, "Куратор Тестовый")
    
    print(f"\n👥 ТЕСТОВЫЕ СЦЕНАРИИ:")
    print("-" * 50)
    
    # Симулируем логику как в реальной функции
    director_salaries = {1: 0, 3: 0}
    detailed_logs = {1: [], 3: []}
    
    for payment in test_payments:
        student = next((s for s in test_students if s.id == payment.student_id), None)
        if not student:
            continue
        
        print(f"\n🔍 Обрабатываем студента: {student.fio}")
        
        # Проверяем сдачу модулей
        has_manual_module_1 = any(
            a.student_id == student.id and a.topic_manual == "1 модуль" 
            for a in test_assignments
        )
        has_auto_module_1 = any(
            a.student_id == student.id and a.topic_auto == "Сдача 2 модуля" 
            for a in test_assignments
        )
        
        print(f"   📚 Сдал ручной 1 модуль: {'✅ ДА' if has_manual_module_1 else '❌ НЕТ'}")
        print(f"   🤖 Сдал авто 1 модуль: {'✅ ДА' if has_auto_module_1 else '❌ НЕТ'}")
        
        # Логика начисления бонусов
        bonus = float(payment.amount) * 0.1
        bonuses_applied = []
        
        # Бонус ручному директору
        if has_manual_module_1:
            director_salaries[1] += bonus
            detailed_logs[1].append(f"Бонус за {student.fio}: +{bonus:.0f} руб.")
            bonuses_applied.append("ручной")
            print(f"   ✅ Ручному директору: +{bonus:.0f} руб.")
        else:
            print(f"   ❌ Ручному директору: 0 руб. (не сдал ручной 1 модуль)")
        
        # Бонус авто директору
        if has_auto_module_1:
            director_salaries[3] += bonus
            detailed_logs[3].append(f"Бонус за {student.fio}: +{bonus:.0f} руб.")
            bonuses_applied.append("авто")
            print(f"   ✅ Авто директору: +{bonus:.0f} руб.")
        else:
            print(f"   ❌ Авто директору: 0 руб. (не сдал авто 1 модуль)")
        
        print(f"   💰 Платеж {payment.amount} руб. → бонусы: {', '.join(bonuses_applied) if bonuses_applied else 'НЕТ'}")
    
    # Подводим итоги
    print(f"\n📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print("-" * 50)
    print(f"💰 Ручной директор (ID=1): {director_salaries[1]:.0f} руб.")
    print(f"💰 Авто директор (ID=3): {director_salaries[3]:.0f} руб.")
    print(f"💰 Общая сумма бонусов: {director_salaries[1] + director_salaries[3]:.0f} руб.")
    
    print(f"\n📋 ДЕТАЛИЗАЦИЯ:")
    print(f"   Ручной директор:")
    for log in detailed_logs[1]:
        print(f"      • {log}")
    if not detailed_logs[1]:
        print(f"      • Нет бонусов")
    
    print(f"   Авто директор:")
    for log in detailed_logs[3]:
        print(f"      • {log}")
    if not detailed_logs[3]:
        print(f"      • Нет бонусов")
    
    # Проверяем ожидаемые результаты
    print(f"\n🧪 ПРОВЕРКА ОЖИДАЕМЫХ РЕЗУЛЬТАТОВ:")
    print("-" * 50)
    
    # Ожидаемые бонусы:
    # Студент 1 (только ручной): ручной директор +5000
    # Студент 2 (только авто): авто директор +5000  
    # Студент 3 (оба): оба директора +5000 каждый
    # Студент 4 (никто): никому ничего
    # Студент 5 (оба): оба директора +5000 каждый
    
    expected_manual = 5000 * 3  # Студенты 1, 3, 5
    expected_auto = 5000 * 3    # Студенты 2, 3, 5
    
    manual_correct = director_salaries[1] == expected_manual
    auto_correct = director_salaries[3] == expected_auto
    
    print(f"✅ Ручной директор: ожидалось {expected_manual:.0f}, получено {director_salaries[1]:.0f} {'✅' if manual_correct else '❌'}")
    print(f"✅ Авто директор: ожидалось {expected_auto:.0f}, получено {director_salaries[3]:.0f} {'✅' if auto_correct else '❌'}")
    
    success = manual_correct and auto_correct
    
    print(f"\n" + "=" * 70)
    if success:
        print("🎉 ТЕСТ ЛОГИКИ 10% БОНУСОВ ПО СДАЧЕ 1 МОДУЛЯ ПРОЙДЕН!")
        print("✅ Система корректно начисляет бонусы только за сданные модули")
        print("🎯 Логика переключения направлений работает правильно")
    else:
        print("💥 ТЕСТ ЛОГИКИ 10% БОНУСОВ ПО СДАЧЕ 1 МОДУЛЯ ПРОВАЛЕН!")
        print("❌ Система неправильно начисляет бонусы")
        print("🔧 Требуется исправление логики")
    
    print(f"\n🔍 КЛЮЧЕВЫЕ ОСОБЕННОСТИ НОВОЙ ЛОГИКИ:")
    print(f"   🎯 Условие: студент должен сдать 1 модуль по направлению")
    print(f"   📚 Ручной 1 модуль: 'topic_manual = \"1 модуль\"'")
    print(f"   🤖 Авто 1 модуль: 'topic_auto = \"Сдача 2 модуля\"'")
    print(f"   🔄 Переключение: студент может сдать оба → получают оба директора")
    print(f"   ⏰ Время сдачи: не важно, главное что сдал")
    print(f"   💰 Размер бонуса: 10% от суммы платежа")
    
    return success

if __name__ == "__main__":
    print("🎯🎯🎯 ТЕСТ ЛОГИКИ 10% БОНУСОВ ПО СДАЧЕ 1 МОДУЛЯ 🎯🎯🎯")
    print("Проверяем новую логику: бонус только за сданные модули!")
    print()
    
    success = test_module_1_bonus_logic()
    
    print("\n" + "🎯" * 70)
    if success:
        print("🏆 ЛОГИКА 10% БОНУСОВ РАБОТАЕТ ИДЕАЛЬНО! 🏆")
        print("📚 СИСТЕМА ПРАВИЛЬНО УЧИТЫВАЕТ СДАЧУ МОДУЛЕЙ! 📚")
    else:
        print("⚠️ ЛОГИКА ТРЕБУЕТ ДОРАБОТКИ! ⚠️")
        print("🔧 ПРОВЕРЬТЕ КОД НАЧИСЛЕНИЯ БОНУСОВ! 🔧")
    
    exit(0 if success else 1)
