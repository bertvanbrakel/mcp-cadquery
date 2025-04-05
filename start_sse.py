#!/usr/bin/env python3
# Convenience script to run the server in HTTP SSE mode with defaults.
# Ensures environment is set up first using setup_env.py.

import os
import subprocess
import sys
import shutil

VENV_DIR = ".venv-cadquery"
PYTHON_EXE = os.path.join(VENV_DIR, "bin", "python") # Adjust for Windows if needed
SETUP_SCRIPT = "./setup_env.py"

def run_command(command, check=True, **kwargs):
    """Helper to run a command and print output/errors."""
    print(f"Running command: {' '.join(command)}")
    try:
        # Use shell=False for security unless shell features are needed
        process = subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            **kwargs
        )
        if process.stdout:
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
        if e.stdout: print("Stdout:\n" + e.stdout)
        if e.stderr: print("Stderr:\n" + e.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

def main():
    print("Ensuring environment via setup_env.py...")
    # Use sys.executable to run the setup script with the same python
    run_command([sys.executable, SETUP_SCRIPT])
    print("Environment check complete.")

    # Ensure the Python executable exists after setup
    if not os.path.exists(PYTHON_EXE):
        print(f"Error: Python executable still not found at {PYTHON_EXE} after running setup.")
        sys.exit(1)

    # Prepare server command arguments
    server_command = [PYTHON_EXE, "server.py", "--port", "8000", "--reload"]
    # Pass through any additional arguments given to start_sse.py
    server_command.extend(sys.argv[1:])

    print(f"Starting server in HTTP SSE mode...")
    print(f"Executing: {' '.join(server_command)}")

    # Use subprocess.run, but this will block.
    # For a long-running server, os.execvp might be better to replace the current process.
    try:
        # Replace the current process with the server process
        os.execvp(server_command[0], server_command)
    except OSError as e:
        print(f"Error executing server: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer startup interrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()