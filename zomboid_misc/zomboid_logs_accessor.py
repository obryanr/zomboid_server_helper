"""Zomboid Logs accessor."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from constant import ZOMBOID_LOG_GROUPS, ZomboidLogGroup

from .common_utils import extract_datetime_from_file


class ZomboidLogsAccessor:
    """Class to manage and access Project Zomboid log files by inferred type and datetime.

    Provides functionality to group logs and retrieve the latest logs per group.
    """

    def __init__(self, log_path: str):
        """Initialize ZomboidLogs with the given directory path.

        Args:
            log_path (str): Path to the directory containing log files and subdirectories.
        """
        self.available_log_groups = {}
        self.log_path = Path(log_path)
        self.logs_map = self._map_logs()

    def _map_logs(self) -> Dict[str, Dict[str, List[Dict]]]:
        """Maps logs into groups based on inferred grouping/suffix types from filenames.

        Returns:
            dict: A nested dictionary mapping source types ("server", "subdir")
                  to log groups and their corresponding metadata.
        """
        logs_map = {}

        server_filepaths = []
        subdir_logs_group = {}
        for filepath in self.log_path.iterdir():
            if filepath.is_dir():
                subdir_logs_group = self._group_logs(filepath, "subdir")
            elif filepath.suffix == ".txt":
                server_filepaths.append(filepath)

        server_logs = self._group_logs(server_filepaths, "server")

        logs_map["server"] = server_logs
        logs_map["subdir"] = subdir_logs_group
        return logs_map

    def _group_logs(self, filepath: Union[Path, List[Path]], source: str) -> dict:
        """Groups log files based on their suffixes or patterns in filenames.

        Args:
            filepath (Union[Path, List[Path]]): Either a directory path or list of file paths.
            source (str): The source category ("server" or "subdir").

        Returns:
            dict: Mapping of inferred log group names to metadata entries.
        """
        subdir_logs_map: Dict[str, list] = {}
        iterable_filepath = filepath.iterdir() if isinstance(filepath, Path) else filepath

        for subfilepath in iterable_filepath:
            subfilepath_str = str(subfilepath)
            datetime_obj = extract_datetime_from_file(subfilepath_str)

            if datetime_obj:
                log_group = self._get_log_group_by_substring(subfilepath_str)
                if log_group is None:
                    log_group = self._get_log_group_by_filename(subfilepath.name)

                self.available_log_groups.setdefault(source, set()).add(log_group)
                subdir_logs_map.setdefault(log_group, [])

                metadata = {"filepath": subfilepath, "created_at": datetime_obj}
                subdir_logs_map[log_group].append(metadata)

        return subdir_logs_map

    @staticmethod
    def _get_log_group_by_substring(filepath: str) -> Optional[str]:
        """Tries to identify log group by matching known suffix substrings in the file path.

        Args:
            filepath (str): Full string of the file path.

        Returns:
            Optional[str]: Matched suffix substring if found, otherwise None.
        """
        for group_name in ZOMBOID_LOG_GROUPS:
            group_name_pattern = re.compile(rf"{group_name}(?=\.txt|\s)")
            matched_group = group_name_pattern.search(filepath)
            if matched_group:
                return matched_group.group().strip()
        return None

    @staticmethod
    def _get_log_group_by_filename(filename: str, n: int = 2) -> str:
        """Heuristically generates a group name from the filename if no known suffix is found.

        Args:
            filename (str): Name of the file.
            n (int, optional): Number of words to include in the group name. Defaults to 2.

        Returns:
            str: Heuristic group name based on filename.
        """
        sub_filename = filename.split("_", 3)[2] if "_" in filename else filename
        words = sub_filename.split()
        return " ".join(words[:n])

    def _search_from_available_log_groups(self, group_name: str, check_on_name: str) -> Optional[str]:
        """Searches available log group names using regex match.

        Args:
            group_name (str): Target group name or regex pattern.
            check_on_name (str): Source to check ("server" or "subdir").

        Returns:
            Optional[str]: Matched group name if found, else None.
        """
        group_pattern = re.compile(rf"{group_name}")
        for avail_group in self.available_log_groups[check_on_name]:
            match = group_pattern.search(avail_group)
            if match:
                return avail_group
        return None

    def get_latest(
        self,
        group_name: str,
        check_on: Optional[List[str]] = None,
        use_regex: bool = True,
    ) -> Optional[Path]:
        """Gets the latest log file from a specific group.

        Args:
            group_name (str): The name or regex of the group to look for.
            check_on (Optional[List[str]]): List of sources to check ["server", "subdir"]. Defaults to both.
            use_regex (bool): Whether to allow regex match if group_name isn't exact.

        Returns:
            Optional[Path]: Path to the latest log file if found.
        """
        if check_on is None:
            check_on = ["subdir", "server"]

        latest_filepath = None
        latest_datetime = None

        for check_on_name in check_on:
            metadata_list = self.logs_map[check_on_name].get(group_name)
            if metadata_list is None and use_regex:
                matched_group_name = self._search_from_available_log_groups(group_name, check_on_name)
                metadata_list = self.logs_map[check_on_name].get(matched_group_name)
                if metadata_list is None:
                    break
            elif metadata_list is None:
                continue

            metadata_list = sorted(metadata_list, key=lambda x: x["created_at"], reverse=True)
            if metadata_list and latest_datetime is None or latest_datetime < metadata_list[0]["created_at"]:
                latest_filepath = metadata_list[0]["filepath"]
                latest_datetime = metadata_list[0]["created_at"]

        return latest_filepath

    def update_logs_map(self) -> None:
        """Update logs grouping (mapping).

        This method exist because project zomboid always creates
        new log in the same day and differentiate by time.
        Hence it needs to called whenever to get latest log update.
        """
        self.logs_map = self._map_logs()

    @staticmethod
    def search_in_log(logs: Union[str, Path, List[str]], regex_pattern: str) -> list:
        """Search specific"""
        if isinstance(logs, (str, Path)):
            with open(logs, encoding="utf-8") as txt_file:
                logs = txt_file.read().splitlines()

        match_list = []
        for line in logs:
            match = re.search(regex_pattern, line)
            if match:
                match_list.append(match)
        return match_list

    def get_active_players(self, user_log_group_name: str = ZomboidLogGroup.USER) -> int:
        """Get total online/active players in specified server."""
        filepath = self.get_latest(user_log_group_name)
        if filepath:
            connected_players = self.search_in_log(filepath, r" connected")
            disconnected_players = self.search_in_log(filepath, r"disconnected")
            return len(connected_players) - len(disconnected_players)
        return 0
