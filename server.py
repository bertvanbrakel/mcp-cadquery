#!/usr/bin/env python3
import sys
import os
import subprocess # Added for running setup commands
import shutil # Added for checking uv existence
import logging
import json # Needed for stdio mode basic parsing
import asyncio # Needed for stdio mode basic parsing
from typing import Dict, Any, List, Optional, Union # Keep basic typing

# --- Constants for Environment Setup ---
VENV_DIR = ".venv-cadquery"
REQUIREMENTS_FILE = "requirements.txt"
PYTHON_VERSION = "3.11" # Specify desired Python version for uv

# --- Environment Setup Helper ---

def _run_command_helper(command: list[str], check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    """
    Helper to run a command, capture output, and raise exceptions on failure.
    Adapted from setup_env.py. Uses logging.
    """
    # Use basicConfig for setup logging if not already configured
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - Setup - %(levelname)s - %(message)s', stream=sys.stderr)

    logging.info(f"Running command: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            **kwargs
        )
        logging.debug(f"Command stdout:\n{process.stdout}")
        if process.stderr:
            logging.debug(f"Command stderr:\n{process.stderr}")
        return process
    except FileNotFoundError as e:
        logging.error(f"Error: Command '{command[0]}' not found. Is it installed and in PATH?")
        raise e # Re-raise for handling
    except subprocess.CalledProcessError as e:
        logging.error(f"Error running command: {' '.join(command)}")
        logging.error(f"Exit code: {e.returncode}")
        if e.stdout: logging.error("Stdout:\n" + e.stdout)
        if e.stderr: logging.error("Stderr:\n" + e.stderr)
        raise e # Re-raise for handling
    except Exception as e:
        logging.error(f"An unexpected error occurred running command: {e}")
        raise e # Re-raise for handling

def _setup_and_validate_venv() -> str:
    """
    Checks for 'uv', creates/updates the virtual environment if needed,
    and installs/syncs dependencies from requirements.txt using 'uv'.

    Returns:
        The absolute path to the Python executable within the validated venv.

    Raises:
        FileNotFoundError: If 'uv' is not found.
        RuntimeError: If environment setup fails at any step.
        Exception: For other unexpected errors during command execution.
    """
    # Check if uv is installed
    logging.info("Checking for uv...")
    if not shutil.which("uv"):
         msg = "Error: Python 'uv' is not installed or not in PATH. Please install it: https://github.com/astral-sh/uv"
         logging.error(msg)
         raise FileNotFoundError(msg)
    logging.info("uv found.")

    # Create virtual environment if it doesn't exist
    venv_path = os.path.abspath(VENV_DIR)
    # Determine platform-specific bin directory
    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
    python_exe_path = os.path.join(venv_path, bin_dir, "python.exe" if sys.platform == "win32" else "python")

    try:
        if not os.path.isdir(venv_path) or not os.path.exists(python_exe_path):
            logging.info(f"Creating virtual environment in {venv_path} using Python {PYTHON_VERSION}...")
            _run_command_helper(["uv", "venv", venv_path, "-p", PYTHON_VERSION])
            logging.info("Virtual environment created.")
        else:
            logging.info(f"Virtual environment {venv_path} already exists.")

        # Ensure the Python executable exists after potential creation
        if not os.path.exists(python_exe_path):
             msg = f"Error: Python executable still not found at {python_exe_path} after check/creation."
             logging.error(msg)
             raise RuntimeError(msg)

        # Install/sync dependencies using the specific python from the venv
        logging.info(f"Installing/syncing dependencies from {REQUIREMENTS_FILE} into {venv_path}...")
        # Use --python flag for uv pip install to target the correct environment
        _run_command_helper(["uv", "pip", "install", "-r", REQUIREMENTS_FILE, "--python", python_exe_path])

        logging.info("Environment setup/validation complete.")
        return python_exe_path

    except (FileNotFoundError, subprocess.CalledProcessError, Exception) as e:
        logging.error(f"Failed to set up virtual environment: {e}")
        raise RuntimeError(f"Failed to set up virtual environment: {e}") from e

# --- Auto Environment Setup & Re-execution ---

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_PATH = os.path.abspath(os.path.join(_SCRIPT_DIR, VENV_DIR))

# Check if we are running inside the target virtual environment
_IS_IN_VENV = sys.prefix == _VENV_PATH

if not _IS_IN_VENV:
    print(f"Not running in the expected virtual environment ({_VENV_PATH}). Setting up and re-executing...")
    try:
        venv_python_executable = _setup_and_validate_venv()
        # Re-execute the script using the Python from the virtual environment
        # Pass all original arguments
        args = [venv_python_executable] + sys.argv
        print(f"Re-executing with: {' '.join(args)}")
        os.execvp(venv_python_executable, args)
        # os.execvp replaces the current process, so code below here won't run in this branch
    except Exception as setup_error:
        # Use basic config for logging if it failed during setup
        if not logging.getLogger().hasHandlers():
             logging.basicConfig(level=logging.ERROR, format='%(asctime)s - Setup - %(levelname)s - %(message)s', stream=sys.stderr)
        logging.error(f"Automatic environment setup failed: {setup_error}", exc_info=True)
        print(f"ERROR: Automatic environment setup failed: {setup_error}", file=sys.stderr)
        # Removed suggestion for setup_env.py as it's deleted
        print("Please check uv installation and requirements.txt.", file=sys.stderr)
        sys.exit(1)

# --- Imports required only when running IN the venv ---
# These are now safe because the block above ensures we are in the venv
import traceback
import uuid
import ast
import re
import mimetypes
import typer
import uvicorn
from src.mcp_cadquery_server.core import (
    execute_cqgi_script,
    export_shape_to_file,
    export_shape_to_svg_file,
    parse_docstring_metadata,
    _substitute_parameters
)
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse
import cadquery as cq
from cadquery import cqgi # Needed for type hints

# --- Global App Instances (Defined after venv check) ---
# Define app and cli globally so they can be imported by tests
app = FastAPI()
cli = typer.Typer()

# --- Global State and Paths (Defaults) ---
# These might be modified by the CLI command later
shape_results: Dict[str, cqgi.BuildResult] = {}
part_index: Dict[str, Dict[str, Any]] = {}
PART_LIBRARY_DIR = "part_library"
RENDER_DIR_NAME = "renders"
PART_PREVIEW_DIR_NAME = "part_previews"
STATIC_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "frontend/dist")) # Use _SCRIPT_DIR from top level
RENDER_DIR_PATH = os.path.join(STATIC_DIR, RENDER_DIR_NAME)
PART_PREVIEW_DIR_PATH = os.path.join(STATIC_DIR, PART_PREVIEW_DIR_NAME)
ASSETS_DIR_PATH = os.path.join(STATIC_DIR, "assets")
sse_connections: List[asyncio.Queue] = []

# --- Logging Setup (Application Level) ---
# Configure logging now that we are definitely in the venv
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True # Force re-configuration over potential setup logging
)
log = logging.getLogger(__name__) # Get logger after config


# --- Core Application Logic Functions ---
# (SSE, Tool Processing, Handlers, Static Files, Stdio Mode)
# These functions use the globally defined app, cli, state, paths

async def push_sse_message(message_data: dict) -> None:
    """Pushes a message dictionary to all connected SSE clients."""
    if not message_data: return
    log.info(f"Pushing message to {len(sse_connections)} SSE client(s): {json.dumps(message_data)}")
    for queue in sse_connections:
        try: await queue.put(message_data)
        except Exception as e: log.error(f"Failed to push message to a queue: {e}")

def process_tool_request(request: dict) -> Optional[dict]:
    """
    Processes a tool request dictionary, calls the appropriate handler,
    and formats the response or error message for SSE push or stdio output.
    """
    request_id = request.get("request_id", "unknown")
    tool_name = request.get("tool_name")
    result_message: dict | None = None; error_message: str | None = None
    log.debug(f"Processing tool request (ID: {request_id}, Tool: {tool_name})")
    try:
        # Handlers are defined below, they will call the core functions
        tool_handlers = {
            "execute_cadquery_script": handle_execute_cadquery_script,
            "export_shape": handle_export_shape,
            "export_shape_to_svg": handle_export_shape_to_svg,
            "scan_part_library": handle_scan_part_library,
            "search_parts": handle_search_parts,
        }
        handler = tool_handlers.get(tool_name)
        if handler: result_message = handler(request)
        else: error_message = f"Unknown tool: {tool_name}"; log.warning(error_message)
    except Exception as e:
        log.error(f"Error processing tool '{tool_name}' (ID: {request_id}): {e}", exc_info=True)
        detail = getattr(e, 'detail', str(e)); error_message = f"Internal server error processing {tool_name}: {detail}"
    log.debug(f"Tool processing complete (ID: {request_id}). Error: {error_message}, Result: {result_message}")
    message_to_push: Optional[dict] = None
    if error_message: message_to_push = {"type": "tool_error", "request_id": request_id, "error": error_message}
    elif result_message: message_to_push = {"type": "tool_result", "request_id": request_id, "result": result_message}
    else: log.warning(f"No result or error message generated for request ID: {request_id}")
    return message_to_push

def handle_execute_cadquery_script(request: dict) -> dict:
    """
    Handles the 'execute_cadquery_script' tool request.
    Calls core logic for substitution and execution.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling execute_cadquery_script request (ID: {request_id})")
    try:
        args = request.get("arguments", {}); script_content = args.get("script")
        parameter_sets_arg = args.get("parameter_sets")
        parameters_arg = args.get("parameters")
        parameter_sets: List[Dict[str, Any]] = []

        if parameter_sets_arg is not None:
            if not isinstance(parameter_sets_arg, list): raise ValueError("'parameter_sets' argument must be a list of dictionaries.")
            if not all(isinstance(p, dict) for p in parameter_sets_arg): raise ValueError("Each item in 'parameter_sets' must be a dictionary.")
            parameter_sets = parameter_sets_arg
        elif parameters_arg is not None:
            if not isinstance(parameters_arg, dict): raise ValueError("'parameters' argument must be a dictionary.")
            parameter_sets = [parameters_arg]
        else:
            parameter_sets = [{}]

        if not script_content: raise ValueError("Missing 'script' argument.")
        log.info(f"Script content received (first 100 chars): {script_content[:100]}...")
        log.info(f"Processing {len(parameter_sets)} parameter set(s).")

        original_script_lines = script_content.splitlines()
        results_summary = []

        for i, params in enumerate(parameter_sets):
            result_id = f"{request_id}_{i}"
            log.info(f"Executing script for parameter set {i} (Result ID: {result_id}) with params: {params}")
            try:
                # Use core function for substitution
                modified_script_lines = _substitute_parameters(original_script_lines, params)
                modified_script = "\n".join(modified_script_lines)
                log.debug(f"Modified script for set {i}:\n{modified_script[:500]}...")

                # Use core function for execution
                build_result = execute_cqgi_script(modified_script)
                shape_results[result_id] = build_result # Store result
                num_shapes = len(build_result.results) if build_result.results else 0
                results_summary.append({
                    "result_id": result_id,
                    "success": build_result.success,
                    "shapes_count": num_shapes,
                    "error": str(build_result.exception) if build_result.exception else None
                })
                log.info(f"Stored build result for set {i} with ID: {result_id}. Success: {build_result.success}")
            except Exception as exec_err:
                log.error(f"Execution failed for parameter set {i} (Result ID: {result_id}): {exec_err}", exc_info=True)
                results_summary.append({
                    "result_id": result_id,
                    "success": False,
                    "shapes_count": 0,
                    "error": f"Handler execution error: {exec_err}"
                })

        total_sets = len(parameter_sets)
        successful_sets = sum(1 for r in results_summary if r["success"])
        message = f"Script execution processed for {total_sets} parameter set(s). Successful: {successful_sets}, Failed: {total_sets - successful_sets}."
        return {"success": True, "message": message, "results": results_summary}

    except Exception as e: error_msg = f"Error during script execution handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_export_shape(request: dict) -> dict:
    """
    Handles the 'export_shape' tool request.
    Calls core logic for file export.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape request (ID: {request_id})")
    try:
        args = request.get("arguments", {}); result_id = args.get("result_id"); shape_index = args.get("shape_index", 0)
        filename = args.get("filename"); export_format = args.get("format"); export_options = args.get("options", {})
        if not result_id: raise ValueError("Missing 'result_id' argument.")
        if not filename: raise ValueError("Missing 'filename' argument.")
        if not isinstance(shape_index, int) or shape_index < 0: raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(export_options, dict): raise ValueError("'options' argument must be a dictionary.")
        build_result = shape_results.get(result_id)
        if not build_result: raise ValueError(f"Result ID '{result_id}' not found.")
        if not build_result.success: raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")
        if not build_result.results or shape_index >= len(build_result.results): raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")
        shape_to_export = build_result.results[shape_index].shape
        log.info(f"Retrieved shape at index {shape_index} from result ID {result_id}.")
        log.info(f"Attempting to export shape to '{filename}' (Format: {export_format or 'Infer'}, Options: {export_options})")
        # Call the core export function
        export_shape_to_file(shape_to_export, filename, export_format, export_options)
        log.info(f"Shape successfully exported via export_shape_to_file to '{filename}'.")
        return {"success": True, "message": f"Shape successfully exported to {filename}.", "filename": filename}
    except Exception as e: error_msg = f"Error during shape export handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_export_shape_to_svg(request: dict) -> dict:
    """
    Handles the 'export_shape_to_svg' tool request.
    Calls core logic for SVG export.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape_to_svg request (ID: {request_id})")
    try:
        args = request.get("arguments", {}); result_id = args.get("result_id"); shape_index = args.get("shape_index", 0)
        default_svg_name = f"render_{uuid.uuid4()}.svg"; base_filename = os.path.basename(args.get("filename", default_svg_name))
        if not base_filename.lower().endswith(".svg"): base_filename += ".svg"; log.warning(f"Appended .svg to filename. New base filename: {base_filename}")
        export_options = args.get("options", {})
        if not result_id: raise ValueError("Missing 'result_id' argument.")
        if not isinstance(shape_index, int) or shape_index < 0: raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(export_options, dict): raise ValueError("'options' argument must be a dictionary.")
        build_result = shape_results.get(result_id)
        if not build_result: raise ValueError(f"Result ID '{result_id}' not found.")
        if not build_result.success: raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")
        if not build_result.results or shape_index >= len(build_result.results): raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")
        shape_result_obj = build_result.results[shape_index].shape
        log.info(f"Retrieved shape object at index {shape_index} from result ID {result_id}.")
        # Use RENDER_DIR_PATH which is calculated based on CLI args or defaults
        output_path = os.path.join(RENDER_DIR_PATH, base_filename); output_url = f"/{RENDER_DIR_NAME}/{base_filename}"
        svg_opts = {"width": 400, "height": 300, "marginLeft": 10, "marginTop": 10, "showAxes": False, "projectionDir": (0.5, 0.5, 0.5), "strokeWidth": 0.25, "strokeColor": (0, 0, 0), "hiddenColor": (0, 0, 255, 100), "showHidden": False}
        svg_opts.update(export_options)
        # Call core SVG export function
        export_shape_to_svg_file(shape_result_obj, output_path, svg_opts)
        return {"success": True, "message": f"Shape successfully exported to SVG: {output_url}.", "filename": output_url}
    except Exception as e: error_msg = f"Error during SVG export handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_scan_part_library(request: dict) -> dict:
    """
    Handles the 'scan_part_library' tool request.
    Calls core logic for script execution, metadata parsing, and SVG export.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling scan_part_library request (ID: {request_id})")
    # Use paths calculated based on CLI args or defaults
    library_path = os.path.abspath(PART_LIBRARY_DIR); preview_dir_path = PART_PREVIEW_DIR_PATH; preview_dir_url = f"/{PART_PREVIEW_DIR_NAME}"
    if not os.path.isdir(library_path): raise ValueError(f"Part library directory not found: {library_path}")
    scanned_count, indexed_count, updated_count, cached_count, error_count = 0, 0, 0, 0, 0
    found_parts = set(); default_svg_opts = {"width": 150, "height": 100, "showAxes": False}
    for filename in os.listdir(library_path):
        if filename.endswith(".py") and not filename.startswith("_"):
            scanned_count += 1; part_name = os.path.splitext(filename)[0]; found_parts.add(part_name)
            file_path = os.path.join(library_path, filename); error_msg = None
            try:
                current_mtime = os.path.getmtime(file_path); cached_data = part_index.get(part_name)
                if cached_data and cached_data.get('mtime') == current_mtime: log.debug(f"Using cached data for part: {filename}"); cached_count += 1; continue
                log.info(f"Processing part: {filename} (new or modified)")
                with open(file_path, 'r', encoding='utf-8') as f: script_content = f.read()
                # Use core function for metadata parsing
                tree = ast.parse(script_content); docstring = ast.get_docstring(tree)
                metadata = parse_docstring_metadata(docstring); metadata['filename'] = filename
                # Use core function for script execution
                build_result = execute_cqgi_script(script_content)
                if build_result.success and build_result.results:
                    shape_to_preview = build_result.results[0].shape; preview_filename = f"{part_name}.svg"
                    preview_output_path = os.path.join(preview_dir_path, preview_filename); preview_output_url = f"{preview_dir_url}/{preview_filename}"
                    # Use core function for SVG export
                    export_shape_to_svg_file(shape_to_preview, preview_output_path, default_svg_opts)
                    part_data = { "part_id": part_name, "metadata": metadata, "preview_url": preview_output_url, "script_path": file_path, "mtime": current_mtime }
                    if part_name in part_index: updated_count += 1
                    else: indexed_count += 1
                    part_index[part_name] = part_data; log.info(f"Successfully indexed/updated part: {part_name}")
                elif not build_result.results: log.warning(f"Part script {filename} executed successfully but produced no results. Skipping indexing."); error_count += 1
                else: # Handle build failure
                     log.warning(f"Part script {filename} failed execution: {build_result.exception}. Skipping indexing.")
                     error_count += 1
            except SyntaxError as e: error_msg = f"Syntax error parsing {filename}: {e}"; error_count += 1
            except Exception as e: error_msg = f"Error processing {filename}: {e}"; error_count += 1
            if error_msg: log.error(error_msg, exc_info=True)
    removed_count = 0; indexed_parts = set(part_index.keys()); parts_to_remove = indexed_parts - found_parts
    for part_name_to_remove in parts_to_remove:
        log.info(f"Removing deleted part from index: {part_name_to_remove}")
        removed_data = part_index.pop(part_name_to_remove, None)
        if removed_data and 'preview_url' in removed_data:
            preview_filename = os.path.basename(removed_data['preview_url']); preview_file_path = os.path.join(PART_PREVIEW_DIR_PATH, preview_filename)
            if os.path.exists(preview_file_path):
                try: os.remove(preview_file_path); log.info(f"Removed preview file: {preview_file_path}")
                except OSError as e: log.error(f"Error removing preview file {preview_file_path}: {e}")
        removed_count += 1
    summary_msg = (f"Scan complete. Scanned: {scanned_count}, Newly Indexed: {indexed_count}, "
                   f"Updated: {updated_count}, Cached: {cached_count}, Removed: {removed_count}, Errors: {error_count}.")
    log.info(summary_msg)
    return { "success": True, "message": summary_msg, "scanned": scanned_count, "indexed": indexed_count, "updated": updated_count, "cached": cached_count, "removed": removed_count, "errors": error_count }

def handle_search_parts(request: dict) -> dict:
    """
    Handles the 'search_parts' tool request. Searches the in-memory part index.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling search_parts request (ID: {request_id})")
    try:
        args = request.get("arguments", {}); query = args.get("query", "").strip().lower()
        if not query: log.info("Empty search query..."); results = list(part_index.values()); return {"success": True, "message": f"Found {len(results)} parts.", "results": results}
        log.info(f"Searching parts with query: '{query}'")
        search_terms = set(term.strip() for term in query.split() if term.strip()); results = []
        for part_id, part_data in part_index.items():
            match_score = 0; metadata = part_data.get("metadata", {})
            if query in part_id.lower(): match_score += 5
            if query in metadata.get("part", "").lower(): match_score += 3
            if query in metadata.get("description", "").lower(): match_score += 2
            tags = metadata.get("tags", [])
            if isinstance(tags, list):
                 if any(term in tag for term in search_terms for tag in tags): match_score += 5
            if query in metadata.get("filename", "").lower(): match_score += 1
            if match_score > 0: results.append({"score": match_score, "part": part_data})
        results.sort(key=lambda x: x["score"], reverse=True); final_results = [item["part"] for item in results]
        message = f"Found {len(final_results)} parts matching query '{query}'."; log.info(message)
        return {"success": True, "message": message, "results": final_results}
    except Exception as e: error_msg = f"Error during part search: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def configure_static_files(static_dir: str, render_dir_name: str, render_dir_path: str, preview_dir_name: str, preview_dir_path: str, assets_dir_path: str) -> None:
    """
    Configures FastAPI static file serving for frontend, renders, and previews.
    """
    log.info(f"Configuring static files. Base static dir: {static_dir}")

    # Mount renders, previews, and assets if they exist
    if os.path.isdir(render_dir_path):
        app.mount(f"/{render_dir_name}", StaticFiles(directory=render_dir_path), name=render_dir_name)
        log.info(f"Mounted render directory '{render_dir_path}' at '/{render_dir_name}'")
    else: log.warning(f"Render directory '{render_dir_path}' not found, skipping mount.")

    if os.path.isdir(preview_dir_path):
        app.mount(f"/{preview_dir_name}", StaticFiles(directory=preview_dir_path), name=preview_dir_name)
        log.info(f"Mounted preview directory '{preview_dir_path}' at '/{preview_dir_name}'")
    else: log.warning(f"Preview directory '{preview_dir_path}' not found, skipping mount.")

    if os.path.isdir(assets_dir_path):
         app.mount("/assets", StaticFiles(directory=assets_dir_path), name="assets")
         log.info(f"Mounted assets directory '{assets_dir_path}' at '/assets'")
    elif os.path.isdir(os.path.join(static_dir, "assets")): # Check if assets is inside static_dir
         app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")
         log.info(f"Mounted assets directory '{os.path.join(static_dir, 'assets')}' at '/assets'")
    else: log.warning(f"Assets directory '{assets_dir_path}' not found, skipping mount.")


    # Catch-all for SPA routing and serving other static files
    # This needs to be defined *after* specific mounts
    @app.get("/{full_path:path}")
    async def serve_static_or_index(request: Request, full_path: str) -> Union[FileResponse, Response, HTTPException]:
        """Serves static files or index.html for SPA routing."""
        # Prevent serving files outside the static directory
        if ".." in full_path: return HTTPException(status_code=404, detail="Not Found")

        file_path = os.path.join(static_dir, full_path)
        # Check if it's a directory; if so, try serving index.html from there
        if os.path.isdir(file_path): index_path = os.path.join(file_path, "index.html")
        else: index_path = None

        if index_path and os.path.isfile(index_path): return FileResponse(index_path)
        elif os.path.isfile(file_path): return FileResponse(file_path)
        else: # Fallback to root index.html for SPA routing
            root_index = os.path.join(static_dir, "index.html")
            if os.path.isfile(root_index): return FileResponse(root_index)
            else: return HTTPException(status_code=404, detail="Not Found")

async def run_stdio_mode() -> None:
    """Runs the server in stdio mode, reading JSON requests from stdin."""
    log.info("Starting server in Stdio mode. Reading from stdin...")
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    try:
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    except Exception as e:
         log.error(f"Error connecting read pipe for stdin: {e}. Stdio mode may not work.", exc_info=True)
         print(json.dumps({"type": "tool_error", "request_id": "stdio-init-fail", "error": f"Failed to connect stdin: {e}"}), flush=True)
         return # Cannot proceed without stdin

    while True:
        try:
            line_bytes = await reader.readline()
            if not line_bytes: break # EOF
            line = line_bytes.decode('utf-8').strip()
            if not line: continue
            log.debug(f"Received stdio line: {line}")
            request_data = json.loads(line)
            response = process_tool_request(request_data)
            if response: print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode JSON from stdin: {e}"); error_resp = {"type": "tool_error", "request_id": "unknown", "error": f"Invalid JSON received: {e}"}; print(json.dumps(error_resp), flush=True)
        except Exception as e:
             log.error(f"Error processing stdio request: {e}", exc_info=True)
             req_id = request_data.get("request_id", "unknown") if isinstance(request_data, dict) else "unknown"
             error_resp = {"type": "tool_error", "request_id": req_id, "error": f"Internal server error: {e}"}; print(json.dumps(error_resp), flush=True)
        except KeyboardInterrupt: log.info("KeyboardInterrupt received, exiting stdio mode."); break
        except Exception as e: log.error(f"Unexpected error in stdio loop: {e}", exc_info=True); await asyncio.sleep(1)


# --- FastAPI Route Definitions ---
# Define routes using the global 'app' instance

@app.get("/mcp")
async def mcp_sse_endpoint(request: Request) -> EventSourceResponse:
    """Handles SSE connections, keeping track of clients and pushing messages."""
    queue = asyncio.Queue()
    sse_connections.append(queue)
    client_host = request.client.host if request.client else "unknown"
    log.info(f"New SSE connection established from {client_host}. Total connections: {len(sse_connections)}")
    async def event_generator():
        try:
            while True:
                message = await queue.get()
                if message is None: break
                yield {"event": "mcp_message", "data": json.dumps(message)}
                queue.task_done()
        except asyncio.CancelledError: log.info(f"SSE connection from {client_host} cancelled/closed by client.")
        except Exception as e: log.error(f"Error in SSE event generator for {client_host}: {e}", exc_info=True)
        finally:
            if queue in sse_connections: sse_connections.remove(queue)
            log.info(f"SSE connection from {client_host} closed. Remaining connections: {len(sse_connections)}")
    return EventSourceResponse(event_generator())

async def _process_and_push(request: dict) -> None:
    """Helper coroutine to process a tool request and push the result via SSE."""
    message_to_push = process_tool_request(request)
    await push_sse_message(message_to_push)

@app.post("/mcp/execute")
async def execute_tool_endpoint(request_body: dict = Body(...)) -> dict:
    """
    FastAPI endpoint to receive tool execution requests via POST.

    Validates the request, schedules the processing in the background,
    and returns an immediate 'processing' status.
    """
    request_id = request_body.get("request_id", "unknown")
    tool_name = request_body.get("tool_name")
    log.info(f"Received execution request via POST (ID: {request_id}, Tool: {tool_name})")
    if not tool_name:
         log.error("Received execution request without tool_name.")
         raise HTTPException(status_code=400, detail="Missing 'tool_name' in request body")
    asyncio.create_task(_process_and_push(request_body))
    return {"status": "processing", "request_id": request_id}


# --- Typer Command ---
@cli.command()
def main(
    mode: str = typer.Option("sse", "--mode", help="Server mode ('stdio' or 'sse')."),
    host: str = typer.Option("0.0.0.0", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development."),
    library_dir: str = typer.Option(PART_LIBRARY_DIR, "--library-dir", "-l", help="Path to the CadQuery part library directory."), # Use initial default
    static_dir: str = typer.Option(STATIC_DIR, "--static-dir", "-s", help="Path to the static files directory (frontend build)."), # Use initial default
    preview_dir_name: str = typer.Option(PART_PREVIEW_DIR_NAME, "--preview-dir-name", help="Subdirectory name within static-dir for part previews."), # Use initial default
    render_dir_name: str = typer.Option(RENDER_DIR_NAME, "--render-dir-name", help="Subdirectory name within static-dir for renders."), # Use initial default
):
    """Runs the CadQuery MCP Server."""
    # Non-local allows modification of variables defined in the outer scope (initialize_and_run_app)
    # Need to redefine these here or pass them in, as they are not truly global anymore
    # Let's redefine them based on the arguments for clarity within this scope
    current_part_library_dir = os.path.abspath(library_dir)
    current_static_dir = os.path.abspath(static_dir)
    current_preview_dir_name = preview_dir_name
    current_render_dir_name = render_dir_name

    # Recalculate full paths based on CLI args for this run
    current_render_dir_path = os.path.join(current_static_dir, current_render_dir_name)
    current_preview_dir_path = os.path.join(current_static_dir, current_preview_dir_name)
    current_assets_dir_path = os.path.join(current_static_dir, "assets") # Assuming assets is always 'assets'

    # Update the module-level variables used by handlers (this is a bit awkward)
    # A class-based approach might encapsulate this better later
    global PART_LIBRARY_DIR, STATIC_DIR, PART_PREVIEW_DIR_NAME, RENDER_DIR_NAME
    global RENDER_DIR_PATH, PART_PREVIEW_DIR_PATH, ASSETS_DIR_PATH
    PART_LIBRARY_DIR = current_part_library_dir
    STATIC_DIR = current_static_dir
    PART_PREVIEW_DIR_NAME = current_preview_dir_name
    RENDER_DIR_NAME = current_render_dir_name
    RENDER_DIR_PATH = current_render_dir_path
    PART_PREVIEW_DIR_PATH = current_preview_dir_path
    ASSETS_DIR_PATH = current_assets_dir_path


    log.info(f"Using Part Library: {PART_LIBRARY_DIR}"); log.info(f"Using Static Dir: {STATIC_DIR}")
    log.info(f"Using Preview Dir: {PART_PREVIEW_DIR_PATH} (mounted at /{PART_PREVIEW_DIR_NAME})")
    log.info(f"Using Render Dir: {RENDER_DIR_PATH} (mounted at /{RENDER_DIR_NAME})")

    # Ensure directories exist (important after paths might have changed)
    os.makedirs(RENDER_DIR_PATH, exist_ok=True); os.makedirs(PART_PREVIEW_DIR_PATH, exist_ok=True)

    # --- Mode Execution ---
    if mode == "stdio":
        # Initial scan needed even for stdio if library tools are used
        log.info("Performing initial scan of part library for stdio mode...");
        try: handle_scan_part_library({"request_id": "startup-scan", "arguments": {}})
        except Exception as e: log.error(f"Initial part library scan failed: {e}", exc_info=True)
        # Run stdio loop
        asyncio.run(run_stdio_mode())
        # raise typer.Exit() # Exit after stdio mode finishes - Typer might handle this?
    elif mode == "sse":
         # --- HTTP Mode Execution ---
        # Configure static files *before* running uvicorn
        configure_static_files(STATIC_DIR, RENDER_DIR_NAME, RENDER_DIR_PATH, PART_PREVIEW_DIR_NAME, PART_PREVIEW_DIR_PATH, ASSETS_DIR_PATH)
        log.info("Performing initial scan of part library...");
        try: handle_scan_part_library({"request_id": "startup-scan", "arguments": {}})
        except Exception as e: log.error(f"Initial part library scan failed: {e}", exc_info=True)
        log.info(f"Starting Uvicorn server on {host}:{port}...");
        # Need to pass the app instance directly if defined inside a function
        uvicorn.run(app, host=host, port=port, reload=reload) # Pass app instance
    else:
         log.error(f"Invalid mode specified: {mode}. Use 'stdio' or 'sse'.")
         raise typer.Exit(code=1)


if __name__ == "__main__":
    # This block runs regardless of whether we are in the venv or not initially.
    # If not in venv, the re-exec happens above.
    # If in venv (or after re-exec), this calls the main app logic function.
    # initialize_and_run_app() # This was incorrect, Typer needs to run the command
    cli() # Run the Typer app