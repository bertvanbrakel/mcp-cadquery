import typer
import os
import asyncio
import uvicorn
from typing import Optional

# Import necessary components from other modules
from . import state # Import state module
from .web_server import app, configure_static_files # Import FastAPI app and static config
from .stdio_server import run_stdio_mode # Import stdio runner
# Import handlers to ensure they are loaded (though not directly used here)
from . import handlers

# Define the Typer app globally
cli = typer.Typer()

# Define the main command using the global cli
@cli.command()
def main(
    host: str = typer.Option("127.0.0.1", help="Host to bind the server to."),
    port: int = typer.Option(8000, help="Port to run the server on."),
    # Removed output_dir, part_lib_dir as they are workspace-relative now
    static_dir_arg: Optional[str] = typer.Option(
        None, # Default to None
        "--static-dir", "-s",
        help="Path to the static directory for serving a frontend (e.g., frontend/dist). If not provided, frontend serving is disabled.",
        envvar="MCP_STATIC_DIR"
    ),
    mode: str = typer.Option(
        "sse", # Default mode is SSE (HTTP)
        "--mode", "-m",
        help="Server communication mode: 'sse' (HTTP/Server-Sent Events) or 'stdio'.",
        case_sensitive=False, # Allow 'SSE', 'Stdio', etc.
    )
):
    """Main function to start the MCP CadQuery server."""
    # Note: Global path variables like ACTIVE_OUTPUT_DIR_PATH are no longer set here.
    # They are determined within handlers based on the 'workspace_path' argument.
    # Only paths relevant to the server itself (like static files) are set globally.

    # --- Determine Static/Assets Path (if provided) ---
    serve_frontend = False
    if static_dir_arg:
        state.ACTIVE_STATIC_DIR = os.path.abspath(static_dir_arg)
        # Assume assets is always a subdir named 'assets' within the static dir
        state.ACTIVE_ASSETS_DIR_PATH = os.path.join(state.ACTIVE_STATIC_DIR, "assets")
        serve_frontend = True
        state.log.info(f"Static directory for frontend enabled: {state.ACTIVE_STATIC_DIR}")
        # Ensure static/assets dirs exist if specified
        os.makedirs(state.ACTIVE_STATIC_DIR, exist_ok=True)
        if state.ACTIVE_ASSETS_DIR_PATH: os.makedirs(state.ACTIVE_ASSETS_DIR_PATH, exist_ok=True)
        state.log.info(f"Ensured static directory exists: {state.ACTIVE_STATIC_DIR}")
    else:
        state.ACTIVE_STATIC_DIR = None # Explicitly set to None if not provided
        state.ACTIVE_ASSETS_DIR_PATH = None
        state.log.info("No static directory provided, frontend serving disabled.")


    # --- Configure Static Files (Only if serving frontend) ---
    if serve_frontend and state.ACTIVE_STATIC_DIR and state.ACTIVE_ASSETS_DIR_PATH:
        # Configure static files - Render/Preview paths are now workspace-specific.
        # We pass the *default* names for mounting points relative to static root.
        # The actual files live inside workspaces. The frontend needs to handle this.
        state.log.warning("Static file serving enabled, but render/preview paths are now workspace-relative.")
        state.log.warning(f"Mounting default '/{state.DEFAULT_RENDER_DIR_NAME}' and '/{state.DEFAULT_PART_PREVIEW_DIR_NAME}' - actual files must be served separately or via workspace-aware routing.")
        # Use placeholder paths for the function signature, as they aren't used for direct file access here.
        placeholder_render_path = os.path.join(os.getcwd(), state.DEFAULT_RENDER_DIR_NAME)
        placeholder_preview_path = os.path.join(os.getcwd(), state.DEFAULT_PART_PREVIEW_DIR_NAME)
        # configure_static_files is imported from web_server
        configure_static_files(
            app, # Use the imported app instance
            state.ACTIVE_STATIC_DIR,
            state.DEFAULT_RENDER_DIR_NAME, placeholder_render_path,
            state.DEFAULT_PART_PREVIEW_DIR_NAME, placeholder_preview_path,
            state.ACTIVE_ASSETS_DIR_PATH
        )
        state.log.info("Static file serving configured (using default mount points for renders/previews).")
    else:
        state.log.info("Skipping static file configuration.")


    # --- Start Server ---
    mode_lower = mode.lower()
    if mode_lower == "stdio":
        state.log.info("Starting server in stdio mode.")
        # Run the stdio mode handler directly
        asyncio.run(run_stdio_mode()) # Call imported function
    elif mode_lower == "sse":
        state.log.info(f"Starting HTTP/SSE server on {host}:{port}")
        # Run the FastAPI server using uvicorn
        # Pass the app instance imported from web_server
        uvicorn.run(app, host=host, port=port)
    else:
        state.log.error(f"Invalid mode specified: '{mode}'. Must be 'sse' or 'stdio'.")
        raise typer.Exit(code=1)

# Note: The if __name__ == "__main__": block is not needed here,
# as the entry point is handled by the 'mcp-cadquery' script defined in pyproject.toml,
# which points directly to this 'cli' object.