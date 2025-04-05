import pytest
from cadquery import cqgi
import cadquery as cq
import os
import sys
import uuid
import re
import shutil
import time

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the functions/variables to test from server.py in root
from server import (
    execute_cqgi_script, # Needed for fixture
    handle_scan_part_library,
    handle_search_parts,
    part_index,
    PART_PREVIEW_DIR_PATH,
    PART_PREVIEW_DIR_NAME,
    PART_LIBRARY_DIR, # This is the *default* name used by the handler
    RENDER_DIR_PATH # Needed for fixture cleanup
)

# --- Fixtures ---

@pytest.fixture(autouse=True)
def manage_library_state_and_files(request):
    """
    Fixture to clear part_index, generated preview files,
    and ensure part library files exist before each test.
    Populates index for tests marked with 'needs_populated_index'.
    """
    # --- Setup before test ---
    part_index.clear()

    # Ensure part library directory and base files exist
    # Use the global PART_LIBRARY_DIR which reflects the default or CLI override
    # For testing, we assume the default "part_library" unless a test modifies it
    current_part_lib_dir = PART_LIBRARY_DIR
    os.makedirs(current_part_lib_dir, exist_ok=True)
    example_parts = {
        "simple_cube.py": '"""Part: Simple Cube\nDescription: A basic 10x10x10 cube.\nTags: cube, basic\n"""\nimport cadquery as cq\ncube = cq.Workplane("XY").box(10, 10, 10)\nshow_object(cube)',
        "widget_a.py": '"""Part: Widget A\nDescription: A mounting widget.\nTags: widget, metal\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").box(30, 20, 5).faces(">Z").workplane().pushPoints([(-10, 0), (10, 0)]).circle(3).cutThruAll()\nshow_object(result)',
        "bracket.py": '"""Part: L-Bracket\nDescription: An L-shaped bracket.\nTags: bracket, metal, structural\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").hLine(20).vLine(20).hLine(-5).vLine(-15).hLine(-15).close().extrude(5)\nshow_object(result)',
        "error_part.py": '"""Part: Error Part\nDescription: Causes error.\nTags: error\n"""\nimport cadquery as cq\nresult = cq.Workplane("XY").box(1,1,0.1).edges(">Z").fillet(0.2)\nshow_object(result)'
    }
    base_mtime = time.time() - 10
    for i, (filename, content) in enumerate(example_parts.items()):
        filepath = os.path.join(current_part_lib_dir, filename)
        write = True
        if os.path.exists(filepath):
             try:
                 with open(filepath, 'r') as f:
                     if f.read() == content: write = False
             except Exception: pass
        if write:
             with open(filepath, 'w') as f: f.write(content)
             os.utime(filepath, (base_mtime + i, base_mtime + i))

    # Clear render/preview directories
    for dir_path in [RENDER_DIR_PATH, PART_PREVIEW_DIR_PATH]:
        if os.path.exists(dir_path):
            try: shutil.rmtree(dir_path)
            except OSError as e: print(f"Error removing directory {dir_path}: {e}")
        try: os.makedirs(dir_path, exist_ok=True)
        except OSError as e: pytest.fail(f"Failed to create directory {dir_path}: {e}")

    # Populate index only if test needs it
    if request.node.get_closest_marker("needs_populated_index"):
         print(f"\nPopulating part index for test: {request.node.name}...")
         try:
             # Ensure scan uses the correct directory for this fixture run
             handle_scan_part_library({"request_id": "fixture-scan", "arguments": {}})
             print("Part index populated.")
         except Exception as e:
             pytest.fail(f"Failed to populate part index in fixture: {e}")

    yield # Run the test

    # --- Teardown after test ---
    part_index.clear()
    # Clean up example files potentially modified/deleted by tests
    # This ensures next test starts with consistent files
    for filename in example_parts:
        filepath = os.path.join(current_part_lib_dir, filename)
        if os.path.exists(filepath):
            try: os.remove(filepath)
            except OSError as e: print(f"Error removing test file {filepath}: {e}")


# --- Test Cases for handle_scan_part_library ---

def test_handle_scan_part_library_success():
    """Test scanning the library populates the index correctly."""
    request = {"request_id": "scan-1", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting handle_scan_part_library success...")
    response = handle_scan_part_library(request)

    assert response["success"] is True
    assert response["indexed"] == 3
    assert response["updated"] == 0 and response["cached"] == 0 and response["removed"] == 0
    assert response["errors"] == 1
    assert "Scan complete" in response["message"]

    assert "simple_cube" in part_index and "widget_a" in part_index and "bracket" in part_index
    assert "error_part" not in part_index

    cube_data = part_index["simple_cube"]
    assert cube_data["metadata"]["part"] == "Simple Cube"
    assert "cube" in cube_data["metadata"]["tags"]
    assert cube_data["metadata"]["filename"] == "simple_cube.py"
    assert cube_data["preview_url"] == f"/{PART_PREVIEW_DIR_NAME}/simple_cube.svg"
    assert "mtime" in cube_data

    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "simple_cube.svg"))
    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "widget_a.svg"))
    assert os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "bracket.svg"))
    assert not os.path.exists(os.path.join(PART_PREVIEW_DIR_PATH, "error_part.svg"))

    print("handle_scan_part_library success test passed.")

@pytest.mark.needs_populated_index
def test_handle_scan_part_library_caching():
    """Test that a second scan uses the cache for unchanged files."""
    assert len(part_index) == 3 # Precondition from fixture

    scan_request = {"request_id": "scan-cache", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting scan caching: Second run...")
    response = handle_scan_part_library(scan_request)
    assert response["success"] is True
    assert response["indexed"] == 0 and response["updated"] == 0
    assert response["cached"] == 3
    assert response["removed"] == 0 and response["errors"] == 1
    assert len(part_index) == 3

    print("handle_scan_part_library caching test passed.")

@pytest.mark.needs_populated_index
def test_handle_scan_part_library_update():
    """Test that modifying a file causes it to be updated on the next scan."""
    assert "widget_a" in part_index
    original_mtime = part_index["widget_a"]["mtime"]
    original_preview_path = os.path.join(PART_PREVIEW_DIR_PATH, "widget_a.svg")
    assert os.path.exists(original_preview_path)
    original_preview_mtime = os.path.getmtime(original_preview_path)

    part_path = os.path.join(PART_LIBRARY_DIR, "widget_a.py")
    time.sleep(0.01)
    new_mtime = time.time()
    os.utime(part_path, (new_mtime, new_mtime))
    current_mtime = os.path.getmtime(part_path)
    assert current_mtime != original_mtime

    scan_request = {"request_id": "scan-update", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting scan update: Second run after modify...")
    response = handle_scan_part_library(scan_request)
    assert response["success"] is True
    assert response["indexed"] == 0 and response["updated"] == 1
    assert response["cached"] == 2 and response["removed"] == 0 and response["errors"] == 1
    assert len(part_index) == 3

    assert part_index["widget_a"]["mtime"] == current_mtime
    assert os.path.exists(original_preview_path)
    assert os.path.getmtime(original_preview_path) > original_preview_mtime

    print("handle_scan_part_library update test passed.")

@pytest.mark.needs_populated_index
def test_handle_scan_part_library_deletion():
    """Test that deleting a file removes it from the index and deletes its preview."""
    part_to_delete = "bracket.py"
    part_name = "bracket"
    part_path = os.path.join(PART_LIBRARY_DIR, part_to_delete)
    preview_path = os.path.join(PART_PREVIEW_DIR_PATH, f"{part_name}.svg")
    assert part_name in part_index and os.path.exists(preview_path)

    os.remove(part_path)
    assert not os.path.exists(part_path)

    scan_request = {"request_id": "scan-delete", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting scan deletion: Second run after delete...")
    response = handle_scan_part_library(scan_request)
    assert response["success"] is True
    assert response["indexed"] == 0 and response["updated"] == 0
    assert response["cached"] == 2 and response["removed"] == 1 and response["errors"] == 1
    assert len(part_index) == 2

    assert part_name not in part_index
    assert not os.path.exists(preview_path)

    print("handle_scan_part_library deletion test passed.")


def test_handle_scan_part_library_empty_dir():
    """Test scanning an empty library directory using renaming."""
    # Rename the real library temporarily
    real_lib_path = os.path.abspath(PART_LIBRARY_DIR)
    temp_lib_path = real_lib_path + "_temp_rename"
    empty_lib_created = False
    renamed = False
    try:
        if os.path.exists(real_lib_path):
            os.rename(real_lib_path, temp_lib_path)
            renamed = True
        # Create an empty directory with the original name
        os.makedirs(real_lib_path, exist_ok=True)
        empty_lib_created = True

        request = {"request_id": "scan-empty", "tool_name": "scan_part_library", "arguments": {}}
        print("\nTesting handle_scan_part_library empty directory...")
        part_index.clear()
        response = handle_scan_part_library(request)

        assert response["success"] is True
        assert response["indexed"] == 0 and response["updated"] == 0
        assert response["cached"] == 0 and response["removed"] == 0 and response["errors"] == 0
        assert part_index == {}

    finally:
        # Clean up: remove the empty dir, rename the original back
        if empty_lib_created and os.path.exists(real_lib_path):
            try:
                os.rmdir(real_lib_path)
            except OSError as e:
                 print(f"Warning: Could not remove temp empty dir {real_lib_path}: {e}")
        if renamed and os.path.exists(temp_lib_path):
            os.rename(temp_lib_path, real_lib_path)

    print("handle_scan_part_library empty directory test passed.")


def test_handle_scan_part_library_nonexistent_dir(monkeypatch):
    """Test scanning a non-existent library directory."""
    # Keep using monkeypatch for this one as it's simpler than renaming
    original_isdir = os.path.isdir
    def mock_isdir(path):
        if path == os.path.abspath(PART_LIBRARY_DIR): return False
        return original_isdir(path)
    monkeypatch.setattr(os.path, "isdir", mock_isdir)

    request = {"request_id": "scan-nonexistent", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting handle_scan_part_library non-existent directory...")
    with pytest.raises(Exception) as excinfo: handle_scan_part_library(request)
    assert "Part library directory not found" in str(excinfo.value)

    print("handle_scan_part_library non-existent directory test passed.")


# --- Test Cases for handle_search_parts ---

@pytest.mark.needs_populated_index
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

@pytest.mark.needs_populated_index
def test_handle_search_parts_single_result_name():
    """Test searching for a term matching a single part name."""
    request = {"request_id": "search-single-name", "tool_name": "search_parts", "arguments": {"query": "cube"}}
    print("\nTesting handle_search_parts single result (name)...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "simple_cube"
    print("handle_search_parts single result (name) test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_single_result_tag():
    """Test searching for a term matching a single part tag."""
    request = {"request_id": "search-single-tag", "tool_name": "search_parts", "arguments": {"query": "structural"}}
    print("\nTesting handle_search_parts single result (tag)...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "bracket"
    print("handle_search_parts single result (tag) test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_case_insensitive():
    """Test that search is case-insensitive."""
    request = {"request_id": "search-case", "tool_name": "search_parts", "arguments": {"query": "BRACKET"}}
    print("\nTesting handle_search_parts case-insensitive...")
    response = handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "bracket"
    print("handle_search_parts case-insensitive test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_no_results():
    """Test searching for a term that matches nothing."""
    request = {"request_id": "search-none", "tool_name": "search_parts", "arguments": {"query": "xyz_no_match_xyz"}}
    print("\nTesting handle_search_parts no results...")
    response = handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 0
    print("handle_search_parts no results test passed.")

@pytest.mark.needs_populated_index
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
    part_index.clear() # Explicitly clear index for this test
    request = {"request_id": "search-empty-index", "tool_name": "search_parts", "arguments": {"query": "cube"}}
    print("\nTesting handle_search_parts empty index...")
    response = handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 0
    print("handle_search_parts empty index test passed.")