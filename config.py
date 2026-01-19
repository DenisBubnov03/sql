# config.py
from sqlalchemy.util.queue import FallbackAsyncAdaptedQueue
from datetime import date  # Импорт date для использования в NEW_PAYMENT_SYSTEM_START_DATE


class Config:
    # Фича-флаги
    CURATOR_INSURANCE_ENABLED = False  # Включить/выключить страховочные выплаты для кураторов
    CONSULTANT_INSURANCE_ENABLED = True  # Включить/выключить страховочные выплаты для карьерных консультантов
    KPI_ENABLED = False  # Включить/выключить KPI систему
    
    # Настройки страховки
    INSURANCE_AMOUNT = 5000.00  # Сумма страховки для кураторов
    CONSULTANT_INSURANCE_AMOUNT = 1000.00  # Сумма страховки для карьерных консультантов
    INSURANCE_TRAINING_TYPE = "Ручное тестирование"  # Тип обучения для страховки
    
    # Настройки KPI
    KPI_THRESHOLDS = {
        "step1": {
            "min_students": 5,
            "max_students": 9,
            "percent": 0.25,  # 25%
            "description": "5-9 студентов"
        },
        "step2": {
            "min_students": 10,
            "max_students": None,  # Без ограничений
            "percent": 0.30,  # 30%
            "description": "10+ студентов"
        }
    }
    
    # Стандартный процент для сравнения
    STANDARD_PERCENT = 0.20  # 20%
    
    # Дополнительные настройки
    AUTO_INSURANCE_ENABLED = True  # Автоматическое начисление при расчете ЗП
    MANUAL_INSURANCE_ENABLED = True  # Ручное начисление при изменении статуса
    
    # Настройки холдирования для фуллстек кураторов
    FULLSTACK_MANUAL_COURSE_COST = 46000.00  # Стоимость ручного курса фуллстек
    FULLSTACK_AUTO_COURSE_COST = 86000.00    # Стоимость авто курса фуллстек
    MANUAL_CURATOR_RESERVE_PERCENT = 0.20      # 20% от стоимости для ручного куратора
    AUTO_CURATOR_RESERVE_PERCENT = 0.20        # 20% от стоимости для авто куратора
    MANUAL_MODULES_TOTAL = 5                   # Всего ручных модулей
    AUTO_MODULES_TOTAL = 8                     # Всего авто модулей
    HELD_AMOUNTS_ENABLED = True                # Включить/выключить систему холдирования
    
    # Настройки холдирования для директоров направлений
    DIRECTOR_MANUAL_ID = 1                     # ID директора ручного направления
    DIRECTOR_AUTO_ID = 3                       # ID директора авто направления
    DIRECTOR_RESERVE_PERCENT = 0.30            # 30% от total_cost студента для директоров
    
    # Дата перехода на новую форму оплаты (расчет по темам/модулям вместо процента от платежей)
    NEW_PAYMENT_SYSTEM_START_DATE = date(2025, 11,
                                         1)  # Студенты, пришедшие с этой даты, рассчитываются по новой системе

    # Методы для управления страховкой кураторов
    @classmethod
    def enable_curator_insurance(cls):
        """Включить страховочные выплаты для кураторов"""
        cls.CURATOR_INSURANCE_ENABLED = True
        print("🛡️ Страховочные выплаты для кураторов включены")
    
    @classmethod
    def disable_curator_insurance(cls):
        """Отключить страховочные выплаты для кураторов"""
        cls.CURATOR_INSURANCE_ENABLED = False
        print("🛡️ Страховочные выплаты для кураторов отключены")
    
    @classmethod
    def get_curator_insurance_status(cls):
        """Получить статус страховочных выплат для кураторов"""
        return "включены" if cls.CURATOR_INSURANCE_ENABLED else "отключены"
    
    # Методы для управления страховкой КК
    @classmethod
    def enable_consultant_insurance(cls):
        """Включить страховочные выплаты для карьерных консультантов"""
        cls.CONSULTANT_INSURANCE_ENABLED = True
        print("🛡️ Страховочные выплаты для КК включены")
    
    @classmethod
    def disable_consultant_insurance(cls):
        """Отключить страховочные выплаты для карьерных консультантов"""
        cls.CONSULTANT_INSURANCE_ENABLED = False
        print("🛡️ Страховочные выплаты для КК отключены")
    
    @classmethod
    def get_consultant_insurance_status(cls):
        """Получить статус страховочных выплат для карьерных консультантов"""
        return "включены" if cls.CONSULTANT_INSURANCE_ENABLED else "отключены"
    
    # Обратная совместимость (для старых методов)
    @classmethod
    def enable_insurance(cls):
        """Включить страховочные выплаты (для кураторов и КК)"""
        cls.CURATOR_INSURANCE_ENABLED = True
        cls.CONSULTANT_INSURANCE_ENABLED = True
        print("🛡️ Страховочные выплаты включены (кураторы и КК)")
    
    @classmethod
    def disable_insurance(cls):
        """Отключить страховочные выплаты (для кураторов и КК)"""
        cls.CURATOR_INSURANCE_ENABLED = False
        cls.CONSULTANT_INSURANCE_ENABLED = False
        print("🛡️ Страховочные выплаты отключены (кураторы и КК)")
    
    @classmethod
    def get_insurance_status(cls):
        """Получить статус страховочных выплат (для кураторов и КК)"""
        curator_status = "включены" if cls.CURATOR_INSURANCE_ENABLED else "отключены"
        consultant_status = "включены" if cls.CONSULTANT_INSURANCE_ENABLED else "отключены"
        return f"Кураторы: {curator_status}, КК: {consultant_status}"
    
    # Методы для управления KPI
    @classmethod
    def enable_kpi(cls):
        """Включить KPI систему"""
        cls.KPI_ENABLED = True
        print("🎯 KPI система включена")
    
    @classmethod
    def disable_kpi(cls):
        """Отключить KPI систему"""
        cls.KPI_ENABLED = False
        print("🎯 KPI система отключена")
    
    @classmethod
    def get_kpi_status(cls):
        """Получить статус KPI системы"""
        return "включена" if cls.KPI_ENABLED else "отключена"
    
    @classmethod
    def get_kpi_percent(cls, student_count):
        """Получить процент KPI для количества студентов"""
        if not cls.KPI_ENABLED:
            return 0
        
        for step_name, step_config in cls.KPI_THRESHOLDS.items():
            min_students = step_config["min_students"]
            max_students = step_config["max_students"]
            
            if max_students is None:
                # Без ограничений (например, 10+ студентов)
                if student_count >= min_students:
                    return step_config["percent"]
            else:
                # С ограничениями (например, 5-9 студентов)
                if min_students <= student_count <= max_students:
                    return step_config["percent"]
        
        return 0  # Не попадает ни под одну ступень
    
    @classmethod
    def update_kpi_threshold(cls, step_name, min_students=None, max_students=None, percent=None):
        """Обновить пороги KPI"""
        if step_name not in cls.KPI_THRESHOLDS:
            print(f"❌ Ступень {step_name} не найдена")
            return
        
        if min_students is not None:
            cls.KPI_THRESHOLDS[step_name]["min_students"] = min_students
        if max_students is not None:
            cls.KPI_THRESHOLDS[step_name]["max_students"] = max_students
        if percent is not None:
            cls.KPI_THRESHOLDS[step_name]["percent"] = percent
        
        print(f"✅ Ступень {step_name} обновлена: {cls.KPI_THRESHOLDS[step_name]}")
    
    @classmethod
    def get_kpi_info(cls):
        """Получить информацию о настройках KPI"""
        info = f"KPI система: {cls.get_kpi_status()}\n"
        info += f"Стандартный процент: {cls.STANDARD_PERCENT * 100}%\n\n"
        
        for step_name, step_config in cls.KPI_THRESHOLDS.items():
            if step_config["max_students"] is None:
                info += f"Ступень {step_name}: {step_config['min_students']}+ студентов → {step_config['percent'] * 100}%\n"
            else:
                info += f"Ступень {step_name}: {step_config['min_students']}-{step_config['max_students']} студентов → {step_config['percent'] * 100}%\n"
        
        return info
