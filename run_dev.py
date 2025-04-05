#!/usr/bin/env python3
# Helper script to guide running the full development environment.

import sys

print("--- Running Full Development Environment ---")
print("\nThis script requires running two processes in separate terminals:")
print("\n1. Backend Server (with auto-reload):")
print("   Terminal 1: python3 ./setup_env.py && source .venv-cadquery/bin/activate && python server.py --reload")
print("   (Or use: bash ./start_sse.sh)")
print("\n2. Frontend Dev Server (with hot-reloading):")
print("   Terminal 2: python3 ./run_frontend_dev.py")
print("\nEnsure both are running concurrently.")
print("Backend API typically at http://127.0.0.1:8000")
print("Frontend typically at http://localhost:5173")

# Exit successfully after printing instructions
sys.exit(0)