#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the virtual environment directory
VENV_DIR=".venv-cadquery"

# Check if uv is installed
if ! command -v uv &> /dev/null
then
    echo "Error: Python 'uv' is not installed or not in PATH."
    echo "Please install it: https://github.com/astral-sh/uv"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    uv venv $VENV_DIR -p python3.11 # Specify a stable Python 3.9+ version
    echo "Virtual environment created."
else
    echo "Virtual environment $VENV_DIR already exists."
fi

# Install dependencies
echo "Installing dependencies from requirements.txt..."
uv pip install -r requirements.txt --python $VENV_DIR/bin/python
echo "Dependencies installed."

# Run the server
echo "Starting MCP CadQuery server..."
uv run --python $VENV_DIR/bin/python server.py