"""
Менеджер VPN-конфигурационных файлов.

Оркестрирует полный цикл генерации VPN-конфига:
SSH-подключение → выполнение скрипта → скачивание файла через SFTP → локальное хранение.
"""

import logging
import os
from typing import Optional

from utils.ssh.ssh_client import SSHClient, SSHConnectionError, SSHCommandError
from utils.ssh.console import RemoteConsole, VPNConfigError

logger = logging.getLogger(__name__)


class VPNConfigManager:
    """
    Управление жизненным циклом VPN-конфигурационных файлов.

    Подключается к VPN-серверу по SSH, вызывает wrapper-скрипт
    для выпуска .ovpn конфига и скачивает его в локальную
    директорию ``doc/``.

    Args:
        host: Имя хоста или IP VPN-сервера.
        username: SSH-пользователь (по умолчанию ``vpnbot``).
        key_path: Путь к приватному SSH-ключу.
        port: SSH-порт (по умолчанию 22).
        local_config_dir: Локальная директория для хранения .ovpn файлов.
            Если не указано, используется ``doc/`` в корне проекта.
    """

    def __init__(
        self,
        host: str,
        username: str,
        key_path: str,
        port: int = 22,
        local_config_dir: Optional[str] = None,
    ) -> None:
        self._host: str = host
        self._username: str = username
        self._key_path: str = key_path
        self._port: int = port
        self._local_config_dir: str = local_config_dir or self._default_config_dir()

    def issue_config(self, telegram_user_id: int) -> str:
        """
        Сгенерировать (или перегенерировать) VPN-конфиг для студента.

        Полный pipeline:
            1. Подключение к VPN-серверу по SSH
            2. Выполнение wrapper-скрипта (отзыв старого + создание нового)
            3. Скачивание .ovpn файла через SFTP
            4. Сохранение в локальную директорию ``doc/``

        Args:
            telegram_user_id: Telegram user_id студента.

        Returns:
            Абсолютный локальный путь к скачанному .ovpn файлу.

        Raises:
            VPNConfigError: Если любой шаг завершился ошибкой.
        """
        self._remove_old_local_config(telegram_user_id)
        local_path: str = self.get_local_config_path(telegram_user_id)

        try:
            with SSHClient(
                host=self._host,
                username=self._username,
                key_path=self._key_path,
                port=self._port,
            ) as ssh:
                console = RemoteConsole(ssh)
                remote_path: str = console.issue_vpn_config(telegram_user_id)
                ssh.download_file(remote_path, local_path)

        except SSHConnectionError as e:
            raise VPNConfigError(f"Не удалось подключиться к VPN-серверу: {e}") from e
        except SSHCommandError as e:
            raise VPNConfigError(
                f"Ошибка выполнения команды на VPN-сервере: {e}"
            ) from e
        except FileNotFoundError as e:
            raise VPNConfigError(
                f"Не удалось скачать конфиг с VPN-сервера: {e}"
            ) from e

        logger.info("VPN: конфиг сохранён локально: %s", local_path)
        return local_path

    def get_local_config_path(self, telegram_user_id: int) -> str:
        """
        Получить ожидаемый локальный путь для .ovpn конфига пользователя.

        Args:
            telegram_user_id: Telegram user_id студента.

        Returns:
            Абсолютный путь, где конфиг будет (или уже) сохранён.
        """
        filename: str = f"tg{telegram_user_id}.ovpn"
        return os.path.join(self._local_config_dir, filename)

    def _remove_old_local_config(self, telegram_user_id: int) -> None:
        """
        Удалить ранее скачанный локальный конфиг, если он существует.

        Args:
            telegram_user_id: Telegram user_id студента.
        """
        local_path: str = self.get_local_config_path(telegram_user_id)
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info("VPN: удалён старый локальный конфиг: %s", local_path)

    @staticmethod
    def _default_config_dir() -> str:
        """
        Определить директорию ``doc/`` относительно корня проекта.

        Поднимается вверх по дереву каталогов от текущего файла,
        пока не найдёт ``bot.py`` или ``.git``.

        Returns:
            Абсолютный путь к директории ``doc/``.
        """
        current_dir: str = os.path.abspath(os.path.dirname(__file__))

        while current_dir != os.path.dirname(current_dir):
            if (os.path.exists(os.path.join(current_dir, "bot.py"))
                    or os.path.exists(os.path.join(current_dir, ".git"))):
                doc_dir: str = os.path.join(current_dir, "doc")
                os.makedirs(doc_dir, exist_ok=True)
                return doc_dir
            current_dir = os.path.dirname(current_dir)

        fallback: str = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "doc"
        )
        os.makedirs(fallback, exist_ok=True)
        return fallback
