from data_base import engine, Base
from data_base.models import Student  # Импортируем модели
import logging

# Установите уровень логирования для SQLAlchemy

# Создание таблиц
def initialize_database():
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    initialize_database()
