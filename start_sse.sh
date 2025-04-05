#!/bin/bash
# Convenience script to run the server in HTTP SSE mode with defaults.
# Ensures environment is set up first.

set -e

echo "Ensuring environment..."
bash ./setup_env.sh

VENV_DIR=".venv-cadquery"
PYTHON_EXE="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON_EXE" ]; then
    echo "Error: Python executable not found at $PYTHON_EXE after setup."
    exit 1
fi

echo "Starting server in HTTP SSE mode (Host: 0.0.0.0, Port: 8000, Reload: On)..."
# Use the venv python to run the server script
# Pass --reload for development convenience
"$PYTHON_EXE" server.py --port 8000 --reload "$@"