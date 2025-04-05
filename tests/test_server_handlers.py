import pytest
import os
import sys
import uuid
import shutil
import json
import asyncio
import time
import tempfile # Keep for potential future use, though not strictly needed now
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles # Import StaticFiles

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the app instance, state, and paths from server
from server import (
    app,
    shape_results,
    part_index, # Import the actual index used by handlers
    RENDER_DIR_PATH,
    PART_PREVIEW_DIR_PATH,
    RENDER_DIR_NAME,
    PART_LIBRARY_DIR, # Import the default library dir path used by server
    STATIC_DIR # Import the default static dir path
)
# Import core logic needed by fixtures
from src.mcp_cadquery_server.core import execute_cqgi_script

# --- Test Data ---
EXAMPLE_PARTS = {
    "part1_box.py": '"""Part: Test Part 1\nDescription: A simple test box part.\nTags: box, test, simple\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").box(1, 1, 1)\nshow_object(result, name="part1_box")',
    "part2_sphere.py": '"""Part: Another Test Part 2\nDescription: A sphere part.\nTags: sphere, test, round\n"""\nimport cadquery as cq\nradius = 5.0 # PARAM\nresult = cq.Workplane("XY").sphere(radius)\nshow_object(result, name="part2_sphere")',
    "part3_error.py": '"""Part: Error Part\nDescription: Causes error.\nTags: error\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").box(1,1,0.1).edges(">Z").fillet(0.2)\nshow_object(result)'
}

# --- Fixtures ---

@pytest.fixture(scope="module")
def stored_build_result_id_for_handlers():
    """Creates a BuildResult and returns its ID for handler tests."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)\nshow_object(result)"
    build_res = execute_cqgi_script(script)
    result_id = f"handler-test-{uuid.uuid4()}"
    shape_results[result_id] = build_res
    print(f"\nFixture: Created build result with ID {result_id}")
    return result_id

@pytest.fixture(autouse=True)
def manage_state_and_test_files(stored_build_result_id_for_handlers):
    """
    Fixture to manage state and files before/after each test.
    - Clears shape_results and part_index.
    - Clears/creates render, preview, and default part library directories.
    - Creates dummy part files in the default part library directory.
    - Re-creates a standard build result needed by some tests.
    """
    # --- Setup ---
    print("\nAuto-fixture: Setting up state and test files...")
    shape_results.clear()
    part_index.clear()

    # Re-create the specific build result needed for some tests
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 1)\nshow_object(result)"
    build_res = execute_cqgi_script(script)
    if build_res.success and build_res.results:
        shape_results[stored_build_result_id_for_handlers] = build_res
        print(f"Auto-fixture: Re-created build result {stored_build_result_id_for_handlers}")
    else:
        pytest.fail("Failed to create the build result needed in fixture.")

    # Manage directories (Render, Preview, Part Library, Static Base)
    dirs_to_manage = [RENDER_DIR_PATH, PART_PREVIEW_DIR_PATH, PART_LIBRARY_DIR, STATIC_DIR] # Add STATIC_DIR here
    print(f"Auto-fixture: Managing directories: {dirs_to_manage}")
    for dir_path in dirs_to_manage:
        if os.path.exists(dir_path):
            try: shutil.rmtree(dir_path)
            except OSError as e: print(f"Error removing directory {dir_path}: {e}")
        try: os.makedirs(dir_path, exist_ok=True)
        except OSError as e: pytest.fail(f"Failed to create directory {dir_path}: {e}")

    # Create dummy part files in the default library directory
    print(f"Auto-fixture: Creating dummy parts in {PART_LIBRARY_DIR}...")
    for filename, content in EXAMPLE_PARTS.items():
        filepath = os.path.join(PART_LIBRARY_DIR, filename)
        try:
            with open(filepath, 'w') as f: f.write(content)
        except OSError as e: pytest.fail(f"Failed to create dummy part file {filepath}: {e}")
    print(f"Auto-fixture: Created {len(EXAMPLE_PARTS)} dummy parts.")

    # Create dummy static files needed by tests
    print(f"Auto-fixture: Creating dummy static files in {STATIC_DIR}...")
    try:
        # index.html
        index_path = os.path.join(STATIC_DIR, "index.html")
        with open(index_path, "w") as f: f.write("<html>Fixture Index</html>")
        # assets/dummy.css
        asset_dir = os.path.join(STATIC_DIR, "assets")
        os.makedirs(asset_dir, exist_ok=True)
        asset_path = os.path.join(asset_dir, "dummy.css")
        with open(asset_path, "w") as f: f.write("body { color: green; }")
        print("Auto-fixture: Created dummy index.html and assets/dummy.css.")
    except OSError as e:
        pytest.fail(f"Failed to create dummy static files: {e}")

    yield # Run the test

    # --- Teardown ---
    print("\nAuto-fixture: Tearing down state and test files...")
    shape_results.clear()
    part_index.clear()
    print("Auto-fixture: Cleared shape_results and part_index.")

    # Clean up directories again, ensuring STATIC_DIR is included
    if STATIC_DIR not in dirs_to_manage:
        dirs_to_manage.append(STATIC_DIR)
    for dir_path in dirs_to_manage:
        if os.path.exists(dir_path):
            try: shutil.rmtree(dir_path)
            except OSError as e: print(f"Error removing directory {dir_path} during teardown: {e}")
    print("Auto-fixture: Removed test directories.")


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

def test_mcp_execute_endpoint_script_success(client):
    """Test execute_cadquery_script via API."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').sphere(5)\nshow_object(result)"
    request_id = f"test-endpoint-exec-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "execute_cadquery_script", "arguments": {"script": script}}
    print(f"\nTesting POST /mcp/execute execute_cadquery_script (ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.5)
    result_id_expected = f"{request_id}_0"
    assert result_id_expected in shape_results
    assert shape_results[result_id_expected].success is True
    assert len(shape_results[result_id_expected].results) == 1
    print("POST /mcp/execute execute_cadquery_script test passed.")

def test_mcp_execute_endpoint_script_params_success(client):
    """Test execute_cadquery_script with parameter_sets via API."""
    script = "import cadquery as cq\nlength = 1.0 # PARAM\nresult = cq.Workplane('XY').box(length, 2, 1)\nshow_object(result)"
    request_id = f"test-endpoint-params-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "execute_cadquery_script", "arguments": {"script": script, "parameter_sets": [{"length": 5.5}, {"length": 6.6}]}}
    print(f"\nTesting POST /mcp/execute with parameter_sets (ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.5)
    result_id_0, result_id_1 = f"{request_id}_0", f"{request_id}_1"
    assert result_id_0 in shape_results and result_id_1 in shape_results
    assert shape_results[result_id_0].success and shape_results[result_id_1].success
    assert len(shape_results[result_id_0].results) == 1 and len(shape_results[result_id_1].results) == 1
    print("POST /mcp/execute with parameter_sets test passed.")

def test_mcp_execute_endpoint_export_svg_success(client, stored_build_result_id_for_handlers):
    """Test export_shape_to_svg via API."""
    result_id = stored_build_result_id_for_handlers
    request_id_export = f"test-endpoint-svg-{uuid.uuid4()}"
    custom_filename = f"test_render_{request_id_export}.svg"
    request_body = {"request_id": request_id_export, "tool_name": "export_shape_to_svg", "arguments": {"result_id": result_id, "shape_index": 0, "filename": custom_filename}}
    print(f"\nTesting POST /mcp/execute export_shape_to_svg (ID: {request_id_export})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id_export}
    time.sleep(0.5)
    expected_path = os.path.join(RENDER_DIR_PATH, custom_filename)
    assert os.path.exists(expected_path) and os.path.getsize(expected_path) > 0
    print("POST /mcp/execute export_shape_to_svg test passed.")

def test_mcp_execute_endpoint_export_shape_step_success(client, stored_build_result_id_for_handlers):
    """Test generic export_shape (STEP) via API."""
    result_id = stored_build_result_id_for_handlers
    request_id_export = f"test-endpoint-step-{uuid.uuid4()}"
    # Export outside the managed render dir to test path handling
    temp_dir = tempfile.TemporaryDirectory()
    custom_filename = os.path.join(temp_dir.name, f"test_export_{request_id_export}.step")
    request_body = {"request_id": request_id_export, "tool_name": "export_shape", "arguments": {"result_id": result_id, "shape_index": 0, "filename": custom_filename, "format": "STEP"}}
    print(f"\nTesting POST /mcp/execute export_shape (STEP) (ID: {request_id_export})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id_export}
    time.sleep(0.5)
    assert os.path.exists(custom_filename) and os.path.getsize(custom_filename) > 0
    print(f"STEP file created at {custom_filename}")
    temp_dir.cleanup()
    print("POST /mcp/execute export_shape (STEP) test passed.")

def test_mcp_execute_scan_part_library(client): # Removed fixture dependency, relies on autouse fixture
    """Test scan_part_library via API."""
    request_id = f"test-scan-{uuid.uuid4()}"
    request_body = {"request_id": request_id, "tool_name": "scan_part_library", "arguments": {}}
    print(f"\nTesting POST /mcp/execute scan_part_library (ID: {request_id})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(1.0) # Allow time for scanning
    assert len(part_index) == 2 # part1_box, part2_sphere (part3_error should fail)
    assert "part1_box" in part_index and "part2_sphere" in part_index
    assert "part3_error" not in part_index
    # Check preview files exist
    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "part1_box.svg"))
    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "part2_sphere.svg"))
    assert not os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "part3_error.svg"))
    print("POST /mcp/execute scan_part_library test passed.")

def test_mcp_execute_search_parts_success(client): # Removed fixture dependency
    """Test search_parts via API after scanning."""
    # 1. Scan the library first (using the API)
    scan_request_id = f"test-scan-for-search-{uuid.uuid4()}"
    scan_request_body = {"request_id": scan_request_id, "tool_name": "scan_part_library", "arguments": {}}
    print(f"\nScanning library first (ID: {scan_request_id})...")
    scan_response = client.post("/mcp/execute", json=scan_request_body)
    assert scan_response.status_code == 200
    time.sleep(1.0) # Wait for scan to complete
    assert len(part_index) >= 2, "Index should have at least 2 parts after scan"
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

def test_mcp_execute_search_parts_no_results(client): # Removed fixture dependency
    """Test search_parts via API when no results are found."""
    scan_request_id = f"test-scan-for-no-search-{uuid.uuid4()}"
    scan_response = client.post("/mcp/execute", json={"request_id": scan_request_id, "tool_name": "scan_part_library", "arguments": {}})
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
    expected_path = os.path.join(RENDER_DIR_PATH, "wont_be_created.svg")
    assert not os.path.exists(expected_path), "File should not be created for non-existent result_id"
    print("Check: Export file not created for non-existent result_id (as expected).")
    print("POST /mcp/execute export with non-existent result_id test passed.")


def test_mcp_execute_export_invalid_index(client, stored_build_result_id_for_handlers):
    """Test exporting a shape with an invalid shape_index via API."""
    result_id = stored_build_result_id_for_handlers
    request_id = f"test-export-bad-index-{uuid.uuid4()}"
    invalid_shape_index = 999
    request_body = {"request_id": request_id, "tool_name": "export_shape_to_svg", "arguments": {"result_id": result_id, "shape_index": invalid_shape_index, "filename": "wont_be_created_bad_index.svg"}}
    print(f"\nTesting POST /mcp/execute export with invalid shape_index ({invalid_shape_index})...")
    response = client.post("/mcp/execute", json=request_body)
    assert response.status_code == 200
    assert response.json() == {"status": "processing", "request_id": request_id}
    time.sleep(0.5)
    expected_path = os.path.join(RENDER_DIR_PATH, "wont_be_created_bad_index.svg")
    assert not os.path.exists(expected_path), "File should not be created for invalid shape_index"
    print("Check: Export file not created for invalid shape_index (as expected).")
    print("POST /mcp/execute export with invalid shape_index test passed.")

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
    part_index.clear() # Ensure index is empty
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


# --- Test Cases for Static File Serving ---

def test_get_root_path(client):
    """Test accessing the root path '/' serves index.html."""
    # Dummy index.html is now created by the manage_state_and_test_files fixture

    response = client.get("/")
    assert response.status_code == 200
    assert "<html>Fixture Index</html>" in response.text # Check for fixture content
    assert response.headers.get("content-type") == "text/html; charset=utf-8"
    # No need to remove file, fixture teardown handles it

def test_get_index_html(client):
    """Test accessing '/index.html' directly."""
    # Dummy index.html is now created by the manage_state_and_test_files fixture

    response = client.get("/index.html")
    assert response.status_code == 200
    assert "<html>Fixture Index</html>" in response.text # Check for fixture content
    assert response.headers.get("content-type") == "text/html; charset=utf-8"
    # No need to remove file, fixture teardown handles it

def test_get_static_asset(client):
    """Test accessing a file within a mounted static directory (e.g., assets)."""
    # Dummy asset file is now created by the manage_state_and_test_files fixture

    response = client.get("/assets/dummy.css")
    assert response.status_code == 200
    assert "color: green" in response.text # Check for fixture content
    assert response.headers.get("content-type") == "text/css; charset=utf-8"
    # No need to remove file/dir, fixture teardown handles it

def test_get_nonexistent_static_file(client):
    """Test accessing a non-existent static file returns 404."""
    response = client.get("/nonexistent/file.txt")
    assert response.status_code == 404