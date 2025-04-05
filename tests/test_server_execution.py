import pytest
from cadquery import cqgi
import cadquery as cq
import os
import sys

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the function to test from server.py in root
from server import execute_cqgi_script

# --- Fixtures ---
@pytest.fixture(scope="module")
def test_box_shape():
    """Provides a simple CadQuery box shape for testing."""
    return cq.Workplane("XY").box(10, 5, 2).val()

# --- Test Cases for execute_cqgi_script ---

def test_execute_simple_box_script(test_box_shape):
    """Test executing a valid script that creates a box but doesn't show it."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(10, 5, 2)"
    print("\nTesting valid box script execution (no show_object)...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 0
    print("Valid box script execution (no show_object) test passed.")

def test_execute_script_with_show_object():
    """Test executing a valid script that uses show_object."""
    script = "import cadquery as cq\nbox = cq.Workplane('XY').box(1, 2, 3)\nshow_object(box, name='mybox')"
    print("\nTesting valid script execution with show_object...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 1
    assert isinstance(build_result.results[0].shape, cq.Workplane)
    print("Valid script execution with show_object test passed.")

def test_execute_script_with_syntax_error():
    """Test executing a script with a Python syntax error."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 2,"
    print("\nTesting script execution with syntax error...")
    with pytest.raises(SyntaxError) as excinfo: execute_cqgi_script(script)
    print(f"Caught expected exception: {excinfo.value}")
    print("Syntax error script execution test passed.")

def test_execute_script_with_cadquery_error():
    """Test executing a script that causes an error within CadQuery."""
    script = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1, 0.1).edges('>Z').fillet(0.2)"
    print("\nTesting script execution with CadQuery error...")
    with pytest.raises(Exception) as excinfo: execute_cqgi_script(script)
    assert "failed" in str(excinfo.value).lower()
    assert "ocp" in str(excinfo.value).lower() or "brep_api" in str(excinfo.value).lower()
    print(f"Caught expected exception: {excinfo.value}")
    print("CadQuery error script execution test passed.")

def test_execute_empty_script():
    """Test executing an empty script."""
    script = ""
    print("\nTesting empty script execution...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 0
    print("Empty script execution test passed.")

def test_execute_script_no_result_variable():
    """Test script that runs but doesn't assign to 'result' or use show_object."""
    script = "import cadquery as cq\ncq.Workplane('XY').box(1, 1, 1)"
    print("\nTesting script with no 'result' variable or show_object...")
    build_result = execute_cqgi_script(script)
    assert build_result.success is True and build_result.exception is None
    assert len(build_result.results) == 0
    print("Script with no 'result' variable or show_object test passed.")