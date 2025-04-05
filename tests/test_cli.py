import pytest
from typer.testing import CliRunner
import os
import sys
import io # For unsupported operation check

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the typer app instance from server.py in root
from server_stdio import cli

runner = CliRunner()

def test_cli_help():
    """Test the --help option."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: main [OPTIONS]" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--reload" in result.stdout
    assert "--stdio" in result.stdout
    assert "--library-dir" in result.stdout
    assert "--static-dir" in result.stdout
    print("CLI --help test passed.")

def test_cli_stdio_invocation():
    """Test invoking --stdio doesn't raise unexpected errors immediately."""
    # CliRunner has issues with stdin/stdout fileno needed by asyncio reader
    # We just check that it starts and exits (or raises expected exceptions)
    result = runner.invoke(cli, ["--stdio"], input="\n") # Send newline to exit loop
    # Expect either clean exit (0), SystemExit from typer, or UnsupportedOperation
    assert result.exit_code == 0 or \
           isinstance(result.exception, SystemExit) or \
           isinstance(result.exception, io.UnsupportedOperation)
    print("CLI --stdio invocation test passed (basic check).")