import requests
import json
import time
import uuid
import os

# --- Configuration ---
MCP_SERVER_URL = "http://127.0.0.1:8000" # Default server address
EXECUTE_ENDPOINT = f"{MCP_SERVER_URL}/mcp/execute"
DEFAULT_SHAPES_DIR = "shapes" # Default directory where server saves files if only filename is given
# OUTPUT_DIR = "output" # Directory to save exported files (Now handled by server default)

# --- Helper Function ---
def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    """
    Sends a tool execution request to the MCP server via HTTP POST.

    Args:
        tool_name: The name of the tool to execute.
        arguments: A dictionary of arguments for the tool.

    Returns:
        The request_id sent to the server.

    Raises:
        Exception: If the HTTP request fails or the server returns an error status immediately.
    """
    request_id = f"example-{tool_name}-{uuid.uuid4()}"
    payload = {
        "request_id": request_id,
        "tool_name": tool_name,
        "arguments": arguments,
    }
    print(f"\n[Client] Calling tool '{tool_name}' (Request ID: {request_id})")
    print(f"[Client] Arguments: {json.dumps(arguments, indent=2)}")

    try:
        response = requests.post(EXECUTE_ENDPOINT, json=payload, timeout=10) # 10 second timeout
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        response_data = response.json()
        print(f"[Client] Server immediate response: {response_data}")
        if response_data.get("status") != "processing":
            raise Exception(f"Server did not return 'processing' status: {response_data}")

        return request_id
    except requests.exceptions.RequestException as e:
        print(f"[Client] ERROR: HTTP request failed: {e}")
        raise
    except Exception as e:
        print(f"[Client] ERROR: Failed to call tool '{tool_name}': {e}")
        raise

# --- CadQuery Scripts ---

# Basic Wall Script
wall_script = """
import cadquery as cq

# Parameters (could be substituted by MCP server if needed)
width = 50.0
height = 30.0
thickness = 5.0

# Create wall
wall = cq.Workplane("XY").box(width, thickness, height)

show_object(wall, name="wall_part")
"""

# Basic Roof Script (Simple Wedge)
roof_script = """
import cadquery as cq

# Parameters
width = 50.0
depth = 50.0 # Should match wall width + overhang? Let's make it wider
height = 15.0
thickness = 5.0 # Wall thickness for cutout

# Create roof shape (simple wedge)
roof_points = [
    (0, 0),
    (width, 0),
    (width / 2, height)
]
roof_profile = cq.Workplane("XZ").polyline(roof_points).close()
roof = roof_profile.extrude(depth)

# Center it for easier assembly placement later
roof = roof.translate((-width / 2, -depth / 2, 0))

show_object(roof, name="roof_part")
"""

# Assembly Script (Imports STEP files)
# NOTE: Assumes wall.step and roof.step exist in the server's configured output directory (default: shapes/)
assembly_script = f"""
import cadquery as cq
import os

# Define paths relative to the server's execution context, using the default name
shapes_dir = "{DEFAULT_SHAPES_DIR}"
wall_path = os.path.join(shapes_dir, "wall.step")
roof_path = os.path.join(shapes_dir, "roof.step")

# Check if files exist before importing
if not os.path.exists(wall_path):
    raise FileNotFoundError(f"Wall file not found at {{wall_path}}")
if not os.path.exists(roof_path):
    raise FileNotFoundError(f"Roof file not found at {{roof_path}}")

# Import shapes
wall = cq.importers.importStep(wall_path)
roof = cq.importers.importStep(roof_path)

# Create assembly
assembly = cq.Assembly(name="SimpleHouse")

# Add walls (example: 4 walls forming a rectangle)
# Wall dimensions: width=50, thickness=5, height=30
wall_width = 50.0
wall_thickness = 5.0
wall_center_offset = (wall_width - wall_thickness) / 2.0

assembly.add(wall, name="wall_front", loc=cq.Location(cq.Vector(0, -wall_center_offset, 0)))
assembly.add(wall, name="wall_back", loc=cq.Location(cq.Vector(0, wall_center_offset, 0)))
assembly.add(wall.rotate((0,0,0), (0,0,1), 90), name="wall_left", loc=cq.Location(cq.Vector(-wall_center_offset, 0, 0)))
assembly.add(wall.rotate((0,0,0), (0,0,1), 90), name="wall_right", loc=cq.Location(cq.Vector(wall_center_offset, 0, 0)))

# Add roof
# Roof dimensions: width=50, depth=50, height=15
# Position roof centered on top of walls (height = wall height)
wall_height = 30.0
assembly.add(roof, name="roof", loc=cq.Location(cq.Vector(0, 0, wall_height)))


# Show the final assembly
show_object(assembly, name="house_assembly")
"""

# --- Main Execution Logic ---
if __name__ == "__main__":
    print(f"--- Running MCP Client Example ---")
    print(f"Target Server: {MCP_SERVER_URL}")
    print(f"Expecting server output in directory: '{DEFAULT_SHAPES_DIR}' (or as overridden on server start)")

    # Server now handles directory creation based on its configuration
    # if not os.path.exists(DEFAULT_SHAPES_DIR):
    #     print(f"[Client] Ensuring local directory exists (for clarity): {DEFAULT_SHAPES_DIR}")
    #     os.makedirs(DEFAULT_SHAPES_DIR, exist_ok=True)

    try:
        # 1. Generate Wall Part
        req_id_wall = call_mcp_tool("execute_cadquery_script", {"script": wall_script})
        result_id_wall = f"{req_id_wall}_0" # Assuming single result set

        # 2. Generate Roof Part
        req_id_roof = call_mcp_tool("execute_cadquery_script", {"script": roof_script})
        result_id_roof = f"{req_id_roof}_0" # Assuming single result set

        # Allow server time to process script executions
        print("[Client] Waiting for parts generation...")
        time.sleep(3) # Adjust sleep time as needed

        # 3. Export Wall Part to STEP (Provide only filename, server uses default dir)
        wall_filename = "wall.step"
        call_mcp_tool("export_shape", {
            "result_id": result_id_wall,
            "shape_index": 0,
            "filename": wall_filename, # Just the filename
            "filename": wall_export_path,
            "format": "STEP"
        })

        # 4. Export Roof Part to STEP (Provide only filename, server uses default dir)
        roof_filename = "roof.step"
        call_mcp_tool("export_shape", {
            "result_id": result_id_roof,
            "shape_index": 0,
            "filename": roof_filename, # Just the filename
            "filename": roof_export_path,
            "format": "STEP"
        })

        # Allow server time to process exports
        print("[Client] Waiting for STEP exports...")
        time.sleep(2) # Adjust sleep time as needed

        # 5. Run Assembly Script
        req_id_assembly = call_mcp_tool("execute_cadquery_script", {"script": assembly_script})
        result_id_assembly = f"{req_id_assembly}_0" # Assuming single result set

        # Allow server time to process assembly
        print("[Client] Waiting for assembly...")
        time.sleep(3) # Adjust sleep time as needed

        # 6. Get Description of Assembly
        call_mcp_tool("get_shape_description", {
            "result_id": result_id_assembly,
            "shape_index": 0
        })
        # Note: We don't receive the description here in this simple example

        # 7. Export Assembly SVG Preview (Provide only filename, server saves to its render dir)
        svg_filename = "house_assembly.svg"
        call_mcp_tool("export_shape_to_svg", {
            "result_id": result_id_assembly,
            "shape_index": 0,
            "filename": svg_filename # Just the filename
        })
        # Note: We don't receive the SVG URL here in this simple example

        print("\n--- Example Script Finished ---")
        print(f"Check the server's output directory (default: '{DEFAULT_SHAPES_DIR}') for '{wall_filename}' and '{roof_filename}'.")
        print(f"Check the server's render directory (inside output dir, default: '{DEFAULT_SHAPES_DIR}/{DEFAULT_RENDER_DIR_NAME}') for '{svg_filename}'.")
        print("Check the server logs for the assembly description.")

    except Exception as e:
        print(f"\n--- Example Script Failed ---")
        print(f"Error: {e}")
