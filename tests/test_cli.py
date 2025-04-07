import pytest
import os
import sys
import subprocess # Use subprocess to run the script



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
    # Set NO_COLOR to disable rich formatting in subprocess
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    return subprocess.run(command, capture_output=True, text=True, env=env, **kwargs)

def test_cli_help():
    """Test the --help option by running the script as a subprocess."""
    result = run_server_cli(["--help"])
    print(f"Exit Code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
    assert result.returncode == 0
    # Adjust checks based on actual Typer output format
    # Check if any line starts with the usage string after stripping
    # Check if any line contains the usage string after stripping
    assert "Usage:" in result.stdout, "Usage string not found in help output" # Check raw output
    assert "--host" in result.stdout, "--host option not found in plain help output"
    assert "--port" in result.stdout, "--port option not found in plain help output"
    assert "--static-dir" in result.stdout, "--static-dir option not found in plain help output" # Should still exist
    assert "--mode" in result.stdout, "--mode option not found in plain help output" # Check for the option name
    # Check that removed options are NOT present
    assert "--output-dir" not in result.stdout
    assert "--part-library-dir" not in result.stdout
    assert "--render-dir-name" not in result.stdout
    assert "--preview-dir-name" not in result.stdout
    assert "--output-dir" not in result.stdout
    assert "--part-library-dir" not in result.stdout
    assert "--render-dir-name" not in result.stdout
    assert "--preview-dir-name" not in result.stdout
    assert "--static-dir" in result.stdout
    print("CLI --help test passed.")

def test_cli_stdio_invocation():
    """Test invoking --mode stdio via subprocess."""
    # Running stdio mode expects input and hangs if none provided.
    # We can send a minimal JSON request and check if it processes without crashing.
    # Or just check if it starts without immediate error.
    # Let's check if it starts without immediate error by using the --stdio flag.
    # It should hang waiting for input, so we expect a timeout.
    try:
        # Timeout after a short period, assuming it started okay if no crash
        print("Running CLI command with --stdio, expecting timeout...")
        result = run_server_cli(["--mode", "stdio"], timeout=3) # Use --mode stdio
        # If it *doesn't* timeout and exits, something is wrong.
        print(f"Exit Code: {result.returncode}")
        print(f"Stdout:\n{result.stdout}")
        print(f"Stderr:\n{result.stderr}") # Log stderr in case of unexpected exit
        pytest.fail(f"CLI --stdio invocation exited unexpectedly with code {result.returncode}")
    except subprocess.TimeoutExpired:
        print("CLI --stdio invocation timed out (expected behavior). Test passes.")
        pass # Timeout is expected for a running server waiting for input
    except Exception as e:
        pytest.fail(f"CLI --stdio invocation failed unexpectedly: {e}")

    print("CLI --mode stdio invocation test passed.")

def test_cli_default_invocation_help():
    """Test invoking default mode (HTTP) shows help correctly."""
    # Default mode is HTTP, so just running --help should work
    result = run_server_cli(["--help"])
    print(f"Exit Code: {result.returncode}")
    print(f"Stdout:\n{result.stdout}")
    print(f"Stderr:\n{result.stderr}")
    assert result.returncode == 0
    # Check if any line starts with the usage string after stripping
    # Check if any line contains the usage string after stripping
    assert "Usage:" in result.stdout, "Usage string not found in help output" # Check raw output
    # Check for relevant options for HTTP mode
    assert "--host" in result.stdout, "--host option not found in plain help output"
    assert "--port" in result.stdout, "--port option not found in plain help output"
    assert "--static-dir" in result.stdout, "--static-dir option not found in plain help output"
    assert "--mode" in result.stdout, "--mode option not found in plain help output" # Check for the option name
    # Check removed options are not present
    assert "--output-dir" not in result.stdout
    assert "--part-library-dir" not in result.stdout
    print("CLI --mode sse (default) --help test passed.")

# TODO: Add more specific CLI tests if needed, e.g., passing invalid args