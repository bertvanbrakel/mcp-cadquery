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
    metadata = {};
    if not docstring: return metadata
    lines = docstring.strip().split('\n')
    for line in lines:
        line = line.strip(); match = re.match(r'^([\w\s]+):\s*(.*)$', line)
        if match:
            key = match.group(1).strip().lower().replace(' ', '_'); value = match.group(2).strip()
            if key and value:
                 if key == 'tags': metadata[key] = [tag.strip().lower() for tag in value.split(',') if tag.strip()]
                 else: metadata[key] = value
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