import logging
import sys
import os
import asyncio
from typing import Dict, Any, List, Optional
from cadquery import cqgi # For type hint

# --- Logging Setup (Application Level) ---
# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True # Force re-configuration if already configured elsewhere
)
log = logging.getLogger("mcp_cadquery_server") # Use a consistent logger name

# --- Global State ---
shape_results: Dict[str, Dict[str, Any]] = {} # Store result dicts from script_runner
part_index: Dict[str, Dict[str, Any]] = {} # Index for scanned parts
sse_connections: List[asyncio.Queue] = [] # List of active SSE client queues

# --- Global Path Configuration (Defaults & Placeholders) ---

# Define script directory early for use in finding runners or resources
# Assumes state.py is in src/mcp_cadquery_server/
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_MODULE_DIR)
_PROJECT_ROOT = os.path.dirname(_SRC_DIR) # This should be the project root

# Default names/relative paths (can be overridden by CLI)
DEFAULT_PART_LIBRARY_DIR = "part_library"
DEFAULT_OUTPUT_DIR_NAME = "shapes" # Main output directory within workspace
DEFAULT_RENDER_DIR_NAME = "renders" # Subdir within output dir for renders
DEFAULT_PART_PREVIEW_DIR_NAME = "part_previews" # Subdir within output dir for previews

# These will be dynamically set in main() based on CLI args or defaults
# They represent the *active* configuration for the running server instance.
# Absolute paths are preferred after initialization.
ACTIVE_PART_LIBRARY_DIR: str = "" # Absolute path to part library (input)
ACTIVE_OUTPUT_DIR_PATH: str = "" # Absolute path to the main output dir (e.g., workspace/shapes)
ACTIVE_RENDER_DIR_PATH: str = "" # Absolute path to the render subdir
ACTIVE_PART_PREVIEW_DIR_PATH: str = "" # Absolute path to the preview subdir
ACTIVE_STATIC_DIR: Optional[str] = None # Absolute path to static dir (optional, for frontend)
ACTIVE_ASSETS_DIR_PATH: Optional[str] = None # Absolute path to assets dir (optional, within static)

# --- Workspace Environment Cache ---
# Moved from env_setup to avoid circular dependency if env_setup needs logging
workspace_reqs_mtime_cache: Dict[str, float] = {}