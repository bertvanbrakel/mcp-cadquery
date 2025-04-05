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
from server_stdio import (
    execute_cqgi_script, # Needed for fixture
    export_shape_to_svg_file,
    export_shape_to_file, # <-- Add import for the new function
    handle_export_shape_to_svg,
    shape_results,
    RENDER_DIR_PATH,
    RENDER_DIR_NAME,
    PART_PREVIEW_DIR_PATH # Needed for fixture cleanup
)

# --- Fixtures ---

@pytest.fixture(scope="module")
def test_box_shape():
    """Provides a simple CadQuery box shape for testing."""
    return cq.Workplane("XY").box(10, 5, 2).val()

@pytest.fixture(scope="module")
def stored_build_result_id():
    """Creates a BuildResult with a visible object and returns its ID."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 5, 2)\nshow_object(result)"
    build_res = execute_cqgi_script(script)
    result_id = str(uuid.uuid4())
    shape_results[result_id] = build_res
    return result_id

@pytest.fixture(autouse=True)
def manage_export_state_and_files(stored_build_result_id):
    """Fixture to clear shape_results and render dir before/after each test."""
    shape_results.clear()
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
            try: shutil.rmtree(dir_path)
            except OSError as e: print(f"Error removing directory {dir_path}: {e}")
        try: os.makedirs(dir_path, exist_ok=True)
        except OSError as e: pytest.fail(f"Failed to create directory {dir_path}: {e}")

    yield # Run the test

    shape_results.clear()


# --- Test Cases for export_shape_to_svg_file ---

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


# --- Test Cases for export_shape_to_file ---

def test_export_shape_to_step_success(test_box_shape, tmp_path):
    """Test exporting a cq.Shape to STEP format."""
    output_file = tmp_path / "test_box.step"
    print(f"\nTesting successful STEP export to {output_file}...")
    export_shape_to_file(test_box_shape, str(output_file), export_format="STEP")
    assert output_file.exists() and output_file.stat().st_size > 0
    # Basic check for STEP file content (ASCII)
    content = output_file.read_text()
    assert "HEADER;" in content and "ENDSEC;" in content
    print("Successful STEP export test passed.")

def test_export_workplane_to_stl_success(tmp_path):
    """Test exporting a cq.Workplane directly to STL format."""
    wp = cq.Workplane("XY").box(5, 5, 5) # Use a Workplane directly
    output_file = tmp_path / "test_wp.stl"
    print(f"\nTesting successful STL export from Workplane to {output_file}...")
    export_shape_to_file(wp, str(output_file), export_format="STL")
    assert output_file.exists() and output_file.stat().st_size > 0
    # Basic check for STL file content (ASCII or binary start)
    try:
        content = output_file.read_text()
        assert content.strip().startswith("solid")
    except UnicodeDecodeError: # Binary STL
        content_bytes = output_file.read_bytes()
        assert len(content_bytes) > 80 # Header size
    print("Successful STL export from Workplane test passed.")

def test_export_shape_creates_directory(test_box_shape, tmp_path):
    """Test that export creates the necessary output directory."""
    output_dir = tmp_path / "nested" / "output"
    output_file = output_dir / "test_box.step"
    print(f"\nTesting directory creation during export to {output_file}...")
    assert not output_dir.exists() # Ensure dir doesn't exist beforehand
    export_shape_to_file(test_box_shape, str(output_file), export_format="STEP")
    assert output_file.exists() and output_file.stat().st_size > 0
    assert output_dir.is_dir()
    print("Directory creation test passed.")

def test_export_shape_invalid_type(tmp_path):
    """Test exporting an invalid object type."""
    output_file = tmp_path / "invalid.step"
    invalid_object = "this is not a shape"
    print(f"\nTesting export with invalid type ({type(invalid_object)})...")
    with pytest.raises(TypeError) as excinfo:
        export_shape_to_file(invalid_object, str(output_file), export_format="STEP")
    assert "Object to export is not a cq.Shape or cq.Workplane" in str(excinfo.value)
    assert not output_file.exists()
    print("Invalid type export test passed.")

# --- Test Cases for handle_export_shape_to_svg ---

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