import subprocess
import sys
import os
import pytest

VENV_DIR = ".venv-cadquery" # Make sure this matches run_server.sh
PYTHON_EXE = os.path.join(VENV_DIR, "bin", "python") # Adjust for Windows if needed

@pytest.fixture(scope="module", autouse=True)
def setup_environment():
    """Fixture to ensure the virtual environment and dependencies are set up."""
    print("\nSetting up test environment using setup_env.sh...")
    try:
        setup_command = ["bash", "./setup_env.sh"] # Use the dedicated setup script
        print(f"Running setup command: {' '.join(setup_command)}")
        process = subprocess.run(
            setup_command,
            capture_output=True,
            text=True,
            timeout=180, # Increased timeout for potential downloads
            check=True # Expect setup script to succeed (exit code 0)
        )
        print("Setup script stdout:")
        print(process.stdout)
        print("Setup script stderr:")
        print(process.stderr)
        # We primarily care that the venv and python exe exist now
        assert os.path.isdir(VENV_DIR), f"Virtual environment directory '{VENV_DIR}' not found after setup."
        assert os.path.isfile(PYTHON_EXE), f"Python executable '{PYTHON_EXE}' not found after setup."
        print("Test environment setup seems complete.")
    except subprocess.TimeoutExpired:
        pytest.fail("Setup script timed out.")
    except Exception as e:
        pytest.fail(f"Setup script failed: {e}")

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
        print(f"Import test stderr: {result.stderr.strip()}")
        assert "cadquery" in sys.modules or result.returncode == 0 # Check if import succeeded
        print("cadquery imported successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Import test stdout: {e.stdout}")
        print(f"Import test stderr: {e.stderr}")
        pytest.fail(f"Importing cadquery failed with exit code {e.returncode}: {e.stderr}")
    except subprocess.TimeoutExpired:
        pytest.fail("Import test timed out.")
    except FileNotFoundError:
         pytest.fail(f"Could not run python executable at '{PYTHON_EXE}'. Check venv setup.")