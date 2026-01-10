from datetime import datetime

from sqlalchemy import Column, Integer, BigInteger, String, Date, DECIMAL, Boolean, ForeignKey, Numeric, Text, DateTime, \
    TIMESTAMP, func, UniqueConstraint, CheckConstraint, Computed
from sqlalchemy.orm import relationship


from data_base import Base


class CareerConsultant(Base):
    __tablename__ = "career_consultants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram = Column(String(50), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(Date, nullable=True)

    # Отношения
    students = relationship("Student", back_populates="career_consultant")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fio = Column(String(255), nullable=False)
    telegram = Column(String(50), unique=True, nullable=False)
    contract_signed = Column(Boolean, default=False, server_default="false")
    start_date = Column(Date, nullable=True)
    training_type = Column(String(255), nullable=True)
    total_cost = Column(DECIMAL(10, 2), nullable=True)
    payment_amount = Column(DECIMAL(10, 2), nullable=True)
    last_call_date = Column(Date, nullable=True)
    company = Column(String(255), nullable=True)
    employment_date = Column(Date, nullable=True)
    salary = Column(DECIMAL(10, 2), default=0, server_default="0")
    fully_paid = Column(String(10), default="Нет", server_default="Нет")
    training_status = Column(String(255), default="Учится", server_default="Учится")
    commission = Column(String(255), nullable=True)
    commission_paid = Column(DECIMAL(10, 2), default=0, server_default="0")
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)
    auto_mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=True)
    career_consultant_id = Column(Integer, ForeignKey("career_consultants.id"), nullable=True)
    consultant_start_date = Column(Date, nullable=True)  # Дата взятия студента в работу карьерным консультантом
    # mentor = relationship("Mentor", backref="students")
    career_consultant = relationship("CareerConsultant", back_populates="students")


class Mentor(Base):
    __tablename__ = "mentors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    chat_id = Column(String, nullable=True)
    direction = Column(String, nullable=False)


class Payment(Base):
    """
    Модель платежей для отслеживания оплат студентов.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID платежа
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True)  # Привязка к студенту (может быть NULL для доп расходов)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=True)  # Привязка к ментору (может быть NULL для расходов)
    amount = Column(Numeric(10, 2), nullable=False)  # Сумма платежа
    payment_date = Column(Date, nullable=False)  # Дата платежа
    comment = Column(Text, nullable=True)  # Комментарий к платежу (например, "Первый платеж")
    status = Column(String(20), default="не подтвержден", nullable=False)

    # Отношения (если нужны)
    student = relationship("Student", back_populates="payments")
    mentor = relationship("Mentor", back_populates="payments")

    def __repr__(self):
        return f"<Payment(id={self.id}, student_id={self.student_id}, mentor_id={self.mentor_id}, amount={self.amount}, date={self.payment_date})>"


class FullstackTopicAssign(Base):
    """
    Модель для отслеживания принятых тем по фуллстек курсу.
    """
    __tablename__ = "fullstack_topic_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)  # ID директора направления (1 или 3)
    topic_manual = Column(String(255), nullable=True)  # Название ручной темы
    topic_auto = Column(String(255), nullable=True)    # Название авто темы
    assigned_at = Column(Date, nullable=False)  # Дата принятия темы

    # Отношения
    student = relationship("Student")
    mentor = relationship("Mentor")

    def __repr__(self):
        topic_info = f"manual: {self.topic_manual}" if self.topic_manual else f"auto: {self.topic_auto}"
        return f"<FullstackTopicAssign(id={self.id}, student_id={self.student_id}, mentor_id={self.mentor_id}, {topic_info})>"


class StudentMeta(Base):
    """
    Модель мета-данных студентов для реферальной системы и отслеживания источников.
    """
    __tablename__ = "student_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    is_referral = Column(Boolean, default=False, server_default="false")
    referrer_telegram = Column(String(50), nullable=True)
    source = Column(String(50), nullable=True)  # ОМ, Ютуб, Инстаграм, Авито, Сайт, Через знакомых, пусто
    created_at = Column(Date, nullable=True)

    # Отношения
    student = relationship("Student", back_populates="meta")

    def __repr__(self):
        return f"<StudentMeta(id={self.id}, student_id={self.student_id}, is_referral={self.is_referral}, source={self.source})>"


Student.payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
Student.meta = relationship("StudentMeta", back_populates="student", cascade="all, delete-orphan", uselist=False)
Mentor.payments = relationship("Payment", back_populates="mentor", cascade="all, delete-orphan")


class ManualProgress(Base):
    __tablename__ = "manual_progress"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)

    m1_start_date = Column(Date)
    m1_submission_date = Column(Date)
    m1_homework = Column(Boolean)

    m2_1_start_date = Column(Date)
    m2_2_start_date = Column(Date)
    m2_1_2_2_submission_date = Column(Date)
    m2_1_homework = Column(Boolean)

    m2_3_start_date = Column(Date)
    m3_1_start_date = Column(Date)
    m2_3_3_1_submission_date = Column(Date)
    m2_3_homework = Column(Boolean)
    m3_1_homework = Column(Boolean)

    m3_2_start_date = Column(Date)
    m3_2_submission_date = Column(Date)
    m3_2_homework = Column(Boolean)

    m3_3_start_date = Column(Date)
    m3_3_submission_date = Column(Date)
    m3_3_homework = Column(Boolean)

    m4_1_start_date = Column(Date)
    m4_1_submission_date = Column(Date)

    m4_2_start_date = Column(Date)
    m4_3_start_date = Column(Date)
    m4_2_4_3_submission_date = Column(Date)
    m4_5_homework = Column(Boolean)
    m4_mock_exam_passed_date = Column(Date)
    m5_start_date = Column(Date)
    m1_mentor_id = Column(Integer, nullable=True)
    m2_1_2_2_mentor_id = Column(Integer, nullable=True)
    m2_3_3_1_mentor_id = Column(Integer, nullable=True)
    m3_2_mentor_id = Column(Integer, nullable=True)
    m3_3_mentor_id = Column(Integer, nullable=True)
    m4_1_mentor_id = Column(Integer, nullable=True)
    m4_2_4_3_mentor_id = Column(Integer, nullable=True)
    m4_mock_exam_mentor_id = Column(Integer, nullable=True)
    # Поле m5_topic_passed_date отсутствует в реальной таблице
    # Используем m5_start_date как дату получения 5 модуля
    
    # Отношения
    student = relationship("Student")

    def __repr__(self):
        return f"<ManualProgress(student_id={self.student_id}, m5_date={self.m5_start_date})>"


class CuratorInsuranceBalance(Base):
    """
    Модель баланса страховки кураторов за студентов, получивших 5 модуль.
    """
    __tablename__ = "curator_insurance_balance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    curator_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    insurance_amount = Column(DECIMAL(10, 2), default=5000.00, server_default="5000.00")
    created_at = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")

    # Отношения
    curator = relationship("Mentor", foreign_keys=[curator_id])
    student = relationship("Student", foreign_keys=[student_id])

    def __repr__(self):
        return f"<CuratorInsuranceBalance(id={self.id}, curator_id={self.curator_id}, student_id={self.student_id}, amount={self.insurance_amount}, active={self.is_active})>"


class CuratorKpiStudents(Base):
    """
    Модель для отслеживания студентов, попавших под KPI куратора в определенном периоде.
    Позволяет применять KPI процент не только к первоначальным платежам, но и к доплатам.
    """
    __tablename__ = "curator_kpi_students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    curator_id = Column(Integer, ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    kpi_percent = Column(DECIMAL(5, 2), nullable=False)  # 0.25 или 0.30
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    created_at = Column(Date, nullable=True)

    # Отношения
    curator = relationship("Mentor", foreign_keys=[curator_id])
    student = relationship("Student", foreign_keys=[student_id])

    def __repr__(self):
        return f"<CuratorKpiStudents(id={self.id}, curator_id={self.curator_id}, student_id={self.student_id}, kpi_percent={self.kpi_percent}, period={self.period_start}-{self.period_end})>"


class ConsultantInsuranceBalance(Base):
    """
    Модель баланса страховки карьерных консультантов за студентов, взятых в работу.
    Страховка составляет 1000 руб за каждого студента, взятого в периоде.
    """
    __tablename__ = "consultant_insurance_balance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consultant_id = Column(Integer, ForeignKey("career_consultants.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    insurance_amount = Column(DECIMAL(10, 2), default=1000.00, server_default="1000.00")
    created_at = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, server_default="true")

    # Отношения
    consultant = relationship("CareerConsultant", foreign_keys=[consultant_id])
    student = relationship("Student", foreign_keys=[student_id])

    def __repr__(self):
        return f"<ConsultantInsuranceBalance(id={self.id}, consultant_id={self.consultant_id}, student_id={self.student_id}, amount={self.insurance_amount}, active={self.is_active})>"


class HeldAmount(Base):
    """
    Модель для холдирования (резервирования) денег за фуллстек кураторов.
    Холдируется часть потенциальной суммы, которая будет выплачена куратору при сдаче модулей.
    """
    __tablename__ = "held_amounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    mentor_id = Column(Integer, ForeignKey("mentors.id", ondelete="SET NULL"), nullable=True)  # Ручной куратор или директор (может быть NULL)
    direction = Column(String(20), nullable=False)  # "manual", "auto", "director_manual", "director_auto"
    held_amount = Column(DECIMAL(10, 2), default=0.00, server_default="0.00")  # Текущая сумма холдирования
    potential_amount = Column(DECIMAL(10, 2), nullable=False)  # Потенциальная сумма, если сдаст все
    paid_amount = Column(DECIMAL(10, 2), default=0.00, server_default="0.00")  # Уже выплачено
    modules_completed = Column(Integer, default=0, server_default="0")  # Количество сданных модулей
    total_modules = Column(Integer, nullable=False)  # Всего модулей (5 для manual, 8 для auto)
    status = Column(String(20), default="active", server_default="active")  # "active" или "released"
    created_at = Column(Date, nullable=True)
    updated_at = Column(Date, nullable=True)

    # Отношения
    student = relationship("Student", foreign_keys=[student_id])
    mentor = relationship("Mentor", foreign_keys=[mentor_id])

    def __repr__(self):
        return f"<HeldAmount(id={self.id}, student_id={self.student_id}, mentor_id={self.mentor_id}, direction={self.direction}, held={self.held_amount}, status={self.status})>"


class AutoProgress(Base):
    __tablename__ = "auto_progress"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    # Модули 1-8: даты открытия
    m1_start_date = Column(Date)
    m2_start_date = Column(Date)
    m3_start_date = Column(Date)
    m4_start_date = Column(Date)
    m5_start_date = Column(Date)
    m6_start_date = Column(Date)
    m7_start_date = Column(Date)
    m8_start_date = Column(Date)
    # Для 2 и 3 модуля — даты сдачи экзаменов
    m2_exam_passed_date = Column(Date)
    m3_exam_passed_date = Column(Date)
    # Для 4-7 модулей — даты сдачи тем
    m4_topic_passed_date = Column(Date)
    m5_topic_passed_date = Column(Date)
    m6_topic_passed_date = Column(Date)
    m7_topic_passed_date = Column(Date)
    m2_exam_mentor_id = Column(Integer, nullable=True)
    m3_exam_mentor_id = Column(Integer, nullable=True)
    m4_topic_mentor_id = Column(Integer, nullable=True)
    m5_topic_mentor_id = Column(Integer, nullable=True)
    m6_topic_mentor_id = Column(Integer, nullable=True)
    m7_topic_mentor_id = Column(Integer, nullable=True)


# class Commission(Base):
#     """
#     Модель данных для таблицы зарплаты (salary).
#     Фиксирует расчет суммы, причитающейся куратору за конкретное поступление.
#     """
#     __tablename__ = 'salary'
#     salary_id = Column(Integer, primary_key=True)
#     payment_id = Column(Integer, ForeignKey('receipts.payment_id'), nullable=False)
#     mentor_id = Column(Integer, nullable=False)
#     calculated_amount = Column(DECIMAL(10, 2), nullable=False)
#     is_paid = Column(Boolean, default=False, nullable=False)
#     date_calculated = Column(DateTime, nullable=True)
#     def __repr__(self):
#         return f"<Commission(id={self.salary_id}, payment_id={self.payment_id}, amount={self.calculated_amount}, paid={self.is_paid})>"

class CuratorCommission(Base):
    """
        Таблица учета 'Потолка' (Общего обязательства) перед ментором/директором.
        Создается при трудоустройстве.
        """
    __tablename__ = "curator_commissions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Ссылка на студента (Обязательно)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)

    # Ментор или Директор, которому мы должны
    curator_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)

    # Ссылка на платеж (Опционально, обычно NULL при создании долга)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)

    # Общая сумма, которую мы обещаем выплатить (Потолок)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)

    # Сколько уже выплатили по факту
    paid_amount = Column(Numeric(10, 2), nullable=False, default=0)

    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Уникальность ПАРЫ: Один студент не может иметь два долга перед ОДНИМ и тем же ментором.
    # Но может иметь долги перед разными менторами.
    __table_args__ = (
        UniqueConstraint('student_id', 'curator_id', name='uq_student_curator_debt'),
    )

    # Связи
    student = relationship("Student", backref="commissions_debt")
    curator = relationship("Mentor")


class Salary(Base):
    """
    Модель данных для таблицы Начислений (Salary).
    Фиксирует расчет суммы, причитающейся куратору за конкретное поступление.
    """
    __tablename__ = 'salary'
    salary_id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)
    calculated_amount = Column(DECIMAL(10, 2), nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    comment = Column(Text, nullable=True)
    mentor_id = Column(Integer, nullable=False)
    date_calculated = Column(DateTime, default=datetime.now)  # Или Date

    def __repr__(self):
        # Используем self.salary_id для соответствия имени колонки
        return (f"<Salary(id={self.salary_id}, payment_id={self.payment_id}, "
                f"amount={self.calculated_amount}, paid={self.is_paid}, comment='{self.comment[:20]}...')>")

class Payout(Base):
    """
    Реестр фактических выплат кураторам.
    """
    __tablename__ = 'payouts'

    payout_id = Column(Integer, primary_key=True)
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=True)

    # 🔥 НОВОЕ ПОЛЕ: Ссылка на карьерного консультанта
    kk_id = Column(Integer, ForeignKey("career_consultants.id"), nullable=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    total_amount = Column(DECIMAL(10, 2), nullable=False)
    payout_status = Column(String(50), nullable=False, default='pending_transfer')
    payout_method = Column(String(50))

    date_processed = Column(DateTime)
    transaction_ref = Column(String(255))
    date_created = Column(DateTime, default=datetime.utcnow)


class SalaryKK(Base):
    """
    Таблица начислений для Карьерных Консультантов (КК).
    """
    __tablename__ = 'salary_kk'

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey('payments.id'), nullable=False)
    kk_id = Column(Integer, ForeignKey('career_consultants.id'), nullable=False)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)

    # 10% от текущего платежа
    calculated_amount = Column(Numeric(10, 2), nullable=False)

    # Сколько ВСЕГО КК должен получить (10% от ЗП студента)
    total_potential = Column(Numeric(10, 2), nullable=False)

    # Сколько ОСТАЛОСЬ получить после этого начисления
    remaining_limit = Column(Numeric(10, 2), nullable=False)

    is_paid = Column(Boolean, default=False, nullable=False)
    date_calculated = Column(DateTime, default=datetime.utcnow)
    comment = Column(Text, nullable=True)

    # Отношения
    student = relationship("Student")
    kk = relationship("CareerConsultant")
    payment = relationship("Payment")


class UnitEconomics(Base):
    __tablename__ = "unit_economics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    product_code = Column(Text, nullable=False, default="default", server_default="default")

    om_manual_cost = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    om_auto_cost = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    avito_cost = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    media_cost = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")

    leads_total_count = Column(Integer, nullable=False, default=0, server_default="0")
    leads_om_count = Column(Integer, nullable=False, default=0, server_default="0")

    infrastructure_costs = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    salary_admin_fixed = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    salary_mentors_manual = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    salary_mentors_auto = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")

    revenue_total = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    product_price = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")

    om_total = Column(
        Numeric(14, 2),
        Computed("om_manual_cost + om_auto_cost", persisted=True),
    )
    marketing_total = Column(
        Numeric(14, 2),
        Computed("(om_manual_cost + om_auto_cost) + avito_cost + media_cost", persisted=True),
    )

    lead_cost_total = Column(
        Numeric(14, 4),
        Computed(
            "((om_manual_cost + om_auto_cost) + avito_cost + media_cost) / NULLIF(leads_total_count, 0)",
            persisted=True,
        ),
    )
    lead_cost_om = Column(
        Numeric(14, 4),
        Computed("(om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0)", persisted=True),
    )

    fixed_costs_total = Column(
        Numeric(14, 2),
        Computed(
            "infrastructure_costs + salary_admin_fixed + salary_mentors_manual + salary_mentors_auto",
            persisted=True,
        ),
    )

    profit_manual_before_fixed = Column(
        Numeric(14, 4),
        Computed("product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))", persisted=True),
    )
    profit_auto_before_fixed = Column(
        Numeric(14, 4),
        Computed("product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))", persisted=True),
    )
    profit_full_before_fixed = Column(
        Numeric(14, 4),
        Computed(
            "product_price - (((om_manual_cost + om_auto_cost) + avito_cost + media_cost) / NULLIF(leads_total_count, 0))",
            persisted=True,
        ),
    )

    dir_manual = Column(
        Numeric(14, 4),
        Computed(
            "(product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10",
            persisted=True,
        ),
    )
    dir_auto = Column(
        Numeric(14, 4),
        Computed(
            "(product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10",
            persisted=True,
        ),
    )

    margin_manual = Column(
        Numeric(14, 4),
        Computed(
            "product_price"
            " - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))"
            " - ((product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10)",
            persisted=True,
        ),
    )
    margin_auto = Column(
        Numeric(14, 4),
        Computed(
            "product_price"
            " - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))"
            " - ((product_price - ((om_manual_cost + om_auto_cost) / NULLIF(leads_om_count, 0))) * 0.10)",
            persisted=True,
        ),
    )

    gross_profit = Column(
        Numeric(14, 2),
        Computed("revenue_total - (((om_manual_cost + om_auto_cost) + avito_cost + media_cost))", persisted=True),
    )
    net_profit = Column(
        Numeric(14, 2),
        Computed(
            "revenue_total"
            " - (((om_manual_cost + om_auto_cost) + avito_cost + media_cost))"
            " - (infrastructure_costs + salary_admin_fixed + salary_mentors_manual + salary_mentors_auto)",
            persisted=True,
        ),
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("period_start", "period_end", "product_code", name="uq_unit_economics_period_product"),
        CheckConstraint("leads_total_count >= 0", name="ck_unit_economics_leads_total_nonneg"),
        CheckConstraint("leads_om_count >= 0", name="ck_unit_economics_leads_om_nonneg"),
    )
