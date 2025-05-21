#!/bin/bash

# Extract session name from config.yaml
SESSION_NAME=$(python3 -c "
import yaml
with open('config.yaml') as f:
    print(yaml.safe_load(f)['telegram_bot']['tmux_session_name'])
")

# Check if tmux session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "Session '$SESSION_NAME' already exists."
else
  echo "Creating tmux session '$SESSION_NAME' and running bot.py"
  tmux new-session -d -s "$SESSION_NAME"
  tmux send-keys -t "$SESSION_NAME" "conda activate zomboid-venv" Enter
  tmux send-keys -t "$SESSION_NAME" "python3 bot.py" Enter
fi
