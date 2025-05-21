"""Zomboid Command wrapper using RCON."""

import os
import types
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Type

from aiorcon import RCON


@dataclass(frozen=True)
class RCONConfig:
    """Immutable configuration object for connecting to a Project Zomboid server via RCON.

    Attributes:
        host (str): The hostname or IP address of the RCON server.
        port (int): The port number used for the RCON connection.
        password (str): The RCON password. Can be set via the 'RCON_PASSWORD' environment variable.
        allowed_commands (Optional[List[str]]): A list of allowed base commands (e.g., ['/say', '/save']).
            If None, all commands are allowed.
        timeout (int): Timeout in seconds for the RCON connection and command execution.
    """

    host: str
    port: int
    password: str = field(repr=False, default_factory=lambda: os.environ.get("RCON_PASSWORD", ""))
    allowed_commands: Optional[List[str]] = None  # e.g., ['/say', '/save']
    timeout: int = 10


class ZomboidCommand:
    """Async context-managed wrapper for sending RCON commands to a Project Zomboid server.

    Provides restricted and logged execution of commands via a secure configuration.

    Args:
        config (RCONConfig): RCON connection settings and allowed commands.
        logger (Optional[Callable[[str], None]]): Optional logger callback for debugging.
    """

    def __init__(self, config: RCONConfig, logger: Optional[Callable[[str], None]] = None):
        self._config = config
        self._logger = logger
        self._rcon: Optional[RCON] = None

    async def __aenter__(self):
        """Establishes an asynchronous RCON connection on entering the context.

        Returns:
            ZomboidCommand: The connected command handler instance.

        Raises:
            ConnectionError: If the RCON connection fails.
        """
        try:
            self._rcon = RCON(
                self._config.host,
                self._config.port,
                self._config.password,
                timeout=self._config.timeout,
            )
            await self._rcon.__aenter__()
            self._log("RCON connection established.")
            return self
        except Exception as e:
            raise ConnectionError(f"Failed to connect via RCON: {str(e)}") from e

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[types.TracebackType],
    ):
        """Closes the RCON connection on exiting the context.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Traceback object if an exception occurred.
        """
        if self._rcon:
            await self._rcon.__aexit__(exc_type, exc_val, exc_tb)
            self._log("RCON connection closed.")

    def _log(self, message: str) -> None:
        """Logs a message using the configured logger if available.

        Args:
            message (str): The message to log.
        """
        if self._logger:
            self._logger(message)

    def _is_command_allowed(self, command: str) -> bool:
        """Checks whether a given command is allowed based on configuration.

        Args:
            command (str): The command to check.

        Returns:
            bool: True if the command is allowed, False otherwise.
        """
        if self._config.allowed_commands is None:
            return True
        base_cmd = command.strip().split()[0]
        return base_cmd in self._config.allowed_commands

    async def run_command(self, command: str) -> str:
        """Executes an RCON command on the server after verifying its validity.

        Args:
            command (str): The full command string to execute.

        Returns:
            str: The trimmed response returned by the server.

        Raises:
            RuntimeError: If the RCON client is not connected.
            PermissionError: If the command is not in the allowed list.
            Exception: If the command execution fails.
        """
        if not self._rcon:
            raise RuntimeError("RCON client is not connected.")
        if not self._is_command_allowed(command):
            raise PermissionError(f"Command not allowed: {command}")
        self._log(f"Executing command: {command}")
        try:
            response: str = await self._rcon(command)
            return response.strip()
        except Exception as e:
            self._log(f"Command failed: {e}")
            raise

    async def setaccesslevel(self, player_name: str, access_level: str) -> str:
        """Changes a player's access level on the server.

        Args:
            player_name (str): The name of the player.
            access_level (str): The new access level (e.g., 'admin').

        Returns:
            str: The server's response to the command.

        Raises:
            ValueError: If the player name or access level is missing.
        """
        player_name = player_name.strip()
        access_level = access_level.strip()

        if not player_name or access_level:
            raise ValueError("Message cannot be empty.")
        return await self.run_command(f"/setaccesslevel {player_name} {access_level}")

    async def broadcast(self, message: str) -> str:
        """Sends a server-wide broadcast message to all players.

        Args:
            message (str): The message to broadcast.

        Returns:
            str: The server's response to the command.

        Raises:
            ValueError: If the message is empty.
        """
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty.")
        return await self.run_command(f"/servermsg {message}")

    async def change_option(self, option_name: str, value: str) -> str:
        """Updates a server configuration option on-the-fly.

        Args:
            option_name (str): The name of the configuration option.
            value (str): The new value to apply.

        Returns:
            str: The server's response to the command.

        Raises:
            ValueError: If the option name or value is empty.
        """
        option_name = option_name.strip()
        value = value.strip()

        if not option_name or value:
            raise ValueError("option_name or value cannot be empty")
        return await self.run_command(f"/changeoption {option_name} {value}")
