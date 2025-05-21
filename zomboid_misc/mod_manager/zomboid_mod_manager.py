"""This module provides the `ZomboidModManager` class for managing Project Zomboid server mods.

It handles mod validation, dependency resolution, configuration updates, and local mod graph
persistence.
"""

import os
import re
from typing import Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup

from constant import ZOMBOID_WORKSHOP_URL_PREFIX
from zomboid_misc.zomboid_config import ZomboidConfig

from ._mod_graph import ZomboidModGraph

ModMetadata = Dict[str, Dict[str, Union[Optional[str], list]]]


class ZomboidModManager:
    """A manager class to handle Project Zomboid mod configurations and local mod graph updates for a server.

    Attributes:
        timed_out_url (List[str]): URLs that failed due to timeouts.
        timeout (int): Timeout in seconds for HTTP requests.
        zomboid_config (ZomboidConfig): Interface to the server's config files.
        meta_path (str): Path to the metadata JSON file.
        _mod_graph (ZomboidModGraph): Internal graph tracking mod dependencies.
    """

    def __init__(self, config_dir_path: str, server_name: str, timeout: int = 5):
        """Initialize the manager with server config location and mod graph setup.

        Args:
            config_dir_path (str): Path to the Zomboid server config directory.
            server_name (str): Name of the specific server.
            timeout (int): Request timeout in seconds.
        """
        self.timed_out_url: List[str] = []
        self.timeout = timeout

        self.zomboid_config = ZomboidConfig(config_dir_path, server_name)

        self.meta_path = os.path.join(config_dir_path, f"{server_name}.json")

        self._mod_graph = ZomboidModGraph()
        if os.path.exists(self.meta_path):
            self._mod_graph = ZomboidModGraph.load(meta_path=self.meta_path)
            print("loaded successfully.")

    @staticmethod
    async def parse_mod_id_from_url(mod_url: str) -> Optional[str]:
        """Extract the Steam Workshop ID from a mod URL.

        Args:
            mod_url (str): URL pointing to a Steam Workshop mod.

        Returns:
            Optional[str]: The numeric ID if found, else None.
        """
        match = re.search(r"id=(\d+)", mod_url)
        if match:
            return match.group(1)
        return None

    @staticmethod
    async def get_url_from_mod_id(mod_id: Union[str, int]) -> str:
        """Construct a full Steam Workshop URL from a mod ID.

        Args:
            mod_id (Union[str, int]): Steam Workshop ID.

        Returns:
            str: Full URL to the mod.
        """
        return f"{ZOMBOID_WORKSHOP_URL_PREFIX}{mod_id}"

    async def validate_mod_url(self, mod_url: str) -> bool:
        """Validates if a given mod URL or Steam Workshop ID corresponds to an existing mod.

        If the input is just a numeric ID, it prepends the Steam Workshop URL prefix.

        Args:
            mod_url (str): Full mod URL or Steam Workshop ID.

        Returns:
            bool: True if the mod exists (i.e., no "Sorry!" page), False otherwise.

        Example:
            >>> validate_mod_url("2894412760")
            True

            >>> validate_mod_url("https://steamcommunity.com/sharedfiles/filedetails/?id=11")
            True

            >>> validate_mod_url("123456789")  # Invalid/non-existent mod ID
            False
        """
        if mod_url.isdigit():
            mod_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={mod_url}"

        response = requests.get(mod_url, timeout=self.timeout)
        soup = BeautifulSoup(response.content, "lxml")
        return soup.find("h1").text != "Sorry!"

    async def check_mod_installation(self, workshop_id: str) -> bool:
        """Check if the given mod is already listed in the server's WorkshopItems.

        Args:
            workshop_id (str): Steam Workshop ID of the mod.

        Returns:
            bool: True if installed, False otherwise.
        """
        installed_workshop_ids = await self.zomboid_config.get_main_config_value("WorkshopItems")
        return workshop_id in installed_workshop_ids.split(";")

    async def get_required_mod(self, mod_url: str, n_retry: int = 2) -> ModMetadata:
        """Get full mod metadata including dependencies by scraping the Workshop page.

        Args:
            mod_url (str): URL of the mod to resolve.
            n_retry (int): Number of retry attempts for timed out requests.

        Returns:
            ModMetadata: Dictionary containing metadata for all related mods.
        """
        mod_metadata = await self._request_required_mod(mod_url)

        for _ in range(n_retry):
            if not self.timed_out_url:
                break
            retry_urls = self.timed_out_url.copy()
            self.timed_out_url.clear()
            for url in retry_urls:
                mod_metadata = await self._request_required_mod(url)
                if mod_metadata:
                    break
        return mod_metadata

    async def add_to_config(self, mod_metadata: ModMetadata) -> None:
        """Add a mod and its dependencies to the Zomboid config and save metadata.

        Args:
            mod_metadata (ModMetadata): Dictionary of mod metadata to install.
        """
        workshop_ids = await self.zomboid_config.get_main_config_value("WorkshopItems")
        mod_ids = await self.zomboid_config.get_main_config_value("Mods")

        workshop_ids = workshop_ids.split(";")
        mod_ids = mod_ids.split(";")

        for metadata in mod_metadata.values():
            if metadata["workshop_id"] not in workshop_ids:
                mod_ids = metadata["mod_id"] + mod_ids
                workshop_ids.insert(0, metadata["workshop_id"])

        await self.zomboid_config.change_main_config("WorkshopItems", ";".join(workshop_ids))
        await self.zomboid_config.change_main_config("Mods", ";".join(mod_ids))

        # Update graph
        self._mod_graph.update_by_metadata(mod_metadata)
        self._mod_graph.save(meta_path=self.meta_path)

    async def _request_required_mod(
        self,
        mod_url: str,
        mod_metadata: Optional[ModMetadata] = None,
        child_workshop_id: Optional[str] = None,
    ) -> ModMetadata:
        """Internal recursive method to fetch mod metadata and resolve required mods.

        Args:
            mod_url (str): Steam Workshop mod URL.
            mod_metadata (Optional[ModMetadata]): Accumulated metadata (used during recursion).
            child_workshop_id (Optional[str]): ID of the mod that depends on this one.

        Returns:
            ModMetadata: Updated metadata dictionary including dependencies.
        """
        if mod_metadata is None:
            mod_metadata = {}
        try:
            response = requests.get(mod_url, timeout=self.timeout)
            soup = BeautifulSoup(response.content, "lxml")

            title = soup.find("div", class_="workshopItemTitle").text.strip()
            mod_ids = await self.get_mod_id_from_html(soup)
            workshop_id = await self.get_workshop_id(mod_url)

            mod_metadata[workshop_id] = {
                "url": mod_url,
                "mod_name": title,
                "workshop_id": workshop_id,
                "mod_id": mod_ids,
            }

            if child_workshop_id:
                mod_metadata[child_workshop_id].setdefault("required", []).append(workshop_id)

            # Check for dependencies
            container = soup.find("div", id="RequiredItems")
            if container:
                for item in container.find_all("a"):
                    href = item.get("href")
                    if href and href not in mod_metadata:
                        child_workshop_id = workshop_id
                        mod_metadata = await self._request_required_mod(href, mod_metadata, child_workshop_id)

            return mod_metadata

        except requests.Timeout:
            print(f"[WARNING] Request timed out: {mod_url}")
            if mod_url not in self.timed_out_url:
                self.timed_out_url.append(mod_url)

    @staticmethod
    async def get_mod_id_from_html(parsed_html: BeautifulSoup) -> List[str]:
        """Parse the mod ID(s) from a Workshop page's HTML.

        Args:
            parsed_html (BeautifulSoup): Parsed HTML content of the Workshop page.

        Returns:
            List[str]: List of internal mod IDs.
        """
        desc = parsed_html.find("div", id="highlightContent").text
        matches: List[str] = re.findall(r"Mod ID\s*:\s*(.*?)(?=Mod ID|$)", desc, flags=re.IGNORECASE)
        return [m.strip() for m in matches if m.strip()]

    @staticmethod
    async def get_workshop_id(url: str) -> str:
        """Extract the numeric Workshop ID from a URL.

        Args:
            url (str): Steam Workshop mod URL.

        Returns:
            str: Numeric mod ID or an empty string if not found.
        """
        match = re.search(r"id=(\d+)", url)
        return match.group(1) if match else ""

    async def get_mod_dependents(self, identifier: str) -> List[str]:
        """Retrieve mods that depend on the given mod.

        Args:
            identifier (str): Workshop ID or mod name.

        Returns:
            List[str]: List of dependent mod Workshop IDs.
        """
        return self._mod_graph.get_dependents(identifier)

    async def delete_mod(self, identifier: str, force: bool = False) -> bool:
        """Delete a mod from the system, optionally bypassing dependency checks.

        Args:
            identifier (str): Workshop ID or mod name.
            force (bool): If True, ignore dependent mods and delete anyway.

        Returns:
            bool: True if deletion is done. False if failed.

        Raises:
            ValueError: If mod has dependents and `force` is False.
        """
        dependents = await self.get_mod_dependents(identifier)
        if dependents and not force:
            raise ValueError("Can't be deleted because has dependents:", dependents)
        return True
