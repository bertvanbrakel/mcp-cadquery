import sys
import json
import logging
import traceback
import uuid
import os
import asyncio
import ast
import re
# Removed subprocess import
from typing import Dict, Any, List, Optional, Union
# Removed importlib.resources

import typer
import uvicorn
import cadquery as cq
from cadquery import cqgi
from cadquery import exporters
import cadquery.vis as vis
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse
import mimetypes

# --- Typer CLI App ---
cli = typer.Typer()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
log = logging.getLogger(__name__)

# --- FastAPI App ---
app = FastAPI()

# --- State Management ---
shape_results: Dict[str, cqgi.BuildResult] = {}
part_index: Dict[str, Dict[str, Any]] = {}

# --- Global Path Variables (Defaults, potentially overridden by CLI) ---
# Define simple relative paths or rely on CWD
PART_LIBRARY_DIR = "part_library"
RENDER_DIR_NAME = "renders"
PART_PREVIEW_DIR_NAME = "part_previews"
# Calculate static dir relative to this script's location
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "frontend/dist"))

# Calculate full paths based on defaults initially
RENDER_DIR_PATH = os.path.join(STATIC_DIR, RENDER_DIR_NAME)
PART_PREVIEW_DIR_PATH = os.path.join(STATIC_DIR, PART_PREVIEW_DIR_NAME)
ASSETS_DIR_PATH = os.path.join(STATIC_DIR, "assets")


# --- SSE Connection Management ---
sse_connections: List[asyncio.Queue] = []

async def push_sse_message(message_data: dict) -> None:
    """Pushes a message dictionary to all connected SSE clients."""
    if not message_data: return
    log.info(f"Pushing message to {len(sse_connections)} SSE client(s): {json.dumps(message_data)}")
    for queue in sse_connections:
        try: await queue.put(message_data)
        except Exception as e: log.error(f"Failed to push message to a queue: {e}")

# --- FastAPI Endpoints ---
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

# --- Tool Processing Logic ---
def process_tool_request(request: dict) -> Optional[dict]:
    """
    Processes a tool request dictionary, calls the appropriate handler,
    and formats the response or error message for SSE push or stdio output.

    Args:
        request: The dictionary containing request_id, tool_name, and arguments.

    Returns:
        A dictionary formatted for SSE/stdio output (containing type, request_id,
        and either result or error), or None if no message should be sent.
    """
    request_id = request.get("request_id", "unknown")
    tool_name = request.get("tool_name")
    result_message: dict | None = None; error_message: str | None = None
    log.debug(f"Processing tool request (ID: {request_id}, Tool: {tool_name})")
    try:
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

# --- Tool Implementations ---
def parse_docstring_metadata(docstring: Optional[str]) -> Dict[str, Any]:
    """
    Parses metadata key-value pairs from a Python docstring.

    Looks for lines formatted as 'Key: Value'. Converts keys to lowercase
    snake_case. Handles 'Tags' key specially, splitting by comma.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary containing the parsed metadata.
    """
    metadata = {};
    if not docstring: return metadata
    lines = docstring.strip().split('\n')
    for line in lines:
        line = line.strip(); match = re.match(r'^([\w\s]+):\s*(.*)$', line)
        if match:
            key = match.group(1).strip().lower().replace(' ', '_'); value = match.group(2).strip()
            if key and value:
                 if key == 'tags': metadata[key] = [tag.strip().lower() for tag in value.split(',') if tag.strip()]
                 else: metadata[key] = value
    return metadata

def execute_cqgi_script(script_content: str) -> cqgi.BuildResult:
    """Parses and executes a CQGI script."""
    log.info("Parsing script with CQGI..."); model = cqgi.parse(script_content)
    log.info("Script parsed."); log.info(f"Building model...")
    # Build without attempting parameter injection via arguments
    build_result = model.build(); log.info(f"Model build finished. Success: {build_result.success}")
    if not build_result.success: log.error(f"Script execution failed: {build_result.exception}"); raise Exception(f"Script execution failed: {build_result.exception}")
    return build_result

def _substitute_parameters(script_lines: List[str], params: Dict[str, Any]) -> List[str]:
    """Substitutes parameters into script lines marked with # PARAM."""
    modified_lines = []
    param_pattern = re.compile(r"^\s*(\w+)\s*=\s*.*#\s*PARAM\s*$")
    for line in script_lines:
        match = param_pattern.match(line)
        if match:
            param_name = match.group(1)
            if param_name in params:
                value = params[param_name]
                # Format value as Python literal (basic handling)
                if isinstance(value, str): formatted_value = repr(value)
                elif isinstance(value, (int, float, bool, list, dict, tuple)) or value is None: formatted_value = repr(value)
                else: formatted_value = str(value) # Fallback for other types
                indent = line[:match.start(1)] # Preserve original indentation
                modified_lines.append(f"{indent}{param_name} = {formatted_value} # PARAM (Substituted)")
                log.debug(f"Substituted parameter '{param_name}' with value: {formatted_value}")
                continue # Skip original line
        modified_lines.append(line)
    return modified_lines

def handle_execute_cadquery_script(request: dict) -> dict:
    """
    Handles the 'execute_cadquery_script' tool request.

    Supports parameter substitution using '# PARAM' markers and can process
    multiple parameter sets provided via 'parameter_sets' or a single set
    via 'parameters'. Executes the script for each set and returns a summary.

    Args:
        request: The tool request dictionary.

    Returns:
        A dictionary summarizing the execution results for all parameter sets.
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling execute_cadquery_script request (ID: {request_id})")
    try:
        args = request.get("arguments", {}); script_content = args.get("script")
        # Support both 'parameters' (single dict) and 'parameter_sets' (list of dicts)
        parameter_sets_arg = args.get("parameter_sets")
        parameters_arg = args.get("parameters")
        parameter_sets: List[Dict[str, Any]] = []

        if parameter_sets_arg is not None:
            if not isinstance(parameter_sets_arg, list): raise ValueError("'parameter_sets' argument must be a list of dictionaries.")
            if not all(isinstance(p, dict) for p in parameter_sets_arg): raise ValueError("Each item in 'parameter_sets' must be a dictionary.")
            parameter_sets = parameter_sets_arg
        elif parameters_arg is not None:
            if not isinstance(parameters_arg, dict): raise ValueError("'parameters' argument must be a dictionary.")
            parameter_sets = [parameters_arg] # Treat single dict as a list with one set
        else:
            parameter_sets = [{}] # Default: run once with no substitutions

        if not script_content: raise ValueError("Missing 'script' argument.")
        log.info(f"Script content received (first 100 chars): {script_content[:100]}...")
        log.info(f"Processing {len(parameter_sets)} parameter set(s).")

        original_script_lines = script_content.splitlines()
        results_summary = []

        for i, params in enumerate(parameter_sets):
            result_id = f"{request_id}_{i}"
            log.info(f"Executing script for parameter set {i} (Result ID: {result_id}) with params: {params}")
            try:
                modified_script_lines = _substitute_parameters(original_script_lines, params)
                modified_script = "\n".join(modified_script_lines)
                log.debug(f"Modified script for set {i}:\n{modified_script[:500]}...") # Log start of modified script

                build_result = execute_cqgi_script(modified_script)
                shape_results[result_id] = build_result
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
# Removed leftover lines from previous function version

def handle_export_shape(request: dict) -> dict:
    """
    Handles the 'export_shape' tool request.

    Retrieves a previously generated shape using result_id and shape_index,
    then exports it to the specified filename and format using the refactored
    `export_shape_to_file` function.

    Args:
        request: The tool request dictionary.

    Returns:
        A dictionary indicating success and the output filename.
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
        # Call the refactored export function
        export_shape_to_file(shape_to_export, filename, export_format, export_options)
        log.info(f"Shape successfully exported via export_shape_to_file to '{filename}'.")
        return {"success": True, "message": f"Shape successfully exported to {filename}.", "filename": filename}
    except Exception as e: error_msg = f"Error during shape export handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)
# --- Refactored Export Logic ---
def export_shape_to_file(shape_to_export: Any, output_path: str, export_format: Optional[str] = None, export_options: Optional[dict] = None):
     """Exports a CadQuery shape/workplane to a specified file."""
     shape = shape_to_export.val() if isinstance(shape_to_export, cq.Workplane) else shape_to_export
     if not isinstance(shape, cq.Shape): raise TypeError(f"Object to export is not a cq.Shape or cq.Workplane, but {type(shape)}")
     if export_options is None: export_options = {}
     log.info(f"Exporting shape to file '{output_path}' (Format: {export_format or 'Infer'}, Options: {export_options})")
     try:
         output_dir = os.path.dirname(output_path)
         if output_dir: os.makedirs(output_dir, exist_ok=True)
         exporters.export(shape, output_path, exportType=export_format, opt=export_options)
         log.info(f"Shape successfully exported to file '{output_path}'.")
     except Exception as e:
         error_msg = f"Core shape export to file '{output_path}' failed: {e}"
         log.error(error_msg, exc_info=True)
         raise Exception(error_msg) from e
 

def export_shape_to_svg_file(shape_to_render: Any, output_path: str, svg_opts: dict) -> None:
    """
    Exports a CadQuery shape or Workplane to an SVG file.

    Args:
        shape_to_render: The CadQuery object (Shape or Workplane) to export.
        output_path: The full path to save the SVG file.
        svg_opts: A dictionary of options for cq.exporters.export (SVG specific).

    Raises:
        TypeError: If the object is not a cq.Shape or cq.Workplane.
        Exception: If the export process fails.
    """
    shape = shape_to_render.val() if isinstance(shape_to_render, cq.Workplane) else shape_to_render
    if not isinstance(shape, cq.Shape): raise TypeError(f"Object to export is not a cq.Shape or cq.Workplane, but {type(shape)}")
    log.info(f"Exporting shape to SVG '{output_path}' with options: {svg_opts}")
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        exporters.export(shape, output_path, exportType='SVG', opt=svg_opts)
        log.info(f"Shape successfully exported to SVG '{output_path}'.")
    except Exception as e: error_msg = f"Core SVG export failed: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg) from e

def handle_export_shape_to_svg(request: dict) -> dict:
    """
    Handles the 'export_shape_to_svg' tool request.

    Retrieves a previously generated shape, determines the output path/URL
    in the RENDER_DIR, merges default and provided SVG options, and calls
    `export_shape_to_svg_file` to perform the export.

    Args:
        request: The tool request dictionary.

    Returns:
        A dictionary indicating success and the output file's URL path.
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
        output_path = os.path.join(RENDER_DIR_PATH, base_filename); output_url = f"/{RENDER_DIR_NAME}/{base_filename}"
        svg_opts = {"width": 400, "height": 300, "marginLeft": 10, "marginTop": 10, "showAxes": False, "projectionDir": (0.5, 0.5, 0.5), "strokeWidth": 0.25, "strokeColor": (0, 0, 0), "hiddenColor": (0, 0, 255, 100), "showHidden": False}
        svg_opts.update(export_options)
        export_shape_to_svg_file(shape_result_obj, output_path, svg_opts)
        return {"success": True, "message": f"Shape successfully exported to SVG: {output_url}.", "filename": output_url}
    except Exception as e: error_msg = f"Error during SVG export handling: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg)

def handle_scan_part_library(request: dict) -> dict:
    """
    Handles the 'scan_part_library' tool request.

    Scans the PART_LIBRARY_DIR for .py files, executes them using CQGI,
    extracts metadata, generates SVG previews, and updates the in-memory
    `part_index`. Handles caching based on file modification times and
    removes entries/previews for deleted files.

    Args:
        request: The tool request dictionary (arguments are currently ignored).

    Returns:
        A dictionary summarizing the scan results (counts for scanned, indexed, etc.).
    """
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling scan_part_library request (ID: {request_id})")
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
                tree = ast.parse(script_content); docstring = ast.get_docstring(tree)
                metadata = parse_docstring_metadata(docstring); metadata['filename'] = filename
                build_result = execute_cqgi_script(script_content)
                if build_result.success and build_result.results:
                    shape_to_preview = build_result.results[0].shape; preview_filename = f"{part_name}.svg"
                    preview_output_path = os.path.join(preview_dir_path, preview_filename); preview_output_url = f"{preview_dir_url}/{preview_filename}"
                    export_shape_to_svg_file(shape_to_preview, preview_output_path, default_svg_opts)
                    part_data = { "part_id": part_name, "metadata": metadata, "preview_url": preview_output_url, "script_path": file_path, "mtime": current_mtime }
                    if part_name in part_index: updated_count += 1
                    else: indexed_count += 1
                    part_index[part_name] = part_data; log.info(f"Successfully indexed/updated part: {part_name}")
                elif not build_result.results: log.warning(f"Part script {filename} executed successfully but produced no results. Skipping indexing."); error_count += 1
                else: error_count += 1
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
    Handles the 'search_parts' tool request.

    Searches the in-memory `part_index` based on a query string. Matches against
    part ID, metadata fields (part name, description, filename), and tags.
    Returns a list of matching parts, sorted by a simple relevance score.
    An empty query returns all parts.

    Args:
        request: The tool request dictionary, expecting 'query' in arguments.

    Returns:
        A dictionary containing the list of matching part data objects.
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

# --- Static Files Hosting ---
def configure_static_files(static_dir: str, render_dir_name: str, render_dir_path: str, preview_dir_name: str, preview_dir_path: str, assets_dir_path: str) -> None:
    """
    Configures FastAPI static file serving for frontend, renders, and previews.

    Mounts StaticFiles instances for renders, previews, and assets if the
    corresponding directories exist. Sets up a catch-all route to serve
    files from the static_dir or fall back to index.html for SPA routing.
    Includes a fallback root route if the static directory itself is missing.
    """
    log.info(f"Configuring static files from base: {static_dir}")
    if os.path.isdir(render_dir_path): app.mount(f"/{render_dir_name}", StaticFiles(directory=render_dir_path), name=render_dir_name); log.info(f"Mounted renders directory '{render_dir_path}' at '/{render_dir_name}'")
    else: log.warning(f"Renders directory '{render_dir_path}' not found.")
    if os.path.isdir(preview_dir_path): app.mount(f"/{preview_dir_name}", StaticFiles(directory=preview_dir_path), name=preview_dir_name); log.info(f"Mounted part previews directory '{preview_dir_path}' at '/{preview_dir_name}'")
    else: log.warning(f"Part previews directory '{preview_dir_path}' not found.")
    if os.path.isdir(assets_dir_path): app.mount("/assets", StaticFiles(directory=assets_dir_path), name="assets"); log.info(f"Mounted assets directory '{assets_dir_path}' at '/assets'")
    else: log.warning(f"Assets directory '{assets_dir_path}' not found.")
    @app.get("/{full_path:path}")
    async def serve_static_or_index(request: Request, full_path: str) -> Union[FileResponse, Response, HTTPException]:
        """Serves static files or the index.html for SPA routing."""
        if full_path.startswith("mcp/"): raise HTTPException(status_code=404, detail="API route not found")
        potential_file_path = os.path.join(static_dir, full_path); log.debug(f"Checking for static file at: {potential_file_path}")
        if os.path.isfile(potential_file_path):
            log.debug(f"Serving static file: {potential_file_path}"); mime_type, _ = mimetypes.guess_type(potential_file_path)
            return FileResponse(potential_file_path, media_type=mime_type or 'application/octet-stream')
        log.debug(f"Path '{full_path}' not found as static file, serving index.html.")
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path): return FileResponse(index_path)
        else:
            log.error(f"Frontend index.html not found at {index_path}")
            if not os.path.isdir(static_dir): log.warning(f"Static directory '{static_dir}' not found."); return Response(content="Backend running, but frontend static directory not found.", status_code=503)
            raise HTTPException(status_code=404, detail="index.html not found.")
    if not os.path.isdir(static_dir):
        @app.get("/")
        async def root_fallback() -> dict:
            """Fallback root endpoint if static directory is missing."""
            log.warning(f"Static directory '{static_dir}' not found."); return {"message": "Backend is running, but frontend is not built or found."}

# --- Stdio Mode ---
async def run_stdio_mode() -> None:
    """Runs the server in MCP Stdio mode, reading JSON requests from stdin."""
    log.info("Starting server in MCP stdio mode...")
    reader = asyncio.StreamReader(); protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    while True:
        try:
            line_bytes = await reader.readline()
            if not line_bytes: log.info("Stdin closed, exiting stdio mode."); break
            line = line_bytes.decode('utf-8').strip()
            if not line: continue
            log.debug(f"Received stdio line: {line}"); request_data = None
            try:
                request_data = json.loads(line)
                if not isinstance(request_data, dict) or "tool_name" not in request_data or "request_id" not in request_data: raise ValueError("Invalid MCP request format")
                response_data = process_tool_request(request_data)
                if response_data: response_json = json.dumps(response_data); log.debug(f"Sending stdio response: {response_json}"); print(response_json, flush=True)
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON from stdin: {e}"); error_resp = {"type": "tool_error", "request_id": "unknown", "error": f"Invalid JSON received: {e}"}; print(json.dumps(error_resp), flush=True)
            except Exception as e:
                 log.error(f"Error processing stdio request: {e}", exc_info=True)
                 req_id = request_data.get("request_id", "unknown") if isinstance(request_data, dict) else "unknown"
                 error_resp = {"type": "tool_error", "request_id": req_id, "error": f"Internal server error: {e}"}; print(json.dumps(error_resp), flush=True)
        except KeyboardInterrupt: log.info("KeyboardInterrupt received, exiting stdio mode."); break
        except Exception as e: log.error(f"Unexpected error in stdio loop: {e}", exc_info=True); await asyncio.sleep(1)

# --- Typer Command ---
@cli.command()
def main(
    host: str = typer.Option("0.0.0.0", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development."),
    stdio: bool = typer.Option(False, "--stdio", help="Run in MCP Stdio mode."),
    library_dir: str = typer.Option(PART_LIBRARY_DIR, "--library-dir", "-l", help="Path to the CadQuery part library directory."), # Keep default relative path
    static_dir: str = typer.Option(STATIC_DIR, "--static-dir", "-s", help="Path to the static files directory (frontend build)."), # Keep default relative path
    preview_dir_name: str = typer.Option(PART_PREVIEW_DIR_NAME, "--preview-dir-name", help="Subdirectory name within static-dir for part previews."),
    render_dir_name: str = typer.Option(RENDER_DIR_NAME, "--render-dir-name", help="Subdirectory name within static-dir for renders."),
):
    """Runs the CadQuery MCP Server."""
    global PART_LIBRARY_DIR, STATIC_DIR, PART_PREVIEW_DIR_NAME, RENDER_DIR_NAME
    global RENDER_DIR_PATH, PART_PREVIEW_DIR_PATH, ASSETS_DIR_PATH

    # Update global path variables based on CLI options
    # Use abspath to resolve relative paths based on CWD where script is run
    PART_LIBRARY_DIR = os.path.abspath(library_dir)
    STATIC_DIR = os.path.abspath(static_dir)
    PART_PREVIEW_DIR_NAME = preview_dir_name
    RENDER_DIR_NAME = render_dir_name

    # Recalculate full paths based on potentially updated globals/CLI args
    RENDER_DIR_PATH = os.path.join(STATIC_DIR, RENDER_DIR_NAME)
    PART_PREVIEW_DIR_PATH = os.path.join(STATIC_DIR, PART_PREVIEW_DIR_NAME)
    ASSETS_DIR_PATH = os.path.join(STATIC_DIR, "assets")

    log.info(f"Using Part Library: {PART_LIBRARY_DIR}"); log.info(f"Using Static Dir: {STATIC_DIR}")
    log.info(f"Using Preview Dir: {PART_PREVIEW_DIR_PATH} (mounted at /{PART_PREVIEW_DIR_NAME})")
    log.info(f"Using Render Dir: {RENDER_DIR_PATH} (mounted at /{RENDER_DIR_NAME})")

    # Ensure directories exist (important after paths might have changed)
    os.makedirs(RENDER_DIR_PATH, exist_ok=True); os.makedirs(PART_PREVIEW_DIR_PATH, exist_ok=True)

    # --- Stdio Mode Execution ---
    if stdio:
        # Initial scan needed even for stdio if library tools are used
        log.info("Performing initial scan of part library for stdio mode...");
        try: handle_scan_part_library({"request_id": "startup-scan", "arguments": {}})
        except Exception as e: log.error(f"Initial part library scan failed: {e}", exc_info=True)
        # Run stdio loop
        asyncio.run(run_stdio_mode())
        raise typer.Exit() # Exit after stdio mode finishes

    # --- HTTP Mode Execution ---
    configure_static_files(STATIC_DIR, RENDER_DIR_NAME, RENDER_DIR_PATH, PART_PREVIEW_DIR_NAME, PART_PREVIEW_DIR_PATH, ASSETS_DIR_PATH)
    log.info("Performing initial scan of part library...");
    try: handle_scan_part_library({"request_id": "startup-scan", "arguments": {}})
    except Exception as e: log.error(f"Initial part library scan failed: {e}", exc_info=True)
    log.info(f"Starting Uvicorn server on {host}:{port}...");
    # Use "server:app" as the target since server.py is in the root
    uvicorn.run("server_stdio:app", host=host, port=port, reload=reload) # Updated target after rename

# Removed check_and_setup_env()

if __name__ == "__main__":
    cli()