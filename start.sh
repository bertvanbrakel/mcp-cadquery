#!/bin/bash
# Main entry point script: Sets up environment and runs the server.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Step 1: Ensure Environment is Set Up ---
echo "Ensuring Python environment and dependencies are up to date..."
bash ./setup_env.sh
echo "Environment check complete."

# Define the virtual environment directory and Python executable
VENV_DIR=".venv-cadquery"
PYTHON_EXE="$VENV_DIR/bin/python" # Adjust for Windows if needed

# Double-check Python executable exists after setup
if [ ! -f "$PYTHON_EXE" ]; then
    echo "Error: Python executable still not found at $PYTHON_EXE after running setup."
    exit 1
fi

# --- Step 2: Check/Build Frontend (Optional but helpful) ---
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

# --- Step 3: Run the Server ---
# Pass all arguments received by start.sh directly to the server.py CLI
ARGS=("$@")
echo "Starting MCP CadQuery server via server.py CLI..."
echo "Arguments passed: ${ARGS[*]}"
"$PYTHON_EXE" server.py "${ARGS[@]}"