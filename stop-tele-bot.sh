#!/bin/bash

# Extract session name from config.yaml
SESSION_NAME=$(python3 -c "
import yaml
with open('config.yaml') as f:
    print(yaml.safe_load(f)['telegram_bot']['tmux_session_name'])
")

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
  echo "Session '$SESSION_NAME' session killed."
else
    echo "- Session "$SESSION_NAME" does not exist." >&2
fi
