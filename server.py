import sys
import json
import logging
import traceback
import uuid
import os
import cadquery as cq
# Submodules are accessed via the main 'cq' import
# import cadquery.cqgi as cqgi
# import cadquery.exporters as exporters
# import cadquery.vis as vis

# --- Logging Setup ---
# Configure logging to stderr for visibility in MCP logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Direct logs to stderr
)
log = logging.getLogger(__name__)

# --- State Management ---
# Simple dictionary to store results from script execution
# Keys will be UUIDs, values will be cadquery.cqgi.BuildResult objects
shape_results = {}

# --- MCP Communication ---

def send_response(response_data):
    """Sends a JSON response to stdout."""
    try:
        response_json = json.dumps(response_data)
        sys.stdout.write(response_json + '\n')
        sys.stdout.flush()
        log.info(f"Sent response: {response_json}")
    except Exception as e:
        log.error(f"Failed to send response: {e}\nData: {response_data}")
        log.error(traceback.format_exc())

def send_error_response(request_id, error_message):
    """Sends a standardized error response."""
    send_response({
        "type": "tool_error",
        "request_id": request_id,
        "error": str(error_message)
    })

# --- Tool Implementations (Placeholders) ---

def handle_execute_cadquery_script(request):
    """Handles the 'execute_cadquery_script' tool request using CQGI."""
    request_id = request.get("request_id", "unknown")
    log.info(f"Received execute_cadquery_script request (ID: {request_id})")

    try:
        args = request.get("arguments", {})
        script_content = args.get("script")
        parameters = args.get("parameters", {}) # Should be a dict

        if not script_content:
            send_error_response(request_id, "Missing 'script' argument.")
            return
        if not isinstance(parameters, dict):
             send_error_response(request_id, "'parameters' argument must be a dictionary (JSON object).")
             return

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

            send_response({
                "type": "tool_result",
                "request_id": request_id,
                "result": {
                    "success": True,
                    "message": message,
                    "result_id": result_id, # Use result_id to refer to the whole result set
                    "shapes_count": num_shapes,
                    "debug_objects_count": num_debug
                }
            })
        else:
            # Handle build failure
            error_msg = f"Script execution failed: {build_result.exception}"
            log.error(error_msg)
            log.error(f"Traceback: {build_result.exception_trace}") # Log full traceback if available
            send_error_response(request_id, error_msg)

    except Exception as e:
        error_msg = f"Error during script execution: {e}"
        log.error(error_msg)
        log.error(traceback.format_exc())
        send_error_response(request_id, error_msg)

def handle_export_shape(request):
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
            send_error_response(request_id, "Missing 'result_id' argument.")
            return
        if not filename:
            send_error_response(request_id, "Missing 'filename' argument.")
            return
        if not isinstance(shape_index, int) or shape_index < 0:
             send_error_response(request_id, "'shape_index' must be a non-negative integer.")
             return
        if not isinstance(export_options, dict):
             send_error_response(request_id, "'options' argument must be a dictionary (JSON object).")
             return

        # --- Retrieve Shape ---
        build_result = shape_results.get(result_id)
        if not build_result:
            send_error_response(request_id, f"Result ID '{result_id}' not found.")
            return
        if not build_result.success:
             send_error_response(request_id, f"Result ID '{result_id}' corresponds to a failed build.")
             return
        if not build_result.results or shape_index >= len(build_result.results):
            send_error_response(request_id, f"Invalid shape_index {shape_index} for result ID '{result_id}'.")
            return

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

        send_response({
            "type": "tool_result",
            "request_id": request_id,
            "result": {
                "success": True,
                "message": f"Shape successfully exported to {filename}.",
                "filename": filename
            }
        })

    except Exception as e:
        error_msg = f"Error during shape export: {e}"
        log.error(error_msg)
        log.error(traceback.format_exc())
        send_error_response(request_id, error_msg)

def handle_render_shape_to_png(request):
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
            send_error_response(request_id, "Missing 'result_id' argument.")
            return
        if not filename:
            send_error_response(request_id, "Missing 'filename' argument.")
            return
        if not filename.lower().endswith(".png"):
             send_error_response(request_id, "'filename' must end with .png")
             return
        if not isinstance(shape_index, int) or shape_index < 0:
             send_error_response(request_id, "'shape_index' must be a non-negative integer.")
             return
        if not isinstance(render_options, dict):
             send_error_response(request_id, "'options' argument must be a dictionary (JSON object).")
             return

        # --- Retrieve Shape ---
        build_result = shape_results.get(result_id)
        if not build_result:
            send_error_response(request_id, f"Result ID '{result_id}' not found.")
            return
        if not build_result.success:
             send_error_response(request_id, f"Result ID '{result_id}' corresponds to a failed build.")
             return
        if not build_result.results or shape_index >= len(build_result.results):
            send_error_response(request_id, f"Invalid shape_index {shape_index} for result ID '{result_id}'.")
            return

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

        send_response({
            "type": "tool_result",
            "request_id": request_id,
            "result": {
                "success": True,
                "message": f"Shape successfully rendered to {filename}.",
                "filename": filename
            }
        })

    except Exception as e:
        error_msg = f"Error during shape rendering: {e}"
        log.error(error_msg)
        log.error(traceback.format_exc())
        send_error_response(request_id, error_msg)


# --- Main Loop ---

def main():
    log.info("MCP CadQuery Server starting...")
    log.info("Reading requests from stdin...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        log.info(f"Received line: {line}")

        try:
            request = json.loads(line)
            request_id = request.get("request_id", "unknown")
            tool_name = request.get("tool_name")

            if tool_name == "execute_cadquery_script":
                handle_execute_cadquery_script(request)
            elif tool_name == "export_shape":
                handle_export_shape(request)
            elif tool_name == "render_shape_to_png":
                handle_render_shape_to_png(request)
            else:
                log.warning(f"Unknown tool requested: {tool_name}")
                send_error_response(request_id, f"Unknown tool: {tool_name}")

        except json.JSONDecodeError:
            log.error(f"Failed to decode JSON: {line}")
            # Cannot send error response if we can't parse request_id
        except Exception as e:
            log.error(f"Error processing request: {e}")
            log.error(traceback.format_exc())
            # Try to send error if request_id was parsed
            request_id = "unknown"
            try:
                request_data = json.loads(line)
                request_id = request_data.get("request_id", "unknown")
            except:
                pass
            send_error_response(request_id, f"Internal server error: {e}")

    log.info("Stdin closed. MCP CadQuery Server shutting down.")

if __name__ == "__main__":
    main()