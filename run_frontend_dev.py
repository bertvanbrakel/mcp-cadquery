#!/usr/bin/env python3
"""
Script to run the frontend development server (Vite).

Checks for npm, installs dependencies if needed, and starts the Vite dev server.
"""
import os
import subprocess
import sys
import shutil

FRONTEND_DIR = "frontend"

def run_command_interactive(command: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess | None:
    """
    Helper to run a command interactively, showing output and handling common errors.

    Args:
        command: The command and arguments as a list of strings.
        check: If True, raise CalledProcessError on non-zero exit code.
        **kwargs: Additional arguments passed to subprocess.run.

    Returns:
        The CompletedProcess object if successful, otherwise exits the script.
        Returns None if interrupted by KeyboardInterrupt.
    """
    print(f"Running command: {' '.join(command)}")
    try:
        # Run without capturing output, allow interaction
        process = subprocess.run(command, check=check, **kwargs)
        return process
    except FileNotFoundError:
        print(f"Error: Command '{command[0]}' not found. Is it installed and in PATH?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command)}")
        print(f"Exit code: {e.returncode}")
        # Output was likely already printed
        sys.exit(1)
    except KeyboardInterrupt:
         print("\nProcess interrupted.")
         sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

def main() -> None:
    """
    Main function to set up and run the frontend development server.

    Checks for the frontend directory and npm, runs 'npm install' if
    node_modules is missing, then starts the Vite dev server using 'npm run dev'.
    """
    if not os.path.isdir(FRONTEND_DIR):
        print(f"Error: Frontend directory '{FRONTEND_DIR}' not found.")
        sys.exit(1)

    # Check if npm is installed
    if not shutil.which("npm"):
        print("Error: npm is not installed or not in PATH. Cannot run frontend dev server.")
        sys.exit(1)

    # Check if node_modules exists, run npm install if not
    node_modules_path = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules_path):
        print("node_modules not found. Running 'npm install'...")
        run_command_interactive(["npm", "install"], cwd=FRONTEND_DIR)
        print("npm install finished.")

    # Run the dev server
    print("Starting frontend development server (Vite)...")
    run_command_interactive(["npm", "run", "dev"], cwd=FRONTEND_DIR)

if __name__ == "__main__":
    main()