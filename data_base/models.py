from sqlalchemy import Column, Integer, String, Date, DECIMAL, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from data_base import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fio = Column(String(255), nullable=False)
    telegram = Column(String(50), unique=True, nullable=False)
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
    extra_payment_amount = Column(DECIMAL(10, 2), default=0, server_default="0")  # Сумма доплаты
    extra_payment_date = Column(Date, nullable=True)  # Дата последнего платежа
    mentor_id = Column(Integer, ForeignKey("mentors.id"), nullable=False)
    mentor = relationship("Mentor", backref="students")

class Mentor(Base):
    __tablename__ = "mentors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    chat_id = Column(String, nullable=True)
    direction = Column(String, unique=True, nullable=False)