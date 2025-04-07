import os
import sys
import subprocess
import shutil
import logging
from typing import Optional

# Constants for environment setup
VENV_DIR = ".venv"
PYTHON_VERSION = "3.11"

# Cache for workspace requirements.txt modification times
workspace_reqs_mtime_cache: dict[str, float] = {}

def _run_command_helper(command: list[str], check: bool = True, log_prefix: str = "Setup", **kwargs) -> subprocess.CompletedProcess:
    """
    Helper to run a command, capture output, and raise exceptions on failure.
    Uses logging.
    """
    # Ensure basic logging is configured if needed
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)

    log_msg_prefix = f"[{log_prefix}]"
    logging.info(f"{log_msg_prefix} Running command: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            **kwargs
        )
        logging.debug(f"{log_msg_prefix} Command stdout:\n{process.stdout}")
        if process.stderr:
            logging.debug(f"{log_msg_prefix} Command stderr:\n{process.stderr}")
        return process
    except FileNotFoundError as e:
        logging.error(f"{log_msg_prefix} Error: Command '{command[0]}' not found. Is it installed and in PATH?")
        raise e
    except subprocess.CalledProcessError as e:
        logging.error(f"{log_msg_prefix} Error running command: {' '.join(command)}")
        logging.error(f"{log_msg_prefix} Exit code: {e.returncode}")
        if e.stdout:
            logging.error(f"{log_msg_prefix} Stdout:\n{e.stdout}")
        if e.stderr:
            logging.error(f"{log_msg_prefix} Stderr:\n{e.stderr}")
        raise e
    except Exception as e:
        logging.error(f"{log_msg_prefix} An unexpected error occurred running command: {e}")
        raise e

def prepare_workspace_env(workspace_path: str) -> str:
    """
    Ensures a virtual environment exists in the workspace, creates it if not,
    and installs dependencies from workspace/requirements.txt using uv.

    Args:
        workspace_path: The absolute path to the workspace directory.

    Returns:
        The absolute path to the Python executable within the workspace venv.

    Raises:
        FileNotFoundError: If 'uv' is not found or workspace_path is invalid.
        RuntimeError: If environment setup fails.
    """
    log_prefix = f"WorkspaceEnv({os.path.basename(workspace_path)})"
    logging.info(f"[{log_prefix}] Ensuring environment for workspace: {workspace_path}")

    if not os.path.isdir(workspace_path):
        msg = f"Workspace path does not exist or is not a directory: {workspace_path}"
        logging.error(f"[{log_prefix}] {msg}")
        raise FileNotFoundError(msg)

    # 1. Check for uv
    if not shutil.which("uv"):
        msg = "Error: Python 'uv' is not installed or not in PATH. Please install it: https://github.com/astral-sh/uv"
        logging.error(f"[{log_prefix}] {msg}")
        raise FileNotFoundError(msg)

    # 2. Define paths
    venv_dir = os.path.join(workspace_path, VENV_DIR)
    requirements_file = os.path.join(workspace_path, "requirements.txt")
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    python_exe = os.path.join(venv_dir, bin_subdir, "python.exe" if sys.platform == "win32" else "python")

    try:
        # 3. Create venv if needed
        if not os.path.isdir(venv_dir) or not os.path.exists(python_exe):
            logging.info(f"[{log_prefix}] Creating virtual environment in {venv_dir} using Python {PYTHON_VERSION}...")
            _run_command_helper(["uv", "venv", venv_dir, "-p", PYTHON_VERSION], log_prefix=log_prefix)
            logging.info(f"[{log_prefix}] Virtual environment created.")
        else:
            logging.info(f"[{log_prefix}] Virtual environment already exists: {venv_dir}")

        if not os.path.exists(python_exe):
            msg = f"Python executable still not found at {python_exe} after check/creation."
            logging.error(f"[{log_prefix}] {msg}")
            raise RuntimeError(msg)

        # 4. Install base cadquery
        logging.info(f"[{log_prefix}] Ensuring base 'cadquery' package is installed in {venv_dir}...")
        _run_command_helper(["uv", "pip", "install", "cadquery", "--python", python_exe], log_prefix=log_prefix)
        logging.info(f"[{log_prefix}] Base 'cadquery' installed/verified.")

        # 5. Handle workspace requirements.txt
        install_reqs = False
        current_mtime: Optional[float] = None
        if os.path.isfile(requirements_file):
            try:
                current_mtime = os.path.getmtime(requirements_file)
                cached_mtime = workspace_reqs_mtime_cache.get(workspace_path)
                if current_mtime != cached_mtime:
                    install_reqs = True
                    logging.info(f"[{log_prefix}] requirements.txt changed (Current: {current_mtime}, Cached: {cached_mtime}). Will install.")
                else:
                    logging.info(f"[{log_prefix}] requirements.txt unchanged (mtime: {current_mtime}). Skipping install.")
            except OSError as mtime_err:
                logging.warning(f"[{log_prefix}] Could not get mtime for {requirements_file}: {mtime_err}. Assuming install needed.")
                install_reqs = True
        else:
            if workspace_path in workspace_reqs_mtime_cache:
                del workspace_reqs_mtime_cache[workspace_path]
            logging.info(f"[{log_prefix}] No requirements.txt found in workspace. Skipping additional dependencies.")

        if install_reqs:
            logging.info(f"[{log_prefix}] Installing/syncing additional dependencies from {requirements_file} into {venv_dir}...")
            try:
                _run_command_helper(["uv", "pip", "install", "-r", requirements_file, "--python", python_exe], log_prefix=log_prefix)
                workspace_reqs_mtime_cache[workspace_path] = current_mtime
                logging.info(f"[{log_prefix}] Additional dependencies installed/synced. Updated mtime cache to {current_mtime}.")
            except Exception as install_err:
                if workspace_path in workspace_reqs_mtime_cache:
                    del workspace_reqs_mtime_cache[workspace_path]
                logging.error(f"[{log_prefix}] Failed to install dependencies from {requirements_file}. Error: {install_err}")
                raise RuntimeError(f"Failed to install dependencies from {requirements_file}") from install_err

        logging.info(f"[{log_prefix}] Environment preparation complete.")
        return python_exe

    except (FileNotFoundError, subprocess.CalledProcessError, Exception) as e:
        logging.error(f"[{log_prefix}] Failed to set up workspace environment: {e}")
        raise RuntimeError(f"Failed to set up workspace environment for {workspace_path}: {e}") from e