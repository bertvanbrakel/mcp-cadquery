import sys
import json
import logging
import traceback
import uuid
import os
import asyncio
from typing import Dict, Any, List

import cadquery as cq
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
    result_message = None
    error_message = None

    try:
        if tool_name == "execute_cadquery_script":
            result_message = handle_execute_cadquery_script(request) # Modify to return result/error dict
        elif tool_name == "export_shape":
            result_message = handle_export_shape(request) # Modify to return result/error dict
        elif tool_name == "render_shape_to_png":
            result_message = handle_render_shape_to_png(request) # Modify to return result/error dict
        else:
            log.warning(f"Unknown tool requested: {tool_name}")
            error_message = f"Unknown tool: {tool_name}"

    except Exception as e:
        log.error(f"Error processing tool '{tool_name}' (ID: {request_id}): {e}")
        log.error(traceback.format_exc())
        error_message = f"Internal server error processing {tool_name}: {e}"

    # Push result or error via SSE
    if error_message:
        await push_sse_message({
            "type": "tool_error",
            "request_id": request_id,
            "error": error_message
        })
    elif result_message:
         await push_sse_message({
            "type": "tool_result",
            "request_id": request_id,
            "result": result_message # The dict returned by the handler
        })
    # else: case where handler didn't return anything? Should not happen if handlers are correct.

# --- Tool Implementations (Placeholders) ---

def handle_execute_cadquery_script(request) -> dict: # Returns result dict or raises error
    """Handles the 'execute_cadquery_script' tool request using CQGI."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Received execute_cadquery_script request (ID: {request_id})")

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
        model = cq.cqgi.parse(script_content)
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
            num_debug = len(build_result.debug_objects) if build_result.debug_objects else 0
            message = f"Script executed successfully. Produced {num_shapes} shape(s) and {num_debug} debug object(s)."

            # Return success result data
            return {
                "success": True,
                "message": message,
                "result_id": result_id,
                "shapes_count": num_shapes,
                "debug_objects_count": num_debug
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
        raise Exception(error_msg) # Re-raise other exceptions


def handle_export_shape(request) -> dict: # Returns result dict or raises error
    """Handles the 'export_shape' tool request using cadquery.exporters."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Received export_shape request (ID: {request_id})")

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
        cq.exporters.export(
            shape_to_export,
            filename,
            exportType=export_format, # Exporter handles None format by inferring from extension
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
        raise Exception(error_msg) # Re-raise other exceptions


def handle_render_shape_to_png(request) -> dict: # Returns result dict or raises error
    """Handles the 'render_shape_to_png' tool request using cadquery.vis.show."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Received render_shape_to_png request (ID: {request_id})")

    try:
        args = request.get("arguments", {})
        result_id = args.get("result_id")
        shape_index = args.get("shape_index", 0) # Default to the first shape
        filename = args.get("filename")
        render_options = args.get("options", {}) # Optional dict for vis.show opts

        # --- Input Validation ---
        if not result_id:
            raise ValueError("Missing 'result_id' argument.")
        if not filename:
            raise ValueError("Missing 'filename' argument.")
        if not filename.lower().endswith(".png"):
             raise ValueError("'filename' must end with .png")
        if not isinstance(shape_index, int) or shape_index < 0:
             raise ValueError("'shape_index' must be a non-negative integer.")
        if not isinstance(render_options, dict):
             raise ValueError("'options' argument must be a dictionary (JSON object).")

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

        # --- Render ---
        # Ensure interact is False and screenshot is set
        render_options['screenshot'] = filename
        render_options['interact'] = False
        log.info(f"Attempting to render shape to '{filename}' (Options: {render_options})")

        # vis.show might block or have issues in a non-GUI server environment.
        # Need to be cautious here. Consider running in a separate process if it blocks.
        # For now, assume it works as documented for non-interactive screenshots.
        cq.vis.show(shape_to_render, **render_options)

        log.info(f"Shape successfully rendered to '{filename}'.")

        # Return success result data
        return {
            "success": True,
            "message": f"Shape successfully rendered to {filename}.",
            "filename": filename
        }

    except Exception as e:
        error_msg = f"Error during shape rendering: {e}"
        log.error(error_msg)
        log.error(traceback.format_exc())
        raise Exception(error_msg) # Re-raise other exceptions

# --- Static Files Hosting ---
# Mount the static directory AFTER API routes to avoid conflicts
# This assumes the React app is built into the 'frontend/dist' directory
STATIC_DIR = "frontend/dist"

# Check if the static directory exists before mounting
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve index.html for all non-API routes to enable client-side routing."""
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        else:
            log.error(f"Frontend index.html not found at {index_path}")
            raise HTTPException(status_code=404, detail="Frontend not found. Build the frontend first.")
else:
    log.warning(f"Static directory '{STATIC_DIR}' not found. Frontend will not be served.")
    log.warning("Run 'npm install && npm run build' in the 'frontend' directory.")

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