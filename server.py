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

# --- Environment Setup Helpers ---

def _run_command_helper(command: list[str], check: bool = True, log_prefix: str = "Setup", **kwargs) -> subprocess.CompletedProcess:
    """
    Helper to run a command, capture output, and raise exceptions on failure.
    Uses logging.
    """
    # Ensure basic logging is configured if needed
    if not logging.getLogger().hasHandlers():
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)

    log_msg_prefix = f"[{log_prefix}]" # Add prefix for clarity
    logging.info(f"{log_msg_prefix} Running command: {' '.join(command)}")
    try:
        process = subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            **kwargs
        )
        # Log stdout/stderr only if debug level is enabled or if there was an error (handled below)
        logging.debug(f"{log_msg_prefix} Command stdout:\n{process.stdout}")
        if process.stderr:
            logging.debug(f"{log_msg_prefix} Command stderr:\n{process.stderr}")
        return process
    except FileNotFoundError as e:
        logging.error(f"{log_msg_prefix} Error: Command '{command[0]}' not found. Is it installed and in PATH?")
        raise e # Re-raise for handling
    except subprocess.CalledProcessError as e:
        logging.error(f"{log_msg_prefix} Error running command: {' '.join(command)}")
        logging.error(f"{log_msg_prefix} Exit code: {e.returncode}")
        if e.stdout: logging.error(f"{log_msg_prefix} Stdout:\n" + e.stdout)
        if e.stderr: logging.error(f"{log_msg_prefix} Stderr:\n" + e.stderr)
        raise e # Re-raise for handling
    except Exception as e:
        logging.error(f"{log_msg_prefix} An unexpected error occurred running command: {e}")
        raise e # Re-raise for handling

def prepare_workspace_env(workspace_path: str) -> str: # Renamed function
    """
    Ensures a virtual environment exists in the workspace, creates it if not,
    and installs dependencies from workspace/requirements.txt using uv.

    Args:
        workspace_path: The absolute path to the workspace directory.

    Returns:
        The absolute path to the Python executable within the workspace venv.

    Raises:
        FileNotFoundError: If 'uv' is not found or workspace_path is invalid.
        RuntimeError: If environment setup fails.
    """
    log_prefix = f"WorkspaceEnv({os.path.basename(workspace_path)})"
    logging.info(f"[{log_prefix}] Ensuring environment for workspace: {workspace_path}")

    if not os.path.isdir(workspace_path):
        msg = f"Workspace path does not exist or is not a directory: {workspace_path}"
        logging.error(f"[{log_prefix}] {msg}")
        raise FileNotFoundError(msg)

    # 1. Check for uv (only needs to be done once, but check here for safety)
    if not shutil.which("uv"):
         msg = "Error: Python 'uv' is not installed or not in PATH. Please install it: https://github.com/astral-sh/uv"
         logging.error(f"[{log_prefix}] {msg}")
         raise FileNotFoundError(msg)

    # 2. Define paths within the workspace
    venv_dir = os.path.join(workspace_path, ".venv")
    requirements_file = os.path.join(workspace_path, "requirements.txt")
    bin_subdir = "Scripts" if sys.platform == "win32" else "bin"
    python_exe = os.path.join(venv_dir, bin_subdir, "python.exe" if sys.platform == "win32" else "python")

    try:
        # 4. Check if venv exists, create using `uv venv` if not
        if not os.path.isdir(venv_dir) or not os.path.exists(python_exe):
            logging.info(f"[{log_prefix}] Creating virtual environment in {venv_dir} using Python {PYTHON_VERSION}...")
            # Use the helper, passing the log prefix
            _run_command_helper(["uv", "venv", venv_dir, "-p", PYTHON_VERSION], log_prefix=log_prefix)
            logging.info(f"[{log_prefix}] Virtual environment created.")
        else:
            logging.info(f"[{log_prefix}] Virtual environment already exists: {venv_dir}")

        # Ensure the Python executable exists after potential creation
        if not os.path.exists(python_exe):
             msg = f"Python executable still not found at {python_exe} after check/creation."
             logging.error(f"[{log_prefix}] {msg}")
             raise RuntimeError(msg)

        # 5. Install base 'cadquery' dependency FIRST
        logging.info(f"[{log_prefix}] Ensuring base 'cadquery' package is installed in {venv_dir}...")
        _run_command_helper(["uv", "pip", "install", "cadquery", "--python", python_exe], log_prefix=log_prefix)
        logging.info(f"[{log_prefix}] Base 'cadquery' installed/verified.")

        # 6. Check if workspace requirements.txt exists and if it has changed
        install_reqs = False
        current_mtime: Optional[float] = None
        if os.path.isfile(requirements_file):
            try:
                current_mtime = os.path.getmtime(requirements_file)
                cached_mtime = workspace_reqs_mtime_cache.get(workspace_path)
                if current_mtime != cached_mtime:
                    install_reqs = True
                    logging.info(f"[{log_prefix}] requirements.txt changed (Current: {current_mtime}, Cached: {cached_mtime}). Will install.")
                else:
                    logging.info(f"[{log_prefix}] requirements.txt unchanged (mtime: {current_mtime}). Skipping install.")
            except OSError as mtime_err:
                logging.warning(f"[{log_prefix}] Could not get mtime for {requirements_file}: {mtime_err}. Assuming install needed.")
                install_reqs = True
        else:
            # If file doesn't exist, but we had a cache entry, clear it
            if workspace_path in workspace_reqs_mtime_cache:
                 del workspace_reqs_mtime_cache[workspace_path]
            logging.info(f"[{log_prefix}] No requirements.txt found in workspace. Skipping additional dependencies.")

        if install_reqs:
            logging.info(f"[{log_prefix}] Installing/syncing additional dependencies from {requirements_file} into {venv_dir}...")
            try:
                # Use the specific python from the venv via --python flag
                _run_command_helper(["uv", "pip", "install", "-r", requirements_file, "--python", python_exe], log_prefix=log_prefix)
                # Update cache only on successful install
                workspace_reqs_mtime_cache[workspace_path] = current_mtime
                logging.info(f"[{log_prefix}] Additional dependencies installed/synced. Updated mtime cache to {current_mtime}.")
            except Exception as install_err:
                 # If install fails, remove from cache to force retry next time
                 if workspace_path in workspace_reqs_mtime_cache:
                     del workspace_reqs_mtime_cache[workspace_path]
                 logging.error(f"[{log_prefix}] Failed to install dependencies from {requirements_file}. Error: {install_err}")
                 # Re-raise the error to signal failure
                 raise RuntimeError(f"Failed to install dependencies from {requirements_file}") from install_err

        # 7. Return path to venv python executable
        logging.info(f"[{log_prefix}] Environment preparation complete.")
        return python_exe

    except (FileNotFoundError, subprocess.CalledProcessError, Exception) as e:
        logging.error(f"[{log_prefix}] Failed to set up workspace environment: {e}")
        # Re-raise as RuntimeError to indicate a setup failure
        raise RuntimeError(f"Failed to set up workspace environment for {workspace_path}: {e}") from e

# Define script directory early for use in finding the runner
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Auto Environment Setup & Re-execution (REMOVED) ---
# The server now runs in its own environment (system or a base venv).
# Workspace environments are managed separately per request/workspace.

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
    _substitute_parameters,
    get_shape_properties, # Added for validation tool
    get_shape_description # Added for description tool
)
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse
import cadquery as cq
from cadquery import cqgi # Needed for type hints

# --- Global State and Paths (Defaults & Placeholders) ---
shape_results: Dict[str, cqgi.BuildResult] = {}
part_index: Dict[str, Dict[str, Any]] = {}

# Default names/relative paths (can be overridden by CLI)
DEFAULT_PART_LIBRARY_DIR = "part_library"
DEFAULT_OUTPUT_DIR_NAME = "shapes"
DEFAULT_RENDER_DIR_NAME = "renders" # Subdir within output dir
DEFAULT_PART_PREVIEW_DIR_NAME = "part_previews" # Subdir within output dir

# These will be dynamically set in main() based on CLI args or defaults
PART_LIBRARY_DIR: str = "" # Absolute path to part library (input)
OUTPUT_DIR_PATH: str = "" # Absolute path to the main output dir
RENDER_DIR_PATH: str = "" # Absolute path to the render subdir
PART_PREVIEW_DIR_PATH: str = "" # Absolute path to the preview subdir
STATIC_DIR: Optional[str] = None # Absolute path to static dir (optional)
ASSETS_DIR_PATH: Optional[str] = None # Absolute path to assets dir (optional)

sse_connections: List[asyncio.Queue] = []
workspace_reqs_mtime_cache: Dict[str, float] = {} # Cache for requirements mtime

# --- Logging Setup (Application Level) ---
# Configure logging now that we are definitely in the venv
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
    force=True # Force re-configuration over potential setup logging
)
log = logging.getLogger(__name__) # Get logger after config


# --- FastAPI App and Route Definitions ---
# Define app instance globally FIRST
app = FastAPI()

# Define static file configuration function
def configure_static_files(app_instance: FastAPI, static_dir: str, render_dir_name: str, render_dir_path: str, preview_dir_name: str, preview_dir_path: str, assets_dir_path: str) -> None:
    """
    Configures FastAPI static file serving for frontend, renders, and previews.
    NOTE: This function modifies the passed 'app_instance'.
    """
    log.info(f"Configuring static files. Base static dir: {static_dir}")

    # Mount renders, previews, and assets if they exist
    if os.path.isdir(render_dir_path):
        app_instance.mount(f"/{render_dir_name}", StaticFiles(directory=render_dir_path), name=render_dir_name)
        log.info(f"Mounted render directory '{render_dir_path}' at '/{render_dir_name}'")
    else: log.warning(f"Render directory '{render_dir_path}' not found, skipping mount.")

    if os.path.isdir(preview_dir_path):
        app_instance.mount(f"/{preview_dir_name}", StaticFiles(directory=preview_dir_path), name=preview_dir_name)
        log.info(f"Mounted preview directory '{preview_dir_path}' at '/{preview_dir_name}'")
    else: log.warning(f"Preview directory '{preview_dir_path}' not found, skipping mount.")

    # Catch-all for SPA routing and serving other static files
    # This needs to be defined *after* specific mounts
    @app_instance.get("/{full_path:path}", response_model=None) # Disable response model generation
    async def serve_static_or_index(request: Request, full_path: str) -> Union[FileResponse, Response, HTTPException]:
        """Serves static files or index.html for SPA routing."""
        log.debug(f"Catch-all route received request for full_path: '{full_path}'") # DEBUG LOG
        # Prevent serving files outside the static directory
        if ".." in full_path:
            log.warning(f"Attempted directory traversal: '{full_path}'") # DEBUG LOG
            return HTTPException(status_code=404, detail="Not Found")

        file_path = os.path.join(static_dir, full_path)
        log.debug(f"Checking for file at: '{file_path}'") # DEBUG LOG

        # If the exact file exists, serve it
        if os.path.isfile(file_path):
            log.debug(f"Serving existing file: '{file_path}'") # DEBUG LOG
            return FileResponse(file_path)

        # If the file doesn't exist, check if it was a request for the root path
        if full_path == "":
            log.debug("Request is for root path, but file not found directly. Checking for index.html") # DEBUG LOG
            root_index = os.path.join(static_dir, "index.html")
            if os.path.isfile(root_index):
                log.debug(f"Serving index.html from: '{root_index}'") # DEBUG LOG
                return FileResponse(root_index)
            else:
                # Root path requested, but neither file_path nor index.html exists
                log.warning(f"Root path requested but index.html not found at '{root_index}'") # DEBUG LOG
                return HTTPException(status_code=404, detail="Index not found")
        else:
            # File doesn't exist and it wasn't the root path, raise 404
            log.debug(f"Path '{full_path}' not found as file, raising 404.") # DEBUG LOG
            raise HTTPException(status_code=404, detail="Not Found")

# Static file configuration happens inside main() if static_dir is provided

# Define other routes
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
    asyncio.create_task(_process_and_push(request_body)) # Uses helper defined below
    return {"status": "processing", "request_id": request_id}


# --- Core Application Logic Functions ---
# (SSE Helper, Tool Processing, Handlers, Stdio Mode)
# These functions use the globally defined app, state, paths

async def push_sse_message(message_data: dict) -> None:
    """Pushes a message dictionary to all connected SSE clients."""
    if not message_data: return
    log.info(f"Pushing message to {len(sse_connections)} SSE client(s): {json.dumps(message_data)}")
    for queue in sse_connections:
        try: await queue.put(message_data)
        except Exception as e: log.error(f"Failed to push message to a queue: {e}")

async def _process_and_push(request: dict) -> None:
    """Helper coroutine to process a tool request and push the result via SSE."""
    message_to_push = process_tool_request(request)
    await push_sse_message(message_to_push)

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
            "launch_cq_editor": handle_launch_cq_editor, # Added CQ-Editor launcher
            "get_shape_properties": handle_get_shape_properties, # Added validation tool
            "get_shape_description": handle_get_shape_description, # Added description tool
            "save_workspace_module": handle_save_workspace_module, # Added module saving tool
            "install_workspace_package": handle_install_workspace_package, # Added package install tool
            "save_workspace_module": handle_save_workspace_module, # Added module saving tool
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
    Ensures workspace environment exists and executes the script
    within that environment using a subprocess runner.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling execute_cadquery_script request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        workspace_path_arg = args.get("workspace_path")
        script_content = args.get("script")
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

        if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")
        if not script_content: raise ValueError("Missing 'script' argument.")

        workspace_path = os.path.abspath(workspace_path_arg)
        log.info(f"Target workspace: {workspace_path}")
        log.info(f"Script content received (first 100 chars): {script_content[:100]}...")
        log.info(f"Processing {len(parameter_sets)} parameter set(s).")

        # Ensure the workspace environment is ready
        workspace_python_exe = prepare_workspace_env(workspace_path) # Updated call site

        # Path to the script runner helper (relative to this server file)
        script_runner_path = os.path.join(_SCRIPT_DIR, "src", "mcp_cadquery_server", "script_runner.py")
        if not os.path.exists(script_runner_path):
             raise RuntimeError(f"Script runner not found at {script_runner_path}")

        results_summary = []

        for i, params in enumerate(parameter_sets):
            result_id = f"{request_id}_{i}"
            log_prefix = f"Exec({os.path.basename(workspace_path)}/{result_id})"
            log.info(f"[{log_prefix}] Preparing execution for parameter set {i} with params: {params}")

            try:
                # Prepare arguments for the subprocess runner
                # Pass script content, params, workspace, and result_id via stdin JSON
                runner_input_data = json.dumps({
                    "workspace_path": workspace_path,
                    "script_content": script_content,
                    "parameters": params,
                    "result_id": result_id # Pass the unique result ID
                })

                # Run the script runner using the workspace's python
                cmd = [workspace_python_exe, script_runner_path]
                log.info(f"[{log_prefix}] Running script runner: {' '.join(cmd)}")

                process = subprocess.run(
                    cmd,
                    input=runner_input_data,
                    capture_output=True,
                    text=True,
                    check=False, # Don't raise automatically, check return code manually
                    encoding='utf-8',
                    cwd=workspace_path # Set CWD to the workspace path!
                )

                log.debug(f"[{log_prefix}] Runner stdout:\n{process.stdout}")
                if process.stderr:
                     log.warning(f"[{log_prefix}] Runner stderr:\n{process.stderr}") # Log stderr as warning

                if process.returncode != 0:
                    raise RuntimeError(f"Script runner failed with exit code {process.returncode}. Stderr: {process.stderr}")

                # Parse the JSON result from the runner's stdout
                runner_result = json.loads(process.stdout)

                # Store the build result (assuming runner_result structure matches BuildResult serialization)
                # TODO: Define the exact structure returned by script_runner.py
                # For now, assume it returns a dict with 'success', 'results', 'exception_str'
                success = runner_result.get("success", False)
                shapes_data = runner_result.get("results", []) # Placeholder for shape data
                exception_str = runner_result.get("exception_str")

                # Store the dictionary returned by the runner directly.
                # This dict now contains 'success', 'exception_str', and 'results'
                # where 'results' is a list of dicts including 'intermediate_path'.
                shape_results[result_id] = runner_result # Store the parsed JSON dict

                # Update summary based on the runner's result
                results_summary.append({
                    "result_id": result_id,
                    "success": runner_result.get("success", False),
                    "shapes_count": len(runner_result.get("results", [])),
                    "error": runner_result.get("exception_str")
                })
                log.info(f"[{log_prefix}] Stored execution result for set {i}. Success: {runner_result.get('success', False)}")

            except Exception as exec_err:
                # This catches errors in running the subprocess or parsing its JSON output
                log.error(f"[{log_prefix}] Subprocess execution/processing failed for parameter set {i}: {exec_err}", exc_info=True)
                # Ensure an entry is added to results_summary indicating failure
                results_summary.append({
                    "result_id": result_id,
                    "success": False,
                    "shapes_count": 0,
                    "error": f"Handler error during execution: {exec_err}"
                })
                # Clean up potentially incomplete result from shape_results if it exists
                if result_id in shape_results:
                    del shape_results[result_id]


        total_sets = len(parameter_sets)
        successful_sets = sum(1 for r in results_summary if r["success"])
        message = f"Script execution processed for {total_sets} parameter set(s). Successful: {successful_sets}, Failed: {total_sets - successful_sets}."
        return {"success": True, "message": message, "results": results_summary}

    except Exception as e: error_msg = f"Error during script execution handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_export_shape(request: dict) -> dict:
    """
    Handles the 'export_shape' tool request.
    Imports shape from intermediate file and exports to target format/location.
    Resolves relative target paths based on the workspace.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        workspace_path_arg = args.get("workspace_path") # Expect workspace path
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0)
        filename_arg = args.get("filename") # Target filename/path
        export_format = args.get("format")
        export_options = args.get("options", {})

        if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")
        if not result_id: raise ValueError("Missing 'result_id' argument.")
        if not filename_arg: raise ValueError("Missing 'filename' argument.")
        if not isinstance(shape_index, int) or shape_index < 0: raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(export_options, dict): raise ValueError("'options' argument must be a dictionary.")

        workspace_path = os.path.abspath(workspace_path_arg)
        if not os.path.isdir(workspace_path): raise ValueError(f"Invalid workspace path: {workspace_path}")

        # Retrieve result dict from main process state
        result_dict = shape_results.get(result_id)
        if not result_dict: raise ValueError(f"Result ID '{result_id}' not found.")
        if not result_dict.get("success"): raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")

        results_list = result_dict.get("results", [])
        if not results_list or shape_index >= len(results_list): raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")

        # Get the intermediate path from the stored result data
        shape_data = results_list[shape_index]
        intermediate_path = shape_data.get("intermediate_path")
        if not intermediate_path or not os.path.exists(intermediate_path):
             raise ValueError(f"Intermediate file path not found or file missing for shape {shape_index} in result ID '{result_id}'. Path: {intermediate_path}")

        # Import the shape from the intermediate BREP file
        log.info(f"Importing shape from intermediate file: {intermediate_path}")
        try:
            # Ensure CadQuery is available in the main server env for import/export ops
            shape_to_export = cq.importers.importBrep(intermediate_path)
            log.info(f"Successfully imported shape for export.")
        except Exception as import_err:
            log.error(f"Failed to import BREP file '{intermediate_path}': {import_err}", exc_info=True)
            raise RuntimeError(f"Failed to import intermediate shape file: {import_err}") from import_err

        # Determine final output path, resolving relative paths against the WORKSPACE
        output_path: str
        if os.path.isabs(filename_arg) or os.path.sep in filename_arg or (os.altsep and os.altsep in filename_arg):
            # If filename is absolute or contains a directory path, use it directly (but ensure it's absolute)
            output_path = os.path.abspath(filename_arg)
            log.info(f"Using provided absolute/relative path for export: '{output_path}'")
        else:
            # If filename is just a name, place it inside <workspace_path>/shapes/
            # Define the default output subdir name
            default_output_subdir = "shapes" # TODO: Make this configurable?
            output_path = os.path.join(workspace_path, default_output_subdir, filename_arg)
            log.info(f"Using workspace default output directory. Exporting to: '{output_path}'")

        # Ensure the target directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
             os.makedirs(output_dir, exist_ok=True)

        log.info(f"Attempting to export shape to '{output_path}' (Format: {export_format or 'Infer'}, Options: {export_options})")
        # Call the core export function with the imported shape and calculated absolute path
        export_shape_to_file(shape_to_export, output_path, export_format, export_options)
        log.info(f"Shape successfully exported via export_shape_to_file to '{output_path}'.")
        # Return the final absolute path
        return {"success": True, "message": f"Shape successfully exported to {output_path}.", "filename": output_path}
    except Exception as e: error_msg = f"Error during shape export handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_export_shape_to_svg(request: dict) -> dict:
    """
    Handles the 'export_shape_to_svg' tool request.
    Imports shape from intermediate file and exports SVG to workspace render dir.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape_to_svg request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        workspace_path_arg = args.get("workspace_path") # Expect workspace path
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0)
        filename_arg = args.get("filename") # Optional target filename
        export_options = args.get("options", {})

        if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")
        if not result_id: raise ValueError("Missing 'result_id' argument.")
        if not isinstance(shape_index, int) or shape_index < 0: raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(export_options, dict): raise ValueError("'options' argument must be a dictionary.")

        workspace_path = os.path.abspath(workspace_path_arg)
        if not os.path.isdir(workspace_path): raise ValueError(f"Invalid workspace path: {workspace_path}")

        # Retrieve result dict
        result_dict = shape_results.get(result_id)
        if not result_dict: raise ValueError(f"Result ID '{result_id}' not found.")
        if not result_dict.get("success"): raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")

        results_list = result_dict.get("results", [])
        if not results_list or shape_index >= len(results_list): raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")

        # Get intermediate path
        shape_data = results_list[shape_index]
        intermediate_path = shape_data.get("intermediate_path")
        if not intermediate_path or not os.path.exists(intermediate_path):
             raise ValueError(f"Intermediate file path not found or file missing for shape {shape_index} in result ID '{result_id}'. Path: {intermediate_path}")

        # Import shape
        log.info(f"Importing shape from intermediate file: {intermediate_path}")
        try:
            shape_to_render = cq.importers.importBrep(intermediate_path)
            log.info(f"Successfully imported shape for SVG export.")
        except Exception as import_err:
            log.error(f"Failed to import BREP file '{intermediate_path}': {import_err}", exc_info=True)
            raise RuntimeError(f"Failed to import intermediate shape file: {import_err}") from import_err

        # Determine output path within workspace render dir
        default_svg_name = f"render_{result_id}_{shape_index}_{uuid.uuid4()}.svg"
        base_filename = os.path.basename(filename_arg or default_svg_name)
        if not base_filename.lower().endswith(".svg"): base_filename += ".svg"

        # Use the default render subdir name within the workspace
        render_dir = os.path.join(workspace_path, DEFAULT_RENDER_DIR_NAME)
        os.makedirs(render_dir, exist_ok=True) # Ensure it exists
        output_path = os.path.join(render_dir, base_filename)

        # Generate a relative path for potential URL use (relative to workspace)
        relative_output_path = os.path.join(DEFAULT_RENDER_DIR_NAME, base_filename)

        log.info(f"Exporting SVG to: {output_path}")
        svg_opts = {"width": 400, "height": 300, "marginLeft": 10, "marginTop": 10, "showAxes": False, "projectionDir": (0.5, 0.5, 0.5), "strokeWidth": 0.25, "strokeColor": (0, 0, 0), "hiddenColor": (0, 0, 255, 100), "showHidden": False}
        svg_opts.update(export_options)

        # Call core SVG export function
        export_shape_to_svg_file(shape_to_render, output_path, svg_opts)

        # Return the absolute path and the relative path
        return {"success": True, "message": f"Shape successfully exported to SVG: {output_path}.", "filename": output_path, "relative_path": relative_output_path}
    except Exception as e: error_msg = f"Error during SVG export handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_scan_part_library(request: dict) -> dict:
    """
    Handles the 'scan_part_library' tool request for a specific workspace.
    Scans <workspace_path>/part_library, executes scripts in-process,
    parses metadata, generates previews in <workspace_path>/shapes/part_previews,
    and updates a potentially global part index.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling scan_part_library request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        workspace_path_arg = args.get("workspace_path")
        if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")

        workspace_path = os.path.abspath(workspace_path_arg)
        if not os.path.isdir(workspace_path): raise ValueError(f"Invalid workspace path: {workspace_path}")

        # Define paths relative to the workspace
        library_path = os.path.join(workspace_path, DEFAULT_PART_LIBRARY_DIR)
        preview_dir_path = os.path.join(workspace_path, DEFAULT_OUTPUT_DIR_NAME, DEFAULT_PART_PREVIEW_DIR_NAME)
        preview_dir_url_base = f"/{DEFAULT_PART_PREVIEW_DIR_NAME}" # Relative URL base

        log.info(f"Scanning part library in: {library_path}")
        log.info(f"Saving previews to: {preview_dir_path}")

        # Ensure directories exist
        os.makedirs(library_path, exist_ok=True)
        os.makedirs(preview_dir_path, exist_ok=True)

        scanned_count, indexed_count, updated_count, cached_count, error_count = 0, 0, 0, 0, 0
        found_parts = set()
        default_svg_opts = {"width": 150, "height": 100, "showAxes": False}

        # Add workspace library and modules path to sys.path temporarily for this scan
        modules_dir = os.path.join(workspace_path, "modules")
        original_sys_path = list(sys.path)
        if library_path not in sys.path: sys.path.insert(0, library_path)
        if os.path.isdir(modules_dir) and modules_dir not in sys.path: sys.path.insert(0, modules_dir)

        try: # Ensure sys.path is restored
            for filename in os.listdir(library_path):
                if filename.endswith(".py") and not filename.startswith("_"):
                    scanned_count += 1
                    part_name = os.path.splitext(filename)[0]
                    # Use a workspace-prefixed key for the global index? Or make index workspace-specific?
                    # For now, use simple part_name, assuming names are unique across workspaces or last scan wins.
                    # A better approach might be needed for multi-workspace servers.
                    index_key = part_name # Potentially add workspace prefix later: f"{os.path.basename(workspace_path)}_{part_name}"
                    found_parts.add(index_key)
                    file_path = os.path.join(library_path, filename)
                    relative_script_path = os.path.join(DEFAULT_PART_LIBRARY_DIR, filename) # Store relative path
                    error_msg = None

                    try:
                        current_mtime = os.path.getmtime(file_path)
                        # Check cache using index_key
                        cached_data = part_index.get(index_key)
                        if cached_data and cached_data.get('mtime') == current_mtime and cached_data.get('workspace') == workspace_path:
                            log.debug(f"Using cached data for part: {filename} in workspace {os.path.basename(workspace_path)}")
                            cached_count += 1
                            continue

                        log.info(f"Processing part: {filename} in workspace {os.path.basename(workspace_path)} (new or modified)")
                        with open(file_path, 'r', encoding='utf-8') as f: script_content = f.read()

                        # Metadata Parsing (in-process)
                        tree = ast.parse(script_content); docstring = ast.get_docstring(tree)
                        metadata = parse_docstring_metadata(docstring); metadata['filename'] = filename

                        # Script Execution (in-process for scanning)
                        # NOTE: This runs in the main server environment, NOT the workspace venv.
                        # It relies on sys.path modification above for imports within the library/modules dir.
                        # It will NOT have access to packages installed only in the workspace venv.
                        log.debug(f"Executing script {filename} in-process for scanning...")
                        model = cqgi.parse(script_content)
                        build_result = model.build()
                        log.debug(f"In-process execution complete. Success: {build_result.success}")

                        if build_result.success and build_result.results:
                            shape_to_preview = build_result.results[0].shape
                            preview_filename = f"{part_name}.svg"
                            preview_output_path = os.path.join(preview_dir_path, preview_filename)
                            preview_output_url = f"{preview_dir_url_base}/{preview_filename}"

                            # SVG Export (in-process)
                            export_shape_to_svg_file(shape_to_preview, preview_output_path, default_svg_opts)

                            part_data = {
                                "part_id": part_name, # Original name without prefix
                                "workspace": workspace_path, # Store workspace context
                                "metadata": metadata,
                                "preview_url": preview_output_url, # URL relative to potential static serving
                                "script_path": relative_script_path, # Store path relative to workspace root
                                "mtime": current_mtime
                            }
                            if index_key in part_index: updated_count += 1
                            else: indexed_count += 1
                            part_index[index_key] = part_data # Update global index
                            log.info(f"Successfully indexed/updated part: {part_name} from workspace {os.path.basename(workspace_path)}")
                        elif not build_result.results:
                            log.warning(f"Part script {filename} executed successfully but produced no results. Skipping indexing.")
                            error_count += 1
                        else:
                            error_msg = f"Execution failed: {build_result.exception}"
                            log.warning(f"Part script {filename} failed: {error_msg}")
                            error_count += 1
                    except Exception as e:
                        error_msg = f"Error processing {filename}: {e}"
                        log.error(error_msg, exc_info=True)
                        error_count += 1
                    if error_msg and index_key in part_index:
                        del part_index[index_key]
                        log.info(f"Removed previously indexed part {part_name} from workspace {os.path.basename(workspace_path)} due to error.")
            # End of the inner try block for processing a single file
        # End of the for loop iterating through files
        finally:
            # Restore original sys.path regardless of loop completion or errors within the loop
            sys.path = original_sys_path
            log.debug("Restored original sys.path")
        # This code runs after the inner try...finally completes successfully

        # Remove parts from index associated with *this workspace* that are no longer found
        removed_count = 0
        for index_key in list(part_index.keys()):
            # Check if the part belongs to the current workspace before potentially removing
            if part_index[index_key].get('workspace') == workspace_path and index_key not in found_parts:
                del part_index[index_key]
                removed_count += 1
                log.info(f"Removed part '{index_key}' from index (file deleted from workspace {os.path.basename(workspace_path)}).")

        message = f"Part library scan complete for workspace '{os.path.basename(workspace_path)}'. Scanned: {scanned_count}, Indexed: {indexed_count}, Updated: {updated_count}, Cached: {cached_count}, Removed: {removed_count}, Errors: {error_count}."
        log.info(message)
        # Return counts specific to this scan operation
        return {"success": True, "message": message, "indexed_count": indexed_count, "updated_count": updated_count, "cached_count": cached_count, "removed_count": removed_count, "error_count": error_count}

    # Outer except block for the whole function (aligned with try at line 630)
    except Exception as e:
        error_msg = f"Error during part library scan for workspace {workspace_path_arg}: {e}"
        log.error(error_msg, exc_info=True)
        # Ensure sys.path is restored even if an error occurs before the inner try's finally
        if 'original_sys_path' in locals() and sys.path != original_sys_path:
             sys.path = original_sys_path
             log.warning("Restored original sys.path after error in outer try block.")
        raise Exception(error_msg)

def handle_save_workspace_module(request: dict) -> dict:
    """
    Handles the 'save_workspace_module' tool request.
    Saves Python code content to a specified file within the workspace's 'modules' directory.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling save_workspace_module request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        workspace_path_arg = args.get("workspace_path")
        module_filename = args.get("module_filename")
        module_content = args.get("module_content")

        if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")
        if not module_filename: raise ValueError("Missing 'module_filename' argument.")
        if module_content is None: raise ValueError("Missing 'module_content' argument.") # Allow empty string

        # Basic filename validation
        if not module_filename.endswith(".py"):
             raise ValueError("Invalid module_filename: Must end with '.py'.")
        if os.path.sep in module_filename or (os.altsep and os.altsep in module_filename):
             raise ValueError("Invalid module_filename: Cannot contain path separators.")
        if module_filename == "__init__.py":
             log.warning("Saving to __init__.py in modules directory.") # Allow but warn

        workspace_path = os.path.abspath(workspace_path_arg)
        if not os.path.isdir(workspace_path): raise ValueError(f"Invalid workspace path: {workspace_path}")

        # Define and ensure the modules directory exists
        modules_dir = os.path.join(workspace_path, "modules")
        os.makedirs(modules_dir, exist_ok=True)

        # Construct the full path and write the file
        module_path = os.path.join(modules_dir, module_filename)
        log.info(f"Saving module content to: {module_path}")
        try:
            with open(module_path, 'w', encoding='utf-8') as f:
                f.write(module_content)
            log.info(f"Successfully saved module: {module_filename}")
        except OSError as write_err:
            log.error(f"Failed to write module file '{module_path}': {write_err}", exc_info=True)
            raise RuntimeError(f"Failed to write module file: {write_err}") from write_err

        return {"success": True, "message": f"Module '{module_filename}' saved successfully in workspace '{os.path.basename(workspace_path)}'."}

    except Exception as e:
        error_msg = f"Error saving workspace module: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

def handle_install_workspace_package(request: dict) -> dict:
    """
    Handles the 'install_workspace_package' tool request.
    Installs a Python package into the specified workspace's virtual environment using uv.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling install_workspace_package request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        workspace_path_arg = args.get("workspace_path")
        package_name = args.get("package_name") # e.g., "numpy", "requests", "git+https://..."

        if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")
        if not package_name: raise ValueError("Missing 'package_name' argument.")

        workspace_path = os.path.abspath(workspace_path_arg)
        if not os.path.isdir(workspace_path): raise ValueError(f"Invalid workspace path: {workspace_path}")

        log_prefix = f"InstallPkg({os.path.basename(workspace_path)})"
        log.info(f"[{log_prefix}] Attempting to install package '{package_name}' into workspace '{workspace_path}'")

        # Ensure the environment exists and get the python executable
        workspace_python_exe = prepare_workspace_env(workspace_path) # Updated call site

        # Install the package using uv pip install
        # TODO: Add whitelisting check here if required for security
        install_command = ["uv", "pip", "install", package_name, "--python", workspace_python_exe]
        try:
            _run_command_helper(install_command, log_prefix=log_prefix)
            log.info(f"[{log_prefix}] Successfully installed/updated package '{package_name}'.")

            # TODO: Add logic to update workspace requirements.txt
            # - Read existing requirements
            # - Add/update the package name (handle versions?)
            # - Write back to requirements.txt

            return {"success": True, "message": f"Package '{package_name}' installed successfully in workspace '{os.path.basename(workspace_path)}'."}
        except Exception as install_err:
            log.error(f"[{log_prefix}] Failed to install package '{package_name}': {install_err}", exc_info=True)
            raise RuntimeError(f"Failed to install package '{package_name}': {install_err}") from install_err

    except Exception as e:
        error_msg = f"Error installing workspace package: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

def handle_search_parts(request: dict) -> dict:
    """
    Handles the 'search_parts' tool request.
    Searches the in-memory part index based on keywords.
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

def handle_launch_cq_editor(request: dict) -> dict:
    """
    Handles the 'launch_cq_editor' tool request.
    Launches the CQ-Editor application as a separate process.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling launch_cq_editor request (ID: {request_id})")
    try:
        # Use Popen to launch without waiting for it to exit
        # Ensure CQ-editor is in the PATH (should be if installed in the venv)
        log.info("Attempting to launch CQ-Editor...")
        process = subprocess.Popen(["CQ-editor"]) # Use correct case
        log.info(f"Launched CQ-Editor process with PID: {process.pid}")
        return {"success": True, "message": f"CQ-Editor launched successfully (PID: {process.pid})."}
    except FileNotFoundError: # This error might still occur if PATH is not set up correctly for the subprocess
        error_msg = "Error: 'CQ-editor' command not found. Is CQ-Editor installed in the virtual environment and is the venv bin directory in the PATH?"
        log.error(error_msg)
        raise Exception(error_msg) # Raise to be caught by the main processor
    except Exception as e:
        error_msg = f"Error launching CQ-Editor: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg) # Raise to be caught by the main processor

def handle_get_shape_properties(request: dict) -> dict:
    """
    Handles the 'get_shape_properties' tool request.
    Imports shape from intermediate file and calculates its properties.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling get_shape_properties request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        # workspace_path_arg = args.get("workspace_path") # Workspace path needed for context if resolving paths, but not strictly needed here as intermediate path is absolute
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0)

        # if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.") # Optional for now
        if not result_id: raise ValueError("Missing 'result_id' argument.")
        if not isinstance(shape_index, int) or shape_index < 0: raise ValueError("'shape_index' must be a non-negative integer.")

        # Retrieve result dict
        result_dict = shape_results.get(result_id)
        if not result_dict: raise ValueError(f"Result ID '{result_id}' not found.")
        if not result_dict.get("success"): raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")

        results_list = result_dict.get("results", [])
        if not results_list or shape_index >= len(results_list): raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")

        # Get intermediate path
        shape_data = results_list[shape_index]
        intermediate_path = shape_data.get("intermediate_path")
        if not intermediate_path or not os.path.exists(intermediate_path):
             raise ValueError(f"Intermediate file path not found or file missing for shape {shape_index} in result ID '{result_id}'. Path: {intermediate_path}")

        # Import shape
        log.info(f"Importing shape from intermediate file: {intermediate_path}")
        try:
            shape_to_analyze = cq.importers.importBrep(intermediate_path)
            log.info(f"Successfully imported shape for property analysis.")
        except Exception as import_err:
            log.error(f"Failed to import BREP file '{intermediate_path}': {import_err}", exc_info=True)
            raise RuntimeError(f"Failed to import intermediate shape file: {import_err}") from import_err

        # Call the core function
        properties = get_shape_properties(shape_to_analyze)

        return {"success": True, "message": f"Properties calculated for shape {shape_index} from result {result_id}.", "properties": properties}

    except Exception as e:
        error_msg = f"Error during shape property calculation handling: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

def handle_get_shape_description(request: dict) -> dict:
    """
    Handles the 'get_shape_description' tool request.
    Imports shape from intermediate file and generates its description.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling get_shape_description request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        # workspace_path_arg = args.get("workspace_path") # Optional for now
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0)

        # if not workspace_path_arg: raise ValueError("Missing 'workspace_path' argument.")
        if not result_id: raise ValueError("Missing 'result_id' argument.")
        if not isinstance(shape_index, int) or shape_index < 0: raise ValueError("'shape_index' must be a non-negative integer.")

        # Retrieve result dict
        result_dict = shape_results.get(result_id)
        if not result_dict: raise ValueError(f"Result ID '{result_id}' not found.")
        if not result_dict.get("success"): raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")

        results_list = result_dict.get("results", [])
        if not results_list or shape_index >= len(results_list): raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")

        # Get intermediate path
        shape_data = results_list[shape_index]
        intermediate_path = shape_data.get("intermediate_path")
        if not intermediate_path or not os.path.exists(intermediate_path):
             raise ValueError(f"Intermediate file path not found or file missing for shape {shape_index} in result ID '{result_id}'. Path: {intermediate_path}")

        # Import shape
        log.info(f"Importing shape from intermediate file: {intermediate_path}")
        try:
            shape_to_describe = cq.importers.importBrep(intermediate_path)
            log.info(f"Successfully imported shape for description generation.")
        except Exception as import_err:
            log.error(f"Failed to import BREP file '{intermediate_path}': {import_err}", exc_info=True)
            raise RuntimeError(f"Failed to import intermediate shape file: {import_err}") from import_err

        # Call the core function
        description = get_shape_description(shape_to_describe)

        return {"success": True, "message": f"Description generated for shape {shape_index} from result {result_id}.", "description": description}

    except Exception as e:
        error_msg = f"Error during shape description generation handling: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

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


# --- Typer CLI App Definition ---
# Define the Typer app globally
cli = typer.Typer()

# Define the main command using the global cli
@cli.command()
def main(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    # Removed output_dir, part_lib_dir, render_dir_name, preview_dir_name as they are workspace-relative now
    static_dir_arg: Optional[str] = typer.Option(
        None, # Default to None
        "--static-dir", "-s",
        help="Path to the static directory for serving a frontend (e.g., frontend/dist). If not provided, frontend serving is disabled.",
        envvar="MCP_STATIC_DIR"
    ),
    stdio: bool = typer.Option(False, "--stdio", help="Run in stdio mode instead of HTTP server.")
):
    """Main function to start the MCP CadQuery server."""
    # Use global keyword to modify global path variables for static serving
    global STATIC_DIR, ASSETS_DIR_PATH
    # Note: OUTPUT_DIR_PATH, RENDER_DIR_PATH etc. are no longer global server configs

    # --- Determine Static/Assets Path (if provided) ---
    serve_frontend = False
    if static_dir_arg:
        STATIC_DIR = os.path.abspath(static_dir_arg)
        # Assume assets is always a subdir named 'assets' within the static dir
        ASSETS_DIR_PATH = os.path.join(STATIC_DIR, "assets")
        serve_frontend = True
        log.info(f"Static directory for frontend enabled: {STATIC_DIR}")
        # Ensure static/assets dirs exist if specified
        os.makedirs(STATIC_DIR, exist_ok=True)
        if ASSETS_DIR_PATH: os.makedirs(ASSETS_DIR_PATH, exist_ok=True)
        log.info(f"Ensured static directory exists: {STATIC_DIR}")
    else:
        STATIC_DIR = None # Explicitly set to None if not provided
        ASSETS_DIR_PATH = None
        log.info("No static directory provided, frontend serving disabled.")


    # --- Configure Static Files (Only if serving frontend) ---
    if serve_frontend and STATIC_DIR and ASSETS_DIR_PATH:
        # Configure static files - Render/Preview paths are now workspace-specific,
        # so we pass the *default* names for mounting points relative to static root.
        # The actual files will live inside workspaces, but the frontend might expect
        # URLs like /renders/file.svg or /part_previews/file.svg
        # This assumes the frontend knows how to construct the full URL or that
        # another mechanism provides the workspace context for file serving.
        # For simplicity, we mount the default names. A more complex setup might
        # involve dynamic routing based on workspace.
        log.warning("Static file serving enabled, but render/preview paths are now workspace-relative.")
        log.warning(f"Mounting default '/{DEFAULT_RENDER_DIR_NAME}' and '/{DEFAULT_PART_PREVIEW_DIR_NAME}' - actual files must be served separately or via workspace-aware routing.")
        # We still need *some* path for the function signature, even if not used directly
        # Let's use placeholder paths based on the current dir, they won't be used for file access here.
        placeholder_render_path = os.path.join(os.getcwd(), DEFAULT_RENDER_DIR_NAME)
        placeholder_preview_path = os.path.join(os.getcwd(), DEFAULT_PART_PREVIEW_DIR_NAME)
        configure_static_files(app, STATIC_DIR, DEFAULT_RENDER_DIR_NAME, placeholder_render_path, DEFAULT_PART_PREVIEW_DIR_NAME, placeholder_preview_path, ASSETS_DIR_PATH)
        log.info("Static file serving configured (using default mount points for renders/previews).")
    else:
        log.info("Skipping static file configuration.")


    # --- Start Server ---
    if stdio:
        log.info("Starting server in stdio mode.")
        # Run the stdio mode handler directly
        asyncio.run(run_stdio_mode())
    else:
        log.info(f"Starting HTTP server on {host}:{port}")
        # Run the FastAPI server using uvicorn
        # Note: Reload is not explicitly handled here, add if needed via uvicorn args
        uvicorn.run(app, host=host, port=port)


    # --- Configure Static Files (Only if serving frontend) ---
    if serve_frontend and STATIC_DIR and ASSETS_DIR_PATH:
        # Configure static files - Render/Preview paths are now workspace-specific,
        # so we pass the *default* names for mounting points relative to static root.
        # The actual files will live inside workspaces, but the frontend might expect
        # URLs like /renders/file.svg or /part_previews/file.svg
        # This assumes the frontend knows how to construct the full URL or that
        # another mechanism provides the workspace context for file serving.
        # For simplicity, we mount the default names. A more complex setup might
        # involve dynamic routing based on workspace.
        log.warning("Static file serving enabled, but render/preview paths are now workspace-relative.")
        log.warning(f"Mounting default '/{DEFAULT_RENDER_DIR_NAME}' and '/{DEFAULT_PART_PREVIEW_DIR_NAME}' - actual files must be served separately or via workspace-aware routing.")
        # We still need *some* path for the function signature, even if not used directly
        # Let's use placeholder paths based on the current dir, they won't be used for file access here.
        placeholder_render_path = os.path.join(os.getcwd(), DEFAULT_RENDER_DIR_NAME)
        placeholder_preview_path = os.path.join(os.getcwd(), DEFAULT_PART_PREVIEW_DIR_NAME)
        configure_static_files(app, STATIC_DIR, DEFAULT_RENDER_DIR_NAME, placeholder_render_path, DEFAULT_PART_PREVIEW_DIR_NAME, placeholder_preview_path, ASSETS_DIR_PATH)
        log.info("Static file serving configured (using default mount points for renders/previews).")
    else:
        log.info("Skipping static file configuration.")


    # --- Start Server ---
    if stdio:
        log.info("Starting server in stdio mode.")
        # Run the stdio mode handler directly
        asyncio.run(run_stdio_mode())
    else:
        log.info(f"Starting HTTP server on {host}:{port}")
        # Run the FastAPI server using uvicorn
        # Note: Reload is not explicitly handled here, add if needed via uvicorn args
        uvicorn.run(app, host=host, port=port)

# --- Entry Point ---
if __name__ == "__main__":
    # This block runs regardless of whether we are in the venv or not initially.
    # If not in venv, the re-exec happens above.
    # If in venv (or after re-exec), this runs the Typer CLI.
    cli()
