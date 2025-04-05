#!/usr/bin/env python3
# Script to create/update virtual environment and install dependencies using uv.

import os
import subprocess
import sys
import shutil

VENV_DIR = ".venv-cadquery"
REQUIREMENTS_FILE = "requirements.txt"
PYTHON_VERSION = "3.11" # Specify desired Python version for uv

def run_command(command, check=True, **kwargs):
    """Helper to run a command and print output/errors."""
    print(f"Running command: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            **kwargs
        )
        print("Command stdout:")
        print(process.stdout)
        if process.stderr:
            print("Command stderr:")
            print(process.stderr)
        return process
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is it installed and in PATH?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        print(f"Exit code: {e.returncode}")
        print("Stdout:")
        print(e.stdout)
        print("Stderr:")
        print(e.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

def main():
    # Check if uv is installed
    print("Checking for uv...")
    if not shutil.which("uv"):
         print("Error: Python 'uv' is not installed or not in PATH.")
         print("Please install it: https://github.com/astral-sh/uv")
         sys.exit(1)
    print("uv found.")

    # Create virtual environment if it doesn't exist
    venv_path = os.path.abspath(VENV_DIR)
    python_exe_path = os.path.join(venv_path, "bin", "python") # Standard venv path

    if not os.path.isdir(venv_path) or not os.path.exists(python_exe_path):
        print(f"Creating virtual environment in {venv_path} using Python {PYTHON_VERSION}...")
        run_command(["uv", "venv", venv_path, "-p", PYTHON_VERSION])
        print("Virtual environment created.")
    else:
        print(f"Virtual environment {venv_path} already exists.")

    # Ensure the Python executable exists after potential creation
    if not os.path.exists(python_exe_path):
         print(f"Error: Python executable still not found at {python_exe_path} after check/creation.")
         sys.exit(1)

    # Install/sync dependencies using the specific python from the venv
    print(f"Installing/syncing dependencies from {REQUIREMENTS_FILE} into {venv_path}...")
    run_command(["uv", "pip", "install", "-r", REQUIREMENTS_FILE, "--python", python_exe_path])

    print("\nEnvironment setup complete.")

if __name__ == "__main__":
    main()