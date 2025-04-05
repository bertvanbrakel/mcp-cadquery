#!/bin/bash
# Script to create/update virtual environment and install dependencies.

set -e # Exit on error

VENV_DIR=".venv-cadquery"
REQUIREMENTS_FILE="requirements.txt"

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
    # Specify a stable Python 3.9+ version if needed, otherwise use default found
    uv venv $VENV_DIR -p python3.11
    echo "Virtual environment created."
else
    echo "Virtual environment $VENV_DIR already exists."
fi

# Install/sync dependencies using the specific python from the venv
PYTHON_EXE="$VENV_DIR/bin/python" # Adjust for Windows if needed
if [ ! -f "$PYTHON_EXE" ]; then
    echo "Error: Python executable not found at $PYTHON_EXE"
    exit 1
fi

echo "Installing/syncing dependencies from $REQUIREMENTS_FILE into $VENV_DIR..."
# Use pip sync for potentially faster updates if requirements change often
# uv pip sync $REQUIREMENTS_FILE --python $PYTHON_EXE
# Or use install for broader compatibility
uv pip install -r $REQUIREMENTS_FILE --python $PYTHON_EXE

echo "Environment setup complete."