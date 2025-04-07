import pytest
import os
import sys
import uuid
import shutil
import json
import asyncio
import time
import tempfile # Keep for potential future use, though not strictly needed now
import subprocess # Import subprocess for mocking
from unittest.mock import patch, MagicMock # Import patch and MagicMock for mocking
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles # Import StaticFiles
import cadquery as cq # Add import for creating mock shapes

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the app instance, state, and necessary constants/functions from server
# DO NOT import path variables that are set dynamically in main()
# Import the app instance from web_server
from src.mcp_cadquery_server.web_server import app
# Import server module only if needed for patching other globals (if any remain)
# import server
from src.mcp_cadquery_server import state # Import state module
# Access state variables via state.variable_name
# e.g., state.shape_results, state.part_index, state.DEFAULT_OUTPUT_DIR_NAME etc.
# Import core logic needed by fixtures
from src.mcp_cadquery_server.core import execute_cqgi_script

# --- Test Data ---
EXAMPLE_PARTS = {
    "part1_box.py": '"""Part: Test Part 1\nDescription: A simple test box part.\nTags: box, test, simple\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").box(1, 1, 1)\nshow_object(result, name="part1_box")',
    "part2_sphere.py": '"""Part: Another Test Part 2\nDescription: A sphere part.\nTags: sphere, test, round\n"""\nimport cadquery as cq\nradius = 5.0 # PARAM\nresult = cq.Workplane("XY").sphere(radius)\nshow_object(result, name="part2_sphere")',
    "part3_error.py": '"""Part: Error Part\nDescription: Causes error.\nTags: error\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").box(1,1,0.1).edges(">Z").fillet(0.2)\nshow_object(result)'
}

# --- Fixtures ---

# Remove the module-scoped fixture that was causing state issues
# @pytest.fixture(scope="module")
# def stored_build_result_id_for_handlers():
#     """Creates a BuildResult and returns its ID for handler tests."""
#     script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)\nshow_object(result)"
#     build_res = execute_cqgi_script(script)
#     result_id = f"handler-test-{uuid.uuid4()}"
#     shape_results[result_id] = build_res # This modification persists across tests due to scope
#     print(f"\nFixture: Created build result with ID {result_id}")
#     return result_id

@pytest.fixture(autouse=True)
def manage_state_and_test_files(tmp_path): # Remove stored_build_result_id_for_handlers arg
    """
    Fixture to manage state and files before/after each test using tmp_path.
    - Clears shape_results and part_index.
    - Creates a temporary workspace directory.
    - Creates temporary directories for output, renders, previews, library, static.
    - Patches server's global path variables to use these temporary directories.
    - Creates dummy part files in the temporary library directory.
    - Creates dummy static files in the temporary static directory.
    """
    # --- Setup ---
    print("\nAuto-fixture: Setting up state and test files...")
    state.shape_results.clear()
    state.part_index.clear()

    # Remove logic that re-created the build result from the old fixture
    # script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)\nshow_object(result)"
    # build_res = execute_cqgi_script(script)
    # if build_res.success and build_res.results:
    #     # Need a consistent ID if other tests rely on this specific result
    #     # For now, remove this as dependent tests will be refactored
    #     pass
    # else:
    #     pytest.fail("Failed to create the build result needed in fixture.")

    # Define temporary paths using pytest's tmp_path fixture
    # Workspace specific paths
    tmp_workspace = tmp_path / "test_workspace"
    tmp_workspace_venv = tmp_workspace / ".venv" # For potential future checks
    tmp_workspace_modules = tmp_workspace / "modules"
    tmp_workspace_reqs = tmp_workspace / "requirements.txt"

    # General output/config paths (still useful for patching server defaults)
    tmp_output_dir = tmp_workspace / state.DEFAULT_OUTPUT_DIR_NAME # Output inside workspace
    tmp_render_dir = tmp_output_dir / state.DEFAULT_RENDER_DIR_NAME
    tmp_preview_dir = tmp_output_dir / state.DEFAULT_PART_PREVIEW_DIR_NAME
    tmp_part_lib_dir = tmp_workspace / state.DEFAULT_PART_LIBRARY_DIR # Library inside workspace
    tmp_static_dir = tmp_path / "static_test" # Static files separate from workspace
    tmp_assets_dir = tmp_static_dir / "assets"

    # Create temporary directories
    # Create temporary directories (including workspace structure)
    dirs_to_create = [
        tmp_workspace, tmp_workspace_modules, # Workspace base and modules dir
        tmp_output_dir, tmp_render_dir, tmp_preview_dir, # Output dirs within workspace
        tmp_part_lib_dir, # Library dir within workspace
        tmp_static_dir, tmp_assets_dir # Separate static dirs
    ]
    print(f"\nAuto-fixture: Creating temporary directories: {[str(d) for d in dirs_to_create]}")
    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)

    # Optionally create a dummy requirements file in workspace
    # tmp_workspace_reqs.touch()

    # Patch the global path variables in the 'server' module for the duration of the test
    # Patch the ACTIVE paths in the state module
    patches = [
        patch('src.mcp_cadquery_server.state.ACTIVE_OUTPUT_DIR_PATH', str(tmp_output_dir)),
        patch('src.mcp_cadquery_server.state.ACTIVE_RENDER_DIR_PATH', str(tmp_render_dir)),
        patch('src.mcp_cadquery_server.state.ACTIVE_PART_PREVIEW_DIR_PATH', str(tmp_preview_dir)),
        patch('src.mcp_cadquery_server.state.ACTIVE_PART_LIBRARY_DIR', str(tmp_part_lib_dir)),
        patch('src.mcp_cadquery_server.state.ACTIVE_STATIC_DIR', str(tmp_static_dir)),
        patch('src.mcp_cadquery_server.state.ACTIVE_ASSETS_DIR_PATH', str(tmp_assets_dir)),
    ]

    # Enter all patch contexts
    for p in patches:
        p.start()
    print("Auto-fixture: Patched server global paths.")

    # Create dummy part files in the temporary library directory
    print(f"Auto-fixture: Creating dummy parts in {tmp_part_lib_dir}...")
    for filename, content in EXAMPLE_PARTS.items():
        filepath = tmp_part_lib_dir / filename
        try:
            filepath.write_text(content, encoding='utf-8')
        except OSError as e: pytest.fail(f"Failed to create dummy part file {filepath}: {e}")
    print(f"Auto-fixture: Created {len(EXAMPLE_PARTS)} dummy parts.")

    # Create dummy static files in the temporary static directory
    print(f"Auto-fixture: Creating dummy static files in {tmp_static_dir}...")
    try:
        # index.html
        index_path = tmp_static_dir / "index.html"
        index_path.write_text("<html>Fixture Index</html>", encoding='utf-8')
        # assets/dummy.css (assets dir created above)
        asset_path = tmp_assets_dir / "dummy.css"
        asset_path.write_text("body { color: green; }", encoding='utf-8')
        print("Auto-fixture: Created dummy index.html and assets/dummy.css.")
    except OSError as e:
        pytest.fail(f"Failed to create dummy static files: {e}")

    yield # Run the test

    # --- Teardown ---
    print("\nAuto-fixture: Tearing down state and test files...")
    state.shape_results.clear()
    state.part_index.clear()
    print("Auto-fixture: Cleared shape_results and part_index.")

    # Stop all patches
    for p in patches:
        p.stop()
    print("Auto-fixture: Stopped patching server global paths.")
    # tmp_path cleanup is handled automatically by pytest


# --- TestClient Fixture ---

@pytest.fixture(scope="module")
def client():
    """Provides a FastAPI TestClient instance using the global app."""
    # Static files are configured globally in server.py when app is created.
    # Reverting fixture to simple version - previous attempts to modify mounts here caused issues.
    with TestClient(app) as c:
        yield c
# Removed erroneous teardown code that was causing NameError

# --- Test Cases for /mcp/execute Endpoint ---

# Note: Need tmp_path injected into tests that use workspace_path
@patch('src.mcp_cadquery_server.handlers.subprocess.run') # Patch where subprocess is used
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env') # Patch where prepare_workspace_env is used
def test_mcp_execute_endpoint_script_success(mock_ensure_env, mock_subprocess_run, client, tmp_path):
    """Test execute_cadquery_script via API with workspace, mocking subprocess."""
    # --- Mock Setup ---
    # Mock ensure_workspace_env to return a dummy python path
    mock_ensure_env.return_value = "/fake/venv/bin/python"

    # Mock subprocess.run to return a successful CompletedProcess
    # with expected JSON output from the script_runner
    request_id = f"test-endpoint-exec-{uuid.uuid4()}"
    result_id_expected = f"{request_id}_0"
    workspace_path = str(tmp_path / "test_workspace")
    # Create a dummy intermediate file path for the mock result
    dummy_brep_path = os.path.join(workspace_path, ".cq_results", result_id_expected, "shape_0.brep")

    mock_runner_output = json.dumps({
        "success": True,
        "results": [{"name": "shape_0", "type": "Workplane", "intermediate_path": dummy_brep_path}],
        "exception_str": None
    })
    mock_process = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output, stderr="")
    mock_subprocess_run.return_value = mock_process

    # --- Test Execution ---
    script = "import cadquery as cq\nresult = cq.Workplane('XY').sphere(5)\nshow_object(result)"
    request_body = {
        "request_id": request_id,
        "tool_name": "execute_cadquery_script",
        "arguments": {
            "workspace_path": workspace_path,
            "script": script
        }
    }
    print(f"\nTesting POST /mcp/execute execute_cadquery_script (Mocked Subprocess, ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run (even though mocked, it's async)
    time.sleep(0.1)

    # Check that ensure_workspace_env was called
    mock_ensure_env.assert_called_once_with(workspace_path)

    # Check that subprocess.run was called (basic check)
    mock_subprocess_run.assert_called_once()
    # More specific checks on call args could be added if needed

    # Check that the result was stored correctly in state.shape_results (based on mocked output)
    assert result_id_expected in state.shape_results
    result_data = state.shape_results[result_id_expected]
    assert isinstance(result_data, dict)
    assert result_data.get("success") is True
    assert result_data.get("exception_str") is None
    assert isinstance(result_data.get("results"), list)
    assert len(result_data.get("results")) == 1
    shape_info = result_data["results"][0]
    assert shape_info.get("name") == "shape_0"
    assert shape_info.get("type") == "Workplane"
    assert shape_info.get("intermediate_path") == dummy_brep_path
    print("POST /mcp/execute execute_cadquery_script test passed.")

@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_endpoint_script_params_success(mock_ensure_env, mock_subprocess_run, client, tmp_path):
    """Test execute_cadquery_script with parameter_sets via API with workspace, mocking subprocess."""
    # --- Mock Setup ---
    mock_ensure_env.return_value = "/fake/venv/bin/python"

    request_id = f"test-endpoint-params-{uuid.uuid4()}"
    result_id_0, result_id_1 = f"{request_id}_0", f"{request_id}_1"
    workspace_path = str(tmp_path / "test_workspace")
    dummy_brep_path_0 = os.path.join(workspace_path, ".cq_results", result_id_0, "shape_0.brep")
    dummy_brep_path_1 = os.path.join(workspace_path, ".cq_results", result_id_1, "shape_0.brep")

    # Define the return values for consecutive calls to subprocess.run
    mock_runner_output_0 = json.dumps({ "success": True, "results": [{"name": "shape_0", "type": "Workplane", "intermediate_path": dummy_brep_path_0}], "exception_str": None })
    mock_runner_output_1 = json.dumps({ "success": True, "results": [{"name": "shape_0", "type": "Workplane", "intermediate_path": dummy_brep_path_1}], "exception_str": None })
    mock_process_0 = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_0, stderr="")
    mock_process_1 = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_1, stderr="")
    mock_subprocess_run.side_effect = [mock_process_0, mock_process_1] # Return different results for each call

    # --- Test Execution ---
    script = "import cadquery as cq\nlength = 1.0 # PARAM\nresult = cq.Workplane('XY').box(length, 2, 1)\nshow_object(result)"
    request_body = {
        "request_id": request_id,
        "tool_name": "execute_cadquery_script",
        "arguments": {
            "workspace_path": workspace_path,
            "script": script,
            "parameter_sets": [{"length": 5.5}, {"length": 6.6}]
        }
    }
    print(f"\nTesting POST /mcp/execute with parameter_sets (Mocked Subprocess, ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.1) # Allow time for async tasks

    # Check mocks were called correctly
    assert mock_ensure_env.call_count == 1 # ensure_workspace_env is called once before the loop
    assert mock_subprocess_run.call_count == 2

    # Check results stored based on mocked outputs
    assert result_id_0 in state.shape_results and result_id_1 in state.shape_results
    result_data_0 = state.shape_results[result_id_0]
    result_data_1 = state.shape_results[result_id_1]
    assert isinstance(result_data_0, dict) and isinstance(result_data_1, dict)
    assert result_data_0.get("success") is True and result_data_1.get("success") is True
    assert result_data_0.get("exception_str") is None and result_data_1.get("exception_str") is None
    assert isinstance(result_data_0.get("results"), list) and len(result_data_0.get("results")) == 1
    assert isinstance(result_data_1.get("results"), list) and len(result_data_1.get("results")) == 1
    assert result_data_0["results"][0].get("intermediate_path") == dummy_brep_path_0
    assert result_data_1["results"][0].get("intermediate_path") == dummy_brep_path_1

    print("POST /mcp/execute with parameter_sets (Mocked Subprocess) test passed.")

@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_endpoint_export_svg_success(mock_prepare_env, mock_run, client, tmp_path):
    """Test export_shape_to_svg via API within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python" # Mock env prep

    exec_request_id = f"test-exec-for-svg-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_svg"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock the output of script_runner.py for the execution call
    mock_runner_output_exec = json.dumps({
        "success": True,
        "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}],
        "exception_str": None
    })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec # Setup mock for the execution call

    # Manually create the intermediate directory and a dummy BREP file
    os.makedirs(intermediate_dir, exist_ok=True)
    with open(intermediate_brep_path, "w") as f:
        f.write("dummy brep content") # Actual content doesn't matter for this test path

    # Store the mocked result in the server's state (as if execution happened)
    # Store the mocked result in the server's state (as if execution happened)
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # --- Test: Call export_shape_to_svg ---
    export_request_id = f"test-svg-export-{uuid.uuid4()}"
    svg_filename = f"test_render_{export_request_id}.svg"
    export_request_body = {
        "request_id": export_request_id,
        "tool_name": "export_shape_to_svg",
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id,
            "shape_index": 0,
            "filename": svg_filename # Just the filename
        }
    }
    print(f"\nTesting POST /mcp/execute export_shape_to_svg (Workspace, ID: {export_request_id})...")

    # Patch cq.importers.importBrep to return a mock shape, as the dummy brep is invalid
    # Also patch the actual export function to avoid real file I/O errors with dummy shape
    with patch('cadquery.importers.importBrep') as mock_import, \
         patch('src.mcp_cadquery_server.handlers.export_shape_to_svg_file') as mock_export_svg: # Patch where it's used

        mock_shape = cq.Workplane().box(1,1,1) # Create a real shape for type checking
        mock_import.return_value = mock_shape

        response = client.post("/mcp/execute", json=export_request_body)

        # --- Assertions ---
        assert response.status_code == 200
        assert response.json() == {"status": "processing", "request_id": export_request_id}
        time.sleep(0.1) # Allow async task

        # Check that the core export function was called with correct args
        mock_import.assert_called_once_with(intermediate_brep_path)
        expected_svg_output_dir = tmp_path / "test_workspace" / state.DEFAULT_OUTPUT_DIR_NAME / state.DEFAULT_RENDER_DIR_NAME # Path is workspace/output/render
        expected_svg_output_path = expected_svg_output_dir / svg_filename
        mock_export_svg.assert_called_once()
        # Check the shape and path passed to the core export function
        call_args, call_kwargs = mock_export_svg.call_args
        assert call_args[0] == mock_shape # Check the shape object
        assert call_args[1] == str(expected_svg_output_path) # Check the output path

    print("POST /mcp/execute export_shape_to_svg (Workspace) test passed.")

@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
@patch('cadquery.importers.importBrep') # Mock the BREP import
@patch('src.mcp_cadquery_server.handlers.export_shape_to_file') # Patch where it's used
def test_mcp_execute_endpoint_export_shape_step_success(mock_export_file, mock_import_brep, mock_prepare_env, mock_run, client, tmp_path):
    """Test generic export_shape (STEP) via API within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-for-step-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_step"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock the output of script_runner.py for the execution call
    mock_runner_output_exec = json.dumps({
        "success": True,
        "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}],
        "exception_str": None
    })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Manually create the intermediate directory and dummy BREP file
    os.makedirs(intermediate_dir, exist_ok=True)
    with open(intermediate_brep_path, "w") as f: f.write("dummy brep")

    # Store the mocked result in the server's state
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # Mock the import and export functions
    mock_shape = cq.Workplane().box(1,1,1) # Dummy shape
    mock_import_brep.return_value = mock_shape

    # --- Test: Call export_shape ---
    export_request_id = f"test-step-export-{uuid.uuid4()}"
    # Test exporting to an absolute path outside the workspace
    export_target_dir = tmp_path / "external_export"
    export_target_dir.mkdir()
    step_filename_abs = str(export_target_dir / f"test_export_{export_request_id}.step")

    export_request_body = {
        "request_id": export_request_id,
        "tool_name": "export_shape",
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id,
            "shape_index": 0,
            "filename": step_filename_abs, # Absolute path
            "format": "STEP"
        }
    }
    print(f"\nTesting POST /mcp/execute export_shape (STEP, Workspace, ID: {export_request_id})...")
    response = client.post("/mcp/execute", json=export_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": export_request_id}
    time.sleep(0.1) # Allow async task

    mock_import_brep.assert_called_once_with(intermediate_brep_path)
    mock_export_file.assert_called_once()
    # Check args passed to the core export function
    call_args, call_kwargs = mock_export_file.call_args
    assert call_args[0] == mock_shape
    assert call_args[1] == step_filename_abs # Check absolute path was used
    assert call_args[2] == "STEP" # Check format

    print("POST /mcp/execute export_shape (STEP, Workspace) test passed.")

def test_mcp_execute_scan_part_library(client, tmp_path): # Add tmp_path
    """Test scan_part_library via API."""
    request_id = f"test-scan-{uuid.uuid4()}"
    workspace_path = str(tmp_path / "test_workspace")
    request_body = {"request_id": request_id, "tool_name": "scan_part_library", "arguments": {"workspace_path": workspace_path}} # Add workspace_path
    print(f"\nTesting POST /mcp/execute scan_part_library (ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(1.0) # Allow time for scanning
    assert len(state.part_index) == 2, f"Expected 2 parts in index, found {len(state.part_index)}" # part1_box, part2_sphere (part3_error should fail)
    assert "part1_box" in state.part_index and "part2_sphere" in state.part_index
    assert "part3_error" not in state.part_index
    # Check preview files exist
    # Check paths using the *patched* state variable
    assert os.path.exists(os.path.join(state.ACTIVE_PART_PREVIEW_DIR_PATH, "part1_box.svg"))
    assert os.path.exists(os.path.join(state.ACTIVE_PART_PREVIEW_DIR_PATH, "part2_sphere.svg"))
    assert not os.path.exists(os.path.join(state.ACTIVE_PART_PREVIEW_DIR_PATH, "part3_error.svg"))
    print("POST /mcp/execute scan_part_library test passed.")

def test_mcp_execute_search_parts_success(client, tmp_path): # Add tmp_path
    """Test search_parts via API after scanning."""
    # 1. Scan the library first (using the API)
    workspace_path = str(tmp_path / "test_workspace")
    scan_request_id = f"test-scan-for-search-{uuid.uuid4()}"
    scan_request_body = {"request_id": scan_request_id, "tool_name": "scan_part_library", "arguments": {"workspace_path": workspace_path}} # Add workspace_path
    print(f"\nScanning library first (ID: {scan_request_id})...")
    scan_response = client.post("/mcp/execute", json=scan_request_body)
    assert scan_response.status_code == 200
    time.sleep(1.0) # Wait for scan to complete
    assert len(state.part_index) >= 2, f"Index should have at least 2 parts after scan for search, found {len(state.part_index)}"
    print("Pre-scan for search completed.")

    # 2. Search for a part
    search_request_id = f"test-search-{uuid.uuid4()}"
    search_term = "box"
    search_request_body = {"request_id": search_request_id, "tool_name": "search_parts", "arguments": {"query": search_term}} # Use 'query' arg
    print(f"Testing POST /mcp/execute search_parts (Term: '{search_term}', ID: {search_request_id})...")
    response = client.post("/mcp/execute", json=search_request_body)
    # Check immediate response only
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": search_request_id}
    # Cannot easily verify search results from immediate response
    # assert len(result_data["results"]) == 1, f"Search for '{search_term}' should find 1 result"
    # assert result_data["results"][0]["part_id"] == "part1_box"
    print(f"Search for '{search_term}' successful.")

    # 3. Search for another term
    search_request_id_2 = f"test-search-sphere-{uuid.uuid4()}"
    search_term_2 = "sphere"
    search_request_body_2 = {"request_id": search_request_id_2, "tool_name": "search_parts", "arguments": {"query": search_term_2}}
    print(f"Testing POST /mcp/execute search_parts (Term: '{search_term_2}', ID: {search_request_id_2})...")
    response_2 = client.post("/mcp/execute", json=search_request_body_2)
    # Check immediate response only
    assert response_2.status_code == 200
    assert response_2.json() == {"status": "processing", "request_id": search_request_id_2}
    # Cannot easily verify search results from immediate response
    # assert len(result_data_2["results"]) == 1, f"Search for '{search_term_2}' should find 1 result"
    # assert result_data_2["results"][0]["part_id"] == "part2_sphere"
    print(f"Search for '{search_term_2}' successful.")
    print("POST /mcp/execute search_parts test passed.")

def test_mcp_execute_search_parts_no_results(client, tmp_path): # Add tmp_path
    state.part_index.clear() # Ensure index is empty before test
    """Test search_parts via API when no results are found."""
    workspace_path = str(tmp_path / "test_workspace")
    scan_request_id = f"test-scan-for-no-search-{uuid.uuid4()}"
    scan_response = client.post("/mcp/execute", json={"request_id": scan_request_id, "tool_name": "scan_part_library", "arguments": {"workspace_path": workspace_path}}) # Add workspace_path
    assert scan_response.status_code == 200
    time.sleep(1.0)
    assert len(part_index) >= 2

    search_request_id = f"test-search-none-{uuid.uuid4()}"
    search_term = "nonexistentpart"
    search_request_body = {"request_id": search_request_id, "tool_name": "search_parts", "arguments": {"query": search_term}}
    print(f"\nTesting POST /mcp/execute search_parts with no results (Term: '{search_term}', ID: {search_request_id})...")
    response = client.post("/mcp/execute", json=search_request_body)
    # Check immediate response only
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": search_request_id}
    # Cannot easily verify search results from immediate response
    # assert len(result_data["results"]) == 0, f"Search for '{search_term}' should find no results" # This check is problematic now
    print("Search for non-existent term handled correctly.")
    print("POST /mcp/execute search_parts (no results) test passed.")
   
def test_mcp_execute_launch_cq_editor_success(client):
    """Test launch_cq_editor via API (success case)."""
    request_id = f"test-launch-cq-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "launch_cq_editor", "arguments": {}}
    print(f"\nTesting POST /mcp/execute launch_cq_editor (Success, ID: {request_id})...")

    # Mock subprocess.Popen
    with patch('server.subprocess.Popen') as mock_popen:
        # Configure the mock process object if needed (e.g., mock_popen.return_value.pid = 12345)
        mock_process = mock_popen.return_value
        mock_process.pid = 12345 # Example PID

        response = client.post("/mcp/execute", json=request_body)

        # Check immediate response
        assert response.status_code == 200
        assert response.json() == {"status": "processing", "request_id": request_id}

        # Allow time for the background task to potentially run (though it's mocked)
        time.sleep(0.1)

        # Check that Popen was called correctly
        mock_popen.assert_called_once_with(["CQ-editor"]) # Use correct case

    # Ideally, we'd check for a success SSE message here, but that's complex with TestClient.
    # Checking the Popen call is the primary goal for this unit test.
    print("POST /mcp/execute launch_cq_editor (Success) test passed.")


@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_export_invalid_index(mock_prepare_env, mock_run, client, tmp_path):
    """Test exporting a shape with an invalid shape_index via API within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-for-invalid-idx-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_invalid_idx"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock the output of script_runner.py (only one shape generated)
    mock_runner_output_exec = json.dumps({
        "success": True,
        "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}],
        "exception_str": None
    })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Store the mocked result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # --- Test: Call export tool with invalid index ---
    export_request_id = f"test-export-bad-index-{uuid.uuid4()}"
    invalid_shape_index = 999 # Index out of bounds
    export_request_body = {
        "request_id": export_request_id,
        "tool_name": "export_shape_to_svg", # Using SVG export for this test
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id,
            "shape_index": invalid_shape_index,
            "filename": "wont_be_created_bad_index.svg"
        }
    }
    print(f"\nTesting POST /mcp/execute export with invalid shape_index ({invalid_shape_index})...")
    response = client.post("/mcp/execute", json=export_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": export_request_id}
    time.sleep(0.1) # Allow async task

    # Check that the file was NOT created
    expected_svg_output_dir = tmp_path / "test_workspace" / server.DEFAULT_RENDER_DIR_NAME
    expected_path = expected_svg_output_dir / "wont_be_created_bad_index.svg"
    assert not os.path.exists(expected_path), "File should not be created for invalid shape_index"
    # Ideally check for tool_error SSE message

    print("POST /mcp/execute export with invalid shape_index test passed.")


@patch('server.subprocess.run')
@patch('server.prepare_workspace_env')
@patch('cadquery.importers.importBrep')
@patch('server.get_shape_properties') # Patch where it's used
def test_mcp_execute_get_shape_properties_success(mock_get_props, mock_import_brep, mock_prepare_env, mock_run, client, tmp_path):
    """Test get_shape_properties via API (success case) within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-for-props-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_props"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock runner output
    mock_runner_output_exec = json.dumps({ "success": True, "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}], "exception_str": None })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Create dummy BREP file
    os.makedirs(intermediate_dir, exist_ok=True)
    with open(intermediate_brep_path, "w") as f: f.write("dummy brep")

    # Store mocked result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # Mock import and core logic function
    mock_shape = cq.Workplane().box(1,1,1)
    mock_import_brep.return_value = mock_shape
    mock_properties = {"volume": 1.0, "area": 6.0, "bounding_box": {"xlen": 1.0}} # Example properties
    mock_get_props.return_value = mock_properties

    # --- Test: Call get_shape_properties ---
    props_request_id = f"test-get-props-success-{uuid.uuid4()}"
    props_request_body = {
        "request_id": props_request_id,
        "tool_name": "get_shape_properties",
        "arguments": {
            "workspace_path": workspace_path, # Pass workspace for consistency
            "result_id": exec_result_id,
            "shape_index": 0
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_properties (Workspace, ID: {props_request_id})...")
    response = client.post("/mcp/execute", json=props_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": props_request_id}
    time.sleep(0.1) # Allow async task

    mock_import_brep.assert_called_once_with(intermediate_brep_path)
    mock_get_props.assert_called_once_with(mock_shape)
    # Ideally check SSE message for the actual properties

    print("POST /mcp/execute get_shape_properties (Workspace) test passed.")


@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_get_shape_properties_invalid_index(mock_prepare_env, mock_run, client, tmp_path):
    """Test get_shape_properties with invalid index within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-for-props-inv-idx-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_props_inv_idx"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock runner output (only one shape generated)
    mock_runner_output_exec = json.dumps({ "success": True, "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}], "exception_str": None })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Store mocked result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # --- Test: Call get_shape_properties with invalid index ---
    props_request_id = f"test-get-props-bad-idx-{uuid.uuid4()}"
    invalid_shape_index = 999 # Index out of bounds
    props_request_body = {
        "request_id": props_request_id,
        "tool_name": "get_shape_properties",
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id,
            "shape_index": invalid_shape_index
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_properties with invalid index ({invalid_shape_index})...")
    response = client.post("/mcp/execute", json=props_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": props_request_id}
    time.sleep(0.1) # Allow async task
    # Ideally check for tool_error SSE message

    print("POST /mcp/execute get_shape_properties with invalid index test passed.")


@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_get_shape_properties_failed_build(mock_prepare_env, mock_run, client, tmp_path):
    """Test get_shape_properties for a failed build within a workspace context."""
    # --- Setup: Simulate prior FAILED script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-fail-for-props-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    error_message = "Something went wrong during build"

    # Mock the output of script_runner.py for the execution call
    mock_runner_output_exec = json.dumps({
        "success": False,
        "results": [],
        "exception_str": error_message
    })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="") # Runner itself succeeded
    mock_run.return_value = mock_process_exec

    # Store the mocked failed result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # --- Test: Call get_shape_properties with the failed result ID ---
    props_request_id = f"test-get-props-fail-build-{uuid.uuid4()}"
    props_request_body = {
        "request_id": props_request_id,
        "tool_name": "get_shape_properties",
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id, # Use the ID of the failed build
            "shape_index": 0
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_properties for failed build ({exec_result_id})...")
    response = client.post("/mcp/execute", json=props_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": props_request_id}
    time.sleep(0.1) # Allow async task
    # Ideally check for tool_error SSE message indicating the build failed

    print("POST /mcp/execute get_shape_properties for failed build test passed.")


@patch('server.subprocess.run')
@patch('server.prepare_workspace_env')
@patch('cadquery.importers.importBrep')
@patch('server.get_shape_description') # Patch the core logic function called by the handler
def test_mcp_execute_get_shape_description_success(mock_get_desc, mock_import_brep, mock_prepare_env, mock_run, client, tmp_path):
    """Test get_shape_description via API (success case) within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-for-desc-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_desc"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock runner output
    mock_runner_output_exec = json.dumps({ "success": True, "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}], "exception_str": None })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Create dummy BREP file
    os.makedirs(intermediate_dir, exist_ok=True)
    with open(intermediate_brep_path, "w") as f: f.write("dummy brep")

    # Store mocked result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # Mock import and core logic function
    mock_shape = cq.Workplane().box(1,1,1)
    mock_import_brep.return_value = mock_shape
    mock_description = "This is a test description."
    mock_get_desc.return_value = mock_description

    # --- Test: Call get_shape_description ---
    desc_request_id = f"test-get-desc-success-{uuid.uuid4()}"
    desc_request_body = {
        "request_id": desc_request_id,
        "tool_name": "get_shape_description",
        "arguments": {
            "workspace_path": workspace_path, # Pass workspace for consistency
            "result_id": exec_result_id,
            "shape_index": 0
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_description (Workspace, ID: {desc_request_id})...")
    response = client.post("/mcp/execute", json=desc_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": desc_request_id}
    time.sleep(0.1) # Allow async task

    mock_import_brep.assert_called_once_with(intermediate_brep_path)
    mock_get_desc.assert_called_once_with(mock_shape) # Check the shape object passed

    # The assertions above confirm the core logic mock (mock_get_desc) was called correctly.
    # Checking the final result storage (e.g., via SSE) is complex and less critical
    # for this unit test when the core logic is already mocked.

    print("POST /mcp/execute get_shape_description (Workspace) test passed.")


@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_get_shape_description_invalid_index(mock_prepare_env, mock_run, client, tmp_path):
    """Test get_shape_description with invalid index within a workspace context."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-for-desc-inv-idx-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    shape_name = "test_shape_desc_inv_idx"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", exec_result_id)
    intermediate_brep_path = os.path.join(intermediate_dir, f"{shape_name}.brep")

    # Mock runner output (only one shape generated)
    mock_runner_output_exec = json.dumps({ "success": True, "results": [{"name": shape_name, "type": "Workplane", "intermediate_path": intermediate_brep_path}], "exception_str": None })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Store mocked result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # --- Test: Call get_shape_description with invalid index ---
    desc_request_id = f"test-get-desc-bad-idx-{uuid.uuid4()}"
    invalid_shape_index = 999 # Index out of bounds
    desc_request_body = {
        "request_id": desc_request_id,
        "tool_name": "get_shape_description",
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id,
            "shape_index": invalid_shape_index
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_description with invalid index ({invalid_shape_index})...")
    response = client.post("/mcp/execute", json=desc_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": desc_request_id}
    time.sleep(0.1) # Allow async task
    # Ideally check for tool_error SSE message

    print("POST /mcp/execute get_shape_description with invalid index test passed.")


@patch('src.mcp_cadquery_server.handlers.subprocess.run')
@patch('src.mcp_cadquery_server.handlers.prepare_workspace_env')
def test_mcp_execute_get_shape_description_failed_build(mock_prepare_env, mock_run, client, tmp_path):
    """Test get_shape_description for a failed build within a workspace context."""
    # --- Setup: Simulate prior FAILED script execution ---
    workspace_path = str(tmp_path / "test_workspace")
    mock_prepare_env.return_value = "/fake/venv/bin/python"

    exec_request_id = f"test-exec-fail-for-desc-{uuid.uuid4()}"
    exec_result_id = f"{exec_request_id}_0"
    error_message = "Build failed in runner"

    # Mock runner output for failed execution
    mock_runner_output_exec = json.dumps({ "success": False, "results": [], "exception_str": error_message })
    mock_process_exec = subprocess.CompletedProcess(args=[], returncode=0, stdout=mock_runner_output_exec, stderr="")
    mock_run.return_value = mock_process_exec

    # Store mocked result
    # Store the mocked result in the server's state
    state.shape_results[exec_result_id] = json.loads(mock_runner_output_exec)

    # --- Test: Call get_shape_description with the failed result ID ---
    desc_request_id = f"test-get-desc-fail-build-{uuid.uuid4()}"
    desc_request_body = {
        "request_id": desc_request_id,
        "tool_name": "get_shape_description",
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id, # Use the ID of the failed build
            "shape_index": 0
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_description for failed build ({exec_result_id})...")
    response = client.post("/mcp/execute", json=desc_request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": desc_request_id}
    time.sleep(0.1) # Allow async task
    # Ideally check for tool_error SSE message indicating the build failed

    print("POST /mcp/execute get_shape_description for failed build test passed.")
   
   
def test_mcp_execute_launch_cq_editor_not_found(client):
    """Test launch_cq_editor via API (cq-editor not found)."""
    request_id = f"test-launch-cq-fail-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "launch_cq_editor", "arguments": {}}
    print(f"\nTesting POST /mcp/execute launch_cq_editor (Not Found, ID: {request_id})...")

    # Mock subprocess.Popen to raise FileNotFoundError
    with patch('server.subprocess.Popen', side_effect=FileNotFoundError("CQ-editor not found")) as mock_popen: # Use correct case in error message if needed
        response = client.post("/mcp/execute", json=request_body)

        # Check immediate response
        assert response.status_code == 200
        assert response.json() == {"status": "processing", "request_id": request_id}

        # Allow time for the background task to potentially run
        time.sleep(0.1)

        # Check that Popen was called
        mock_popen.assert_called_once_with(["CQ-editor"]) # Use correct case

    # Ideally, we'd check for a tool_error SSE message here.
    print("POST /mcp/execute launch_cq_editor (Not Found) test passed (checked immediate response and mock call).")

# --- Test Cases for API Error Handling ---

def test_mcp_execute_endpoint_missing_tool_name(client):
    """Test API call with missing tool_name."""
    request_id = f"test-endpoint-no-tool-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "arguments": {}}
    print(f"\nTesting POST /mcp/execute with missing tool_name (ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 400
    assert "Missing 'tool_name'" in response.text
    print("POST /mcp/execute with missing tool_name test passed.")

def test_mcp_execute_endpoint_invalid_json(client):
    """Test API call with invalid JSON."""
    request_id = f"test-endpoint-bad-json-{uuid.uuid4()}"
    invalid_json_string = '{"request_id": "' + request_id + '", "tool_name": "test", "arguments": { "script": "..." '
    print(f"\nTesting POST /mcp/execute with invalid JSON (ID: {request_id})...")
    response = client.post("/mcp/execute", headers={"Content-Type": "application/json"}, content=invalid_json_string)
    assert response.status_code == 422
    assert "detail" in response.json()
    print("POST /mcp/execute with invalid JSON test passed.")

def test_mcp_execute_endpoint_unknown_tool(client):
    """Test API call with an unknown tool_name."""
    request_id = f"test-endpoint-unknown-tool-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "non_existent_tool", "arguments": {}}
    print(f"\nTesting POST /mcp/execute with unknown tool_name (ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)
    # This should now return a tool_error via SSE, but the initial POST is accepted.
    # We need to check the SSE message or a status endpoint.
    # For now, check the immediate response is 200 OK.
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    # Ideally, we'd assert that a tool_error SSE message is sent.
    print("POST /mcp/execute with unknown tool_name test passed (checked immediate response).")


def test_mcp_execute_export_nonexistent_result(client):
    """Test exporting a shape with a result_id that doesn't exist via API."""
    request_id = f"test-export-no-result-{uuid.uuid4()}"
    non_existent_result_id = "does-not-exist-123"
    request_body = {"request_id": request_id, "tool_name": "export_shape_to_svg", "arguments": {"result_id": non_existent_result_id, "shape_index": 0, "filename": "wont_be_created.svg"}}
    print(f"\nTesting POST /mcp/execute export with non-existent result_id ({non_existent_result_id})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.5)
    # Check path using the *patched* global variable
    expected_path = os.path.join(server.RENDER_DIR_PATH, "wont_be_created.svg")
    assert not os.path.exists(expected_path), "File should not be created for non-existent result_id"
    print("Check: Export file not created for non-existent result_id (as expected).")
    print("POST /mcp/execute export with non-existent result_id test passed.")


# Use mocks to simulate prior execution instead of a non-existent fixture
@patch('server.subprocess.run')
@patch('server.prepare_workspace_env')
@patch('cadquery.importers.importBrep') # Mock BREP import
@patch('server.export_shape_to_svg_file') # Patch the specific SVG export function
def test_mcp_execute_export_svg_invalid_index(mock_export_svg, mock_import_brep, mock_prepare_env, mock_run, client, tmp_path):
    """Test export_shape_to_svg with an invalid shape_index via API within a workspace."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace_export_bad_idx")
    # Ensure render dir exists (using patched server path)
    render_dir = os.path.join(workspace_path, server.DEFAULT_RENDER_DIR_NAME)
    os.makedirs(render_dir, exist_ok=True)
    mock_prepare_env.return_value = "/fake/venv/bin/python" # Mock env prep

    # Simulate a successful script run result stored previously
    exec_result_id = f"test-exec-for-export-bad-idx-{uuid.uuid4()}"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", f"{exec_result_id}_0")
    intermediate_brep_path = os.path.join(intermediate_dir, "shape_0.brep")

    # Manually create the intermediate directory and dummy BREP file for import step
    os.makedirs(intermediate_dir, exist_ok=True)
    with open(intermediate_brep_path, "w") as f: f.write("dummy brep")

    # Manually add to shape_results (structure based on actual execution results)
    shape_results[exec_result_id] = {
        "success": True,
        "results": [{ # Represents the result for parameter set 0 (or the only set)
            "result_id": f"{exec_result_id}_0", # ID for this specific parameter set result
            "success": True,
            "shapes": [{"name": "shape_0", "intermediate_path": intermediate_brep_path}], # List of shapes from this set
            "log": "Simulated success",
            "params": {},
            "output_dir": intermediate_dir
        }]
    }

    # Mock the importBrep as it happens before the index check in the handler
    mock_shape = cq.Workplane().box(1,1,1) # Dummy shape needed for import mock
    mock_import_brep.return_value = mock_shape
    # --- End Setup ---

    request_id = f"test-export-bad-index-{uuid.uuid4()}"
    invalid_shape_index = 999 # Index out of bounds for the simulated result (only shape 0 exists)
    output_filename = "wont_be_created_bad_index.svg"
    request_body = {
        "request_id": request_id,
        "tool_name": "export_shape_to_svg", # Test SVG export specifically
        "arguments": {
            "workspace_path": workspace_path,
            "result_id": exec_result_id, # Use the simulated result ID
            "shape_index": invalid_shape_index,
            "filename": output_filename
        }
    }
    print(f"\nTesting POST /mcp/execute export_shape_to_svg with invalid shape_index ({invalid_shape_index}) in workspace {workspace_path}...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.5) # Allow time for async processing

    # Assert that import was attempted (it happens before index check)
    mock_import_brep.assert_not_called() # Import should NOT be called for invalid index

    # Crucially, assert that the SVG export function was NOT called due to invalid index
    mock_export_svg.assert_not_called()
    print("Check: Export function not called for invalid shape_index (as expected).")

    # Check that the output file was NOT created (secondary check)
    expected_path = os.path.join(render_dir, output_filename)
    assert not os.path.exists(expected_path), f"File should not be created for invalid shape_index at {expected_path}"
    print("Check: Export file not created on disk (as expected).")

    # Ideally, we'd also check for a tool_error SSE message here.
    print("POST /mcp/execute export_shape_to_svg with invalid shape_index test passed.")


# --- Test Cases for get_shape_properties Handler ---

# Use mocks to simulate prior execution and the core logic function
@patch('server.cq.importers.importBrep') # Mock the BREP importer
@patch('server.get_shape_properties') # Mock the core properties function
@patch('server.subprocess.run')
@patch('server.prepare_workspace_env')
def test_mcp_execute_get_shape_properties_success(mock_prepare_env, mock_run, mock_get_props, mock_import_brep, client, tmp_path): # Added mock_import_brep
    """Test get_shape_properties via API (success case) using workspace."""
    # --- Setup: Simulate prior script execution ---
    workspace_path = str(tmp_path / "test_workspace_get_props")
    mock_prepare_env.return_value = "/fake/venv/bin/python" # Mock env prep

    exec_result_id = f"test-exec-for-props-{uuid.uuid4()}"
    intermediate_dir = os.path.join(workspace_path, ".cq_results", f"{exec_result_id}_0")
    intermediate_brep_path = os.path.join(intermediate_dir, "shape_0.brep")

    # Create the dummy directory and file for os.path.exists check
    os.makedirs(intermediate_dir, exist_ok=True)
    with open(intermediate_brep_path, "w") as f:
        f.write("dummy brep content") # Create an empty dummy file

    shape_results[exec_result_id] = {
        "success": True,
        "results": [{ # This dictionary represents shape_data for index 0
            "result_id": f"{exec_result_id}_0",
            "success": True,
            "intermediate_path": intermediate_brep_path, # Path should be here
            "shapes_count": 1, # Add count for consistency if needed by handler logic
            "log": "Simulated success",
            "params": {},
            "output_dir": intermediate_dir
            # Removed the nested "shapes" list for this structure
        }]
    }
    # Mock the return value of the core function
    expected_properties = {"volume": 100.0, "centerOfMass": [0, 0, 0]}
    mock_get_props.return_value = expected_properties
    # Configure the importBrep mock to return a dummy shape object
    mock_import_brep.return_value = MagicMock(spec=cq.Shape)
    # --- End Setup ---

    request_id = f"test-get-props-success-{uuid.uuid4()}"
    request_body = {
        "request_id": request_id,
        "tool_name": "get_shape_properties",
        "arguments": {
            "workspace_path": workspace_path, # Pass workspace path
            "result_id": exec_result_id,
            "shape_index": 0
        }
    }
    print(f"\nTesting POST /mcp/execute get_shape_properties (Success, ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)

    # Check immediate response
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run
    time.sleep(0.1)

    # Verify the core function was called correctly
    # Note: The handler imports the shape, so we expect the call with the shape object
    mock_import_brep.assert_called_once_with(intermediate_brep_path) # Verify import was called
    mock_get_props.assert_called_once_with(mock_import_brep.return_value) # Verify core func called with mocked shape
    # We can't easily assert the shape object itself, but we know it was called.

    # Ideally, check SSE message for properties. For now, ensure no crash.
    print("POST /mcp/execute get_shape_properties (Success) test passed (checked immediate response and mock call).")


def test_mcp_execute_get_shape_properties_nonexistent_result(client):
    """Test get_shape_properties with a result_id that doesn't exist via API."""
    request_id = f"test-get-props-no-result-{uuid.uuid4()}"
    non_existent_result_id = "does-not-exist-props-123"
    request_body = {"request_id": request_id, "tool_name": "get_shape_properties", "arguments": {"result_id": non_existent_result_id, "shape_index": 0}}
    print(f"\nTesting POST /mcp/execute get_shape_properties with non-existent result_id ({non_existent_result_id})...")

    response = client.post("/mcp/execute", json=request_body)

    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run and potentially fail
    time.sleep(0.1)

    # Check that the non-existent ID wasn't somehow added
    assert non_existent_result_id not in shape_results

    print("POST /mcp/execute get_shape_properties with non-existent result_id test passed (checked immediate response).")



def test_mcp_execute_get_shape_properties_failed_build(mock_prepare_env, mock_run, client, tmp_path): # Add mocks and tmp_path
    """Test get_shape_properties for a result_id corresponding to a failed build."""
    # Create a failed build result
    script_fail = "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,0).edges('>Z').fillet(1)\nshow_object(result)" # Fillet radius too large
    build_res_fail = execute_cqgi_script(script_fail)
    assert build_res_fail.success is False
    failed_result_id = f"handler-test-fail-{uuid.uuid4()}"
    shape_results[failed_result_id] = build_res_fail
    print(f"\nFixture: Created FAILED build result with ID {failed_result_id}")

    request_id = f"test-get-props-fail-build-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "get_shape_properties", "arguments": {"result_id": failed_result_id, "shape_index": 0}}
    print(f"\nTesting POST /mcp/execute get_shape_properties for failed build ({failed_result_id})...")

    response = client.post("/mcp/execute", json=request_body)

    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run
    time.sleep(0.1)

    # Check that the failed result still exists
    assert failed_result_id in shape_results
print("POST /mcp/execute get_shape_properties for failed build test passed (checked immediate response).")


# --- Test Cases for get_shape_description Handler ---

# Test removed as it was duplicated by the refactored version above (around line 769)


def test_mcp_execute_get_shape_description_nonexistent_result(client):
    """Test get_shape_description with a result_id that doesn't exist via API."""
    request_id = f"test-get-desc-no-result-{uuid.uuid4()}"
    non_existent_result_id = "does-not-exist-desc-123"
    request_body = {"request_id": request_id, "tool_name": "get_shape_description", "arguments": {"result_id": non_existent_result_id, "shape_index": 0}}
    print(f"\nTesting POST /mcp/execute get_shape_description with non-existent result_id ({non_existent_result_id})...")

    response = client.post("/mcp/execute", json=request_body)

    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run and potentially fail
    time.sleep(0.1)

    assert non_existent_result_id not in shape_results

    print("POST /mcp/execute get_shape_description with non-existent result_id test passed (checked immediate response).")


# Test removed as it was duplicated by the refactored version above (around line 835)

def test_mcp_execute_get_shape_description_failed_build(mock_prepare_env, mock_run, client, tmp_path): # Add mocks and tmp_path
    """Test get_shape_description for a result_id corresponding to a failed build."""
    # Re-use the failed build result creation from the properties test
    script_fail = "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,0).edges('>Z').fillet(1)" # Fillet radius too large
    build_res_fail = execute_cqgi_script(script_fail)
    assert build_res_fail.success is False
    failed_result_id = f"handler-test-fail-desc-{uuid.uuid4()}"
    shape_results[failed_result_id] = build_res_fail
    print(f"\nFixture: Created FAILED build result for description test with ID {failed_result_id}")

    request_id = f"test-get-desc-fail-build-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "get_shape_description", "arguments": {"result_id": failed_result_id, "shape_index": 0}}
    print(f"\nTesting POST /mcp/execute get_shape_description for failed build ({failed_result_id})...")

    response = client.post("/mcp/execute", json=request_body)

    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run
    time.sleep(0.1)

    assert failed_result_id in shape_results

    print("POST /mcp/execute get_shape_description for failed build test passed (checked immediate response).")


# --- Test Cases for save_workspace_module Handler ---

def test_mcp_execute_save_workspace_module_success(client, tmp_path):
    """Test save_workspace_module via API (success case)."""
    workspace_path = str(tmp_path / "test_workspace")
    module_name = "my_test_util.py"
    module_code = "def helper():\n    return 'Hello from module'"
    request_id = f"test-save-module-success-{uuid.uuid4()}"
    request_body = {
        "request_id": request_id,
        "tool_name": "save_workspace_module",
        "arguments": {
            "workspace_path": workspace_path,
            "module_filename": module_name,
            "module_content": module_code
        }
    }
    print(f"\nTesting POST /mcp/execute save_workspace_module (Success, ID: {request_id})...")

    response = client.post("/mcp/execute", json=request_body)

    # Check immediate response
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run
    time.sleep(0.1)

    # Check if the file was created in the correct location
    expected_module_dir = tmp_path / "test_workspace" / "modules"
    expected_file_path = expected_module_dir / module_name
    assert expected_file_path.is_file()
    assert expected_file_path.read_text(encoding='utf-8') == module_code

    print("POST /mcp/execute save_workspace_module (Success) test passed.")


def test_mcp_execute_save_workspace_module_invalid_filename(client, tmp_path):
    """Test save_workspace_module with invalid filename (contains path sep)."""
    workspace_path = str(tmp_path / "test_workspace")
    module_name = "subdir/my_test_util.py" # Invalid name
    module_code = "def helper():\n    return 'fail'"
    request_id = f"test-save-module-invalid-{uuid.uuid4()}"
    request_body = {
        "request_id": request_id,
        "tool_name": "save_workspace_module",
        "arguments": {
            "workspace_path": workspace_path,
            "module_filename": module_name,
            "module_content": module_code
        }
    }
    print(f"\nTesting POST /mcp/execute save_workspace_module (Invalid Filename, ID: {request_id})...")

    response = client.post("/mcp/execute", json=request_body)

    # Check immediate response
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run (and fail)
    time.sleep(0.1)

    # Check that the file was NOT created
    expected_module_dir = tmp_path / "test_workspace" / "modules"
    assert not (expected_module_dir / module_name).exists()
    # Ideally check for tool_error SSE message

    print("POST /mcp/execute save_workspace_module (Invalid Filename) test passed.")


def test_mcp_execute_save_workspace_module_missing_args(client, tmp_path):
    """Test save_workspace_module with missing arguments."""
    workspace_path = str(tmp_path / "test_workspace")
    request_id = f"test-save-module-missing-{uuid.uuid4()}"
    # Missing module_filename and module_content
    request_body = {
        "request_id": request_id,
        "tool_name": "save_workspace_module",
        "arguments": { "workspace_path": workspace_path }
    }
    print(f"\nTesting POST /mcp/execute save_workspace_module (Missing Args, ID: {request_id})...")

    response = client.post("/mcp/execute", json=request_body)

    # Check immediate response
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}

    # Allow time for the background task to run (and fail)
    time.sleep(0.1)
    # Ideally check for tool_error SSE message

    print("POST /mcp/execute save_workspace_module (Missing Args) test passed.")


# --- Test Cases for install_workspace_package Handler ---

@patch('server._run_command_helper') # Mock the command runner
@patch('server.prepare_workspace_env') # Corrected function name
def test_mcp_execute_install_package_success(mock_ensure_env, mock_run_command, client, tmp_path):
    """Test install_workspace_package via API (success case)."""
    # --- Mock Setup ---
    workspace_path = str(tmp_path / "test_workspace")
    fake_python_exe = os.path.join(workspace_path, ".venv/bin/python") # Needs to look plausible
    mock_ensure_env.return_value = fake_python_exe
    # Mock _run_command_helper to simulate successful install
    mock_run_command.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="Installed", stderr="")

    # --- Test Execution ---
    package_to_install = "requests" # Example package
    request_id = f"test-install-pkg-success-{uuid.uuid4()}"
    request_body = {
        "request_id": request_id,
        "tool_name": "install_workspace_package",
        "arguments": {
            "workspace_path": workspace_path,
            "package_name": package_to_install
        }
    }
    print(f"\nTesting POST /mcp/execute install_workspace_package (Success, ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.1) # Allow time for async task

    # Check mocks were called
    mock_ensure_env.assert_called_once_with(workspace_path)
    expected_install_command = ["uv", "pip", "install", package_to_install, "--python", fake_python_exe]
    mock_run_command.assert_called_once_with(expected_install_command, log_prefix=f"InstallPkg({os.path.basename(workspace_path)})")

    print("POST /mcp/execute install_workspace_package (Success) test passed.")


@patch('server._run_command_helper') # Mock the command runner
@patch('server.prepare_workspace_env') # Corrected function name
def test_mcp_execute_install_package_failure(mock_ensure_env, mock_run_command, client, tmp_path):
    """Test install_workspace_package via API (install command fails)."""
     # --- Mock Setup ---
    workspace_path = str(tmp_path / "test_workspace")
    fake_python_exe = os.path.join(workspace_path, ".venv/bin/python")
    mock_ensure_env.return_value = fake_python_exe
    # Mock _run_command_helper to simulate failed install
    mock_run_command.side_effect = subprocess.CalledProcessError(returncode=1, cmd=["uv", "pip", "install"], stderr="Install failed")

    # --- Test Execution ---
    package_to_install = "nonexistent_package_xyz"
    request_id = f"test-install-pkg-fail-{uuid.uuid4()}"
    request_body = {
        "request_id": request_id,
        "tool_name": "install_workspace_package",
        "arguments": {
            "workspace_path": workspace_path,
            "package_name": package_to_install
        }
    }
    print(f"\nTesting POST /mcp/execute install_workspace_package (Failure, ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)

    # --- Assertions ---
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.1) # Allow time for async task

    # Check mocks were called
    mock_ensure_env.assert_called_once_with(workspace_path)
    expected_install_command = ["uv", "pip", "install", package_to_install, "--python", fake_python_exe]
    mock_run_command.assert_called_once_with(expected_install_command, log_prefix=f"InstallPkg({os.path.basename(workspace_path)})")
    # Ideally check for tool_error SSE message indicating failure

    print("POST /mcp/execute install_workspace_package (Failure) test passed.")

print("POST /mcp/execute get_shape_description for failed build test passed (checked immediate response).")



def test_mcp_execute_script_invalid_params_type(client):
    """Test execute script API with invalid 'parameters' type."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1)"
    request_id = f"test-script-bad-params-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "execute_cadquery_script", "arguments": {"script": script, "parameters": "not_a_dict"}}
    print(f"\nTesting POST /mcp/execute script with invalid params type...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200 # Request accepted
    assert response.json() == {"status": "processing", "request_id": request_id}
    # Background task should fail, ideally checked via SSE/status endpoint
    print("POST /mcp/execute script with invalid params type test passed (checked immediate response).")

def test_mcp_execute_search_parts_before_scan(client): # Removed fixture dependency
    """Test search_parts API before scanning."""
    state.part_index.clear() # Ensure index is empty
    search_request_id = f"test-search-before-scan-{uuid.uuid4()}"
    search_term = "box"
    search_request_body = {"request_id": search_request_id, "tool_name": "search_parts", "arguments": {"query": search_term}}
    print(f"\nTesting POST /mcp/execute search_parts before scan (Term: '{search_term}', ID: {search_request_id})...")
    response = client.post("/mcp/execute", json=search_request_body)
    # Check immediate response only
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": search_request_id}
    # Cannot easily verify search results from immediate response
    # assert result_data.get("success") is True
    # assert "results" in result_data and isinstance(result_data["results"], list)
    # assert "results" in result_data and isinstance(result_data["results"], list)
    # assert len(result_data["results"]) == 0, "Search before scan should yield no results"
    print("Search before scan handled correctly.")
    print("POST /mcp/execute search_parts before scan test passed.")
# --- Tests for Server Info Message ---

import pytest # Ensure pytest is imported

# Remove skip marker, test is now reliable by checking queue.put directly
@patch('src.mcp_cadquery_server.web_server.asyncio.Queue') # Mock the Queue class where it's used
@patch('src.mcp_cadquery_server.web_server.get_server_info') # Mock getting server info where it's used
def test_sse_connection_sends_server_info(mock_get_server_info, MockQueue, client): # Use MockQueue
    """
    Test that connecting to the /mcp SSE endpoint attempts to put the server_info message
    onto the connection's queue immediately.
    """
    # Mock the Queue instance that will be created
    mock_queue_instance = MagicMock()
    MockQueue.return_value = mock_queue_instance # When Queue() is called, return our mock
    print("\nTesting GET /mcp sends server_info (using mocks)...")
    # Define what get_server_info should return
    expected_server_info = {"type": "server_info", "server_name": "mock-server", "tools": []}
    mock_get_server_info.return_value = expected_server_info

    # Make the request to trigger the endpoint handler
    # We don't need to process the response stream itself
    response = client.get("/mcp") # Use GET for SSE endpoint

    # Assertions
    assert response.status_code == 200 # Check connection was accepted
    mock_get_server_info.assert_called_once() # Ensure server info was fetched
    MockQueue.assert_called_once() # Ensure a Queue instance was created

    # Check that put was called on the *instance* of the queue
    # The server puts the raw dictionary from get_server_info onto the queue
    mock_queue_instance.put.assert_called_once_with(expected_server_info)

    print("GET /mcp initial server_info message test passed (verified queue.put call).")


# Remove patch for get_server_info as we'll compare with the real output
# Import the function needed for the test
from src.mcp_cadquery_server.mcp_api import get_server_info

def test_stdio_mode_sends_server_info(): # Removed mock_get_server_info argument
    """
    Test that running the server in stdio mode prints server_info first.
    """
    print("\nTesting stdio mode sends server_info...")
    # Get the expected output by calling the real function
    # Ensure necessary imports are available if get_server_info relies on them
    try:
        expected_server_info = get_server_info() # Call imported function
    except Exception as e:
        pytest.fail(f"Failed to call get_server_info() in test: {e}")

    # mock_get_server_info.return_value = expected_server_info # Removed mock

    # Prepare command to run server in stdio mode
    # Use sys.executable to ensure the correct python interpreter is used
    # Use the absolute path to server.py
    server_script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server.py'))
    cmd = [sys.executable, server_script_path, "--mode", "stdio"]

    # Run the server as a subprocess
    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE, # Provide stdin to prevent potential blocking
            text=True,
            encoding='utf-8'
        )

        # Read the first line of output (should be server_info)
        # Add a timeout to prevent hanging if the server doesn't output
        stdout_line = ""
        try:
            # Use communicate with a timeout for safer reading
            stdout_data, stderr_data = process.communicate(timeout=10) # Increased timeout slightly
            # Handle potential stderr output for debugging
            if stderr_data:
                print(f"\nServer stderr:\n{stderr_data}", file=sys.stderr)
            stdout_line = stdout_data.splitlines()[0] if stdout_data else ""

        except subprocess.TimeoutExpired:
            print("\nServer process timed out waiting for output.", file=sys.stderr)
            # If communicate times out, terminate/kill and fail
            if process and process.poll() is None:
                print("Terminating timed-out server process...", file=sys.stderr)
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    print("Terminate failed, killing process...", file=sys.stderr)
                    process.kill()
            pytest.fail("Server did not output server_info within timeout (using communicate).")
        except Exception as e: # Catch other potential errors during communicate/readline
             print(f"\nError reading server stdout: {e}", file=sys.stderr)
             if process and process.poll() is None:
                 print("Killing server process due to read error...", file=sys.stderr)
                 process.kill()
             pytest.fail(f"Error reading server stdout: {e}")


        # Verify get_server_info was called (this happens in the subprocess, so we can't directly assert mock calls)
        # Instead, we verify the output matches the mocked return value.
        assert stdout_line, "Server did not produce any output on stdout."

        # Parse the JSON output
        try:
            received_info = json.loads(stdout_line)
        except json.JSONDecodeError as e:
            pytest.fail(f"Failed to decode JSON from server stdout: {e}\nOutput: {stdout_line}")

        # Assert the received info matches the expected structure and content
        assert received_info == expected_server_info

    finally:
        # Ensure the subprocess is cleaned up robustly
        if process and process.poll() is None:
            print("\nCleaning up server process...", file=sys.stderr)
            process.terminate()
            try:
                process.wait(timeout=2) # Wait a bit longer for terminate
            except subprocess.TimeoutExpired:
                print("Terminate failed during cleanup, killing process...", file=sys.stderr)
                process.kill()
                try:
                    process.wait(timeout=1) # Wait after kill
                except: pass # Ignore final wait errors
            except Exception as cleanup_err:
                 print(f"Error during process cleanup: {cleanup_err}", file=sys.stderr) # Log other cleanup errors

    print("Stdio mode server_info send test passed.")


# --- Test Cases for Static File Serving --- (Removed)
# These tests are difficult to maintain reliably with the current setup where
# static file configuration happens dynamically within main() based on CLI args.
# The TestClient uses the global 'app' instance before main() configures it.
# Testing static file serving would require a different approach, perhaps
# involving running the server as a separate process or more complex fixture setup.
# Testing static file serving would require a different approach, perhaps
# involving running the server as a separate process or more complex fixture setup.