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

# Install backend dependencies (if needed)
echo "Ensuring backend dependencies from requirements.txt are installed..."
uv pip install -r requirements.txt --python $VENV_DIR/bin/python
echo "Backend dependencies checked/installed."

# --- Defaults ---
PORT=8000
LOG_LEVEL="info"

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --port)
      PORT="$2"
      shift # past argument
      shift # past value
      ;;
    --verbose|--debug)
      LOG_LEVEL="debug"
      shift # past argument
      ;;
    *)    # unknown option
      echo "Unknown option: $1"
      echo "Usage: $0 [--port <port>] [--verbose|--debug]"
      exit 1
      ;;
  esac
done

# Build frontend if not in dev mode (optional, could be separate build step)
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


# Run the FastAPI server using uvicorn (without reload)
echo "Starting MCP CadQuery FastAPI backend server with uvicorn..."
echo "Host: 0.0.0.0, Port: $PORT, Log Level: $LOG_LEVEL"
echo "(Serving built frontend from '$FRONTEND_DIR/dist' if available)"
uv run --python $VENV_DIR/bin/python -m uvicorn server:app --host 0.0.0.0 --port $PORT --log-level $LOG_LEVEL