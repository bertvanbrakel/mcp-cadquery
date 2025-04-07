#!/usr/bin/env python3
import sys
import os

# Ensure the src directory is in the path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import and run the Typer CLI application
# This is now the main entry point logic
from src.mcp_cadquery_server.cli import cli

if __name__ == "__main__":
    cli()
