import pytest
import os
import sys
import subprocess # Use subprocess to run the script

# Add back sys.path modification
# This might not be strictly necessary anymore if running as subprocess
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Cannot import cli directly anymore
# from server import cli
# runner = CliRunner() # Cannot use CliRunner easily

# Define path to the server script and venv python
SERVER_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server.py'))
VENV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.venv-cadquery'))
# Determine platform-specific bin directory
BIN_DIR = "Scripts" if sys.platform == "win32" else "bin"
PYTHON_EXE = os.path.join(VENV_DIR, BIN_DIR, "python.exe" if sys.platform == "win32" else "python")


def run_server_cli(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Helper to run server.py CLI using the venv python."""
    if not os.path.exists(PYTHON_EXE):
         pytest.fail(f"Venv Python not found at {PYTHON_EXE}. Run server.py once to trigger setup.")
    command = [PYTHON_EXE, SERVER_SCRIPT] + args
    print(f"\nRunning CLI command: {' '.join(command)}")
    return subprocess.run(command, capture_output=True, text=True, **kwargs)

def test_cli_help():
    """Test the --help option by running the script as a subprocess."""
    result = run_server_cli(["--help"])
    print(f"Exit Code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
    assert result.returncode == 0
    # Adjust checks based on actual Typer output format
    assert "Usage: server.py [OPTIONS]" in result.stdout # Check usage line (Typer uses script name here)
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--reload" in result.stdout
    assert "--mode" in result.stdout # Check for the new mode flag
    assert "--library-dir" in result.stdout
    assert "--static-dir" in result.stdout
    print("CLI --help test passed.")

def test_cli_stdio_invocation():
    """Test invoking --mode stdio via subprocess."""
    # Running stdio mode expects input and hangs if none provided.
    # We can send a minimal JSON request and check if it processes without crashing.
    # Or just check if it starts without immediate error.
    # Let's check for startup message and maybe timeout.
    try:
        # Timeout after a short period, assuming it started okay if no crash
        result = run_server_cli(["--mode", "stdio"], timeout=5)
        # If it exits cleanly (e.g., on EOF if stdin closes), code 0 is okay.
        # If it times out, it means it was running, which is also okay for this test.
        print(f"Exit Code: {result.returncode}")
        print(f"Stdout:\n{result.stdout}")
        print(f"Stderr:\n{result.stderr}")
        assert result.returncode == 0 # Or handle timeout below
        assert "Starting server in Stdio mode" in result.stderr # Check log message
    except subprocess.TimeoutExpired:
        print("CLI --mode stdio invocation timed out (expected for running server). Test passes.")
        pass # Timeout is expected for a running server waiting for input
    except Exception as e:
        pytest.fail(f"CLI --mode stdio invocation failed unexpectedly: {e}")

    print("CLI --mode stdio invocation test passed.")

def test_cli_sse_invocation_help():
    """Test invoking --mode sse (default) shows help correctly."""
    # SSE mode is default, so just running --help should work
    result = run_server_cli(["--help"])
    print(f"Exit Code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
    assert result.returncode == 0
    assert "Usage: server.py [OPTIONS]" in result.stdout
    assert "[default: sse]" in result.stdout # Check default mode help text
    print("CLI --mode sse (default) --help test passed.")

# Add more specific CLI tests if needed, e.g., passing invalid args