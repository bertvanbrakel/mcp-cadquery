#!/usr/bin/env python3
import requests
import json
import time
import uuid
import os
from typing import Optional # Added for type hinting

# --- Configuration ---
MCP_SERVER_URL = "http://127.0.0.1:8000" # Default server address
EXECUTE_ENDPOINT = f"{MCP_SERVER_URL}/mcp/execute"
WORKSPACE_DIR = "my_cq_workspace" # Example workspace directory name

# --- Helper Function ---
def call_mcp_tool(tool_name: str, arguments: dict, workspace_path: Optional[str] = None) -> str:
    """
    Sends a tool execution request to the MCP server via HTTP POST.
    Adds workspace_path to arguments if provided and required by the tool.

    Args:
        tool_name: The name of the tool to execute.
        arguments: A dictionary of arguments for the tool.
        workspace_path: The absolute path to the workspace directory.

    Returns:
        The request_id sent to the server.

    Raises:
        Exception: If the HTTP request fails or the server returns an error status immediately.
    """
    request_id = f"example-{tool_name}-{uuid.uuid4()}"
    # Add workspace_path to arguments if provided and required by the tool
    if workspace_path and tool_name in [
        "execute_cadquery_script", "export_shape", "export_shape_to_svg",
        "scan_part_library", "get_shape_properties", "get_shape_description",
        "save_workspace_module", "install_workspace_package"
    ]:
        # Ensure we don't overwrite if it was already present
        if "workspace_path" not in arguments:
            arguments["workspace_path"] = workspace_path

    payload = {
        "request_id": request_id,
        "tool_name": tool_name,
        "arguments": arguments, # Arguments dict now potentially includes workspace_path
    }
    print(f"\n[Client] Calling tool '{tool_name}' (Request ID: {request_id})")
    # Avoid printing potentially large script content
    print_args = {k: (v[:100] + '...' if isinstance(v, str) and len(v) > 100 else v) for k, v in arguments.items()}
    print(f"[Client] Arguments: {json.dumps(print_args, indent=2)}")


    try:
        response = requests.post(EXECUTE_ENDPOINT, json=payload, timeout=20) # Increased timeout for potential installs
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

# Basic Roof Script (Simple Wedge) - No changes needed
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

# Assembly Script (Imports STEP files from workspace 'shapes' dir)
# Paths are relative to the workspace root where the script runs
assembly_script = """
import cadquery as cq
import os

# Define paths relative to the workspace root where the script runs
# Use absolute paths within the script temporarily for debugging CWD issues
# Assuming the script runner *is* running with CWD = workspace_path
workspace_root = os.getcwd() # Runner's CWD should be the workspace path
shapes_dir = os.path.join(workspace_root, "shapes")
wall_path = os.path.join(shapes_dir, "wall.step")
roof_path = os.path.join(shapes_dir, "roof.step")
print(f"Assembly Script: Looking for wall at: {{wall_path}}") # Add debug print
print(f"Assembly Script: Looking for roof at: {{roof_path}}")

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
    print(f"Using Workspace: {WORKSPACE_DIR}")

    # Define absolute workspace path for the client
    client_workspace_path = os.path.abspath(WORKSPACE_DIR)

    # Ensure workspace directory exists locally (server handles its own checks)
    if not os.path.exists(client_workspace_path):
        print(f"[Client] Creating workspace directory: {client_workspace_path}")
        os.makedirs(client_workspace_path)
    # Ensure standard subdirs exist locally for clarity
    os.makedirs(os.path.join(client_workspace_path, "shapes"), exist_ok=True)
    os.makedirs(os.path.join(client_workspace_path, "modules"), exist_ok=True)
    os.makedirs(os.path.join(client_workspace_path, "part_library"), exist_ok=True)
    os.makedirs(os.path.join(client_workspace_path, ".cq_results"), exist_ok=True) # For intermediate files

    try:
        # --- Optional: Add a custom module ---
        print("\n[Client] Step 0: Saving a custom utility module...")
        util_module_name = "house_utils.py"
        util_module_code = """
def get_wall_dimensions():
    # Example utility function
    return {"width": 50.0, "height": 30.0, "thickness": 5.0}
"""
        call_mcp_tool(
            "save_workspace_module",
            {"module_filename": util_module_name, "module_content": util_module_code},
            workspace_path=client_workspace_path
        )
        time.sleep(0.5) # Allow server time

        # --- Optional: Install a package ---
        # print("\n[Client] Step 0b: Installing 'numpy' package (example)...")
        # call_mcp_tool(
        #     "install_workspace_package",
        #     {"package_name": "numpy"},
        #     workspace_path=client_workspace_path
        # )
        # time.sleep(15) # Allow more time for potential install

        # 1. Generate Wall Part (using the module)
        print("\n[Client] Step 1: Generating Wall Part...")
        # Modify wall script to use the module
        wall_script_mod = """
import cadquery as cq
import house_utils # Import the saved module

dims = house_utils.get_wall_dimensions()
wall = cq.Workplane("XY").box(dims['width'], dims['thickness'], dims['height'])
show_object(wall, name="wall_part")
"""
        req_id_wall = call_mcp_tool(
            "execute_cadquery_script",
            {"script": wall_script_mod},
            workspace_path=client_workspace_path
        )
        result_id_wall = f"{req_id_wall}_0" # Assuming single result set

        # 2. Generate Roof Part
        print("\n[Client] Step 2: Generating Roof Part...")
        req_id_roof = call_mcp_tool(
            "execute_cadquery_script",
            {"script": roof_script},
            workspace_path=client_workspace_path
        )
        result_id_roof = f"{req_id_roof}_0" # Assuming single result set

        # Allow server time to process script executions
        print("[Client] Waiting for parts generation...")
        time.sleep(3) # Adjust sleep time as needed

        # 3. Export Wall Part to STEP (Provide only filename, server saves to workspace shapes dir)
        print("\n[Client] Step 3: Exporting Wall Part...")
        wall_filename = "wall.step"
        call_mcp_tool(
            "export_shape",
            {
                "result_id": result_id_wall,
                "shape_index": 0,
                "filename": wall_filename, # Just the filename
                "format": "STEP"
            },
            workspace_path=client_workspace_path
        )

        # 4. Export Roof Part to STEP (Provide only filename)
        print("\n[Client] Step 4: Exporting Roof Part...")
        roof_filename = "roof.step"
        call_mcp_tool(
            "export_shape",
            {
                "result_id": result_id_roof,
                "shape_index": 0,
                "filename": roof_filename, # Just the filename
                "format": "STEP"
            },
            workspace_path=client_workspace_path
        )

        # Allow server time to process exports
        print("[Client] Waiting for STEP exports...")
        time.sleep(5) # Increased sleep time significantly

        # 5. Run Assembly Script
        print("\n[Client] Step 5: Running Assembly Script...")
        req_id_assembly = call_mcp_tool(
            "execute_cadquery_script",
            {"script": assembly_script},
            workspace_path=client_workspace_path
        )
        result_id_assembly = f"{req_id_assembly}_0" # Assuming single result set

        # Allow server time to process assembly
        print("[Client] Waiting for assembly...")
        time.sleep(3) # Adjust sleep time as needed

        # 6. Get Description of Assembly
        print("\n[Client] Step 6: Getting Assembly Description...")
        call_mcp_tool(
            "get_shape_description",
            {
                "result_id": result_id_assembly,
                "shape_index": 0
            },
            workspace_path=client_workspace_path # Pass workspace for consistency
        )
        # Note: We don't receive the description here in this simple client example

        # 7. Export Assembly SVG Preview (Provide only filename, server saves to workspace render dir)
        print("\n[Client] Step 7: Exporting Assembly SVG...")
        svg_filename = "house_assembly.svg"
        call_mcp_tool(
            "export_shape_to_svg",
            {
                "result_id": result_id_assembly,
                "shape_index": 0,
                "filename": svg_filename # Just the filename
            },
            workspace_path=client_workspace_path
        )
        # Note: We don't receive the SVG URL here in this simple client example

        print("\n--- Example Script Finished ---")
        print(f"Check the workspace directory '{client_workspace_path}' for:")
        print(f"  - ./shapes/{wall_filename}")
        print(f"  - ./shapes/{roof_filename}")
        print(f"  - ./shapes/renders/{svg_filename}") # Assumes default render dir name
        print(f"  - ./modules/{util_module_name}")
        print("Check the server logs for the assembly description.")

    except Exception as e:
        print(f"\n--- Example Script Failed ---")
        print(f"Error: {e}")
