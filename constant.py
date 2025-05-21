"""Zomboid constants."""


class ZomboidLogGroup:
    """Zomboid log group constants."""

    DEBUG_LOG = "DebugLog"
    ZOMBIE_SPAWN = "ZombieSpawn"
    CLIENT = "client chat"
    CHAT = "chat"
    USER = "user"


ZOMBOID_LOG_GROUPS = [getattr(ZomboidLogGroup, attr) for attr in dir(ZomboidLogGroup) if attr.isupper()]


ZOMBOID_WORKSHOP_URL_PREFIX = "https://steamcommunity.com/sharedfiles/filedetails/?id="
