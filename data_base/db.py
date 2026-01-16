from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
import logging

# Установите уровень логирования для SQLAlchemy

DATABASE_URL = "postgresql://denisbubnov:denbub0311@localhost/test"
engine = create_engine(DATABASE_URL, echo=False)


# Создание базы для описания таблиц
Base = declarative_base()

# Настройка сессии
Session = sessionmaker(bind=engine)
session = Session()
session_factory = scoped_session(Session)

def get_session():
    """Получить сессию для текущего контекста"""
    return session_factory()

def close_session():
    """Закрыть текущую сессию"""
    session_factory.remove()

# Для обратной совместимости
session = get_session()

# Экспортируем функции для импорта
__all__ = ['get_session', 'close_session', 'session', 'Session', 'Base', 'engine']