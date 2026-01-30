"""
Обработчики Telegram-бота для генерации VPN-конфигов.

Поток ConversationHandler:
    1. Админ/ментор нажимает «Создать OVPN конфиг»
    2. Бот просит ввести @telegram студента
    3. Бот проверяет наличие студента в БД
    4. Бот генерирует/перегенерирует .ovpn конфиг через SSH
    5. Бот отправляет .ovpn файл обратно запросившему
"""

import logging
import os
import traceback

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from classes.vpn_config import VPNConfigManager, VPNConfigError
from commands.start_commands import exit_to_main_menu
from commands.states import VPN_AWAITING_TELEGRAM
from data_base.db import session
from data_base.models import Student
from utils.security import restrict_to

logger = logging.getLogger(__name__)


def _get_vpn_manager() -> VPNConfigManager:
    """
    Создать ``VPNConfigManager`` из переменных окружения.

    Читает из ``.env``:
        - ``VPN_SSH_HOST`` — IP или hostname VPN-сервера
        - ``VPN_SSH_PORT`` — SSH-порт (по умолчанию 22)
        - ``VPN_SSH_USERNAME`` — SSH-пользователь (по умолчанию ``adminbot``)
        - ``VPN_SSH_KEY_PATH`` — путь к приватному SSH-ключу

    Returns:
        Сконфигурированный экземпляр ``VPNConfigManager``.

    Raises:
        ValueError: Если ``VPN_SSH_HOST`` или ``VPN_SSH_KEY_PATH`` не заданы.
    """
    host: str = os.getenv("VPN_SSH_HOST", "")
    port: int = int(os.getenv("VPN_SSH_PORT", "22"))
    username: str = os.getenv("VPN_SSH_USERNAME", "adminbot")
    key_path: str = os.getenv("VPN_SSH_KEY_PATH", "")

    if not host:
        raise ValueError("Переменная окружения VPN_SSH_HOST не задана")
    if not key_path:
        raise ValueError("Переменная окружения VPN_SSH_KEY_PATH не задана")

    return VPNConfigManager(
        host=host,
        username=username,
        key_path=key_path,
        port=port,
    )


@restrict_to(["admin", "mentor"])
async def start_vpn_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Точка входа: запрос у пользователя Telegram-хэндла студента.

    Args:
        update: Входящее обновление Telegram.
        context: Контекст обработчика.

    Returns:
        Состояние ``VPN_AWAITING_TELEGRAM``.
    """
    await update.message.reply_text(
        "Введите Telegram ученика (например: @student):",
        reply_markup=ReplyKeyboardMarkup(
            [["Главное меню"]],
            one_time_keyboard=True,
            resize_keyboard=True,
        ),
    )
    return VPN_AWAITING_TELEGRAM


async def handle_vpn_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработать введённый Telegram-хэндл студента.

    Последовательность:
        1. Нормализация @хэндла
        2. Поиск студента в БД
        3. Проверка наличия chat_id (Telegram user_id)
        4. Генерация VPN-конфига через SSH
        5. Отправка .ovpn файла запросившему

    При любой ошибке отправляет детали исключения пользователю
    и возвращает в главное меню.

    Args:
        update: Входящее обновление Telegram.
        context: Контекст обработчика.

    Returns:
        ``VPN_AWAITING_TELEGRAM`` при ошибке валидации,
        ``ConversationHandler.END`` при завершении.
    """
    text: str = update.message.text.strip()

    if text == "Главное меню":
        return await exit_to_main_menu(update, context)

    try:
        # 1. Нормализация хэндла
        tg_clean: str = text.replace("@", "").strip()
        tg_with_at: str = f"@{tg_clean}"

        # 2. Поиск студента в БД
        student = session.query(Student).filter(
            (Student.telegram == tg_with_at) | (Student.telegram == tg_clean)
        ).first()

        if not student:
            await update.message.reply_text(
                f"❌ Студент с Telegram {tg_with_at} не найден в базе данных.\n"
                "Попробуйте ещё раз или нажмите «Главное меню».",
                reply_markup=ReplyKeyboardMarkup(
                    [["Главное меню"]],
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return VPN_AWAITING_TELEGRAM

        # 3. Проверка chat_id
        if not student.chat_id:
            await update.message.reply_text(
                f"❌ У студента {student.fio} ({tg_with_at}) не указан chat_id.\n"
                "Студент должен хотя бы раз написать боту /start.\n"
                "Попробуйте другого студента или нажмите «Главное меню».",
                reply_markup=ReplyKeyboardMarkup(
                    [["Главное меню"]],
                    one_time_keyboard=True,
                    resize_keyboard=True,
                ),
            )
            return VPN_AWAITING_TELEGRAM

        user_id: int = int(student.chat_id)

        # 4. Уведомление о начале генерации
        await update.message.reply_text(
            f"⏳ Генерация VPN конфига для {student.fio} ({tg_with_at})...\n"
            "Это может занять несколько секунд."
        )

        # 5. Генерация конфига
        manager: VPNConfigManager = _get_vpn_manager()
        local_path: str = manager.issue_config(user_id)

        # 6. Отправка файла
        with open(local_path, "rb") as ovpn_file:
            await update.message.reply_document(
                document=ovpn_file,
                filename=os.path.basename(local_path),
                caption=f"✅ VPN конфиг для {student.fio} ({tg_with_at})",
            )

        return await exit_to_main_menu(update, context)

    except VPNConfigError as e:
        logger.error("VPN config error: %s", e, exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка генерации VPN конфига:\n{e}\n\n"
            "Обратитесь к администратору сервера.",
            reply_markup=ReplyKeyboardMarkup(
                [["Главное меню"]],
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return await exit_to_main_menu(update, context)

    except Exception as e:
        logger.error("Unexpected error in VPN handler: %s", e, exc_info=True)
        error_details: str = traceback.format_exc()
        # Отправляем трейсбек запросившему (обрезаем до 1500 символов для Telegram)
        await update.message.reply_text(
            f"❌ Непредвиденная ошибка:\n\n"
            f"<pre>{error_details[-1500:]}</pre>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                [["Главное меню"]],
                one_time_keyboard=True,
                resize_keyboard=True,
            ),
        )
        return await exit_to_main_menu(update, context)
