import sys
import json
import logging
import traceback
import uuid
import os
import asyncio
from typing import Dict, Any, List

import cadquery as cq
from cadquery import cqgi # Import directly from cadquery
from cadquery import exporters # Import directly from cadquery
import cadquery.vis as vis # Keep this import structure based on docs
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

# --- Logging Setup ---
# Configure logging to stderr for visibility in MCP logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Direct logs to stderr
)
log = logging.getLogger(__name__)
app = FastAPI() # Create FastAPI app instance

# --- State Management ---
# Simple dictionary to store results from script execution
# Keys will be UUIDs, values will be cadquery.cqgi.BuildResult objects
shape_results: Dict[str, Any] = {} # Store BuildResult objects

# --- SSE Connection Management ---
# Store active SSE connections (using asyncio Queues)
sse_connections: List[asyncio.Queue] = []

async def push_sse_message(message_data: dict):
    """Pushes a message to all connected SSE clients."""
    log.info(f"Pushing message to {len(sse_connections)} SSE client(s): {json.dumps(message_data)}")
    for queue in sse_connections:
        try:
            await queue.put(message_data)
        except Exception as e:
            log.error(f"Failed to push message to a queue: {e}")

# --- FastAPI Endpoints ---

@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    """Endpoint for establishing SSE connection."""
    queue = asyncio.Queue()
    sse_connections.append(queue)
    client_host = request.client.host if request.client else "unknown"
    log.info(f"New SSE connection established from {client_host}. Total connections: {len(sse_connections)}")

    async def event_generator():
        try:
            while True:
                # Wait for a message to be put in the queue
                message = await queue.get()
                if message is None: # Signal to close connection
                    log.info("SSE connection closing signal received.")
                    break
                # Format as SSE event
                yield {"event": "mcp_message", "data": json.dumps(message)}
                queue.task_done() # Mark message as processed
        except asyncio.CancelledError:
            log.info(f"SSE connection from {client_host} cancelled/closed by client.")
        except Exception as e:
            log.error(f"Error in SSE event generator for {client_host}: {e}")
            log.error(traceback.format_exc())
        finally:
            # Remove the queue when the connection closes
            if queue in sse_connections:
                sse_connections.remove(queue)
            log.info(f"SSE connection from {client_host} closed. Remaining connections: {len(sse_connections)}")

    # Keep-alive mechanism (optional, helps detect broken connections)
    # async def keep_alive():
    #     while True:
    #         await asyncio.sleep(15) # Send a comment every 15 seconds
    #         yield ":" # SSE comment for keep-alive

    # return EventSourceResponse(asyncio.as_completed([event_generator(), keep_alive()]))
    return EventSourceResponse(event_generator())


@app.post("/mcp/execute")
async def execute_tool_endpoint(request_body: dict = Body(...)):
    """Endpoint to receive tool execution requests."""
    request_id = request_body.get("request_id", "unknown")
    tool_name = request_body.get("tool_name")
    log.info(f"Received execution request via POST (ID: {request_id}, Tool: {tool_name})")

    # Basic validation
    if not tool_name:
         # Cannot easily push error back without request_id mapping if SSE isn't established
         log.error("Received execution request without tool_name.")
         raise HTTPException(status_code=400, detail="Missing 'tool_name' in request body")

    # Asynchronously handle the tool execution and push result via SSE
    # We don't block the HTTP response here
    asyncio.create_task(process_tool_request(request_body))

    # Immediately acknowledge the request
    return {"status": "processing", "request_id": request_id}


# --- Tool Processing Logic ---

async def process_tool_request(request: dict):
    """Processes the tool request asynchronously and pushes result via SSE."""
    request_id = request.get("request_id", "unknown")
    tool_name = request.get("tool_name")
    result_message: dict | None = None
    error_message: str | None = None
    log.debug(f"Processing tool request (ID: {request_id}, Tool: {tool_name})")

    try:
        if tool_name == "execute_cadquery_script":
            result_message = handle_execute_cadquery_script(request) # Modify to return result/error dict
        elif tool_name == "export_shape":
            result_message = handle_export_shape(request) # Modify to return result/error dict
        elif tool_name == "export_shape_to_svg": # Renamed tool
            result_message = handle_export_shape_to_svg(request)
        else:
            log.warning(f"Unknown tool requested: {tool_name}")
            error_message = f"Unknown tool: {tool_name}"

    except Exception as e:
        log.error(f"Error processing tool '{tool_name}' (ID: {request_id}): {e}")
        log.error(traceback.format_exc())
        error_message = f"Internal server error processing {tool_name}: {str(e)}"

    # Push result or error via SSE
    log.debug(f"Tool processing complete (ID: {request_id}). Error: {error_message}, Result: {result_message}")
    if error_message:
        message_to_push = {
            "type": "tool_error",
            "request_id": request_id,
            "error": error_message
        }
        log.debug(f"Pushing error message via SSE (ID: {request_id})")
        await push_sse_message(message_to_push)
    elif result_message:
         message_to_push = {
            "type": "tool_result",
            "request_id": request_id,
            "result": result_message # The dict returned by the handler
        }
         log.debug(f"Pushing result message via SSE (ID: {request_id})")
         await push_sse_message(message_to_push)
    else:
        log.warning(f"No result or error message generated for request ID: {request_id}")

# --- Tool Implementations (Placeholders) ---

def handle_execute_cadquery_script(request) -> dict: # Returns result dict or raises error
    """Handles the 'execute_cadquery_script' tool request using CQGI."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling execute_cadquery_script request (ID: {request_id})")

    try:
        args = request.get("arguments", {})
        script_content = args.get("script")
        parameters = args.get("parameters", {}) # Should be a dict

        if not script_content:
            raise ValueError("Missing 'script' argument.")
        if not isinstance(parameters, dict):
             raise ValueError("'parameters' argument must be a dictionary (JSON object).")

        log.info(f"Script content received (first 100 chars): {script_content[:100]}...")
        log.info(f"Parameters received: {parameters}")

        # Parse the script
        log.info("Parsing script with CQGI...")
        model = cqgi.parse(script_content) # Use direct import
        log.info("Script parsed.")

        # Build the model
        log.info(f"Building model with parameters: {parameters}...")
        build_result = model.build(build_parameters=parameters)
        log.info(f"Model build finished. Success: {build_result.success}")

        if build_result.success:
            # Generate a unique ID for this result set
            result_id = str(uuid.uuid4())
            shape_results[result_id] = build_result
            log.info(f"Stored successful build result with ID: {result_id}")

            # Prepare success response
            num_shapes = len(build_result.results) if build_result.results else 0
            # num_debug = len(build_result.debug_objects) if build_result.debug_objects else 0 # Removed - attribute doesn't exist
            message = f"Script executed successfully. Produced {num_shapes} shape(s)." # Updated message

            # Return success result data
            return {
                "success": True,
                "message": message,
                "result_id": result_id,
                "shapes_count": num_shapes
                # "debug_objects_count": num_debug # Removed
            }
        else:
            # Handle build failure
            error_msg = f"Script execution failed: {build_result.exception}"
            log.error(error_msg)
            log.error(f"Traceback: {build_result.exception_trace}") # Log full traceback if available
            raise Exception(error_msg) # Raise exception on failure

    except Exception as e:
        error_msg = f"Error during script execution: {e}"
        log.error(error_msg)
        log.error(traceback.format_exc())
        log.error(f"Unhandled exception in handle_execute_cadquery_script (ID: {request_id}): {e}")
        raise Exception(error_msg) # Re-raise other exceptions


def handle_export_shape(request) -> dict: # Returns result dict or raises error
    """Handles the 'export_shape' tool request using cadquery.exporters."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape request (ID: {request_id})")

    try:
        args = request.get("arguments", {})
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0) # Default to the first shape
        filename = args.get("filename")
        export_format = args.get("format") # Optional, inferred from filename if None
        export_options = args.get("options", {}) # Optional dict for exporter opts

        # --- Input Validation ---
        if not result_id:
            raise ValueError("Missing 'result_id' argument.")
        if not filename:
            raise ValueError("Missing 'filename' argument.")
        if not isinstance(shape_index, int) or shape_index < 0:
             raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(export_options, dict):
             raise ValueError("'options' argument must be a dictionary (JSON object).")

        # --- Retrieve Shape ---
        build_result = shape_results.get(result_id)
        if not build_result:
            raise ValueError(f"Result ID '{result_id}' not found.")
        if not build_result.success:
             raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")
        if not build_result.results or shape_index >= len(build_result.results):
            raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")

        shape_to_export = build_result.results[shape_index].shape
        log.info(f"Retrieved shape at index {shape_index} from result ID {result_id}.")

        # --- Export ---
        log.info(f"Attempting to export shape to '{filename}' (Format: {export_format or 'Infer'}, Options: {export_options})")
        exporters.export( # Use direct import
            shape_to_export,
            filename,
            exportType=export_format,
            opt=export_options
        )
        log.info(f"Shape successfully exported to '{filename}'.")

        # Return success result data
        return {
            "success": True,
            "message": f"Shape successfully exported to {filename}.",
            "filename": filename
        }

    except Exception as e:
        error_msg = f"Error during shape export: {e}"
        log.error(error_msg)
        log.error(traceback.format_exc())
        log.error(f"Unhandled exception in handle_export_shape (ID: {request_id}): {e}")
        raise Exception(error_msg) # Re-raise other exceptions


def handle_export_shape_to_svg(request) -> dict: # Renamed function
    """Handles the 'export_shape_to_svg' tool request using cadquery.exporters."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Handling export_shape_to_svg request (ID: {request_id})") # Updated log

    try:
        args = request.get("arguments", {})
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0) # Default to the first shape
        # Ensure filename is just the name, not a path
        # Ensure filename ends with .svg
        base_filename = os.path.basename(args.get("filename", f"render_{uuid.uuid4()}.svg"))
        if not base_filename.lower().endswith(".svg"):
             raise ValueError("'filename' must end with .svg")

        # Construct full path within the render directory
        output_path = os.path.join(RENDER_DIR_PATH, base_filename)
        # Construct the URL path for the client
        output_url = f"/{RENDER_DIR_NAME}/{base_filename}"

        export_options = args.get("options", {}) # Optional dict for exporter opts
        # Default SVG options (can be overridden by client)
        svg_opts = {
            "width": 400,
            "height": 300,
            "marginLeft": 10,
            "marginTop": 10,
            "showAxes": False, # Axes not useful in SVG usually
            "projectionDir": (0.5, 0.5, 0.5), # Isometric-like view
            "strokeWidth": 0.25,
            "strokeColor": (0, 0, 0), # Black lines
            "hiddenColor": (0, 0, 255, 100), # Blueish transparent hidden lines
            "showHidden": False, # Keep hidden lines off by default
        }
        svg_opts.update(export_options) # Merge client options

        # --- Input Validation ---
        if not result_id:
            raise ValueError("Missing 'result_id' argument.")
        if not filename:
            # filename validation happens above with basename
            pass
        # Validation for base_filename happens above
        if not isinstance(shape_index, int) or shape_index < 0:
             raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(render_options, dict):
             raise ValueError("'options' argument must be a dictionary (JSON object).") # Keep this check

        # --- Retrieve Shape ---
        build_result = shape_results.get(result_id)
        if not build_result:
            raise ValueError(f"Result ID '{result_id}' not found.")
        if not build_result.success:
             raise ValueError(f"Result ID '{result_id}' corresponds to a failed build.")
        if not build_result.results or shape_index >= len(build_result.results):
            raise ValueError(f"Invalid shape_index {shape_index} for result ID '{result_id}'.")

        shape_to_render = build_result.results[shape_index].shape
        log.info(f"Retrieved shape at index {shape_index} from result ID {result_id}.")

        # --- Export SVG ---
        log.info(f"Attempting to export shape to SVG '{output_path}' (URL: {output_url}, Options: {svg_opts})")
        exporters.export(
            shape_to_render,
            output_path,
            exportType='SVG',
            opt=svg_opts
        )

        log.info(f"Shape successfully exported to SVG '{output_path}'.")

        # Return success result data
        return {
            "success": True,
            "message": f"Shape successfully exported to SVG: {output_url}.",
            "filename": output_url # Return the URL path
        }

    except Exception as e:
        error_msg = f"Error during SVG export: {e}" # Updated error message
        log.error(error_msg)
        log.error(traceback.format_exc())
        log.error(f"Unhandled exception in handle_export_shape_to_svg (ID: {request_id}): {e}") # Updated log
        raise Exception(error_msg)

# --- Static Files & Render Output Hosting ---
RENDER_DIR_NAME = "renders"
STATIC_DIR = "frontend/dist"
RENDER_DIR_PATH = os.path.join(STATIC_DIR, RENDER_DIR_NAME)

# Ensure render directory exists
os.makedirs(RENDER_DIR_PATH, exist_ok=True)
log.info(f"Ensured render directory exists: {RENDER_DIR_PATH}")

# Mount the static directory AFTER API routes to avoid conflicts
# This assumes the React app is built into the 'frontend/dist' directory
# Mount the renders directory specifically
app.mount(f"/{RENDER_DIR_NAME}", StaticFiles(directory=RENDER_DIR_PATH), name=RENDER_DIR_NAME)

# Check if the static directory exists before mounting
# Mount the main static assets (like JS/CSS) from the build output
if os.path.isdir(STATIC_DIR):
    # Serve specific assets like JS/CSS bundles
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
    # Serve other static files like vite.svg etc. from the root of STATIC_DIR
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static_root") # Avoid clash with root catch-all

    @app.get("/{full_path:path}")
    async def serve_frontend_catch_all(request: Request, full_path: str):
        """Serve index.html for all non-API, non-static file routes."""
        # Check if the path looks like a file request that wasn't caught by StaticFiles
        # This is a basic check, might need refinement
        if "." in full_path.split("/")[-1] and not full_path.startswith("mcp"):
             # It looks like a file but wasn't found by StaticFiles mounts
             log.warning(f"Potential static file not found: {full_path}")
             raise HTTPException(status_code=404, detail=f"Static file not found: {full_path}")

        # Otherwise, assume it's a client-side route and serve index.html
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            log.error(f"Frontend index.html not found at {index_path}")
            raise HTTPException(status_code=503, detail="Frontend not built or index.html missing.")
else:
    log.warning(f"Static directory '{STATIC_DIR}' not found. Frontend UI will not be served.")
    log.warning("Run 'npm install && npm run build' in the 'frontend' directory, or use run_dev.sh.")

    @app.get("/")
    async def root_fallback():
        return {"message": "Backend is running, but frontend is not built or found."}


# Note: The old main() function and stdin loop are removed.
# Uvicorn will run the FastAPI app instance 'app'.
# Add uvicorn run command at the end if needed for direct execution,
# but typically run via `uvicorn server:app --host 0.0.0.0 --port 8000`

# Example for direct run (though run_server.sh is preferred)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
#     uvicorn.run(app, host="0.0.0.0", port=8000)