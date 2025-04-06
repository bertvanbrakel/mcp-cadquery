#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper script executed within a workspace's virtual environment to run
a CadQuery script with parameter substitution and custom module support.

Reads input configuration (script, params, workspace path) from stdin as JSON.
Adds <workspace_path>/modules to sys.path.
Executes the script using cadquery.cqgi.
Prints the serialized BuildResult (or error info) as JSON to stdout.
"""

import sys
import os
import json
import traceback
import logging
import re
import time # Import the time module
from typing import Dict, Any, List, Optional

# --- Logging Setup (Basic for Runner) ---
# Log errors to stderr so they can be captured by the calling process
logging.basicConfig(
    level=logging.INFO, # Or DEBUG for more verbose runner logs
    format='%(asctime)s - ScriptRunner - %(levelname)s - %(message)s',
    stream=sys.stderr
)
log = logging.getLogger(__name__)

# --- Parameter Substitution Logic (Copied from core.py for standalone execution) ---
def _substitute_parameters(script_lines: List[str], params: Dict[str, Any]) -> List[str]:
    """Substitutes parameters into script lines marked with # PARAM."""
    modified_lines = []
    param_pattern = re.compile(r"^\s*(\w+)\s*=\s*.*#\s*PARAM\s*$")
    log.debug(f"Attempting substitution with params: {params}")
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
            else:
                 log.debug(f"Parameter '{param_name}' found in script but not in provided params.")
        modified_lines.append(line)
    return modified_lines

# --- Main Execution ---
def run():
    log.info("Script runner started.")
    output_result = {"success": False, "results": [], "exception_str": None}

    try:
        # 1. Read input from stdin
        log.info("Reading input JSON from stdin...")
        input_data_str = sys.stdin.read()
        log.debug(f"Received stdin data: {input_data_str[:200]}...")
        if not input_data_str:
            raise ValueError("No input data received from stdin.")
        input_data = json.loads(input_data_str)

        workspace_path = input_data.get("workspace_path")
        script_content = input_data.get("script_content")
        parameters = input_data.get("parameters", {})
        result_id = input_data.get("result_id") # Get result_id from input

        if not result_id:
             raise ValueError("Missing 'result_id' in input.")

        if not workspace_path or not os.path.isdir(workspace_path):
            raise ValueError(f"Invalid or missing 'workspace_path': {workspace_path}")
        if not script_content:
            raise ValueError("Missing 'script_content' in input.")

        log.info(f"Workspace: {workspace_path}")
        log.info(f"Result ID: {result_id}")
        log.info(f"Parameters: {parameters}")

        # 2. Add workspace modules directory to sys.path
        modules_dir = os.path.join(workspace_path, "modules")
        if os.path.isdir(modules_dir):
            log.info(f"Adding modules directory to sys.path: {modules_dir}")
            sys.path.insert(0, modules_dir) # Add to front to prioritize workspace modules
        else:
            log.info(f"Modules directory not found, skipping sys.path modification: {modules_dir}")

        # Ensure the main workspace dir is also importable if needed
        if workspace_path not in sys.path:
             sys.path.insert(0, workspace_path)


        # 3. Perform parameter substitution
        log.info("Performing parameter substitution...")
        original_script_lines = script_content.splitlines()
        modified_script_lines = _substitute_parameters(original_script_lines, parameters)
        modified_script = "\n".join(modified_script_lines)
        log.debug(f"Substituted script:\n{modified_script[:500]}...")

        # 4. Execute the script using cadquery.cqgi
        # IMPORTANT: Need cadquery installed in the workspace venv!
        try:
            import cadquery as cq
            from cadquery import cqgi
        except ImportError as import_err:
             log.error("Failed to import CadQuery. Is it installed in the workspace venv?")
             raise ImportError("CadQuery not found in workspace environment.") from import_err

        log.info("Parsing script with CQGI...")
        model = cqgi.parse(modified_script)
        log.info("Script parsed. Building model...")
        build_result = model.build()
        log.info(f"Model build finished. Success: {build_result.success}")

        # 5. Serialize the result
        output_result["success"] = build_result.success
        if build_result.exception:
            output_result["exception_str"] = traceback.format_exception(
                type(build_result.exception),
                build_result.exception,
                build_result.exception.__traceback__
            )
            # Join the list into a single string for JSON
            output_result["exception_str"] = "".join(output_result["exception_str"])
            log.error(f"Script execution failed:\n{output_result['exception_str']}")

        if build_result.results:
            # Create a directory for this specific result's intermediate files
            # Use the result_id passed from the server handler
            result_files_dir = os.path.join(workspace_path, ".cq_results", result_id)
            os.makedirs(result_files_dir, exist_ok=True)
            log.info(f"Created results directory: {result_files_dir}")

            shapes_to_export = []
            if build_result.results:
                # Handle scripts that show multiple individual shapes/workplanes
                log.info(f"Found {len(build_result.results)} shapes in build_result.results.")
                for i, res in enumerate(build_result.results):
                    # Try getting name from options dict first, fallback to default
                    shape_name = res.options.get('name') if hasattr(res, 'options') and isinstance(res.options, dict) else None
                    shape_name = shape_name or f"shape_{i}"
                    shapes_to_export.append({"name": shape_name, "shape": res.shape})
            elif build_result.first_result and isinstance(build_result.first_result.shape, cq.Assembly):
                # Handle scripts that show a single Assembly object
                log.info("Found Assembly object in build_result.first_result.")
                assembly_name = getattr(build_result.first_result, 'name', None) or "assembly_0"
                shapes_to_export.append({"name": assembly_name, "shape": build_result.first_result.shape})
            else:
                log.warning("No exportable results found in BuildResult.")

            # Export shapes/assemblies and store paths
            for item in shapes_to_export:
                shape_info = {"name": item["name"], "type": type(item["shape"]).__name__}
                try:
                    intermediate_filename = f"{shape_info['name']}.brep"
                    intermediate_filepath = os.path.join(result_files_dir, intermediate_filename)
                    log.info(f"Exporting '{shape_info['name']}' ({shape_info['type']}) to {intermediate_filepath}...")
                    # Export either Assembly or Shape/Workplane
                    shape_to_export = item["shape"]
                    if isinstance(shape_to_export, cq.Assembly):
                        # Convert assembly to compound for export if necessary
                        log.debug("Converting Assembly to Compound for BREP export.")
                        shape_to_export = shape_to_export.toCompound()

                    cq.exporters.export(shape_to_export, intermediate_filepath, exportType='BREP')
                    shape_info["intermediate_path"] = intermediate_filepath # Store the path
                    log.info(f"'{shape_info['name']}' exported successfully.")
                except Exception as export_err:
                    log.exception(f"Failed to export '{shape_info['name']}' to BREP.")
                    shape_info["intermediate_path"] = None
                    shape_info["export_error"] = str(export_err)

                output_result["results"].append(shape_info)
            log.info(f"Processed {len(output_result['results'])} result item(s).")

    except Exception as e:
        log.exception("Error during script execution in runner.") # Log full traceback to stderr
        output_result["success"] = False
        # Format exception for JSON output
        output_result["exception_str"] = "".join(traceback.format_exception(type(e), e, e.__traceback__))

    # 6. Print JSON result to stdout
    log.info("Execution finished. Printing JSON result to stdout.")
    try:
        json_output = json.dumps(output_result, indent=2)
        print(json_output)
    except Exception as json_err:
         # Fallback if JSON serialization fails
         log.exception("Failed to serialize result to JSON.")
         fallback_output = json.dumps({"success": False, "exception_str": f"JSON serialization error: {json_err}\nOriginal error: {output_result.get('exception_str', 'Unknown')}"})
         print(fallback_output)

if __name__ == "__main__":
    run()