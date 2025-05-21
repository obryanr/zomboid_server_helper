# 🧠 Zomboid Server Telegram Bot

A FastAPI-based webhook integration for managing and monitoring your Project Zomboid server via Telegram commands.

## 📦 Requirements
```bash
pip install -r requirements.txt
```

`requirements.txt` should include:

```txt
fastapi
uvicorn
httpx
python-telegram-bot==13.15
```

## 🔐 Configuration (config.py)
Make sure your config.py includes the following:

```python
## Server config ##
SERVER_NAME = "aliformer"
SERVER_CONFIG_DIRPATH = '/home/pzuser/Zomboid/Server'
LOGS_DIR_PATH = "Zomboid/Logs"
ZOMBOID_START_SERVER_FILEPATH = "/opt/pzserver/start-server.sh"
TMUX_SESSION_NAME = ""

# Telegram BOT
TELEGRAM_BOT_TOKEN = ""

# OTHER
MOD_MANAGER_TIMEOUT = 10
```

## 🪝 Set Telegram Webhook
Run the following command (replace values accordingly):

```bash
curl -X POST https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook \
     -d "url=https://yourdomain.com/telegram/webhook"
```

> If running locally, use ngrok:
    ```bash
    ngrok http 8000
    ```

## 🧪 Available Bot Commands

| Command                 | Description                                             |
|------------------------|---------------------------------------------------------|
| `/start`               | Show available commands                                 |
| `/active_players`      | Show currently connected players                        |
| `/restart_server`      | Restart server (only when no players are online)        |
| `/check_mod <id>`      | Check if a Steam Workshop mod is installed on the server |
| `/get_mod <mod_url>`      | Install specified mod to the zomboid server |

## 🧠 Notes
This bot uses tmux to manage the server session.
If players are online, the server will not restart.
Customize further by adding more bot commands.
