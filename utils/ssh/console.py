"""
Интерфейс удалённой консоли VPN-сервера.

Предоставляет высокоуровневые методы для взаимодействия
с VPN-сервером через SSH-соединение.
"""

import logging

from utils.ssh.ssh_client import SSHClient, SSHCommandError

logger = logging.getLogger(__name__)


class VPNConfigError(Exception):
    """Ошибка генерации VPN-конфигурации на сервере."""
    pass


class RemoteConsole:
    """
    Высокоуровневый интерфейс для операций на VPN-сервере.

    Оборачивает ``SSHClient`` и предоставляет доменные методы
    вместо прямого выполнения shell-команд.

    Args:
        ssh_client: Активный (подключённый) экземпляр ``SSHClient``.
    """

    WRAPPER_SCRIPT: str = "/etc/openvpn/scripts/adminbot-wrapper.sh"

    def __init__(self, ssh_client: SSHClient) -> None:
        self._ssh: SSHClient = ssh_client

    def issue_vpn_config(self, user_id: int) -> str:
        """
        Выпустить (или перевыпустить) VPN-конфиг для пользователя Telegram.

        Вызывает серверный wrapper-скрипт, который автоматически отзывает
        старый конфиг (если есть) и создаёт новый на 365 дней.

        Args:
            user_id: Telegram user_id студента.

        Returns:
            Абсолютный путь к .ovpn файлу на удалённом сервере.

        Raises:
            VPNConfigError: Если скрипт вернул ошибку или конфиг не создан.
        """
        command: str = f"sudo {self.WRAPPER_SCRIPT} issue {user_id}"
        logger.info("VPN: выпуск конфига для user_id=%d", user_id)

        try:
            stdout, stderr, exit_code = self._ssh.execute(command, timeout=60)
        except SSHCommandError as e:
            raise VPNConfigError(
                f"Скрипт генерации VPN завершился с ошибкой (код {e.exit_code}): "
                f"{e.stderr or e}"
            ) from e

        if not stdout or stdout.startswith("ERROR"):
            raise VPNConfigError(
                f"VPN-сервер не создал конфиг: {stdout or 'пустой ответ'}"
            )

        remote_path: str = stdout.strip()
        logger.info("VPN: конфиг создан на сервере: %s", remote_path)
        return remote_path
