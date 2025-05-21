"""Zomboid configuration manipulator."""

import configparser
import os
import re
from enum import Enum
from typing import Callable, List, Optional


class ConfigType(Enum):
    """Config enumeration."""

    MAIN = "main"
    SPAWN_REGIONS = "spawn_regions"
    SANDBOX_VARS = "sandbox_vars"


class ZomboidConfig:
    """A class to manage and modify Project Zomboid server configuration files.

    This class provides asynchronous methods to read and modify key-value pairs
    in the main configuration INI file. It also handles delimiter-separated values
    such as mod lists or admin IDs.

    Attributes:
        server_name (str): The name of the Zomboid server.
        config_dir_path (str): Path to the configuration directory.
    """

    def __init__(self, config_dir_path: str, server_name: str):
        """Initialize the ZomboidConfig instance with config file paths.

        Args:
            config_dir_path (str): Path to the directory containing config files.
            server_name (str): Name of the server (used to find related config files).
        """
        self.server_name = server_name
        self.config_parser = configparser.ConfigParser()
        self.config_parser.optionxform = str

        self._main_config_file_path = os.path.join(config_dir_path, f"{server_name}.ini")
        self._spawn_regions_config_path = os.path.join(config_dir_path, f"{server_name}_spawnregions.lua")
        self._sandbox_vars_config_path = os.path.join(config_dir_path, f"{server_name}_SandboxVars.lua")
        self.config_dir_path = config_dir_path

        self.read_mod_config()

    def read_mod_config(self) -> None:
        """Reads the main server config file and loads it into a config parser.

        Prepends a dummy section header to allow parsing of key-value pairs.
        """
        with open(self._main_config_file_path, encoding="utf-8") as file:
            content = "[default_section]\n" + file.read()
        self.config_parser.read_string(content)

    async def get_main_config_value(self, key: str, fallback: Optional[str] = None) -> Optional[str]:
        """Retrieve a value from the main server config.

        Args:
            key (str): The key to retrieve.
            fallback (Optional[str]): The value to return if the key is not found.

        Returns:
            Optional[str]: The value associated with the key, or the fallback.
        """
        return self.config_parser.get("default_section", key, fallback=fallback)

    async def change_main_config(self, key: str, value: str) -> None:
        """Change or set the value of a key in the main config.

        Args:
            key (str): The config key.
            value (str): The new value to set.
        """
        await self._write_config(key, value)

    async def insert_to_main_config(self, index: int, key: str, value: str, delimiter: str = ";") -> None:
        """Insert a value at a specific index in a delimited config value.

        Args:
            index (int): Position to insert at.
            key (str): The key whose value is a delimited list.
            value (str): The value to insert.
            delimiter (str): Delimiter separating values (default is ';').
        """
        await self._mutate_config_list(key, lambda lst: lst.insert(index, value), delimiter)

    async def append_to_main_config(self, key: str, value: str, delimiter: str = ";") -> None:
        """Append a value to the end of a delimited config list.

        Args:
            key (str): The key whose value is a delimited list.
            value (str): The value to append.
            delimiter (str): Delimiter separating values (default is ';').
        """
        await self._mutate_config_list(key, lambda lst: lst.append(value), delimiter)

    async def extend_to_main_config(self, key: str, values: List[str], delimiter: str = ";") -> None:
        """Extend a delimited config list with multiple values.

        Args:
            key (str): The key whose value is a delimited list.
            values (List[str]): List of values to add.
            delimiter (str): Delimiter separating values (default is ';').
        """
        await self._mutate_config_list(key, lambda lst: lst.extend(values), delimiter)

    async def _mutate_config_list(self, key: str, mutator: Callable[[List[str]], None], delimiter: str) -> None:
        """Helper to apply a mutation function to a delimited config value list.

        Args:
            key (str): The config key.
            mutator (Callable[[List[str]], None]): A function that mutates the list in-place.
            delimiter (str): The delimiter used in the config value.
        """
        config_values = await self._split_config(key, delimiter)
        mutator(config_values)
        await self._write_config(key, delimiter.join(config_values))

    async def _split_config(self, key: str, delimiter: str = ";") -> List[str]:
        """Splits a delimited config value into a list.

        Args:
            key (str): The config key.
            delimiter (str): The delimiter (default is ';').

        Returns:
            List[str]: List of split values.
        """
        return self.config_parser.get("default_section", key, fallback="").split(delimiter)

    async def _write_config(self, key: str, value: str) -> None:
        """Writes a new value for a key to the config file and refreshes the parser.

        Args:
            key (str): The config key to modify.
            value (str): The new value to set.
        """
        self.config_parser.set("default_section", key, value)

        with open(self._main_config_file_path, encoding="utf-8") as f:
            original = f.read()

        original = re.sub(rf"({key}=.+)\n", f"{key}={value}\n", original)
        with open(self._main_config_file_path, "w", encoding="utf-8") as f:
            f.write(original)

        self.read_mod_config()
