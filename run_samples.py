#!/usr/bin/env python3
import requests
import json
import time
import uuid
import os
import argparse
from typing import Optional, Dict, Any

# --- Configuration ---
MCP_SERVER_URL = "http://127.0.0.1:8000" # Default server address
EXECUTE_ENDPOINT = f"{MCP_SERVER_URL}/mcp/execute"
WORKSPACE_DIR = "sample_house_workspace" # Dedicated workspace for this script
REPORTS_DIR = "reports" # Subdirectory for markdown reports
RENDERS_DIR = "renders" # Subdirectory for SVG renders within the workspace shapes dir
SHAPES_DIR = "shapes"   # Subdirectory for STEP/BREP files

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
    request_id = f"sample-{tool_name}-{uuid.uuid4()}"
    # Add workspace_path to arguments if provided and required by the tool
    # List of tools known to require workspace_path
    workspace_tools = [
        "execute_cadquery_script", "export_shape", "export_shape_to_svg",
        "scan_part_library", "get_shape_properties", "get_shape_description",
        "save_workspace_module", "install_workspace_package"
    ]
    if workspace_path and tool_name in workspace_tools:
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
        # Increased timeout for potentially long script executions or installs
        response = requests.post(EXECUTE_ENDPOINT, json=payload, timeout=60)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        response_data = response.json()
        print(f"[Client] Server immediate response: {response_data}")
        if response_data.get("status") != "processing":
            # Handle potential immediate errors more gracefully
            error_details = response_data.get("details", "No details provided.")
            raise Exception(f"Server returned status '{response_data.get('status', 'N/A')}' instead of 'processing'. Details: {error_details}")

        return request_id
    except requests.exceptions.Timeout:
        print(f"[Client] ERROR: Request timed out calling tool '{tool_name}'.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"[Client] ERROR: HTTP request failed: {e}")
        # Attempt to get more details from the response if available
        try:
            error_response = e.response.json() if e.response else None
            if error_response:
                print(f"[Client] Server Error Response: {json.dumps(error_response, indent=2)}")
        except json.JSONDecodeError:
            print(f"[Client] Server Error Response (non-JSON): {e.response.text if e.response else 'No response body'}")
        raise
    except Exception as e:
        print(f"[Client] ERROR: Failed to call tool '{tool_name}': {e}")
        raise
# --- Color Parsing Helper ---
def parse_color_string(color_str: str) -> tuple[float, ...]:
    """Parses a comma-separated string into a tuple of floats."""
    try:
        parts = [float(p.strip()) for p in color_str.split(',')]
        if len(parts) < 3 or len(parts) > 4:
            raise ValueError("Color string must have 3 (RGB) or 4 (RGBA) components.")
        # Clamp values between 0.0 and 1.0
        return tuple(max(0.0, min(1.0, p)) for p in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid color format '{color_str}'. Use comma-separated floats (e.g., '0.8,0.7,0.6'). Error: {e}")


# --- CadQuery Part Scripts ---

# Note: Parameters like dimensions and colors will be passed into the script execution context later.
# For now, we define them within the scripts for simplicity.

# --- Wall Script ---
wall_script = """
import cadquery as cq

# Parameters (will be injected later)
width = 100.0
height = 60.0
thickness = 10.0
color = (0.8, 0.7, 0.6) # Beige-ish

wall = cq.Workplane("XY").box(width, thickness, height)

# Add color
wall_colored = wall.val().located(cq.Location(cq.Vector(0,0,0))) # Ensure it's a Solid for coloring
wall_colored.color = cq.Color(*color)

show_object(wall_colored, name="wall_part")
"""

# --- Window Script ---
window_script = """
import cadquery as cq

# Parameters
width = 30.0
height = 40.0
frame_thickness = 3.0
pane_thickness = 1.0
frame_color = (0.4, 0.3, 0.2) # Brown
pane_color = (0.8, 0.9, 1.0, 0.5) # Light blue, semi-transparent

# Create frame
frame_outer = cq.Workplane("XY").box(width, frame_thickness, height)
frame_inner_cut = cq.Workplane("XY").box(width - 2 * frame_thickness, frame_thickness + 1, height - 2 * frame_thickness) # Cut slightly deeper
frame = frame_outer.cut(frame_inner_cut)

# Create pane
pane = cq.Workplane("XY").box(width - 2 * frame_thickness, pane_thickness, height - 2 * frame_thickness)

# Assemble window
window_assembly = cq.Assembly()
frame_colored = frame.val().located(cq.Location())
frame_colored.color = cq.Color(*frame_color)
pane_colored = pane.val().located(cq.Location(cq.Vector(0, (frame_thickness - pane_thickness) / 2.0, 0))) # Center pane in frame depth
pane_colored.color = cq.Color(*pane_color)

window_assembly.add(frame_colored, name="window_frame")
window_assembly.add(pane_colored, name="window_pane")

show_object(window_assembly, name="window_part")
"""

# --- Door Script ---
door_script = """
import cadquery as cq

# Parameters
width = 40.0
height = 55.0
thickness = 4.0
color = (0.6, 0.4, 0.2) # Darker wood

door = cq.Workplane("XY").box(width, thickness, height)

# Add color
door_colored = door.val().located(cq.Location())
door_colored.color = cq.Color(*color)

show_object(door_colored, name="door_part")
"""

# --- Door Handle Script ---
door_handle_script = """
import cadquery as cq

# Parameters
handle_radius = 1.0
shaft_radius = 0.5
shaft_length = 5.0
color = (0.8, 0.8, 0.1) # Brass

handle = cq.Workplane("YZ").sphere(handle_radius)
shaft = cq.Workplane("YZ").cylinder(shaft_length, shaft_radius).translate((0, 0, -shaft_length / 2)) # Center shaft base at origin

door_handle = handle.union(shaft)

# Add color
handle_colored = door_handle.val().located(cq.Location())
handle_colored.color = cq.Color(*color)

show_object(handle_colored, name="door_handle_part")
"""

# --- Roof Script ---
roof_script = """
import cadquery as cq

# Parameters
width = 110.0 # Slightly wider than wall
depth = 110.0 # Slightly deeper than wall thickness
height = 30.0
thickness = 5.0
color = (0.7, 0.2, 0.2) # Red-ish

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

# Add color
roof_colored = roof.val().located(cq.Location())
roof_colored.color = cq.Color(*color)

show_object(roof_colored, name="roof_part")
"""

# --- Base Script ---
base_script = """
import cadquery as cq

# Parameters
length = 150.0
width = 150.0
thickness = 5.0
color = (0.2, 0.6, 0.2) # Green

base = cq.Workplane("XY").box(length, width, thickness).translate((0, 0, -thickness / 2)) # Center top at Z=0

# Add color
base_colored = base.val().located(cq.Location())
base_colored.color = cq.Color(*color)

show_object(base_colored, name="base_part")
"""


# --- Main Execution Logic ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate CadQuery house parts and assembly using MCP server.")
    # --- Add Command Line Arguments ---
    parser.add_argument('--house-length', type=float, default=100.0, help='Length of the house (X dimension)')
    parser.add_argument('--house-width', type=float, default=100.0, help='Width of the house (Y dimension)')
    parser.add_argument('--wall-height', type=float, default=60.0, help='Height of the walls')
    parser.add_argument('--roof-height', type=float, default=30.0, help='Height of the roof peak')
    # Colors as comma-separated strings for easier CLI input
    parser.add_argument('--wall-color', type=str, default="0.8,0.7,0.6", help='Wall color (R,G,B) e.g., "0.8,0.7,0.6"')
    parser.add_argument('--roof-color', type=str, default="0.7,0.2,0.2", help='Roof color (R,G,B) e.g., "0.7,0.2,0.2"')
    # Add other part dimensions/colors if needed later
    args = parser.parse_args()

    # --- Parse Colors ---
    try:
        parsed_wall_color = parse_color_string(args.wall_color)
        parsed_roof_color = parse_color_string(args.roof_color)
        # Add parsing for other colors if arguments are added
    except argparse.ArgumentTypeError as e:
        parser.error(str(e)) # Exit if color parsing fails

    print(f"--- Using Parameters ---")
    print(f"  House Length: {args.house_length}, House Width: {args.house_width}")
    print(f"  Wall Height: {args.wall_height}, Roof Height: {args.roof_height}")
    print(f"  Wall Color: {parsed_wall_color}, Roof Color: {parsed_roof_color}")

    print(f"--- Running MCP CadQuery Sample House Generator ---")
    print(f"Target Server: {MCP_SERVER_URL}")
    print(f"Using Workspace: {WORKSPACE_DIR}")

    # Define absolute workspace path for the client
    client_workspace_path = os.path.abspath(WORKSPACE_DIR)
    client_reports_path = os.path.join(client_workspace_path, REPORTS_DIR)
    # Renders will be placed inside the workspace's shapes directory by the server tool
    server_renders_path = os.path.join(SHAPES_DIR, RENDERS_DIR) # Relative path used in export tool
    server_shapes_path = SHAPES_DIR # Relative path used in export tool

    # Ensure workspace and report directories exist locally
    print(f"[Client] Ensuring workspace directory exists: {client_workspace_path}")
    os.makedirs(client_workspace_path, exist_ok=True)
    print(f"[Client] Ensuring reports directory exists: {client_reports_path}")
    os.makedirs(client_reports_path, exist_ok=True)
    # Server handles creation of shapes/renders dirs within the workspace

    # Ensure standard subdirs expected by server exist within workspace
    os.makedirs(os.path.join(client_workspace_path, "modules"), exist_ok=True)
    os.makedirs(os.path.join(client_workspace_path, "part_library"), exist_ok=True)
    os.makedirs(os.path.join(client_workspace_path, ".cq_results"), exist_ok=True) # For intermediate files
    os.makedirs(os.path.join(client_workspace_path, SHAPES_DIR), exist_ok=True)
    os.makedirs(os.path.join(client_workspace_path, server_renders_path), exist_ok=True) # Ensure render subdir exists


    try:
        # --- Define Parts and Scripts (using f-strings for parameter injection) ---
        # Note: Base, Window, Door, Handle scripts currently use hardcoded values.
        # Modify them similarly if parameterization is needed.
        parameterized_wall_script = f"""
import cadquery as cq

# Parameters (injected)
width = {args.house_length} # Use house_length for the main wall dimension
height = {args.wall_height}
thickness = 10.0 # Keep thickness hardcoded for now, or add arg
color = {parsed_wall_color}

wall = cq.Workplane("XY").box(width, thickness, height)
wall_colored = wall.val().located(cq.Location(cq.Vector(0,0,0)))
wall_colored.color = cq.Color(*color)
show_object(wall_colored, name="wall_part")
"""

        parameterized_roof_script = f"""
import cadquery as cq

# Parameters (injected)
width = {args.house_length + 10.0} # Slightly wider than house length
depth = {args.house_width + 10.0} # Slightly deeper than house width
height = {args.roof_height}
thickness = 5.0 # Keep hardcoded or add arg
color = {parsed_roof_color}

roof_points = [(0, 0), (width, 0), (width / 2, height)]
roof_profile = cq.Workplane("XZ").polyline(roof_points).close()
roof = roof_profile.extrude(depth)
roof = roof.translate((-width / 2, -depth / 2, 0)) # Center it
roof_colored = roof.val().located(cq.Location())
roof_colored.color = cq.Color(*color)
show_object(roof_colored, name="roof_part")
"""

        # Base script needs parameterization too if house size changes significantly
        parameterized_base_script = f"""
import cadquery as cq

# Parameters (injected)
length = {args.house_length + 50.0} # Make base larger than house footprint
width = {args.house_width + 50.0}
thickness = 5.0
color = (0.2, 0.6, 0.2) # Green

base = cq.Workplane("XY").box(length, width, thickness).translate((0, 0, -thickness / 2))
base_colored = base.val().located(cq.Location())
base_colored.color = cq.Color(*color)
show_object(base_colored, name="base_part")
"""

        part_scripts = {
            "wall": parameterized_wall_script,
            "window": window_script, # Keep non-parameterized for now
            "door": door_script,     # Keep non-parameterized for now
            "door_handle": door_handle_script, # Keep non-parameterized for now
            "roof": parameterized_roof_script,
            "base": parameterized_base_script,
        }
        part_results = {} # Dict to store execution results: {"part_name": "result_id"}
        part_renders = {} # Dict to store render filenames: {"part_name": "render.svg"}
        part_exports = {} # Dict to store export filenames: {"part_name": "part.step"}

        # --- Step 1: Generate Parts ---
        print("\n[Client] Step 1: Generating Parts...")
        for part_name, script_code in part_scripts.items():
            print(f"  - Generating {part_name}...")
            try:
                req_id = call_mcp_tool(
                    "execute_cadquery_script",
                    {"script": script_code},
                    workspace_path=client_workspace_path
                )
                # Assuming the first object shown is the one we want
                part_results[part_name] = f"{req_id}_0"
                print(f"    > Submitted. Result ID (expected): {part_results[part_name]}")
                time.sleep(1) # Small delay between requests
            except Exception as e:
                print(f"    > FAILED to submit {part_name} generation: {e}")
                # Decide if we should continue or raise the exception
                raise # Stop execution if a part fails to generate

        # Allow server time to process script executions
        print("[Client] Waiting for parts generation to complete...")
        time.sleep(5) # Adjust sleep time as needed based on server performance

        # --- Step 2: Render Parts to SVG ---
        print("\n[Client] Step 2: Rendering Parts to SVG...")
        for part_name, result_id in part_results.items():
            if not result_id: # Skip if generation failed
                print(f"  - Skipping rendering for {part_name} (no result ID)")
                continue
            print(f"  - Rendering {part_name}...")
            svg_filename = f"{part_name}.svg"
            # The server prepends the workspace path, so provide the relative path within the workspace
            relative_render_path = os.path.join(server_renders_path, svg_filename)
            try:
                call_mcp_tool(
                    "export_shape_to_svg",
                    {
                        "result_id": result_id,
                        "shape_index": 0, # Assuming the main part is the first shape
                        "filename": relative_render_path, # Relative path within workspace
                        # Add optional render options if needed, e.g.:
                        # "opt": {"width": 200, "height": 150, "marginLeft": 10}
                    },
                    workspace_path=client_workspace_path
                )
                part_renders[part_name] = relative_render_path # Store relative path for report
                print(f"    > Submitted SVG export request for {relative_render_path}")
                time.sleep(1) # Small delay between requests
            except Exception as e:
                print(f"    > FAILED to submit {part_name} SVG export: {e}")
                # Continue rendering other parts even if one fails? For now, let's continue.
                # If rendering is critical, add 'raise' here.

        # Allow server time to process SVG exports
        print("[Client] Waiting for SVG rendering to complete...")
        time.sleep(5) # Adjust as needed
        # These dictionaries are populated in steps 2 and 4 respectively.
        # Ensure they are not re-initialized here.

        # --- Step 3: Generate Markdown Report ---
        print("\n[Client] Step 3: Generating Markdown Report...")
        report_filename = os.path.join(client_reports_path, "sample_house_report.md")
        print(f"  - Writing report to: {report_filename}")
        try:
            with open(report_filename, "w") as f:
                f.write("# Sample House Parts Report\n\n")
                f.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Workspace: `{client_workspace_path}`\n\n")

                # Ensure consistent order for the report
                part_order = ["base", "wall", "window", "door", "door_handle", "roof"]
                for part_name in part_order:
                    if part_name not in part_scripts:
                        continue # Skip if part wasn't defined

                    script_code = part_scripts[part_name]
                    f.write(f"## {part_name.replace('_', ' ').title()} Part\n\n") # e.g., "Wall Part"

                    # Write Code Block
                    f.write("### Code:\n")
                    f.write("```python\n")
                    f.write(script_code.strip() + "\n") # Add stripped code
                    f.write("```\n\n")

                    # Write Render Image
                    f.write("### Render (SVG):\n")
                    render_path = part_renders.get(part_name) # Get relative path from workspace root
                    if render_path:
                        # Calculate relative path from report file to render file
                        # Report is in: client_reports_path (e.g., /abs/path/workspace/reports)
                        # Render is in: client_workspace_path + render_path (e.g., /abs/path/workspace/shapes/renders/part.svg)
                        absolute_render_path = os.path.join(client_workspace_path, render_path)
                        relative_image_path = os.path.relpath(absolute_render_path, client_reports_path)
                        # Ensure forward slashes for Markdown compatibility, even on Windows
                        relative_image_path = relative_image_path.replace(os.sep, '/')
                        f.write(f"![{part_name} Render]({relative_image_path})\n\n")
                    else:
                        f.write("*Render not available.*\n\n")

                    f.write("---\n\n") # Separator

            print(f"  - Report successfully generated.")
        except IOError as e:
            print(f"  > FAILED to write report file: {e}")
            # Decide whether to continue or raise
            raise # Stop if report generation fails

        # --- Step 4: Export Parts for Assembly ---
        print("\n[Client] Step 4: Exporting Parts for Assembly (STEP format)...")
        # Parts needed for the basic assembly: wall, roof, base, door, window, door_handle
        assembly_parts = ["wall", "roof", "base", "door", "window", "door_handle"]
        for part_name in assembly_parts:
            if part_name not in part_results or not part_results[part_name]:
                print(f"  - Skipping STEP export for {part_name} (no result ID)")
                continue
            result_id = part_results[part_name]
            print(f"  - Exporting {part_name} to STEP...")
            step_filename = f"{part_name}.step"
            # Relative path within the workspace shapes directory
            relative_export_path = os.path.join(server_shapes_path, step_filename)
            try:
                call_mcp_tool(
                    "export_shape",
                    {
                        "result_id": result_id,
                        "shape_index": 0, # Assuming the main part is the first shape
                        "filename": relative_export_path, # Relative path within workspace
                        "format": "STEP"
                    },
                    workspace_path=client_workspace_path
                )
                part_exports[part_name] = relative_export_path # Store relative path for assembly script
                print(f"    > Submitted STEP export request for {relative_export_path}")
                time.sleep(1) # Small delay between requests
            except Exception as e:
                print(f"    > FAILED to submit {part_name} STEP export: {e}")
                # If exports are critical for assembly, raise the exception
                raise # Stop execution if export fails

        # Allow server time to process STEP exports
        print("[Client] Waiting for STEP exports to complete...")
        time.sleep(5) # Adjust as needed

        # --- Step 5: Define and Run Assembly Script ---
        print("\n[Client] Step 5: Generating House Assembly...")

        # Define the assembly script - uses relative paths from workspace root and parameters
        # Note: Door/Window/Handle dimensions are still hardcoded in this script.
        # They could be parameterized further if needed.
        parameterized_assembly_script = f"""
import cadquery as cq
import os

# --- Parameters (Injected from client) ---
house_length = {args.house_length}
house_width = {args.house_width}
wall_thickness = 10.0 # Hardcoded, assumed consistent with wall part script
wall_height = {args.wall_height}
# roof_height = {args.roof_height} # Roof geometry is imported, height param not directly used here
# Hardcoded dimensions for door/window/handle (matching their part scripts)
door_width = 40.0
door_height = 55.0
window_width = 30.0
window_height = 40.0
window_sill_height = 15.0
door_handle_offset_x = 15.0
door_handle_offset_z = 25.0

# --- File Paths (Relative to workspace root where script runs) ---
shapes_dir = "{SHAPES_DIR}"
base_path = os.path.join(shapes_dir, "base.step")
wall_path = os.path.join(shapes_dir, "wall.step")
roof_path = os.path.join(shapes_dir, "roof.step")
door_path = os.path.join(shapes_dir, "door.step")
window_path = os.path.join(shapes_dir, "window.step")
door_handle_path = os.path.join(shapes_dir, "door_handle.step")

# --- Import Shapes ---
print("Importing shapes...")
required_files = [base_path, wall_path, roof_path, door_path, window_path, door_handle_path]
for p in required_files:
    if not os.path.exists(p):
        raise FileNotFoundError(f"Assembly Error: Required STEP file not found at {{p}}")
    print(f" - Found: {{p}}")

base = cq.importers.importStep(base_path)
wall_orig = cq.importers.importStep(wall_path) # Original wall before cutouts
roof = cq.importers.importStep(roof_path)
door = cq.importers.importStep(door_path)
window = cq.importers.importStep(window_path)
door_handle = cq.importers.importStep(door_handle_path)
print("Shapes imported successfully.")


# --- Create Assembly ---
assembly = cq.Assembly(name="SimpleHouse")

# Add Base
assembly.add(base, name="base_plane", loc=cq.Location(cq.Vector(0, 0, 0)))

# --- Walls ---
wall_center_offset_x = (house_length - wall_thickness) / 2.0
wall_center_offset_y = (house_width - wall_thickness) / 2.0

# Create cutouts (use hardcoded dimensions for now)
door_cutout = cq.Workplane("XY").box(door_width, wall_thickness + 2, door_height).translate((0, 0, door_height / 2.0))
window_cutout = cq.Workplane("XY").box(window_width, wall_thickness + 2, window_height).translate((0, 0, window_sill_height + window_height / 2.0))

# Front Wall
front_wall_loc = cq.Location(cq.Vector(0, -wall_center_offset_y, wall_height / 2.0))
door_cutout_loc_rel = cq.Vector(0, 0, -(wall_height / 2.0) + door_height / 2.0)
# Position window relative to house length
window_cutout_loc_rel = cq.Vector(house_length / 4.0, 0, -(wall_height / 2.0) + window_sill_height + window_height / 2.0)

# Ensure wall_orig is a valid shape before cutting
if not isinstance(wall_orig, cq.Shape):
    # Attempt to get the solid if it's wrapped, e.g., in a Workplane result
    if hasattr(wall_orig, 'val') and callable(wall_orig.val) and isinstance(wall_orig.val(), cq.Solid):
         wall_solid = wall_orig.val()
    else:
         raise TypeError(f"Imported wall is not a valid Shape or Solid: {{type(wall_orig)}}")
else:
    wall_solid = wall_orig

# Perform cuts
try:
    wall_front_cut = wall_solid.cut(door_cutout.translate(door_cutout_loc_rel))
    wall_front_cut = wall_front_cut.cut(window_cutout.translate(window_cutout_loc_rel))
except Exception as cut_e:
    print(f"Error during wall cutting: {{cut_e}}")
    # Fallback to using the original wall if cutting fails
    wall_front_cut = wall_solid

assembly.add(wall_front_cut, name="wall_front", loc=front_wall_loc)

# Back Wall
assembly.add(wall_solid, name="wall_back", loc=cq.Location(cq.Vector(0, wall_center_offset_y, wall_height / 2.0)))

# Left Wall
assembly.add(wall_solid.rotate((0,0,0), (0,0,1), 90), name="wall_left", loc=cq.Location(cq.Vector(-wall_center_offset_x, 0, wall_height / 2.0)))

# Right Wall
assembly.add(wall_solid.rotate((0,0,0), (0,0,1), 90), name="wall_right", loc=cq.Location(cq.Vector(wall_center_offset_x, 0, wall_height / 2.0)))

# --- Add Door, Window, Handle ---
door_loc = cq.Location(front_wall_loc.vec + door_cutout_loc_rel)
assembly.add(door, name="door", loc=door_loc)

window_loc = cq.Location(front_wall_loc.vec + window_cutout_loc_rel)
assembly.add(window, name="window", loc=window_loc)

handle_relative_loc = cq.Vector(
    -door_width / 2.0 + door_handle_offset_x,
    wall_thickness / 2.0,
    -door_height / 2.0 + door_handle_offset_z
)
handle_final_loc = cq.Location(door_loc.vec + handle_relative_loc, cq.Vector(1,0,0), -90)
assembly.add(door_handle, name="door_handle", loc=handle_final_loc)


# --- Add Roof ---
roof_loc = cq.Location(cq.Vector(0, 0, wall_height))
assembly.add(roof, name="roof", loc=roof_loc)


# --- Show Result ---
print("Assembly complete. Showing object.")
show_object(assembly, name="house_assembly")
"""

        # Execute the assembly script
        try:
            req_id_assembly = call_mcp_tool(
                "execute_cadquery_script",
                {"script": parameterized_assembly_script},
                workspace_path=client_workspace_path
            )
            assembly_result_id = f"{req_id_assembly}_0" # Assuming single result set
            print(f"  > Submitted Assembly. Result ID (expected): {assembly_result_id}")
        except Exception as e:
            print(f"  > FAILED to submit assembly script execution: {e}")
            raise # Stop if assembly fails

        # Allow server time to process assembly
        print("[Client] Waiting for assembly generation...")
        time.sleep(5) # Adjust as needed

        # --- Step 6: Render Assembly to SVG ---
        print("\n[Client] Step 6: Rendering Final Assembly to SVG...")
        assembly_render_filename = None # Initialize
        if assembly_result_id:
            print(f"  - Rendering assembly (Result ID: {assembly_result_id})...")
            svg_filename = "house_assembly.svg"
            relative_render_path = os.path.join(server_renders_path, svg_filename)
            try:
                call_mcp_tool(
                    "export_shape_to_svg",
                    {
                        "result_id": assembly_result_id,
                        "shape_index": 0, # Assuming the assembly is the first shape
                        "filename": relative_render_path, # Relative path within workspace
                        "opt": {"width": 600, "height": 400} # Larger render for assembly
                    },
                    workspace_path=client_workspace_path
                )
                assembly_render_filename = relative_render_path # Store relative path
                print(f"    > Submitted Assembly SVG export request for {relative_render_path}")
                # Allow server time to process the final SVG export
                print("[Client] Waiting for final assembly SVG rendering...")
                time.sleep(5) # Adjust as needed
            except Exception as e:
                print(f"    > FAILED to submit Assembly SVG export: {e}")
                # Continue even if final render fails
        else:
            print("  - Skipping assembly rendering (no assembly result ID).")
        assembly_render_filename = None


        print("\n--- Sample Script Finished Successfully ---")
        print(f"Check the workspace directory '{client_workspace_path}' for:")
        print(f"  - Report: {os.path.relpath(report_filename, os.getcwd())}")
        print(f"  - Part STEP files in: ./{os.path.relpath(os.path.join(client_workspace_path, server_shapes_path), os.getcwd())}")
        print(f"  - Part SVG renders in: ./{os.path.relpath(os.path.join(client_workspace_path, server_renders_path), os.getcwd())}")
        if assembly_render_filename:
             assembly_render_abs_path = os.path.join(client_workspace_path, assembly_render_filename)
             print(f"  - Final Assembly SVG: ./{os.path.relpath(assembly_render_abs_path, os.getcwd())}")
        else:
             print("  - Final Assembly SVG: Not generated (assembly might have failed).")

    except Exception as e:
        print(f"\n--- Sample Script Failed ---")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error: {e}")