#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the virtual environment directory
VENV_DIR=".venv-cadquery"
PYTHON_EXE="$VENV_DIR/bin/python" # Adjust for Windows if needed

# --- Prerequisite Check ---
if [ ! -f "$PYTHON_EXE" ]; then
    echo "Error: Virtual environment $VENV_DIR not found or Python executable missing."
    echo "Please run 'bash setup_env.sh' first."
    exit 1
fi

# --- Defaults ---
PORT=8000
HOST="0.0.0.0"
RELOAD="" # Empty means no reload

# --- Argument Parsing (Simplified for Typer) ---
# Pass all arguments directly to the python script
# Typer will handle parsing --port, --host, --reload etc.
ARGS=("$@")

# Build frontend if not in dev mode (optional, could be separate build step)
# Keep this part as it's useful for ensuring static files exist
FRONTEND_DIR="frontend"
if [ -d "$FRONTEND_DIR" ]; then
    echo "Checking frontend build..."
    if [ ! -d "$FRONTEND_DIR/dist" ]; then
        echo "Frontend not built. Building now..."
         if ! command -v npm &> /dev/null; then
            echo "Warning: npm is not installed. Cannot build frontend."
         else
            echo "Installing frontend dependencies..."
            (cd $FRONTEND_DIR && npm install)
            echo "Building frontend..."
            (cd $FRONTEND_DIR && npm run build)
            echo "Frontend built."
        fi
    else
        echo "Frontend already built."
    fi
else
    echo "Warning: Frontend directory '$FRONTEND_DIR' not found. Cannot build or serve frontend."
fi


# Run the server using the typer CLI in server.py
echo "Starting MCP CadQuery server via server.py CLI..."
echo "Arguments passed: ${ARGS[*]}"
"$PYTHON_EXE" server.py "${ARGS[@]}" # Pass all original arguments to the script