#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

FRONTEND_DIR="frontend"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Error: Frontend directory '$FRONTEND_DIR' not found."
    exit 1
fi

if ! command -v npm &> /dev/null
then
    echo "Error: npm is not installed. Cannot run frontend dev server."
    exit 1
fi

echo "Changing to frontend directory: $FRONTEND_DIR"
cd $FRONTEND_DIR

echo "Installing frontend dependencies (if needed)..."
npm install

echo "Starting Vite development server..."
# This will typically run on http://localhost:5173
npm run dev