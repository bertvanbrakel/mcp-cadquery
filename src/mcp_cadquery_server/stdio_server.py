import asyncio
import sys
import json
from typing import Dict, Any, Optional

# Import necessary components from other modules
from .state import log
from .mcp_api import get_server_info, process_tool_request # Import process_tool_request

async def run_stdio_mode() -> None:
    """Runs the server in MCP stdio mode, reading JSON requests from stdin."""
    log.info("Starting server in Stdio mode. Reading from stdin...")

    # Send server_info once at the start for stdio mode
    try:
        server_info_message = get_server_info()
        print(json.dumps(server_info_message), flush=True)
        log.info("Sent server_info via stdout for stdio mode.")
    except Exception as e:
        log.error(f"Failed to generate or send initial server_info in stdio mode: {e}")
        # Send an error message if possible
        error_resp = {"type": "tool_error", "request_id": "server-init-fail", "error": f"Failed to send server_info: {e}"}
        try: print(json.dumps(error_resp), flush=True)
        except: pass # Ignore if print fails

    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    try:
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    except Exception as e:
         log.error(f"Error connecting read pipe for stdin: {e}. Stdio mode may not work.", exc_info=True)
         print(json.dumps({"type": "tool_error", "request_id": "stdio-init-fail", "error": f"Failed to connect stdin: {e}"}), flush=True)
         return # Cannot proceed without stdin

    request_data: Optional[Dict[str, Any]] = None # Define request_data outside loop for error handling scope
    while True:
        try:
            line_bytes = await reader.readline()
            if not line_bytes: break # EOF
            line = line_bytes.decode('utf-8').strip()
            if not line: continue
            log.debug(f"Received stdio line: {line}")
            request_data = json.loads(line) # Assign here
            # Validate basic structure
            if not isinstance(request_data, dict) or "tool_name" not in request_data or "request_id" not in request_data:
                raise ValueError("Invalid MCP request format (missing tool_name or request_id)")

            response = process_tool_request(request_data) # Use imported function
            if response: print(json.dumps(response), flush=True)
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode JSON from stdin: {e}"); error_resp = {"type": "tool_error", "request_id": "unknown", "error": f"Invalid JSON received: {e}"}; print(json.dumps(error_resp), flush=True)
        except ValueError as e: # Catch validation errors
             log.error(f"Invalid request format: {e}")
             req_id = request_data.get("request_id", "unknown") if isinstance(request_data, dict) else "unknown"
             error_resp = {"type": "tool_error", "request_id": req_id, "error": f"Invalid request format: {e}"}; print(json.dumps(error_resp), flush=True)
        except Exception as e:
             log.error(f"Error processing stdio request: {e}", exc_info=True)
             req_id = request_data.get("request_id", "unknown") if isinstance(request_data, dict) else "unknown"
             error_resp = {"type": "tool_error", "request_id": req_id, "error": f"Internal server error: {e}"}; print(json.dumps(error_resp), flush=True)
        except KeyboardInterrupt: log.info("KeyboardInterrupt received, exiting stdio mode."); break
        except Exception as e: log.error(f"Unexpected error in stdio loop: {e}", exc_info=True); await asyncio.sleep(1)