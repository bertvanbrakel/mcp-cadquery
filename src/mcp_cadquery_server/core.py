import os
import re
import ast
import logging
from typing import Dict, Any, List, Optional

# Import CadQuery-related libraries directly needed by core functions
import cadquery as cq
from cadquery import cqgi
from cadquery import exporters

log = logging.getLogger(__name__) # Use standard logging

# --- Core Logic Functions (Moved from server.py) ---

def parse_docstring_metadata(docstring: Optional[str]) -> Dict[str, Any]:
    """
    Parses metadata key-value pairs from a Python docstring.

    Looks for lines formatted as 'Key: Value'. Converts keys to lowercase
    snake_case. Handles 'Tags' key specially, splitting by comma.

    Args:
        docstring: The docstring to parse.

    Returns:
        A dictionary containing the parsed metadata.
    """
    metadata = {}
    if not docstring: return metadata
    lines = docstring.strip().split('\n')
    for line in lines:
        line = line.strip()
        if ':' in line:
            parts = line.split(':', 1)
            key_part = parts[0].strip()
            value = parts[1].strip()
            # Check if value is non-empty and original key_part doesn't contain spaces
            # before converting to snake_case and checking isidentifier()
            if value and ' ' not in key_part:
                 key = key_part.lower() # No need for replace if no spaces
                 if key.isidentifier():
                     if key == 'tags':
                         metadata[key] = [tag.strip().lower() for tag in value.split(',') if tag.strip()]
                     else:
                         metadata[key] = value
            # Handle known multi-word keys explicitly (like 'Part Name')
            elif value and key_part.lower() == "part name":
                 metadata["part_name"] = value
            # Add other known multi-word keys here if needed
    return metadata

def execute_cqgi_script(script_content: str) -> cqgi.BuildResult:
    """Parses and executes a CQGI script."""
    log.info("Parsing script with CQGI..."); model = cqgi.parse(script_content)
    log.info("Script parsed."); log.info(f"Building model...")
    # Build without attempting parameter injection via arguments
    build_result = model.build(); log.info(f"Model build finished. Success: {build_result.success}")
    if not build_result.success:
        log.error(f"Script execution failed: {build_result.exception}")
        # Don't raise here, let the caller handle the BuildResult
        # raise Exception(f"Script execution failed: {build_result.exception}")
    return build_result

def _substitute_parameters(script_lines: List[str], params: Dict[str, Any]) -> List[str]:
    """Substitutes parameters into script lines marked with # PARAM."""
    modified_lines = []
    param_pattern = re.compile(r"^\s*(\w+)\s*=\s*.*#\s*PARAM\s*$")
    for line in script_lines:
        match = param_pattern.match(line)
        if match:
            param_name = match.group(1)
            if param_name in params:
                value = params[param_name]
                # Format value as Python literal (basic handling)
                if isinstance(value, str): formatted_value = repr(value)
                elif isinstance(value, (int, float, bool, list, dict, tuple)) or value is None: formatted_value = repr(value)
                else: formatted_value = str(value) # Fallback for other types
                indent = line[:match.start(1)] # Preserve original indentation
                modified_lines.append(f"{indent}{param_name} = {formatted_value} # PARAM (Substituted)")
                log.debug(f"Substituted parameter '{param_name}' with value: {formatted_value}")
                continue # Skip original line
        modified_lines.append(line)
    return modified_lines

def export_shape_to_file(shape_to_export: Any, output_path: str, export_format: Optional[str] = None, export_options: Optional[dict] = None):
     """Exports a CadQuery shape/workplane to a specified file."""
     shape = shape_to_export.val() if isinstance(shape_to_export, cq.Workplane) else shape_to_export
     if not isinstance(shape, cq.Shape): raise TypeError(f"Object to export is not a cq.Shape or cq.Workplane, but {type(shape)}")
     if export_options is None: export_options = {}
     log.info(f"Exporting shape to file '{output_path}' (Format: {export_format or 'Infer'}, Options: {export_options})")
     try:
         output_dir = os.path.dirname(output_path)
         if output_dir: os.makedirs(output_dir, exist_ok=True)
         exporters.export(shape, output_path, exportType=export_format, opt=export_options)
         log.info(f"Shape successfully exported to file '{output_path}'.")
     except Exception as e:
         error_msg = f"Core shape export to file '{output_path}' failed: {e}"
         log.error(error_msg, exc_info=True)
         raise Exception(error_msg) from e

def export_shape_to_svg_file(shape_to_render: Any, output_path: str, svg_opts: dict) -> None:
    """
    Exports a CadQuery shape or Workplane to an SVG file.

    Args:
        shape_to_render: The CadQuery object (Shape or Workplane) to export.
        output_path: The full path to save the SVG file.
        svg_opts: A dictionary of options for cq.exporters.export (SVG specific).

    Raises:
        TypeError: If the object is not a cq.Shape or cq.Workplane.
        Exception: If the export process fails.
    """
    shape = shape_to_render.val() if isinstance(shape_to_render, cq.Workplane) else shape_to_render
    if not isinstance(shape, cq.Shape): raise TypeError(f"Object to export is not a cq.Shape or cq.Workplane, but {type(shape)}")
    log.info(f"Exporting shape to SVG '{output_path}' with options: {svg_opts}")
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        exporters.export(shape, output_path, exportType='SVG', opt=svg_opts)
        log.info(f"Shape successfully exported to SVG '{output_path}'.")
    except Exception as e: error_msg = f"Core SVG export failed: {e}"; log.error(error_msg, exc_info=True); raise Exception(error_msg) from e

def get_shape_properties(shape_to_analyze: Any) -> Dict[str, Any]:
    """
    Calculates various geometric properties of a CadQuery Shape or Workplane.

    Args:
        shape_to_analyze: The CadQuery object (Shape or Workplane) to analyze.

    Returns:
        A dictionary containing properties like 'bounding_box', 'volume',
        'area', 'center_of_mass'. Returns None for properties that cannot
        be calculated.

    Raises:
        TypeError: If the object is not a cq.Shape or cq.Workplane.
        Exception: For errors during property calculation.
    """
    shape = shape_to_analyze.val() if isinstance(shape_to_analyze, cq.Workplane) else shape_to_analyze
    if not isinstance(shape, cq.Shape):
        raise TypeError(f"Object to analyze is not a cq.Shape or cq.Workplane, but {type(shape)}")

    log.info(f"Calculating properties for shape of type {type(shape)}")
    properties = {}
    try:
        # Bounding Box
        try:
            bb = shape.BoundingBox()
            properties['bounding_box'] = {
                'xmin': bb.xmin, 'ymin': bb.ymin, 'zmin': bb.zmin,
                'xmax': bb.xmax, 'ymax': bb.ymax, 'zmax': bb.zmax,
                'xlen': bb.xlen, 'ylen': bb.ylen, 'zlen': bb.zlen,
                'center': {'x': bb.center.x, 'y': bb.center.y, 'z': bb.center.z}
            }
            log.debug(f"Calculated bounding box: {properties['bounding_box']}")
        except Exception as bb_err:
            log.warning(f"Could not calculate bounding box: {bb_err}", exc_info=True)
            properties['bounding_box'] = None

        # Volume
        try:
            properties['volume'] = shape.Volume()
            log.debug(f"Calculated volume: {properties['volume']}")
        except Exception as vol_err:
            # Volume calculation can fail for non-solids (wires, faces, shells)
            log.warning(f"Could not calculate volume (may be expected for non-solids): {vol_err}")
            properties['volume'] = None

        # Area
        try:
            properties['area'] = shape.Area()
            log.debug(f"Calculated area: {properties['area']}")
        except Exception as area_err:
            log.warning(f"Could not calculate area: {area_err}", exc_info=True)
            properties['area'] = None

        # Center of Mass
        try:
            com = shape.Center() # Use Center() which works for more types than CenterOfMass()
            properties['center_of_mass'] = {'x': com.x, 'y': com.y, 'z': com.z}
            log.debug(f"Calculated center of mass: {properties['center_of_mass']}")
        except Exception as com_err:
            log.warning(f"Could not calculate center of mass: {com_err}", exc_info=True)
            properties['center_of_mass'] = None

        # TODO: Add more properties as needed (e.g., inertia, specific checks)

        log.info("Finished calculating shape properties.")
        return properties

    except Exception as e:
        error_msg = f"Core property calculation failed: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg) from e

def get_shape_description(shape_to_describe: Any) -> str:
    """
    Generates a textual description of a CadQuery Shape or Workplane based on
    its geometric properties and type.

    Args:
        shape_to_describe: The CadQuery object (Shape or Workplane) to describe.

    Returns:
        A string describing the shape.

    Raises:
        TypeError: If the object is not a cq.Shape or cq.Workplane.
        Exception: For errors during analysis.
    """
    shape = shape_to_describe.val() if isinstance(shape_to_describe, cq.Workplane) else shape_to_describe
    if not isinstance(shape, cq.Shape):
        raise TypeError(f"Object to describe is not a cq.Shape or cq.Workplane, but {type(shape)}")

    log.info(f"Generating description for shape of type {type(shape)}")
    description_parts = []

    try:
        # 1. Identify Shape Type
        shape_type = shape.ShapeType()
        description_parts.append(f"The object is a {shape_type}.")

        # 2. Get Properties (reuse existing function for consistency)
        properties = get_shape_properties(shape) # Call the existing properties function

        # 3. Add Bounding Box Info
        bb = properties.get('bounding_box')
        if bb:
            description_parts.append(
                f"It occupies a bounding box of size "
                f"{bb['xlen']:.3f} x {bb['ylen']:.3f} x {bb['zlen']:.3f} units."
            )
            description_parts.append(
                f"The geometric center is at ({bb['center']['x']:.3f}, {bb['center']['y']:.3f}, {bb['center']['z']:.3f})."
            )
        else:
            description_parts.append("Bounding box could not be determined.")

        # 4. Add Volume Info (if applicable)
        volume = properties.get('volume')
        if volume is not None: # Check for None, as 0 is a valid volume
             description_parts.append(f"It has a volume of {volume:.3f} cubic units.")
        elif shape_type == "Solid": # Only mention lack of volume if it was expected
             description_parts.append("Volume calculation failed, though it appears to be a solid.")

        # 5. Add Area Info
        area = properties.get('area')
        if area is not None:
            description_parts.append(f"The total surface area is {area:.3f} square units.")
        else:
            description_parts.append("Surface area could not be determined.")

        # 6. Add Center of Mass Info
        com = properties.get('center_of_mass')
        if com:
            # Check if it's significantly different from the geometric center
            if bb and (abs(com['x'] - bb['center']['x']) > 1e-6 or \
                       abs(com['y'] - bb['center']['y']) > 1e-6 or \
                       abs(com['z'] - bb['center']['z']) > 1e-6):
                description_parts.append(
                    f"Its center of mass is located at ({com['x']:.3f}, {com['y']:.3f}, {com['z']:.3f})."
                )
            # Otherwise, it's likely the same as the geometric center already mentioned
        else:
             description_parts.append("Center of mass could not be determined.")

        # 7. Add Counts (Faces, Edges, Vertices)
        try:
            num_faces = len(shape.Faces())
            num_edges = len(shape.Edges())
            num_vertices = len(shape.Vertices())
            description_parts.append(f"It consists of {num_faces} faces, {num_edges} edges, and {num_vertices} vertices.")
        except Exception as count_err:
            log.warning(f"Could not count faces/edges/vertices: {count_err}")
            description_parts.append("Could not determine the count of faces, edges, or vertices.")

        # TODO: Add more sophisticated analysis later if needed (e.g., feature recognition)

        log.info("Finished generating shape description.")
        return " ".join(description_parts)

    except Exception as e:
        error_msg = f"Core description generation failed: {e}"
        log.error(error_msg, exc_info=True)
        raise Exception(error_msg) from e