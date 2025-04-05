import subprocess
import sys
import os
import pytest

VENV_DIR = ".venv-cadquery"
PYTHON_EXE = os.path.join(VENV_DIR, "bin", "python") # Adjust for Windows if needed
# SETUP_SCRIPT = "./setup_env.py" # No longer needed, server.py handles setup

# Note: Environment setup is now handled automatically by server.py when imported/run
# outside the venv. This test primarily verifies the outcome.

def test_cadquery_import():
    """Test if cadquery can be imported within the virtual environment."""
    assert os.path.isfile(PYTHON_EXE), f"Python executable '{PYTHON_EXE}' does not exist. Setup failed?"

    command = [PYTHON_EXE, "-c", "import cadquery; print(cadquery.__version__)"]
    print(f"\nRunning test command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            check=True, # Fail if import fails
            capture_output=True,
            text=True,
            timeout=30
        )
        print(f"Import test stdout: {result.stdout.strip()}")
        if result.stderr:
             print(f"Import test stderr: {result.stderr.strip()}")
        assert result.returncode == 0 # Check if import succeeded
        print("cadquery imported successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Import test stdout: {e.stdout}")
        print(f"Import test stderr: {e.stderr}")
        pytest.fail(f"Importing cadquery failed with exit code {e.returncode}: {e.stderr}")
    except subprocess.TimeoutExpired:
        pytest.fail("Import test timed out.")
    except FileNotFoundError:
         pytest.fail(f"Could not run python executable at '{PYTHON_EXE}'. Check venv setup.")