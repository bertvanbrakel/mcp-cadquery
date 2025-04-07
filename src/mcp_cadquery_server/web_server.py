import json
import asyncio
import os # Added import
from typing import Optional, Dict, Any, Union # Added Union
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles # Added import
from sse_starlette.sse import EventSourceResponse

# Import necessary components from other modules
from .state import log, sse_connections # Import log and sse_connections from state
from .mcp_api import get_server_info, process_tool_request # Import API functions
from . import state # Import state for default dir names

app = FastAPI() # Define the app instance

def configure_static_files(app_instance: FastAPI, static_dir: str, render_dir_name: str, render_dir_path: str, preview_dir_name: str, preview_dir_path: str, assets_dir_path: str) -> None:
    """
    Configures FastAPI static file serving for frontend, renders, and previews.
    NOTE: This function modifies the passed 'app_instance'.
    """
    state.log.info(f"Configuring static files. Base static dir: {static_dir}")

    # Mount renders, previews, and assets if they exist
    # Use placeholder paths for mounting points, actual serving might need workspace context
    if os.path.isdir(assets_dir_path): # Mount assets first
         app_instance.mount("/assets", StaticFiles(directory=assets_dir_path), name="assets")
         state.log.info(f"Mounted assets directory '{assets_dir_path}' at '/assets'")
    else: state.log.warning(f"Assets directory '{assets_dir_path}' not found, skipping mount.")

    # Mount placeholder routes for renders and previews relative to root
    # These might not serve actual files directly without more complex routing
    # if os.path.isdir(render_dir_path): # Check actual path for logging, but mount default name
    app_instance.mount(f"/{render_dir_name}", StaticFiles(directory=render_dir_path, check_dir=False), name=render_dir_name) # check_dir=False might be needed if dir doesn't exist at startup
    state.log.info(f"Mounted render directory (placeholder) at '/{render_dir_name}' (points to: {render_dir_path})")
    # else: state.log.warning(f"Render directory '{render_dir_path}' not found, skipping mount.")

    # if os.path.isdir(preview_dir_path): # Check actual path for logging, but mount default name
    app_instance.mount(f"/{preview_dir_name}", StaticFiles(directory=preview_dir_path, check_dir=False), name=preview_dir_name)
    state.log.info(f"Mounted preview directory (placeholder) at '/{preview_dir_name}' (points to: {preview_dir_path})")
    # else: state.log.warning(f"Preview directory '{preview_dir_path}' not found, skipping mount.")


    # Catch-all for SPA routing and serving other static files from the main static_dir
    # This needs to be defined *after* specific mounts like /assets
    @app_instance.get("/{full_path:path}", response_model=None) # Disable response model generation
    async def serve_static_or_index(request: Request, full_path: str) -> Union[FileResponse, Response, HTTPException]:
        """Serves static files from static_dir or index.html for SPA routing."""
        state.log.debug(f"Catch-all route received request for full_path: '{full_path}'")
        # Prevent serving files outside the static directory
        if ".." in full_path:
            state.log.warning(f"Attempted directory traversal: '{full_path}'")
            return HTTPException(status_code=404, detail="Not Found")

        # Construct potential path within the main static directory
        file_path = os.path.join(static_dir, full_path)
        state.log.debug(f"Checking for static file at: '{file_path}'")

        # If the exact path is a file, serve it
        if os.path.isfile(file_path):
            state.log.debug(f"Serving static file: '{file_path}'")
            return FileResponse(file_path)

        # If it's not a file, assume SPA routing and serve index.html
        index_path = os.path.join(static_dir, "index.html")
        state.log.debug(f"Path '{full_path}' not found as static file, checking for index.html at '{index_path}'")
        if os.path.isfile(index_path):
            state.log.debug(f"Serving index.html from: '{index_path}'")
            return FileResponse(index_path)
        else:
            # If index.html doesn't exist either, return 404
            state.log.warning(f"index.html not found at '{index_path}'")
            return HTTPException(status_code=404, detail="Not Found")


@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    """Handles SSE connections, sends initial server_info, and streams messages."""
    queue: asyncio.Queue = asyncio.Queue()
    sse_connections.append(queue)
    client_host = request.client.host if request.client else "unknown"
    log.info(f"New SSE connection from {client_host}. Total: {len(sse_connections)}")

    # Send server_info immediately upon connection
    server_info_message = get_server_info() # Use imported function
    try:
        await queue.put(server_info_message)
        log.debug(f"Sent initial server_info to {client_host}")
    except Exception as e:
        log.error(f"Failed to send initial server_info to {client_host}: {e}")
        # Don't necessarily close connection, but log the error

    async def event_generator():
        try:
            while True:
                message = await queue.get()
                if message is None: # Sentinel value to close connection
                    log.info(f"Received None sentinel, closing SSE stream for {client_host}.")
                    break
                log.debug(f"SSE sending to {client_host}: {json.dumps(message)}")
                yield {"event": "mcp_message", "data": json.dumps(message)}
                queue.task_done()
        except asyncio.CancelledError:
            log.info(f"SSE connection from {client_host} cancelled/closed by client.")
        except Exception as e:
            log.error(f"Error in SSE event generator for {client_host}: {e}", exc_info=True)
        finally:
            if queue in sse_connections:
                sse_connections.remove(queue)
            log.info(f"SSE connection from {client_host} closed. Remaining: {len(sse_connections)}")

    return EventSourceResponse(event_generator())

@app.post("/mcp/execute")
async def execute_tool_endpoint(request_body: dict = Body(...)) -> dict:
    """Receives tool execution requests via POST and processes them asynchronously."""
    request_id = request_body.get("request_id", "unknown")
    tool_name = request_body.get("tool_name")
    log.info(f"Received execution request via POST (ID: {request_id}, Tool: {tool_name})")
    if not tool_name:
        log.error("Received execution request without tool_name.")
        raise HTTPException(status_code=400, detail="Missing 'tool_name' in request body")

    # Run processing and SSE push in background
    asyncio.create_task(_process_and_push(request_body))
    # Return immediate acknowledgment
    return {"status": "processing", "request_id": request_id}

async def push_sse_message(message_data: Optional[dict]) -> None:
    """Pushes a message dictionary to all connected SSE clients."""
    if not message_data:
        log.debug("push_sse_message called with None data, skipping.")
        return
    log.info(f"Pushing message to {len(sse_connections)} SSE client(s): {json.dumps(message_data)}")
    # Create a list of tasks to put messages onto queues
    tasks = []
    for queue in sse_connections:
        tasks.append(asyncio.create_task(queue.put(message_data)))

    # Wait for all tasks to complete (or handle exceptions)
    if tasks:
        try:
            await asyncio.gather(*tasks)
            log.debug(f"Successfully pushed message ID {message_data.get('request_id')} to all queues.")
        except Exception as e:
            log.error(f"Error pushing message ID {message_data.get('request_id')} via SSE: {e}", exc_info=True)

async def _process_and_push(request: dict) -> None:
    """Helper to run processing and push result via SSE."""
    # process_tool_request is synchronous, run it directly
    message_to_push = process_tool_request(request) # Use imported function
    # push_sse_message is asynchronous
    await push_sse_message(message_to_push)