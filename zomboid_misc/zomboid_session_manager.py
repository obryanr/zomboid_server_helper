"""Zomboid session manager."""

import subprocess


def restart_session(session_name: str, zomboid_start_server_path: str, server_name: str) -> bool:
    """Restart a tmux session with the given name and run the Zomboid server startup script.

    If the session already exists, it is killed and restarted.
    Then, the function sends keys to the tmux session to:
    - Switch to user `pzuser`
    - Navigate to the zomboid server directory
    - Run the start-server.sh script with the specified server name

    Args:
        session_name (str): Name of the tmux session.
        zomboid_start_server_path (str): Absolute path to the Zomboid start-server directory.
        server_name (str): Name of the Zomboid server. Default is "aliformer".

    Returns:
        bool: True if the restart process completes.

    Example:
        >>> restart_session("zomboid_sess", "/home/pzuser/Zomboid", "myserver")
        True
    """

    def run_cmd(cmd: str, **kwargs: dict) -> str:
        return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, **kwargs)  # noqa

    # Check if tmux session exists
    check = run_cmd(f"tmux has-session -t {session_name}")
    if check.returncode == 0:
        print(f"- Session '{session_name}' already exists.")
        run_cmd(f"tmux kill-session -t {session_name}")
        return restart_session(session_name, zomboid_start_server_path, server_name)
    print(f"- Session '{session_name}' does not exist.")
    run_cmd(f"tmux new-session -d -s {session_name}")
    print("- Restarting zomboid server ..")

    run_cmd(f'tmux send-keys -t {session_name} "cd {zomboid_start_server_path}" Enter')
    run_cmd(f'tmux send-keys -t {session_name} "/opt/pzserver/start-server.sh -servername {server_name}" Enter')

    print("- Restarted successfully.")
    return True
