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
# Construct the command to run pytest via coverage in parallel mode
coverage_run_command = [
    python_executable, "-m", "coverage", "run", "-p", # -p for parallel mode
    "-m", "pytest", "-vv" # Run pytest module
    # Coverage source is now specified in .coveragerc
]

# Pass any arguments from this script call to pytest
# Pass any arguments from this script call to pytest (appended to coverage run)
coverage_run_command.extend(sys.argv[1:])

# Commands to combine parallel data and generate reports
coverage_combine_command = [python_executable, "-m", "coverage", "combine"]
coverage_report_command = [python_executable, "-m", "coverage", "report"] # Uses .coveragerc for options
coverage_html_command = [python_executable, "-m", "coverage", "html"] # Uses .coveragerc for options

print(f"Running tests with coverage using: {python_executable}")
print(f"Executing command: {' '.join(coverage_run_command)}")
print("-" * 30)

try:
    # Execute pytest, allowing it to take over stdin/stdout/stderr
    # Execute coverage run (which runs pytest)
    pytest_process = subprocess.run(coverage_run_command, check=False)
    pytest_exit_code = pytest_process.returncode

    # Combine coverage data regardless of pytest exit code
    print("-" * 30)
    print("Combining coverage data...")
    print(f"Executing command: {' '.join(coverage_combine_command)}")
    combine_process = subprocess.run(coverage_combine_command, check=False, capture_output=True, text=True)
    if combine_process.returncode != 0:
        print(f"Warning: 'coverage combine' failed with exit code {combine_process.returncode}:")
        print(combine_process.stderr)
        # Don't exit yet, try reporting anyway

    # Generate reports
    print("-" * 30)
    print("Generating coverage reports...")
    print(f"Executing command: {' '.join(coverage_report_command)}")
    report_process = subprocess.run(coverage_report_command, check=False) # Show terminal report

    print(f"Executing command: {' '.join(coverage_html_command)}")
    html_process = subprocess.run(coverage_html_command, check=False) # Generate HTML report

    print("-" * 30)
    if pytest_exit_code != 0:
        print(f"Pytest failed with exit code {pytest_exit_code}")
    else:
        print("Tests completed successfully.")

    sys.exit(pytest_exit_code) # Exit with the original pytest exit code
except KeyboardInterrupt:
    print("\nTests interrupted.")
    sys.exit(1)
except Exception as e:
    print(f"\nAn error occurred while trying to run pytest: {e}")
    sys.exit(1)