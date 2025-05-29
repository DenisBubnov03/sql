import logging
from datetime import datetime
# Настройка логирования
logging.basicConfig(
    filename="bot_logs.log",  # Имя файла для логирования
    level=logging.INFO,       # Уровень логирования
    format="%(asctime)s - %(levelname)s - %(message)s",  # Формат логов
)
custom_logger = logging.getLogger("custom_logger")
custom_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)


# Настройка логгера
logging.basicConfig(
    filename="student_changes.log",
    level=logging.WARNING,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Функция для логирования изменений
def log_student_change(editor_tg, student_name, changes):
    """
    Логирование изменений данных ученика.
    :param editor_tg: Telegram пользователя, который изменил данные
    :param student_name: Имя ученика
    :param changes: Словарь с изменениями (формат: {поле: (старое значение, новое значение)})
    """
    for field, (old_value, new_value) in changes.items():
        logging.info(
            f"@{editor_tg} изменил данные ученика {student_name}: {field}: {old_value} на {new_value}"
        )

