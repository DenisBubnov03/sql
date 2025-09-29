from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import logging

# Установите уровень логирования для SQLAlchemy
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)

# URL подключения к базе данных
DATABASE_URL = "postgresql://denisbubnov:denbub0311@localhost/test1"

# Создаем движок для работы с базой данных
engine = create_engine(DATABASE_URL, echo=True)

# Настройка базы для описания таблиц
Base = declarative_base()

# Сессия для работы с базой данных
Session = sessionmaker(bind=engine)

# Глобальная сессия
session = Session()


def get_session():
    """Возвращает новую сессию для работы с базой данных"""
    return Session()


def debug_fullstack_data():
    """Отладочная функция для проверки данных фуллстеков"""
    from data_base.models import Student, FullstackTopicAssign
    from commands.logger import custom_logger

    logger = custom_logger

    try:
        # Проверяем фуллстек студентов
        fullstack_students = session.query(Student).filter(Student.training_type == "Фуллстек").all()
        logger.info(f"🔍 DEBUG: Всего фуллстек студентов: {len(fullstack_students)}")

        # Проверяем записи принятых тем
        all_topics = session.query(FullstackTopicAssign).all()
        logger.info(f"🔍 DEBUG: Всего записей принятых тем: {len(all_topics)}")

        # Проверяем ручные темы
        manual_topics = session.query(FullstackTopicAssign).filter(
            FullstackTopicAssign.topic_manual.isnot(None)
        ).all()
        logger.info(f"🔍 DEBUG: Всего ручных тем: {len(manual_topics)}")

        # Проверяем авто темы
        auto_topics = session.query(FullstackTopicAssign).filter(
            FullstackTopicAssign.topic_auto.isnot(None)
        ).all()
        logger.info(f"🔍 DEBUG: Всего авто тем: {len(auto_topics)}")

        # Показываем примеры данных
        if manual_topics:
            logger.info("🔍 DEBUG: Примеры ручных тем:")
            for topic in manual_topics[:5]:  # Первые 5
                logger.info(f"  • Студент {topic.student_id}, Ментор {topic.mentor_id}: {topic.topic_manual}")

        if auto_topics:
            logger.info("🔍 DEBUG: Примеры авто тем:")
            for topic in auto_topics[:5]:  # Первые 5
                logger.info(f"  • Студент {topic.student_id}, Ментор {topic.mentor_id}: {topic.topic_auto}")

    except Exception as e:
        logger.error(f"❌ Ошибка при отладке данных фуллстеков: {e}")