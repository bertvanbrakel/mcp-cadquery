import pytest
from cadquery import cqgi
import cadquery as cq
import os
import sys
import uuid
import shutil

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions/variables to test from server.py in root
from server import (
    execute_cqgi_script, # Needed for fixture
    handle_execute_cadquery_script,
    shape_results,
    RENDER_DIR_PATH, # Needed for fixture cleanup
    PART_PREVIEW_DIR_PATH # Needed for fixture cleanup
)

# --- Fixtures ---

@pytest.fixture(scope="module")
def stored_build_result_id_for_handlers(): # Renamed to avoid conflict if run together
    """Creates a BuildResult and returns its ID for handler tests."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)\nshow_object(result)" # Use show_object
    build_res = execute_cqgi_script(script)
    result_id = str(uuid.uuid4())
    shape_results[result_id] = build_res
    return result_id

@pytest.fixture(autouse=True)
def manage_handler_state_and_files(stored_build_result_id_for_handlers):
    """Fixture to clear shape_results and render dir before/after each test."""
    shape_results.clear()
    # Ensure the specific result needed for some tests exists
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)\nshow_object(result)" # Use show_object
    build_res = execute_cqgi_script(script)
    if build_res.success and build_res.results: # Check results exist
        shape_results[stored_build_result_id_for_handlers] = build_res
    # else: # Don't fail here, some tests might not need it populated
        # pytest.fail("Failed to create the build result needed for handler tests in fixture.")

    # Clear render/preview directories
    for dir_path in [RENDER_DIR_PATH, PART_PREVIEW_DIR_PATH]:
        if os.path.exists(dir_path):
            try: shutil.rmtree(dir_path)
            except OSError as e: print(f"Error removing directory {dir_path}: {e}")
        try: os.makedirs(dir_path, exist_ok=True)
        except OSError as e: pytest.fail(f"Failed to create directory {dir_path}: {e}")

    yield # Run the test

    shape_results.clear()


# --- Test Cases for handle_execute_cadquery_script ---

def test_handle_execute_success_no_show_object():
    """Test successful execution via the handler for script without show_object."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 2, 3)"
    request = { "request_id": "test-success-noshow-123", "tool_name": "execute_cadquery_script", "arguments": { "script": script, "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script success (no show_object)...")
    response = handle_execute_cadquery_script(request)
    assert response["success"] is True and "result_id" in response
    assert response["shapes_count"] == 0 # Correct: no show_object means 0 results
    assert response["result_id"] in shape_results
    assert shape_results[response["result_id"]].success is True
    assert len(shape_results[response["result_id"]].results) == 0
    print("handle_execute_cadquery_script success (no show_object) test passed.")

def test_handle_execute_success_with_show_object():
    """Test successful execution via the handler for script with show_object."""
    script = "import cadquery as cq\nbox = cq.Workplane('XY').box(1, 2, 3)\nshow_object(box)"
    request = { "request_id": "test-success-show-456", "tool_name": "execute_cadquery_script", "arguments": { "script": script, "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script success (with show_object)...")
    response = handle_execute_cadquery_script(request)
    assert response["success"] is True and "result_id" in response
    assert response["shapes_count"] == 1 # Correct: show_object means 1 result
    assert response["result_id"] in shape_results
    assert shape_results[response["result_id"]].success is True
    assert len(shape_results[response["result_id"]].results) == 1
    print("handle_execute_cadquery_script success (with show_object) test passed.")

def test_handle_execute_missing_script():
    """Test handler failure when script argument is missing."""
    request = { "request_id": "test-missing-script", "tool_name": "execute_cadquery_script", "arguments": { "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script missing script...")
    with pytest.raises(Exception) as excinfo: handle_execute_cadquery_script(request)
    assert "Missing 'script' argument" in str(excinfo.value)
    print("handle_execute_cadquery_script missing script test passed.")

def test_handle_execute_invalid_params_type():
    """Test handler failure when parameters argument is not a dict."""
    request = { "request_id": "test-invalid-params", "tool_name": "execute_cadquery_script", "arguments": { "script": "result = None", "parameters": "not_a_dict" } }
    print("\nTesting handle_execute_cadquery_script invalid params type...")
    with pytest.raises(Exception) as excinfo: handle_execute_cadquery_script(request)
    assert "'parameters' argument must be a dictionary" in str(excinfo.value)
    print("handle_execute_cadquery_script invalid params type test passed.")

def test_handle_execute_script_failure():
    """Test handler correctly raises exception when core execution fails."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 0.1).edges('>Z').fillet(0.2)"
    request = { "request_id": "test-script-fail", "tool_name": "execute_cadquery_script", "arguments": { "script": script, "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script script failure...")
    with pytest.raises(Exception) as excinfo: handle_execute_cadquery_script(request)
    assert "Script execution failed" in str(excinfo.value)
    print("handle_execute_cadquery_script script failure test passed.")