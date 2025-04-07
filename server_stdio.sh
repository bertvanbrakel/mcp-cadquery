#!/bin/bash

# Setup and activate the virtual environment
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_DIR="$SCRIPT_DIR/.venv-cadquery" # Corrected venv name
VENV_ACTIVATE="$VENV_DIR/bin/activate"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

# Check if venv exists, create if not
if [ ! -d "$VENV_DIR" ]; then
  echo "Virtual environment not found at $VENV_DIR. Creating..."
  uv venv "$VENV_DIR"
  if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
  fi
  echo "Virtual environment created."

  # Activate and install requirements after creation
  echo "Activating environment..."
  source "$VENV_ACTIVATE"
  if [ $? -ne 0 ]; then
    echo "Error: Failed to activate virtual environment after creation."
    exit 1
  fi

  if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Installing dependencies from $REQUIREMENTS_FILE..."
    uv pip install -r "$REQUIREMENTS_FILE"
    if [ $? -ne 0 ]; then
      echo "Error: Failed to install dependencies."
      # Consider exiting or just warning depending on desired behavior
      # exit 1
    else
       echo "Dependencies installed."
    fi
  else
    echo "Warning: requirements.txt not found. Skipping dependency installation."
  fi

else
  # Activate existing environment
  echo "Activating existing environment..."
  source "$VENV_ACTIVATE"
  if [ $? -ne 0 ]; then
    echo "Error: Failed to activate existing virtual environment at $VENV_ACTIVATE."
    exit 1
  fi
fi

# Run the server in stdio mode, passing through any additional arguments
echo "Starting server in stdio mode..."
python3 "$SCRIPT_DIR/server.py" --mode stdio "$@" # Ensure python3 is used here too