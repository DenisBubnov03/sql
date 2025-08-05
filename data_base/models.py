from sqlalchemy import Column, Integer, String, Date, DECIMAL, Boolean, ForeignKey, Numeric, Text
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
    # mentor = relationship("Mentor", backref="students")
    career_consultant = relationship("CareerConsultant", back_populates="students")


class Mentor(Base):
    __tablename__ = "mentors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    chat_id = Column(String, nullable=True)
    direction = Column(String, unique=True, nullable=False)


class Payment(Base):
    """
    Модель платежей для отслеживания оплат студентов.
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID платежа
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)  # Привязка к студенту
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


Student.payments = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
Mentor.payments = relationship("Payment", back_populates="mentor", cascade="all, delete-orphan")

