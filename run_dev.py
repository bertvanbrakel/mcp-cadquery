#!/usr/bin/env python3
"""
Helper script that prints instructions for running the full development environment,
including the backend server and the frontend development server.
"""
import sys

print("--- Running Full Development Environment ---")
print("\nThis script requires running two processes in separate terminals:")
print("\n1. Backend Server (with auto-reload):")
print("   Terminal 1: python3 ./setup_env.py && source .venv-cadquery/bin/activate && python server_stdio.py --reload")
print("   (The SSE server can be run separately if needed: python server_sse.py)")
print("\n2. Frontend Dev Server (with hot-reloading):")
print("   Terminal 2: python3 ./run_frontend_dev.py")
print("\nEnsure both are running concurrently.")
print("Backend API typically at http://127.0.0.1:8000")
print("Frontend typically at http://localhost:5173")

# Exit successfully after printing instructions
sys.exit(0)