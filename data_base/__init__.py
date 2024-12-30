from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

# Установите уровень логирования для SQLAlchemy

# URL подключения к базе данных
DATABASE_URL = "postgresql://bot_user:password@localhost/student_tracker"

# Создаем движок для работы с базой данных
engine = create_engine(DATABASE_URL, echo=True)

# Настройка базы для описания таблиц
Base = declarative_base()

# Сессия для работы с базой данных
Session = sessionmaker(bind=engine)
