#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Defaults ---
BACKEND_PORT=8000
LOG_LEVEL="info" # Default log level for backend

# --- Argument Parsing ---
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --port)
      BACKEND_PORT="$2"
      shift # past argument
      shift # past value
      ;;
    --verbose)
      LOG_LEVEL="debug"
      shift # past argument
      ;;
    *)    # unknown option
      echo "Unknown option: $1"
      echo "Usage: $0 [--port <backend_port>] [--verbose]"
      exit 1
      ;;
  esac
done

# --- Prerequisite Checks ---
VENV_DIR=".venv-cadquery"
FRONTEND_DIR="frontend"

if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment $VENV_DIR not found. Run 'bash run_server.sh' once first to create it."
    exit 1
fi
if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Error: Frontend directory '$FRONTEND_DIR' not found."
    exit 1
fi
if ! command -v npm &> /dev/null; then
    echo "Error: npm is not installed. Cannot run frontend dev server."
    exit 1
fi
if ! npx -v &> /dev/null; then
    echo "Warning: npx might not be installed or in PATH. Concurrently might fail."
    echo "Consider installing Node.js/npm which usually includes npx."
fi
# --- Assume Dependencies are installed via setup_env.sh ---
echo "Assuming dependencies are installed. Run 'bash setup_env.sh' if needed."



# --- Run Concurrently ---
echo "Starting backend (port $BACKEND_PORT, log: $LOG_LEVEL) and frontend dev servers concurrently..."

# Define commands
# Use quotes to handle potential spaces or special characters in paths/commands
BACKEND_CMD="uv run --python $VENV_DIR/bin/python -m uvicorn server:app --host 0.0.0.0 --port $BACKEND_PORT --reload --log-level $LOG_LEVEL"
FRONTEND_CMD="npm run dev --prefix $FRONTEND_DIR"

# Run using npx concurrently
# --kill-others: Kill other processes if one exits
# --names: Prefix output with process names
# -c: Define colors for prefixes
npx concurrently --kill-others --names "BACKEND,FRONTEND" -c "bgBlue.bold,bgMagenta.bold" "$BACKEND_CMD" "$FRONTEND_CMD"