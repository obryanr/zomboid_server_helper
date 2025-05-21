"""Main config"""

import yaml

# Load YAML config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Server config
SERVER_NAME = config["server"]["name"]
SERVER_CONFIG_DIRPATH = config["server"]["config_dirpath"]
LOGS_DIR_PATH = config["server"]["logs_dir_path"]
ZOMBOID_START_SERVER_FILEPATH = config["server"]["start_server_filepath"]
TMUX_SESSION_NAME = config["server"]["tmux_session_name"]

# Telegram BOT
TELEGRAM_BOT_TMUX_SESSION_NAME = config["telegram_bot"]["tmux_session_name"]

# OTHER
MOD_MANAGER_TIMEOUT = config["other"]["mod_manager_timeout"]
MINIMUM_AGREE_MEMBERS_FOR_MOD = config["other"]["minimum_agree_members_for_mod"]
