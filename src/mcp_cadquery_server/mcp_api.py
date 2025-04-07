from typing import Dict, Any, Optional

# Import necessary components from other modules
from .state import log # Import log from state
from .handlers import tool_handlers # Import tool_handlers from handlers
# Removed import from server to break circular dependency

def get_tool_schemas() -> Dict[str, Dict[str, Any]]:
    """
    Generates input schemas for each tool based on Pydantic models.
    """
    from src.mcp_cadquery_server.models import (
        ExecuteCadqueryScriptArgs,
        ExportShapeArgs,
        ExportShapeToSvgArgs,
        ScanPartLibraryArgs,
        SaveWorkspaceModuleArgs,
        InstallWorkspacePackageArgs,
        SearchPartsArgs,
        GetShapePropertiesArgs,
        GetShapeDescriptionArgs,
    )

    schemas = {
        "execute_cadquery_script": ExecuteCadqueryScriptArgs.schema(),
        "export_shape": ExportShapeArgs.schema(),
        "export_shape_to_svg": ExportShapeToSvgArgs.schema(),
        "scan_part_library": ScanPartLibraryArgs.schema(),
        "save_workspace_module": SaveWorkspaceModuleArgs.schema(),
        "install_workspace_package": InstallWorkspacePackageArgs.schema(),
        "search_parts": SearchPartsArgs.schema(),
        "get_shape_properties": GetShapePropertiesArgs.schema(),
        "get_shape_description": GetShapeDescriptionArgs.schema(),
        "launch_cq_editor": {"type": "object", "properties": {}, "required": []},
    }

    # Ensure all handlers have a schema entry (even if empty)
    # tool_handlers is imported directly now
    for tool_name in tool_handlers:
        if tool_name not in schemas:
            log.warning(f"No schema defined for tool: {tool_name}. Adding empty schema.")
            schemas[tool_name] = {"type": "object", "properties": {}, "required": []}
    return schemas

def get_server_info() -> dict:
    """Constructs the server_info message."""
    # from server import get_tool_schemas # Moved to top-level of this file
    # from .handlers import tool_handlers # Moved to top-level of this file

    server_name = "mcp-cadquery-server"  # TODO: Make configurable?
    server_version = "0.2.0-workspace"  # TODO: Get version dynamically?
    tool_schemas = get_tool_schemas() # Call local function
    tools = []

    for name, handler in tool_handlers.items():
        schema = tool_schemas.get(name, {"type": "object", "properties": {}})
        # Get docstring, strip, and take only the first line
        docstring = getattr(handler, '__doc__', f"Executes the {name} tool.")
        description = docstring.strip().split('\n')[0] if docstring else f"Executes the {name} tool."

        tools.append({
            "name": name,
            "description": description,
            "input_schema": schema
        })

    return {
        "type": "server_info",
        "server_name": server_name,
        "version": server_version,
        "tools": tools,
        "resources": [] # Define if any resources are provided
    }

def process_tool_request(request: dict) -> Optional[dict]:
    """
    Processes a tool request synchronously and returns the message dictionary
    to be sent back (either via SSE or stdio). Returns None if no message should be sent.
    """
    request_id = request.get("request_id", "unknown")
    tool_name = request.get("tool_name")
    result_message: Optional[dict] = None
    error_message: Optional[str] = None
    log.debug(f"Processing tool request (ID: {request_id}, Tool: {tool_name})")
    try:
        handler = tool_handlers.get(tool_name)
        if handler:
            # Execute the handler function associated with the tool_name
            result_message = handler(request)
        else:
            error_message = f"Unknown tool: {tool_name}"
            log.warning(error_message)
    except Exception as e:
        log.error(f"Error processing tool '{tool_name}' (ID: {request_id}): {e}", exc_info=True)
        # Attempt to get a more specific error detail if available (e.g., from HTTPException)
        detail = getattr(e, 'detail', str(e))
        error_message = f"Internal server error processing {tool_name}: {detail}"

    log.debug(f"Tool processing complete (ID: {request_id}). Error: {error_message}, Result: {result_message}")

    # Construct the response message
    message_to_push: Optional[dict] = None
    if error_message:
        message_to_push = {"type": "tool_error", "request_id": request_id, "error": error_message}
    elif result_message is not None: # Ensure result_message is not None before creating result message
         message_to_push = {"type": "tool_result", "request_id": request_id, "result": result_message}
    else:
        # This case might happen if a handler intentionally returns None or has no return value
        log.warning(f"No result or error message generated for request ID: {request_id}, tool: {tool_name}")
        # Optionally send a generic success/no-op message, or just return None
        # Example: message_to_push = {"type": "tool_result", "request_id": request_id, "result": {"success": True, "message": "Operation completed with no specific output."}}

    return message_to_push