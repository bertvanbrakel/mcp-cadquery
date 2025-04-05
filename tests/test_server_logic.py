import pytest
from cadquery import cqgi
import cadquery as cq
import os
import sys
import uuid
import re
import shutil # For cleaning directories

# Assuming server.py is in the parent directory relative to tests/
# Adjust the import path if your project structure is different
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions/variables to test AFTER adjusting sys.path
# Import handlers and the global state they modify
from server import (
    execute_cqgi_script,
    export_shape_to_svg_file,
    handle_execute_cadquery_script,
    handle_export_shape_to_svg,
    handle_scan_part_library,
    handle_search_parts,
    shape_results,
    part_index,
    RENDER_DIR_PATH,
    RENDER_DIR_NAME,
    PART_PREVIEW_DIR_PATH,
    PART_PREVIEW_DIR_NAME,
    PART_LIBRARY_DIR
)

# --- Fixtures ---

@pytest.fixture(scope="module")
def test_box_shape():
    """Provides a simple CadQuery box shape for testing."""
    return cq.Workplane("XY").box(10, 5, 2).val() # Return the cq.Shape

@pytest.fixture(scope="module")
def stored_build_result_id():
    """Creates a BuildResult with a visible object and returns its ID."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 5, 2)\nshow_object(result)"
    build_res = execute_cqgi_script(script)
    result_id = str(uuid.uuid4())
    # Store temporarily just to get an ID, fixture below will manage state
    shape_results[result_id] = build_res
    return result_id

@pytest.fixture(autouse=True)
def manage_state_and_files(stored_build_result_id, request): # request fixture needed for monkeypatching in tests
    """
    Fixture to clear global state (shape_results, part_index),
    generated files (renders, previews), and populate part_index
    before each test.
    """
    # --- Setup before test ---
    shape_results.clear()
    part_index.clear()

    # Ensure the specific result needed for export tests exists
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 5, 2)\nshow_object(result)"
    build_res = execute_cqgi_script(script)
    if build_res.success and build_res.results:
        shape_results[stored_build_result_id] = build_res
    else:
        pytest.fail("Failed to create the build result needed for export tests in fixture.")

    # Clear render/preview directories
    for dir_path in [RENDER_DIR_PATH, PART_PREVIEW_DIR_PATH]:
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
            except OSError as e:
                 print(f"Error removing directory {dir_path}: {e}")
        try:
             os.makedirs(dir_path, exist_ok=True)
        except OSError as e:
             pytest.fail(f"Failed to create directory {dir_path}: {e}")

    # Populate part index for tests that need it (scan/search)
    # Run scan silently to populate index
    # Check if the test needs the populated index (e.g., search tests)
    # This avoids running scan for tests that don't need it.
    # A marker could be used, but checking test name is simpler for now.
    if "search" in request.node.name or "scan_part_library_success" in request.node.name:
        print(f"\nPopulating part index for test: {request.node.name}...")
        try:
            # Ensure PART_LIBRARY_DIR points to the actual library for population
            # This assumes tests needing population don't run after patching tests
            handle_scan_part_library({"request_id": "fixture-scan", "arguments": {}})
            print("Part index populated.")
        except Exception as e:
            pytest.fail(f"Failed to populate part index in fixture: {e}")


    yield # Run the test

    # --- Teardown after test ---
    shape_results.clear()
    part_index.clear()
    # Directories are cleared again by the next test's setup


# --- Test Cases for execute_cqgi_script ---
# (Unchanged)
def test_execute_simple_box_script(test_box_shape):
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 5, 2)"
    print("\nTesting valid box script execution (no show_object)...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 0
    print("Valid box script execution (no show_object) test passed.")

def test_execute_script_with_show_object():
    script = "import cadquery as cq\nbox = cq.Workplane('XY').box(1, 2, 3)\nshow_object(box, name='mybox')"
    print("\nTesting valid script execution with show_object...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 1
    assert isinstance(build_result.results[0].shape, cq.Workplane)
    print("Valid script execution with show_object test passed.")

def test_execute_script_with_syntax_error():
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 2,"
    print("\nTesting script execution with syntax error...")
    with pytest.raises(SyntaxError) as excinfo: execute_cqgi_script(script)
    print(f"Caught expected exception: {excinfo.value}")
    print("Syntax error script execution test passed.")

def test_execute_script_with_cadquery_error():
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 0.1).edges('>Z').fillet(0.2)"
    print("\nTesting script execution with CadQuery error...")
    with pytest.raises(Exception) as excinfo: execute_cqgi_script(script)
    assert "failed" in str(excinfo.value).lower()
    assert "ocp" in str(excinfo.value).lower() or "brep_api" in str(excinfo.value).lower()
    print(f"Caught expected exception: {excinfo.value}")
    print("CadQuery error script execution test passed.")

def test_execute_empty_script():
    script = ""
    print("\nTesting empty script execution...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 0
    print("Empty script execution test passed.")

def test_execute_script_no_result_variable():
    script = "import cadquery as cq\ncq.Workplane('XY').box(1, 1, 1)"
    print("\nTesting script with no 'result' variable or show_object...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 0
    print("Script with no 'result' variable or show_object test passed.")

# --- Test Cases for handle_execute_cadquery_script ---
# (Unchanged)
def test_handle_execute_success_no_show_object():
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 2, 3)"
    request = { "request_id": "test-success-noshow-123", "tool_name": "execute_cadquery_script", "arguments": { "script": script, "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script success (no show_object)...")
    response = handle_execute_cadquery_script(request)
    assert response["success"] is True and "result_id" in response
    assert response["shapes_count"] == 0
    assert response["result_id"] in shape_results
    assert shape_results[response["result_id"]].success is True
    assert len(shape_results[response["result_id"]].results) == 0
    print("handle_execute_cadquery_script success (no show_object) test passed.")

def test_handle_execute_success_with_show_object():
    script = "import cadquery as cq\nbox = cq.Workplane('XY').box(1, 2, 3)\nshow_object(box)"
    request = { "request_id": "test-success-show-456", "tool_name": "execute_cadquery_script", "arguments": { "script": script, "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script success (with show_object)...")
    response = handle_execute_cadquery_script(request)
    assert response["success"] is True and "result_id" in response
    assert response["shapes_count"] == 1
    assert response["result_id"] in shape_results
    assert shape_results[response["result_id"]].success is True
    assert len(shape_results[response["result_id"]].results) == 1
    print("handle_execute_cadquery_script success (with show_object) test passed.")

def test_handle_execute_missing_script():
    request = { "request_id": "test-missing-script", "tool_name": "execute_cadquery_script", "arguments": { "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script missing script...")
    with pytest.raises(Exception) as excinfo: handle_execute_cadquery_script(request)
    assert "Missing 'script' argument" in str(excinfo.value)
    print("handle_execute_cadquery_script missing script test passed.")

def test_handle_execute_invalid_params_type():
    request = { "request_id": "test-invalid-params", "tool_name": "execute_cadquery_script", "arguments": { "script": "result = None", "parameters": "not_a_dict" } }
    print("\nTesting handle_execute_cadquery_script invalid params type...")
    with pytest.raises(Exception) as excinfo: handle_execute_cadquery_script(request)
    assert "'parameters' argument must be a dictionary" in str(excinfo.value)
    print("handle_execute_cadquery_script invalid params type test passed.")

def test_handle_execute_script_failure():
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 0.1).edges('>Z').fillet(0.2)"
    request = { "request_id": "test-script-fail", "tool_name": "execute_cadquery_script", "arguments": { "script": script, "parameters": {} } }
    print("\nTesting handle_execute_cadquery_script script failure...")
    with pytest.raises(Exception) as excinfo: handle_execute_cadquery_script(request)
    assert "Script execution failed" in str(excinfo.value)
    print("handle_execute_cadquery_script script failure test passed.")

# --- Test Cases for export_shape_to_svg_file ---
# (Unchanged)
def test_export_svg_success(test_box_shape, tmp_path):
    output_file = tmp_path / "test_box.svg"
    svg_opts = {"width": 100, "height": 80}
    print(f"\nTesting successful SVG export to {output_file}...")
    export_shape_to_svg_file(test_box_shape, str(output_file), svg_opts)
    assert output_file.exists() and output_file.stat().st_size > 0
    content = output_file.read_text()
    assert "<svg" in content and "</svg>" in content
    print("Successful SVG export test passed.")

def test_export_svg_with_options(test_box_shape, tmp_path):
    output_file = tmp_path / "test_box_options.svg"
    svg_opts = { "width": 150, "height": 120, "showAxes": True, "strokeColor": (255, 0, 0) }
    print(f"\nTesting SVG export with options to {output_file}...")
    export_shape_to_svg_file(test_box_shape, str(output_file), svg_opts)
    assert output_file.exists() and output_file.stat().st_size > 0
    content = output_file.read_text()
    assert "<svg" in content and "</svg>" in content
    print("SVG export with options test passed.")

def test_export_svg_invalid_path(test_box_shape):
    output_file = "/non_existent_directory/test.svg"
    svg_opts = {}
    print(f"\nTesting SVG export to invalid path {output_file}...")
    with pytest.raises(Exception) as excinfo: export_shape_to_svg_file(test_box_shape, output_file, svg_opts)
    assert isinstance(excinfo.value.__cause__, (FileNotFoundError, PermissionError, OSError))
    print("Invalid path SVG export test passed.")

# --- Test Cases for handle_export_shape_to_svg ---
# (Unchanged)
def test_handle_export_svg_success(stored_build_result_id):
    request = { "request_id": "test-svg-success", "tool_name": "export_shape_to_svg", "arguments": { "result_id": stored_build_result_id, "shape_index": 0 } }
    print("\nTesting handle_export_shape_to_svg success (default filename)...")
    response = handle_export_shape_to_svg(request)
    assert response["success"] is True and "filename" in response
    filename_url = response["filename"]
    assert filename_url.startswith(f"/{RENDER_DIR_NAME}/render_") and filename_url.endswith(".svg")
    expected_path = os.path.join(RENDER_DIR_PATH, os.path.basename(filename_url))
    assert os.path.exists(expected_path) and os.path.getsize(expected_path) > 0
    print("handle_export_shape_to_svg success (default filename) test passed.")

def test_handle_export_svg_with_filename_and_options(stored_build_result_id):
    custom_filename = "my_custom_render.svg"
    custom_options = {"width": 500, "height": 400, "showAxes": True}
    request = { "request_id": "test-svg-custom", "tool_name": "export_shape_to_svg", "arguments": { "result_id": stored_build_result_id, "shape_index": 0, "filename": custom_filename, "options": custom_options } }
    print("\nTesting handle_export_shape_to_svg success (custom filename/options)...")
    response = handle_export_shape_to_svg(request)
    assert response["success"] is True and response["filename"] == f"/{RENDER_DIR_NAME}/{custom_filename}"
    expected_path = os.path.join(RENDER_DIR_PATH, custom_filename)
    assert os.path.exists(expected_path) and os.path.getsize(expected_path) > 0
    print("handle_export_shape_to_svg success (custom filename/options) test passed.")

def test_handle_export_svg_missing_result_id():
    request = { "request_id": "test-svg-no-id", "tool_name": "export_shape_to_svg", "arguments": { "shape_index": 0 } }
    print("\nTesting handle_export_shape_to_svg missing result_id...")
    with pytest.raises(Exception) as excinfo: handle_export_shape_to_svg(request)
    assert "Missing 'result_id' argument" in str(excinfo.value)
    print("handle_export_shape_to_svg missing result_id test passed.")

def test_handle_export_svg_invalid_result_id():
    request = { "request_id": "test-svg-bad-id", "tool_name": "export_shape_to_svg", "arguments": { "result_id": "invalid-uuid", "shape_index": 0 } }
    print("\nTesting handle_export_shape_to_svg invalid result_id...")
    with pytest.raises(Exception) as excinfo: handle_export_shape_to_svg(request)
    assert "Result ID 'invalid-uuid' not found" in str(excinfo.value)
    print("handle_export_shape_to_svg invalid result_id test passed.")

def test_handle_export_svg_invalid_shape_index(stored_build_result_id):
    request = { "request_id": "test-svg-bad-index", "tool_name": "export_shape_to_svg", "arguments": { "result_id": stored_build_result_id, "shape_index": 99 } }
    print("\nTesting handle_export_shape_to_svg invalid shape_index...")
    with pytest.raises(Exception) as excinfo: handle_export_shape_to_svg(request)
    assert f"Invalid shape_index 99 for result ID '{stored_build_result_id}'" in str(excinfo.value)
    print("handle_export_shape_to_svg invalid shape_index test passed.")

def test_handle_export_svg_invalid_options_type(stored_build_result_id):
    request = { "request_id": "test-svg-bad-options", "tool_name": "export_shape_to_svg", "arguments": { "result_id": stored_build_result_id, "shape_index": 0, "options": "not_a_dict" } }
    print("\nTesting handle_export_shape_to_svg invalid options type...")
    with pytest.raises(Exception) as excinfo: handle_export_shape_to_svg(request)
    assert "'options' argument must be a dictionary" in str(excinfo.value)
    print("handle_export_shape_to_svg invalid options type test passed.")

def test_handle_export_svg_filename_no_extension(stored_build_result_id):
    custom_filename = "my_render_no_ext"
    request = { "request_id": "test-svg-no-ext", "tool_name": "export_shape_to_svg", "arguments": { "result_id": stored_build_result_id, "shape_index": 0, "filename": custom_filename } }
    print("\nTesting handle_export_shape_to_svg filename without extension...")
    response = handle_export_shape_to_svg(request)
    assert response["success"] is True and response["filename"] == f"/{RENDER_DIR_NAME}/{custom_filename}.svg"
    expected_path = os.path.join(RENDER_DIR_PATH, f"{custom_filename}.svg")
    assert os.path.exists(expected_path)
    print("handle_export_shape_to_svg filename without extension test passed.")

# --- Test Cases for handle_scan_part_library ---

def test_handle_scan_part_library_success():
    """Test scanning the library with multiple valid and one invalid part."""
    request = {"request_id": "scan-1", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting handle_scan_part_library success...")
    response = handle_scan_part_library(request) # This populates part_index via the fixture logic now

    assert response["success"] is True
    assert response["indexed_count"] == 3 # simple_cube, widget_a, bracket
    assert response["error_count"] == 1 # error_part
    assert "Scan complete" in response["message"]

    assert "simple_cube" in part_index
    assert "widget_a" in part_index
    assert "bracket" in part_index
    assert "error_part" not in part_index

    cube_data = part_index["simple_cube"]
    assert cube_data["metadata"]["part"] == "Simple Cube"
    assert "cube" in cube_data["metadata"]["tags"]
    assert cube_data["metadata"]["filename"] == "simple_cube.py"
    assert cube_data["preview_url"] == f"/{PART_PREVIEW_DIR_NAME}/simple_cube.svg"

    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "simple_cube.svg"))
    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "widget_a.svg"))
    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "bracket.svg"))
    assert not os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "error_part.svg"))

    print("handle_scan_part_library success test passed.")

def test_handle_scan_part_library_empty_dir(tmp_path, monkeypatch): # Add monkeypatch fixture
    """Test scanning an empty library directory."""
    empty_dir = tmp_path / "empty_lib"
    empty_dir.mkdir()

    # Patch os.path.abspath, os.listdir, and os.path.isdir for this test
    original_abspath = os.path.abspath
    original_listdir = os.listdir
    original_isdir = os.path.isdir

    def mock_abspath(path):
         if path == PART_LIBRARY_DIR:
             return str(empty_dir) # Make abspath point to temp dir
         return original_abspath(path)

    def mock_listdir(path):
        # Use the *mocked* abspath to check if it's the library dir
        if path == mock_abspath(PART_LIBRARY_DIR):
            return [] # Simulate empty directory
        return original_listdir(path)

    def mock_isdir(path):
         # Use the *mocked* abspath to check if it's the library dir
         if path == mock_abspath(PART_LIBRARY_DIR):
             return True # Simulate directory exists
         return original_isdir(path)

    monkeypatch.setattr(os.path, "abspath", mock_abspath)
    monkeypatch.setattr(os, "listdir", mock_listdir)
    monkeypatch.setattr(os.path, "isdir", mock_isdir) # Corrected target

    request = {"request_id": "scan-empty", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting handle_scan_part_library empty directory...")
    response = handle_scan_part_library(request)

    assert response["success"] is True
    assert response["indexed_count"] == 0 and response["error_count"] == 0
    assert part_index == {}

    print("handle_scan_part_library empty directory test passed.")


def test_handle_scan_part_library_nonexistent_dir(monkeypatch):
    """Test scanning a non-existent library directory."""
    original_isdir = os.path.isdir
    def mock_isdir(path):
        if path == os.path.abspath(PART_LIBRARY_DIR):
            return False
        return original_isdir(path)
    monkeypatch.setattr(os.path, "isdir", mock_isdir) # Corrected target

    request = {"request_id": "scan-nonexistent", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting handle_scan_part_library non-existent directory...")
    with pytest.raises(Exception) as excinfo: handle_scan_part_library(request)
    assert "Part library directory not found" in str(excinfo.value)

    print("handle_scan_part_library non-existent directory test passed.")


# --- Test Cases for handle_search_parts ---
# Remove the separate setup fixture, rely on manage_state_and_files

def test_handle_search_parts_multiple_results():
    """Test searching for a term matching multiple parts (e.g., in description/tags)."""
    request = {"request_id": "search-multi", "tool_name": "search_parts", "arguments": {"query": "metal"}}
    print("\nTesting handle_search_parts multiple results...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 2
    part_ids = {p["part_id"] for p in response["results"]}
    assert {"widget_a", "bracket"} == part_ids
    print("handle_search_parts multiple results test passed.")

def test_handle_search_parts_single_result_name():
    """Test searching for a term matching a single part name."""
    request = {"request_id": "search-single-name", "tool_name": "search_parts", "arguments": {"query": "cube"}}
    print("\nTesting handle_search_parts single result (name)...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "simple_cube"
    print("handle_search_parts single result (name) test passed.")

def test_handle_search_parts_single_result_tag():
    """Test searching for a term matching a single part tag."""
    request = {"request_id": "search-single-tag", "tool_name": "search_parts", "arguments": {"query": "structural"}}
    print("\nTesting handle_search_parts single result (tag)...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "bracket"
    print("handle_search_parts single result (tag) test passed.")

def test_handle_search_parts_case_insensitive():
    """Test that search is case-insensitive."""
    request = {"request_id": "search-case", "tool_name": "search_parts", "arguments": {"query": "BRACKET"}}
    print("\nTesting handle_search_parts case-insensitive...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "bracket"
    print("handle_search_parts case-insensitive test passed.")

def test_handle_search_parts_no_results():
    """Test searching for a term that matches nothing."""
    request = {"request_id": "search-none", "tool_name": "search_parts", "arguments": {"query": "xyz_no_match_xyz"}}
    print("\nTesting handle_search_parts no results...")
    response = handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 0
    print("handle_search_parts no results test passed.")

def test_handle_search_parts_empty_query():
    """Test searching with an empty query (should return all)."""
    request = {"request_id": "search-empty", "tool_name": "search_parts", "arguments": {"query": "  "}}
    print("\nTesting handle_search_parts empty query...")
    response = handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 3
    part_ids = {p["part_id"] for p in response["results"]}
    assert {"simple_cube", "widget_a", "bracket"} == part_ids
    print("handle_search_parts empty query test passed.")

def test_handle_search_parts_empty_index():
    """Test searching when the part index is empty."""
    part_index.clear()
    request = {"request_id": "search-empty-index", "tool_name": "search_parts", "arguments": {"query": "cube"}}
    print("\nTesting handle_search_parts empty index...")
    response = handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 0
    print("handle_search_parts empty index test passed.")