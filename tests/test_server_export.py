import pytest
from cadquery import cqgi
import cadquery as cq
import os
import sys
import uuid
import shutil
from unittest.mock import patch


# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the core functions to test
from src.mcp_cadquery_server.core import (
    execute_cqgi_script, # Still needed for one fixture
    export_shape_to_svg_file,
    export_shape_to_file
)
# Import cqgi for type hints if needed
from cadquery import cqgi

# Define test paths locally
TEST_RENDER_DIR_NAME = "test_renders_temp"
TEST_STATIC_DIR = "test_static_temp_export" # Base for renders
TEST_RENDER_DIR_PATH = os.path.join(TEST_STATIC_DIR, TEST_RENDER_DIR_NAME)

# --- Fixtures ---

@pytest.fixture(scope="module")
def test_box_shape():
    """Provides a simple CadQuery box shape for testing."""
    return cq.Workplane("XY").box(10, 5, 2).val()


@pytest.fixture(autouse=True)
def manage_export_files():
    """Fixture to clear the test render dir before/after each test."""
    # Use test path
    dir_path = TEST_RENDER_DIR_PATH
    # Clear render/preview directories
    # Only clear render dir for these tests
    # for dir_path in [TEST_RENDER_DIR_PATH, TEST_PREVIEW_DIR_PATH]: # If preview dir was needed
    if os.path.exists(dir_path):
        try: shutil.rmtree(dir_path)
        except OSError as e: print(f"Error removing directory {dir_path}: {e}")
    try: os.makedirs(dir_path, exist_ok=True)
    except OSError as e: pytest.fail(f"Failed to create directory {dir_path}: {e}")

    yield # Run the test

    # No shape_results to clear
    # Clean up temp dirs
    if os.path.exists(TEST_STATIC_DIR):
        try: shutil.rmtree(TEST_STATIC_DIR)
        except OSError as e: print(f"Error removing test dir {TEST_STATIC_DIR}: {e}")


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



@patch('src.mcp_cadquery_server.core.exporters.export')
def test_export_shape_to_file_exporter_exception(mock_export, test_box_shape, tmp_path):
    """Test the exception handling when exporters.export fails."""
    output_file = tmp_path / "fail_export.step"
    mock_export.side_effect = RuntimeError("Simulated export error")
    print(f"\nTesting export failure handling for {output_file}...")

    with pytest.raises(Exception) as excinfo:
        export_shape_to_file(test_box_shape, str(output_file), export_format="STEP")

    assert "Core shape export to file" in str(excinfo.value)
    assert "Simulated export error" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    mock_export.assert_called_once()
    print("Exporter exception handling test passed.")
