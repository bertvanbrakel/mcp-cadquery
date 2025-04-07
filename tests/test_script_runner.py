#!/usr/bin/env python3
import pytest
import subprocess
import sys
import os
import json
import uuid
import shutil
from typing import Optional, Dict, Any # Added Optional

from unittest.mock import patch, MagicMock

# Add project root to path to allow importing src components if needed indirectly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Path to the script runner executable
SCRIPT_RUNNER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'mcp_cadquery_server', 'script_runner.py'))
# Use the same python interpreter that's running pytest
PYTHON_EXE = sys.executable

@pytest.fixture(scope="function")
def test_workspace(tmp_path_factory):
    """Creates a temporary workspace directory for a test function."""
    ws_path = tmp_path_factory.mktemp("script_runner_ws_")
    print(f"\nCreated test workspace: {ws_path}")
    # Create modules subdir for import tests
    (ws_path / "modules").mkdir(exist_ok=True)
    yield ws_path
    # print(f"Cleaning up test workspace: {ws_path}") # Keep for debugging if needed
    # shutil.rmtree(ws_path) # tmp_path_factory handles cleanup

def run_script_runner(input_data: dict, workspace_path: str, env_vars: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Helper function to run the script_runner.py subprocess."""
    cmd = [PYTHON_EXE, SCRIPT_RUNNER_PATH]
    input_json = json.dumps(input_data)

    # Prepare environment
    run_env = os.environ.copy()
    if env_vars:
        run_env.update(env_vars)

    print(f"Running script runner in: {workspace_path}")
    print(f"Input JSON: {input_json[:200]}...") # Log truncated input

    process = subprocess.run(
        cmd,
        input=input_json,
        capture_output=True,
        text=True,
        check=False,
        encoding='utf-8',
        cwd=workspace_path, # Run from within the workspace
        env=run_env
    )
    print(f"Script runner exited with code: {process.returncode}")
    if process.stdout: print(f"Script runner stdout: {process.stdout.strip()}")
    if process.stderr: print(f"Script runner stderr: {process.stderr.strip()}", file=sys.stderr)
    return process

# --- Test Cases ---

def test_script_runner_success_simple_box(test_workspace):
    """Test a basic successful execution creating a box."""
    script_content = (
        "import cadquery as cq\n"
        "result = cq.Workplane('XY').box(1, 2, 3)\n"
        "show_object(result, name='test_box')"
    )
    request_id = f"test-runner-success-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))

    assert process.returncode == 0, f"Script runner failed unexpectedly. Stderr:\n{process.stderr}"
    try:
        output_json = json.loads(process.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Script runner did not output valid JSON. Stdout:\n{process.stdout}")

    assert output_json["success"] is True
    assert output_json["exception_str"] is None
    assert len(output_json["results"]) == 1
    shape_result = output_json["results"][0]
    assert shape_result["name"] == "test_box"
    assert shape_result["type"] == "Workplane"
    assert "intermediate_path" in shape_result
    # Only check export_error if it exists
    if "export_error" in shape_result:
        assert shape_result["export_error"] is None

    # Check if the intermediate file was created
    expected_brep = test_workspace / ".cq_results" / result_id / "test_box.brep"
    assert expected_brep.is_file(), f"Expected BREP file not found at {expected_brep}"


def test_script_runner_syntax_error(test_workspace):
    """Test script runner handling of Python syntax errors."""
    script_content = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 2,"
    request_id = f"test-runner-syntax-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))

    assert process.returncode == 0 # Runner itself should succeed
    output_json = json.loads(process.stdout)

    assert output_json["success"] is False
    assert "SyntaxError" in output_json["exception_str"]
    assert len(output_json["results"]) == 0

def test_script_runner_cadquery_error(test_workspace):
    """Test script runner handling of CadQuery execution errors."""
    # Script that causes a CadQuery error (e.g., invalid fillet)
    script_content = "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1).edges().fillet(0)\nshow_object(result)"
    request_id = f"test-runner-cq-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))

    assert process.returncode == 0
    output_json = json.loads(process.stdout)

    assert output_json["success"] is False
    assert "OCP.StdFail.StdFail_NotDone" in output_json["exception_str"]
    assert len(output_json["results"]) == 0

def test_script_runner_export_failure(test_workspace):
    """Test script runner handling of shape export errors."""
    script_content = (
        "import cadquery as cq\n"
        "show_object(cq.Workplane('XY').box(1,1,1), name='export_fail_box')"
    )
    request_id = f"test-runner-export-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    # Create a file where the .cq_results directory should be to cause mkdir to fail
    cq_results_path = os.path.join(test_workspace, ".cq_results")
    with open(cq_results_path, "w") as f:
        f.write("block directory creation")

    process = run_script_runner(input_data, str(test_workspace))

    assert process.returncode == 0
    output_json = json.loads(process.stdout)

    assert output_json["success"] is False
    assert "NotADirectoryError" in output_json["exception_str"]
    assert len(output_json["results"]) == 0

def test_script_runner_general_exception(test_workspace):
    """Test script runner handling of unexpected exceptions (lines 20, 22, 199-201)."""
    script_content = "import cadquery as cq\nshow_object(cq.Workplane('XY').box(1,1,1))"
    request_id = f"test-runner-gen-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    # Mock json.loads to fail when reading input
    with patch('json.loads', side_effect=json.JSONDecodeError("Expecting value", "", 0)):
         # Need to run directly, not via helper which uses json.dumps
        cmd = [PYTHON_EXE, SCRIPT_RUNNER_PATH]
        process = subprocess.run(
            cmd,
            input="invalid json", # Pass invalid json
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            cwd=str(test_workspace)
        )

    # Expect runner to fail and print error to stderr
    # Expect runner to succeed (exit code 0) but output a failure JSON
    assert process.returncode == 0
    try:
        output_json = json.loads(process.stdout)
        assert output_json["success"] is False
        assert "JSONDecodeError" in output_json["exception_str"]
        assert "Expecting value" in output_json["exception_str"]
    except json.JSONDecodeError:
        pytest.fail(f"Script runner did not output valid JSON even on expected failure. Stdout:\n{process.stdout}")

# Test coverage startup block (lines 11, 13)
# This is implicitly tested when running under coverage, but we can add
# a specific test to ensure it doesn't crash if coverage is missing.
@patch.dict(os.environ, {"COVERAGE_RUN_SUBPROCESS": "1"})
@patch('builtins.__import__', side_effect=ImportError("No module named 'coverage'"))
def test_script_runner_coverage_import_error(mock_import, test_workspace):
    """Test runner doesn't crash if coverage import fails when requested."""
    script_content = "show_object(None)" # Minimal script
    request_id = f"test-runner-cov-imp-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    # Run without expecting coverage env var to be set by helper
    process = run_script_runner(input_data, str(test_workspace), env_vars={"COVERAGE_RUN_SUBPROCESS": "1"})

    assert process.returncode == 0 # Should still run successfully
    output_json = json.loads(process.stdout)
    assert output_json["success"] is True # Script itself is trivial

def test_script_runner_workspace_import(test_workspace):
    """Test adding workspace path to sys.path (lines 108-111)."""
    # Create a custom module in the workspace root
    ws_module_content = """
def get_test_value():
    return 42
"""
    with open(os.path.join(test_workspace, "ws_module.py"), "w") as f:
        f.write(ws_module_content)

    script_content = """
import ws_module
result = ws_module.get_test_value()
if result != 42:
    raise ValueError("Failed to import workspace module")
"""
    request_id = f"test-runner-ws-import-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))
    assert process.returncode == 0
    output_json = json.loads(process.stdout)
    assert output_json["success"] is True
    assert output_json["exception_str"] is None

def test_script_runner_cqgi_parse_error(test_workspace):
    """Test CQGI parsing errors (lines 120-121, 130-131)."""
    script_content = """
import cadquery as cq
# Invalid CQGI script (no show_object call)
result = cq.Workplane('XY').box(1,1,1)
"""
    request_id = f"test-runner-cqgi-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))
    assert process.returncode == 0
    output_json = json.loads(process.stdout)
    assert output_json["success"] is True  # Parse succeeds but no results
    assert len(output_json["results"]) == 0  # No show_object calls

def test_script_runner_result_dir_creation_error(test_workspace):
    """Test result files directory creation failure (lines 150-151)."""
    script_content = """
import cadquery as cq
result = cq.Workplane('XY').box(1,1,1)
show_object(result, name='test_box')
"""
    request_id = f"test-runner-mkdir-err-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    # Create a file where the .cq_results directory should be to cause mkdir to fail
    cq_results_path = os.path.join(test_workspace, ".cq_results")
    with open(cq_results_path, "w") as f:
        f.write("block directory creation")

    process = run_script_runner(input_data, str(test_workspace))
    assert process.returncode == 0
    output_json = json.loads(process.stdout)
    assert output_json["success"] is False  # Build fails due to directory creation error
    assert "NotADirectoryError" in output_json["exception_str"]
    assert len(output_json["results"]) == 0

def test_script_runner_shape_name_from_options(test_workspace):
    """Test shape name handling from options (lines 160-161)."""
    script_content = """
import cadquery as cq
result = cq.Workplane('XY').box(1,1,1)
show_object(result, options={"name": "custom_name"})
"""
    request_id = f"test-runner-shape-name-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))
    assert process.returncode == 0
    output_json = json.loads(process.stdout)
    assert output_json["success"] is True
    assert len(output_json["results"]) == 1
    shape_result = output_json["results"][0]
    assert shape_result["name"] == "custom_name"  # Name from options

def test_script_runner_assembly_handling(test_workspace):
    """Test assembly handling (lines 170-171, 180-181)."""
    script_content = """
import cadquery as cq

# Create an assembly
base = cq.Workplane('XY').box(10, 10, 1)
pillar = cq.Workplane('XY').box(1, 1, 5)

assy = cq.Assembly()
assy.add(base, name="base")
assy.add(pillar, loc=cq.Location((2, 2, 0.5)), name="pillar")

show_object(assy, name="test_assembly")
"""
    request_id = f"test-runner-assembly-{uuid.uuid4()}"
    result_id = f"{request_id}_0"
    input_data = {
        "workspace_path": str(test_workspace),
        "script_content": script_content,
        "parameters": {},
        "result_id": result_id
    }

    process = run_script_runner(input_data, str(test_workspace))
    assert process.returncode == 0
    output_json = json.loads(process.stdout)
    assert output_json["success"] is True
    assert len(output_json["results"]) == 1
    shape_result = output_json["results"][0]
    assert shape_result["name"] == "test_assembly"
    assert shape_result["type"] == "Assembly"
    assert "intermediate_path" in shape_result
    # Only check export_error if it exists
    if "export_error" in shape_result:
        assert shape_result["export_error"] is None

    # Check if the intermediate file was created
    expected_brep = test_workspace / ".cq_results" / result_id / "test_assembly.brep"
    assert expected_brep.is_file(), f"Expected BREP file not found at {expected_brep}"
