"""
Модуль SSH-клиента для подключения к удалённым серверам.

Обёртка над paramiko: выполнение команд и передача файлов по SFTP.
Работает на Linux и Windows.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import paramiko

logger = logging.getLogger(__name__)


class SSHConnectionError(Exception):
    """Ошибка установки SSH-соединения."""
    pass


class SSHCommandError(Exception):
    """Ошибка выполнения команды на удалённом сервере."""

    def __init__(self, message: str, exit_code: int, stderr: str) -> None:
        self.exit_code: int = exit_code
        self.stderr: str = stderr
        super().__init__(message)


class SSHClient:
    """
    SSH-клиент для выполнения команд и передачи файлов.

    Поддерживает контекстный менеджер::

        client = SSHClient(host="1.2.3.4", username="adminbot",
                           key_path="~/.ssh/adminbot_key")
        with client:
            stdout, stderr, code = client.execute("whoami")
            client.download_file("/remote/file.ovpn", "/local/file.ovpn")

    Args:
        host: Имя хоста или IP-адрес удалённого сервера.
        username: Имя пользователя для SSH-авторизации.
        key_path: Путь к приватному SSH-ключу (поддерживает ``~``).
        port: Порт SSH (по умолчанию 22).
        timeout: Таймаут подключения в секундах (по умолчанию 10).
    """

    def __init__(
        self,
        host: str,
        username: str,
        key_path: str,
        port: int = 22,
        timeout: int = 10,
    ) -> None:
        self._host: str = host
        self._port: int = port
        self._username: str = username
        self._key_path: str = self._resolve_key_path(key_path)
        self._timeout: int = timeout
        self._client: Optional[paramiko.SSHClient] = None

    # ── context manager ──────────────────────────────────────────

    def __enter__(self) -> "SSHClient":
        """Открыть SSH-соединение при входе в контекст."""
        self.connect()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Закрыть SSH-соединение при выходе из контекста."""
        self.disconnect()

    # ── public API ───────────────────────────────────────────────

    def connect(self) -> None:
        """
        Установить SSH-соединение с аутентификацией по ключу.

        Raises:
            SSHConnectionError: Если соединение не удалось.
        """
        if self._client is not None:
            return

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            private_key = paramiko.Ed25519Key.from_private_key_file(self._key_path)

            client.connect(
                hostname=self._host,
                port=self._port,
                username=self._username,
                pkey=private_key,
                timeout=self._timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            self._client = client
            logger.info("SSH: подключено к %s@%s:%s", self._username, self._host, self._port)

        except paramiko.AuthenticationException as e:
            raise SSHConnectionError(
                f"Ошибка аутентификации SSH на {self._host}: {e}"
            ) from e
        except paramiko.SSHException as e:
            raise SSHConnectionError(
                f"Ошибка SSH-протокола при подключении к {self._host}: {e}"
            ) from e
        except OSError as e:
            raise SSHConnectionError(
                f"Не удалось подключиться к {self._host}:{self._port}: {e}"
            ) from e

    def disconnect(self) -> None:
        """Закрыть SSH-соединение."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("SSH: отключено от %s", self._host)

    def execute(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """
        Выполнить команду на удалённом сервере.

        Args:
            command: Shell-команда для выполнения.
            timeout: Таймаут выполнения команды в секундах.

        Returns:
            Кортеж ``(stdout, stderr, exit_code)``.

        Raises:
            SSHConnectionError: Если соединение не установлено.
            SSHCommandError: Если команда завершилась с ненулевым кодом.
        """
        if self._client is None:
            raise SSHConnectionError("SSH-соединение не установлено. Вызовите connect().")

        logger.debug("SSH exec: %s", command)

        stdin, stdout_ch, stderr_ch = self._client.exec_command(command, timeout=timeout)
        stdin.close()

        stdout_text: str = stdout_ch.read().decode("utf-8", errors="replace").strip()
        stderr_text: str = stderr_ch.read().decode("utf-8", errors="replace").strip()
        exit_code: int = stdout_ch.channel.recv_exit_status()

        logger.debug("SSH exec result: code=%d, stdout=%s, stderr=%s",
                      exit_code, stdout_text[:200], stderr_text[:200])

        if exit_code != 0:
            raise SSHCommandError(
                f"Команда завершилась с кодом {exit_code}: {stderr_text or stdout_text}",
                exit_code=exit_code,
                stderr=stderr_text,
            )

        return stdout_text, stderr_text, exit_code

    def download_file(self, remote_path: str, local_path: str) -> str:
        """
        Скачать файл с удалённого сервера через SFTP.

        Args:
            remote_path: Абсолютный путь к файлу на сервере.
            local_path: Абсолютный путь для сохранения на локальной машине.

        Returns:
            ``local_path`` — путь к сохранённому файлу.

        Raises:
            SSHConnectionError: Если соединение не установлено.
            FileNotFoundError: Если файл на сервере не найден.
        """
        if self._client is None:
            raise SSHConnectionError("SSH-соединение не установлено. Вызовите connect().")

        local_dir: str = os.path.dirname(local_path)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)

        try:
            sftp: paramiko.SFTPClient = self._client.open_sftp()
            try:
                sftp.get(remote_path, local_path)
                logger.info("SFTP: скачан %s -> %s", remote_path, local_path)
            finally:
                sftp.close()
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл не найден на сервере: {remote_path}")
        except IOError as e:
            raise FileNotFoundError(f"Ошибка SFTP при скачивании {remote_path}: {e}") from e

        return local_path

    # ── private ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_key_path(key_path: str) -> str:
        """
        Разрешить путь к SSH-ключу с поддержкой ``~`` на Linux и Windows.

        Args:
            key_path: Путь к приватному ключу (может содержать ``~``).

        Returns:
            Абсолютный путь к ключу.

        Raises:
            FileNotFoundError: Если файл ключа не существует.
        """
        resolved: str = str(Path(key_path).expanduser().resolve())

        if not os.path.isfile(resolved):
            raise FileNotFoundError(f"SSH-ключ не найден: {resolved}")

        return resolved
