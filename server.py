import sys
import json
import logging
import traceback
import uuid
import os
import asyncio
import ast # Added for docstring parsing
import re # Added for docstring parsing
from typing import Dict, Any, List, Optional

import cadquery as cq
from cadquery import cqgi
from cadquery import exporters
import cadquery.vis as vis
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sse_starlette.sse import EventSourceResponse
import mimetypes

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
log = logging.getLogger(__name__)
app = FastAPI()

# --- State Management ---
shape_results: Dict[str, cqgi.BuildResult] = {} # Stores results from execute_cadquery_script
part_index: Dict[str, Dict[str, Any]] = {} # Stores metadata and preview info for library parts

# --- SSE Connection Management ---
sse_connections: List[asyncio.Queue] = []

async def push_sse_message(message_data: dict):
    log.info(f"Pushing message to {len(sse_connections)} SSE client(s): {json.dumps(message_data)}")
    for queue in sse_connections:
        try: await queue.put(message_data)
        except Exception as e: log.error(f"Failed to push message to a queue: {e}")

# --- FastAPI Endpoints ---

@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
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
async def execute_tool_endpoint(request_body: dict = Body(...)):
    request_id = request_body.get("request_id", "unknown")
    tool_name = request_body.get("tool_name")
    log.info(f"Received execution request via POST (ID: {request_id}, Tool: {tool_name})")
    if not tool_name:
         log.error("Received execution request without tool_name.")
         raise HTTPException(status_code=400, detail="Missing 'tool_name' in request body")
    asyncio.create_task(process_tool_request(request_body))
    return {"status": "processing", "request_id": request_id}

# --- Tool Processing Logic ---

async def process_tool_request(request: dict):
    request_id = request.get("request_id", "unknown")
    tool_name = request.get("tool_name")
    result_message: dict | None = None
    error_message: str | None = None
    log.debug(f"Processing tool request (ID: {request_id}, Tool: {tool_name})")
    try:
        if tool_name == "execute_cadquery_script": result_message = handle_execute_cadquery_script(request)
        elif tool_name == "export_shape": result_message = handle_export_shape(request)
        elif tool_name == "export_shape_to_svg": result_message = handle_export_shape_to_svg(request)
        elif tool_name == "scan_part_library": result_message = handle_scan_part_library(request)
        elif tool_name == "search_parts": result_message = handle_search_parts(request) # Added search handler
        else:
            log.warning(f"Unknown tool requested: {tool_name}")
            error_message = f"Unknown tool: {tool_name}"
    except Exception as e:
        log.error(f"Error processing tool '{tool_name}' (ID: {request_id}): {e}", exc_info=True)
        detail = getattr(e, 'detail', str(e))
        error_message = f"Internal server error processing {tool_name}: {detail}"

    log.debug(f"Tool processing complete (ID: {request_id}). Error: {error_message}, Result: {result_message}")
    message_to_push = {}
    if error_message:
        message_to_push = {"type": "tool_error", "request_id": request_id, "error": error_message}
        log.debug(f"Pushing error message via SSE (ID: {request_id})")
    elif result_message:
         message_to_push = {"type": "tool_result", "request_id": request_id, "result": result_message}
         log.debug(f"Pushing result message via SSE (ID: {request_id})")
    else:
        log.warning(f"No result or error message generated for request ID: {request_id}")
        message_to_push = {"type": "tool_error", "request_id": request_id, "error": "Handler produced no result or error."}

    await push_sse_message(message_to_push)

# --- Tool Implementations ---

# Define paths globally
PART_LIBRARY_DIR = "part_library"
RENDER_DIR_NAME = "renders"
PART_PREVIEW_DIR_NAME = "part_previews" # New directory for previews
STATIC_DIR = os.path.abspath("frontend/dist")
RENDER_DIR_PATH = os.path.join(STATIC_DIR, RENDER_DIR_NAME)
PART_PREVIEW_DIR_PATH = os.path.join(STATIC_DIR, PART_PREVIEW_DIR_NAME) # Path for previews
ASSETS_DIR_PATH = os.path.join(STATIC_DIR, "assets")

# Ensure directories exist at startup
os.makedirs(RENDER_DIR_PATH, exist_ok=True)
os.makedirs(PART_PREVIEW_DIR_PATH, exist_ok=True) # Ensure preview dir exists
log.info(f"Ensured render directory exists: {RENDER_DIR_PATH}")
log.info(f"Ensured part preview directory exists: {PART_PREVIEW_DIR_PATH}")


def parse_docstring_metadata(docstring: Optional[str]) -> Dict[str, Any]:
    """Parses key-value metadata from a module-level docstring."""
    metadata = {}
    if not docstring:
        return metadata

    lines = docstring.strip().split('\n')
    for line in lines:
        line = line.strip()
        match = re.match(r'^([\w\s]+):\s*(.*)$', line)
        if match:
            key = match.group(1).strip().lower().replace(' ', '_')
            value = match.group(2).strip()
            if key and value:
                 if key == 'tags':
                     metadata[key] = [tag.strip().lower() for tag in value.split(',') if tag.strip()] # Lowercase tags
                 else:
                     metadata[key] = value
    return metadata

def execute_cqgi_script(script_content: str) -> cqgi.BuildResult:
    """Parses and executes a CQGI script, returning the build result."""
    log.info("Parsing script with CQGI...")
    model = cqgi.parse(script_content)
    log.info("Script parsed.")
    log.info(f"Building model...")
    build_result = model.build()
    log.info(f"Model build finished. Success: {build_result.success}")
    if not build_result.success:
        log.error(f"Script execution failed: {build_result.exception}")
        raise Exception(f"Script execution failed: {build_result.exception}")
    return build_result

def handle_execute_cadquery_script(request) -> dict:
    """Handles the 'execute_cadquery_script' tool request."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling execute_cadquery_script request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        script_content = args.get("script")
        parameters = args.get("parameters", {})
        if not script_content: raise ValueError("Missing 'script' argument.")
        if not isinstance(parameters, dict): raise ValueError("'parameters' argument must be a dictionary.")

        log.info(f"Script content received (first 100 chars): {script_content[:100]}...")
        log.info(f"Parameters received: {parameters}")

        build_result = execute_cqgi_script(script_content)

        result_id = str(uuid.uuid4())
        shape_results[result_id] = build_result
        log.info(f"Stored successful build result with ID: {result_id}")
        num_shapes = len(build_result.results) if build_result.results else 0
        message = f"Script executed successfully. Produced {num_shapes} shape(s)."
        return {"success": True, "message": message, "result_id": result_id, "shapes_count": num_shapes}

    except Exception as e:
        error_msg = f"Error during script execution handling: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

def handle_export_shape(request) -> dict:
    """Handles the generic 'export_shape' tool request."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0)
        filename = args.get("filename")
        export_format = args.get("format")
        export_options = args.get("options", {})

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
        output_dir = os.path.dirname(filename)
        if output_dir: os.makedirs(output_dir, exist_ok=True)

        exporters.export(shape_to_export, filename, exportType=export_format, opt=export_options)
        log.info(f"Shape successfully exported to '{filename}'.")
        return {"success": True, "message": f"Shape successfully exported to {filename}.", "filename": filename}

    except Exception as e:
        error_msg = f"Error during shape export: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

def export_shape_to_svg_file(shape_to_render: Any, output_path: str, svg_opts: dict):
    """Exports a given CadQuery shape (Workplane or Shape) to an SVG file."""
    shape = shape_to_render.val() if isinstance(shape_to_render, cq.Workplane) else shape_to_render
    if not isinstance(shape, cq.Shape):
         raise TypeError(f"Object to export is not a cq.Shape or cq.Workplane, but {type(shape)}")

    log.info(f"Exporting shape to SVG '{output_path}' with options: {svg_opts}")
    try:
        exporters.export(shape, output_path, exportType='SVG', opt=svg_opts)
        log.info(f"Shape successfully exported to SVG '{output_path}'.")
    except Exception as e:
        error_msg = f"Core SVG export failed: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg) from e

def handle_export_shape_to_svg(request) -> dict:
    """Handles the 'export_shape_to_svg' tool request."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape_to_svg request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0)
        default_svg_name = f"render_{uuid.uuid4()}.svg"
        base_filename = os.path.basename(args.get("filename", default_svg_name))
        if not base_filename.lower().endswith(".svg"):
             base_filename += ".svg"
             log.warning(f"Appended .svg to filename. New base filename: {base_filename}")

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

        output_path = os.path.join(RENDER_DIR_PATH, base_filename)
        output_url = f"/{RENDER_DIR_NAME}/{base_filename}"
        svg_opts = {"width": 400, "height": 300, "marginLeft": 10, "marginTop": 10, "showAxes": False, "projectionDir": (0.5, 0.5, 0.5), "strokeWidth": 0.25, "strokeColor": (0, 0, 0), "hiddenColor": (0, 0, 255, 100), "showHidden": False}
        svg_opts.update(export_options)

        export_shape_to_svg_file(shape_result_obj, output_path, svg_opts)

        return {"success": True, "message": f"Shape successfully exported to SVG: {output_url}.", "filename": output_url}

    except Exception as e:
        error_msg = f"Error during SVG export handling: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)

def handle_scan_part_library(request) -> dict:
    """Scans the part library, extracts metadata, generates previews, and indexes."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling scan_part_library request (ID: {request_id})")
    library_path = os.path.abspath(PART_LIBRARY_DIR)
    preview_dir_path = PART_PREVIEW_DIR_PATH
    preview_dir_url = f"/{PART_PREVIEW_DIR_NAME}"

    if not os.path.isdir(library_path):
        raise ValueError(f"Part library directory not found: {library_path}")

    part_index.clear()
    scanned_count = 0
    indexed_count = 0
    error_count = 0

    default_svg_opts = {"width": 150, "height": 100, "showAxes": False}

    for filename in os.listdir(library_path):
        if filename.endswith(".py") and not filename.startswith("_"):
            scanned_count += 1
            part_name = os.path.splitext(filename)[0]
            file_path = os.path.join(library_path, filename)
            log.info(f"Scanning part: {filename}")
            metadata = {}
            build_result = None
            error_msg = None

            try:
                with open(file_path, 'r', encoding='utf-8') as f: script_content = f.read()
                tree = ast.parse(script_content)
                docstring = ast.get_docstring(tree)
                metadata = parse_docstring_metadata(docstring)
                metadata['filename'] = filename
                log.debug(f"Parsed metadata for {filename}: {metadata}")

                build_result = execute_cqgi_script(script_content)

                if build_result.success and build_result.results:
                    shape_to_preview = build_result.results[0].shape
                    preview_filename = f"{part_name}.svg"
                    preview_output_path = os.path.join(preview_dir_path, preview_filename)
                    preview_output_url = f"{preview_dir_url}/{preview_filename}"

                    export_shape_to_svg_file(shape_to_preview, preview_output_path, default_svg_opts)

                    part_data = {
                        "part_id": part_name, # Use part_name as the key/ID
                        "metadata": metadata,
                        "preview_url": preview_output_url,
                        "script_path": file_path
                    }
                    part_index[part_name] = part_data
                    indexed_count += 1
                    log.info(f"Successfully indexed part: {part_name}")
                elif not build_result.results:
                     log.warning(f"Part script {filename} executed successfully but produced no results (use show_object). Skipping indexing.")
                     error_count += 1
                else:
                     log.error(f"Unexpected state for {filename}: build not successful but no exception raised?")
                     error_count += 1

            except SyntaxError as e: error_msg = f"Syntax error parsing {filename}: {e}"; error_count += 1
            except Exception as e: error_msg = f"Error processing {filename}: {e}"; error_count += 1

            if error_msg: log.error(error_msg, exc_info=True)

    summary_msg = f"Scan complete. Scanned: {scanned_count}, Indexed: {indexed_count}, Errors: {error_count}."
    log.info(summary_msg)
    return {"success": True, "message": summary_msg, "indexed_count": indexed_count, "error_count": error_count}

def handle_search_parts(request) -> dict:
    """Searches the part index based on keywords."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling search_parts request (ID: {request_id})")
    try:
        args = request.get("arguments", {})
        query = args.get("query", "").strip().lower()
        if not query:
            # Return all parts if query is empty
            log.info("Empty search query, returning all indexed parts.")
            results = list(part_index.values()) # Return list of part data dicts
            return {"success": True, "message": f"Found {len(results)} parts.", "results": results}

        log.info(f"Searching parts with query: '{query}'")
        search_terms = set(term.strip() for term in query.split() if term.strip())
        results = []

        for part_id, part_data in part_index.items():
            match_score = 0
            metadata = part_data.get("metadata", {})

            # Check part_id (filename without extension)
            if query in part_id.lower(): match_score += 5

            # Check 'part' name from metadata
            if query in metadata.get("part", "").lower(): match_score += 3

            # Check description
            if query in metadata.get("description", "").lower(): match_score += 2

            # Check tags (exact match on any term)
            tags = metadata.get("tags", [])
            if isinstance(tags, list):
                 if any(term in tag for term in search_terms for tag in tags):
                     match_score += 5 # Higher score for tag match

            # Check filename
            if query in metadata.get("filename", "").lower(): match_score += 1

            if match_score > 0:
                results.append({"score": match_score, "part": part_data})

        # Sort results by score descending
        results.sort(key=lambda x: x["score"], reverse=True)

        # Extract just the part data for the final result list
        final_results = [item["part"] for item in results]

        message = f"Found {len(final_results)} parts matching query '{query}'."
        log.info(message)
        return {"success": True, "message": message, "results": final_results}

    except Exception as e:
        error_msg = f"Error during part search: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg)


# --- Static Files Hosting ---
# (Code remains the same)
# Catch-all route defined FIRST
@app.get("/{full_path:path}")
async def serve_static_or_index(request: Request, full_path: str):
    """Serve static files if they exist, otherwise serve index.html."""
    # Exclude API routes explicitly
    if full_path.startswith("mcp/") or full_path.startswith(RENDER_DIR_NAME+"/") or full_path.startswith(PART_PREVIEW_DIR_NAME+"/"):
         log.debug(f"Path '{full_path}' is API or asset route, skipping static/index serving.")
         pass

    potential_file_path = os.path.join(STATIC_DIR, full_path)
    log.debug(f"Checking for static file at: {potential_file_path}")

    if os.path.isfile(potential_file_path):
        log.debug(f"Serving static file: {potential_file_path}")
        mime_type, _ = mimetypes.guess_type(potential_file_path)
        return FileResponse(potential_file_path, media_type=mime_type or 'application/octet-stream')

    log.debug(f"Path '{full_path}' not found as static file, serving index.html.")
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        log.error(f"Frontend index.html not found at {index_path}")
        if not os.path.isdir(STATIC_DIR):
             log.warning(f"Static directory '{STATIC_DIR}' not found. Cannot serve index.html.")
             return Response(content="Backend running, but frontend static directory not found.", status_code=503)
        raise HTTPException(status_code=404, detail="index.html not found.")

# Mount specific static directories AFTER the catch-all.
if os.path.isdir(RENDER_DIR_PATH):
    app.mount(f"/{RENDER_DIR_NAME}", StaticFiles(directory=RENDER_DIR_PATH), name=RENDER_DIR_NAME)
    log.info(f"Mounted renders directory '{RENDER_DIR_PATH}' at '/{RENDER_DIR_NAME}'")
else:
    log.warning(f"Renders directory '{RENDER_DIR_PATH}' not found.")

if os.path.isdir(PART_PREVIEW_DIR_PATH): # Mount preview directory
    app.mount(f"/{PART_PREVIEW_DIR_NAME}", StaticFiles(directory=PART_PREVIEW_DIR_PATH), name=PART_PREVIEW_DIR_NAME)
    log.info(f"Mounted part previews directory '{PART_PREVIEW_DIR_PATH}' at '/{PART_PREVIEW_DIR_NAME}'")
else:
     log.warning(f"Part previews directory '{PART_PREVIEW_DIR_PATH}' not found.")


if os.path.isdir(ASSETS_DIR_PATH):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR_PATH), name="assets")
    log.info(f"Mounted assets directory '{ASSETS_DIR_PATH}' at '/assets'")
else:
     log.warning(f"Assets directory '{ASSETS_DIR_PATH}' not found.")

# Fallback for root if static dir doesn't exist at all
if not os.path.isdir(STATIC_DIR):
    @app.get("/")
    async def root_fallback():
        log.warning(f"Static directory '{STATIC_DIR}' not found. Serving fallback message.")
        return {"message": "Backend is running, but frontend is not built or found."}

# Note: The old main() function and stdin loop are removed.
# Uvicorn will run the FastAPI app instance 'app'.