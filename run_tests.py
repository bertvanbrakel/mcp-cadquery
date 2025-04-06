#!/usr/bin/env python3
"""
Script to run pytest within the project's virtual environment (.venv-cadquery).

Locates the virtual environment, finds the Python executable within it, and then
executes pytest using that interpreter. This ensures that the correct versions
of pytest and project dependencies are used.

Any arguments passed to this script are forwarded directly to pytest.
For example: ./run_tests.py -k my_test -v
"""
import os
import sys
import subprocess
import venv

# --- Configuration ---
VENV_DIR = ".venv-cadquery"
# --- End Configuration ---

# Get the absolute path to the project root (where this script is located)
project_root = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.join(project_root, VENV_DIR)

# Determine the correct path to the python executable within the venv
if sys.platform == "win32":
    python_executable = os.path.join(venv_path, "Scripts", "python.exe")
else:
    python_executable = os.path.join(venv_path, "bin", "python")

# Check if the virtual environment and python executable exist
if not os.path.isdir(venv_path):
    print(f"Error: Virtual environment not found at '{venv_path}'")
    print("Please run 'python3 setup_env.py' first.")
    sys.exit(1)

if not os.path.isfile(python_executable):
    print(f"Error: Python executable not found at '{python_executable}'")
    print("The virtual environment might be corrupted. Try running 'python3 setup_env.py' again.")
    sys.exit(1)

# Construct the command to run pytest using the venv's python
# This ensures pytest and all dependencies are correctly loaded from the venv
pytest_command = [python_executable, "-m", "pytest", "-vv"] # Add verbosity, timeout configured in pytest.ini

# Pass any arguments from this script call to pytest
pytest_command.extend(sys.argv[1:])

print(f"Running pytest using: {python_executable}")
print(f"Executing command: {' '.join(pytest_command)}")
print("-" * 30)

try:
    # Execute pytest, allowing it to take over stdin/stdout/stderr
    process = subprocess.run(pytest_command, check=False) # check=False to handle pytest exit codes manually
    sys.exit(process.returncode) # Exit with the same code as pytest
except KeyboardInterrupt:
    print("\nTests interrupted.")
    sys.exit(1)
except Exception as e:
    print(f"\nAn error occurred while trying to run pytest: {e}")
    sys.exit(1)