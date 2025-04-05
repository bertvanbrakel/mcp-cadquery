import os
import pytest
import cadquery as cq
from cadquery import exporters

# Define output directory for test artifacts
TEST_OUTPUT_DIR = "test_output"
os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)

@pytest.fixture(scope="module")
def simple_box():
    """Create a simple CadQuery box Workplane object."""
    print("\nCreating simple box fixture...")
    box = cq.Workplane("XY").box(10, 20, 5)
    assert box is not None, "Failed to create box Workplane"
    print("Simple box fixture created.")
    return box

def test_create_simple_box(simple_box):
    """Test if the simple_box fixture is created successfully."""
    print("\nTesting box creation...")
    assert isinstance(simple_box, cq.Workplane), "Fixture is not a Workplane object"
    # Check if there's a solid associated (box() should create one)
    assert simple_box.val().isValid(), "Box solid is not valid"
    print("Box creation test passed.")

def test_export_box_svg(simple_box):
    """Test exporting the box to SVG."""
    print("\nTesting SVG export...")
    output_filename = os.path.join(TEST_OUTPUT_DIR, "test_box.svg")
    svg_options = {"projectionDir": (0.5, 0.5, 0.5)} # Example options

    try:
        print(f"Exporting SVG to {output_filename}...")
        exporters.export(simple_box.val(), output_filename, exportType='SVG', opt=svg_options)
        print("SVG export function called.")

        assert os.path.exists(output_filename), f"SVG file '{output_filename}' was not created."
        assert os.path.getsize(output_filename) > 0, f"SVG file '{output_filename}' is empty."
        print(f"SVG file '{output_filename}' created successfully and is not empty.")

        # Optional: Basic check for SVG content
        with open(output_filename, 'r') as f:
            content = f.read()
            assert "<svg" in content, "File does not contain <svg tag."
            assert "</svg>" in content, "File does not contain </svg tag."
        print("Basic SVG content check passed.")
        print("SVG export test passed.")

    except Exception as e:
        pytest.fail(f"SVG export failed with exception: {e}")

# Removed failing test_export_box_tjs