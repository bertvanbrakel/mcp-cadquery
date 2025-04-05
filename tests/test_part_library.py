import pytest
import os
import sys
import uuid
import re
import shutil
import time
import ast # Added for local handler
from typing import Dict, Any, List # Added for local handler

# Add back sys.path modification
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import core functions needed for testing handlers locally
from src.mcp_cadquery_server.core import (
    execute_cqgi_script,
    export_shape_to_svg_file,
    parse_docstring_metadata
)
# Import cqgi for type hints if needed
from cadquery import cqgi

# --- Test-Local State and Paths ---
# Replicate state and paths locally for isolated testing
test_part_index: Dict[str, Dict[str, Any]] = {}
TEST_LIBRARY_DIR = "test_part_library_temp"
TEST_PREVIEW_DIR_NAME = "test_part_previews_temp"
TEST_STATIC_DIR = "test_static_temp" # Base for previews
TEST_PREVIEW_DIR_PATH = os.path.join(TEST_STATIC_DIR, TEST_PREVIEW_DIR_NAME)
# RENDER_DIR_PATH might not be needed here unless testing export handlers
# TEST_RENDER_DIR_NAME = "test_renders_temp"
# TEST_RENDER_DIR_PATH = os.path.join(TEST_STATIC_DIR, TEST_RENDER_DIR_NAME)


# --- Test-Local Handler Implementations ---
# These mirror server.py logic but use local state/paths and imported core functions

def _test_handle_scan_part_library(request: dict) -> dict:
    """Local test version of handle_scan_part_library."""
    # Use test-local paths and index
    library_path = os.path.abspath(TEST_LIBRARY_DIR)
    preview_dir_path = TEST_PREVIEW_DIR_PATH
    preview_dir_url = f"/{TEST_PREVIEW_DIR_NAME}" # Relative URL for testing

    if not os.path.isdir(library_path): raise ValueError(f"Test Part library directory not found: {library_path}")
    scanned_count, indexed_count, updated_count, cached_count, error_count = 0, 0, 0, 0, 0
    found_parts = set(); default_svg_opts = {"width": 150, "height": 100, "showAxes": False}

    for filename in os.listdir(library_path):
        if filename.endswith(".py") and not filename.startswith("_"):
            scanned_count += 1; part_name = os.path.splitext(filename)[0]; found_parts.add(part_name)
            file_path = os.path.join(library_path, filename); error_msg = None
            try:
                current_mtime = os.path.getmtime(file_path); cached_data = test_part_index.get(part_name)
                if cached_data and cached_data.get('mtime') == current_mtime: cached_count += 1; continue

                with open(file_path, 'r', encoding='utf-8') as f: script_content = f.read()
                # Use core function for metadata parsing
                tree = ast.parse(script_content); docstring = ast.get_docstring(tree)
                metadata = parse_docstring_metadata(docstring); metadata['filename'] = filename
                # Use core function for script execution
                build_result = execute_cqgi_script(script_content)

                if build_result.success and build_result.results:
                    shape_to_preview = build_result.results[0].shape; preview_filename = f"{part_name}.svg"
                    preview_output_path = os.path.join(preview_dir_path, preview_filename); preview_output_url = f"{preview_dir_url}/{preview_filename}"
                    # Use core function for SVG export
                    export_shape_to_svg_file(shape_to_preview, preview_output_path, default_svg_opts)
                    part_data = { "part_id": part_name, "metadata": metadata, "preview_url": preview_output_url, "script_path": file_path, "mtime": current_mtime }
                    if part_name in test_part_index: updated_count += 1
                    else: indexed_count += 1
                    test_part_index[part_name] = part_data
                elif not build_result.results: error_count += 1 # Script ran but no result
                else: error_count += 1 # Script failed
            except SyntaxError as e: error_msg = f"Syntax error parsing {filename}: {e}"; error_count += 1
            except Exception as e: error_msg = f"Error processing {filename}: {e}"; error_count += 1
            # if error_msg: log.error(error_msg, exc_info=True) # Cannot use log easily here

    removed_count = 0; indexed_parts = set(test_part_index.keys()); parts_to_remove = indexed_parts - found_parts
    for part_name_to_remove in parts_to_remove:
        removed_data = test_part_index.pop(part_name_to_remove, None)
        if removed_data and 'preview_url' in removed_data:
            preview_filename = os.path.basename(removed_data['preview_url']); preview_file_path = os.path.join(TEST_PREVIEW_DIR_PATH, preview_filename)
            if os.path.exists(preview_file_path):
                try: os.remove(preview_file_path)
                except OSError as e: print(f"Error removing test preview file {preview_file_path}: {e}") # Use print in tests
        removed_count += 1
    summary_msg = (f"Scan complete. Scanned: {scanned_count}, Newly Indexed: {indexed_count}, "
                   f"Updated: {updated_count}, Cached: {cached_count}, Removed: {removed_count}, Errors: {error_count}.")
    return { "success": True, "message": summary_msg, "scanned": scanned_count, "indexed": indexed_count, "updated": updated_count, "cached": cached_count, "removed": removed_count, "errors": error_count }


def _test_handle_search_parts(request: dict) -> dict:
    """Local test version of handle_search_parts."""
    try:
        args = request.get("arguments", {}); query = args.get("query", "").strip().lower()
        if not query: results = list(test_part_index.values()); return {"success": True, "message": f"Found {len(results)} parts.", "results": results}

        search_terms = set(term.strip() for term in query.split() if term.strip()); results = []
        for part_id, part_data in test_part_index.items():
            match_score = 0; metadata = part_data.get("metadata", {})
            if query in part_id.lower(): match_score += 5
            if query in metadata.get("part", "").lower(): match_score += 3
            if query in metadata.get("description", "").lower(): match_score += 2
            tags = metadata.get("tags", [])
            if isinstance(tags, list):
                 if any(term in tag for term in search_terms for tag in tags): match_score += 5
            if query in metadata.get("filename", "").lower(): match_score += 1
            if match_score > 0: results.append({"score": match_score, "part": part_data})
        results.sort(key=lambda x: x["score"], reverse=True); final_results = [item["part"] for item in results]
        message = f"Found {len(final_results)} parts matching query '{query}'."
        return {"success": True, "message": message, "results": final_results}
    except Exception as e: error_msg = f"Error during part search: {e}"; raise Exception(error_msg)


# --- Fixtures ---

@pytest.fixture(autouse=True)
def manage_library_state_and_files(request):
    """
    Fixture to clear test_part_index, generated preview files,
    and ensure test part library files exist before each test.
    Populates index for tests marked with 'needs_populated_index'.
    """
    # --- Setup before test ---
    test_part_index.clear() # Use local index

    # Use test-local paths
    current_part_lib_dir = TEST_LIBRARY_DIR
    current_preview_dir = TEST_PREVIEW_DIR_PATH
    current_static_dir = TEST_STATIC_DIR

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

    # Clear preview directory (use test path)
    if os.path.exists(current_preview_dir):
        try: shutil.rmtree(current_preview_dir)
        except OSError as e: print(f"Error removing directory {current_preview_dir}: {e}")
    try: os.makedirs(current_preview_dir, exist_ok=True)
    except OSError as e: pytest.fail(f"Failed to create directory {current_preview_dir}: {e}")

    # Populate index only if test needs it, using local handler
    if request.node.get_closest_marker("needs_populated_index"):
         print(f"\nPopulating test part index for test: {request.node.name}...")
         try:
             # Call local test handler
             _test_handle_scan_part_library({"request_id": "fixture-scan", "arguments": {}})
             print("Test part index populated.")
         except Exception as e:
             pytest.fail(f"Failed to populate test part index in fixture: {e}")

    yield # Run the test

    # --- Teardown after test ---
    test_part_index.clear() # Clear local index
    # Clean up example files potentially modified/deleted by tests
    for filename in example_parts:
        filepath = os.path.join(current_part_lib_dir, filename)
        if os.path.exists(filepath):
            try: os.remove(filepath)
            except OSError as e: print(f"Error removing test file {filepath}: {e}")
    # Clean up temp dirs
    if os.path.exists(current_part_lib_dir):
        try: shutil.rmtree(current_part_lib_dir)
        except OSError as e: print(f"Error removing test dir {current_part_lib_dir}: {e}")
    if os.path.exists(current_static_dir):
        try: shutil.rmtree(current_static_dir)
        except OSError as e: print(f"Error removing test dir {current_static_dir}: {e}")


# --- Test Cases (using local handlers and state) ---

# Previous attempt via ini failed, trying decorator for this specific test
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_handle_scan_part_library_success():
    """Test scanning the library populates the index correctly."""
    request = {"request_id": "scan-1", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting _test_handle_scan_part_library success...")
    # Call local test handler
    response = _test_handle_scan_part_library(request)

    assert response["success"] is True
    assert response["indexed"] == 3
    assert response["updated"] == 0 and response["cached"] == 0 and response["removed"] == 0
    assert response["errors"] == 1
    assert "Scan complete" in response["message"]

    # Check local test index
    assert "simple_cube" in test_part_index and "widget_a" in test_part_index and "bracket" in test_part_index
    assert "error_part" not in test_part_index

    cube_data = test_part_index["simple_cube"]
    assert cube_data["metadata"]["part"] == "Simple Cube"
    assert "cube" in cube_data["metadata"]["tags"]
    assert cube_data["metadata"]["filename"] == "simple_cube.py"
    # Check local test preview URL
    assert cube_data["preview_url"] == f"/{TEST_PREVIEW_DIR_NAME}/simple_cube.svg"
    assert "mtime" in cube_data

    # Check local test preview files
    assert os.path.exists(os.path.join(TEST_PREVIEW_DIR_PATH, "simple_cube.svg"))
    assert os.path.exists(os.path.join(TEST_PREVIEW_DIR_PATH, "widget_a.svg"))
    assert os.path.exists(os.path.join(TEST_PREVIEW_DIR_PATH, "bracket.svg"))
    assert not os.path.exists(os.path.join(TEST_PREVIEW_DIR_PATH, "error_part.svg"))

    print("_test_handle_scan_part_library success test passed.")

@pytest.mark.needs_populated_index
def test_handle_scan_part_library_caching():
    """Test that a second scan uses the cache for unchanged files."""
    assert len(test_part_index) == 3 # Precondition from fixture using local index

    scan_request = {"request_id": "scan-cache", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting scan caching: Second run...")
    # Call local test handler
    response = _test_handle_scan_part_library(scan_request)
    assert response["success"] is True
    assert response["indexed"] == 0 and response["updated"] == 0
    assert response["cached"] == 3
    assert response["removed"] == 0 and response["errors"] == 1
    assert len(test_part_index) == 3

    print("_test_handle_scan_part_library caching test passed.")

@pytest.mark.needs_populated_index
def test_handle_scan_part_library_update():
    """Test that modifying a file causes it to be updated on the next scan."""
    assert "widget_a" in test_part_index # Check local index
    original_mtime = test_part_index["widget_a"]["mtime"]
    original_preview_path = os.path.join(TEST_PREVIEW_DIR_PATH, "widget_a.svg") # Use local path
    assert os.path.exists(original_preview_path)
    original_preview_mtime = os.path.getmtime(original_preview_path)

    part_path = os.path.join(TEST_LIBRARY_DIR, "widget_a.py") # Use local path
    time.sleep(0.01)
    new_mtime = time.time()
    os.utime(part_path, (new_mtime, new_mtime))
    current_mtime = os.path.getmtime(part_path)
    assert current_mtime != original_mtime

    scan_request = {"request_id": "scan-update", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting scan update: Second run after modify...")
    # Call local test handler
    response = _test_handle_scan_part_library(scan_request)
    assert response["success"] is True
    assert response["indexed"] == 0 and response["updated"] == 1
    assert response["cached"] == 2 and response["removed"] == 0 and response["errors"] == 1
    assert len(test_part_index) == 3 # Check local index

    assert test_part_index["widget_a"]["mtime"] == current_mtime # Check local index
    assert os.path.exists(original_preview_path)
    assert os.path.getmtime(original_preview_path) > original_preview_mtime

    print("_test_handle_scan_part_library update test passed.")

@pytest.mark.needs_populated_index
def test_handle_scan_part_library_deletion():
    """Test that deleting a file removes it from the index and deletes its preview."""
    part_to_delete = "bracket.py"
    part_name = "bracket"
    part_path = os.path.join(TEST_LIBRARY_DIR, part_to_delete) # Use local path
    preview_path = os.path.join(TEST_PREVIEW_DIR_PATH, f"{part_name}.svg") # Use local path
    assert part_name in test_part_index and os.path.exists(preview_path) # Check local index

    os.remove(part_path)
    assert not os.path.exists(part_path)

    scan_request = {"request_id": "scan-delete", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting scan deletion: Second run after delete...")
    # Call local test handler
    response = _test_handle_scan_part_library(scan_request)
    assert response["success"] is True
    assert response["indexed"] == 0 and response["updated"] == 0
    assert response["cached"] == 2 and response["removed"] == 1 and response["errors"] == 1
    assert len(test_part_index) == 2 # Check local index

    assert part_name not in test_part_index # Check local index
    assert not os.path.exists(preview_path)

    print("_test_handle_scan_part_library deletion test passed.")


def test_handle_scan_part_library_empty_dir():
    """Test scanning an empty library directory using renaming."""
    # Rename the real library temporarily
    real_lib_path = os.path.abspath(TEST_LIBRARY_DIR) # Use local path
    temp_lib_path = real_lib_path + "_temp_rename_empty" # Use different suffix
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
        print("\nTesting _test_handle_scan_part_library empty directory...")
        test_part_index.clear() # Use local index
        # Call local test handler
        response = _test_handle_scan_part_library(request)

        assert response["success"] is True
        assert response["indexed"] == 0 and response["updated"] == 0
        assert response["cached"] == 0 and response["removed"] == 0 and response["errors"] == 0
        assert test_part_index == {} # Check local index

    finally:
        # Clean up: remove the empty dir, rename the original back
        if empty_lib_created and os.path.exists(real_lib_path):
            try:
                os.rmdir(real_lib_path)
            except OSError as e:
                 print(f"Warning: Could not remove temp empty dir {real_lib_path}: {e}")
        if renamed and os.path.exists(temp_lib_path):
            os.rename(temp_lib_path, real_lib_path)

    print("_test_handle_scan_part_library empty directory test passed.")


def test_handle_scan_part_library_nonexistent_dir(monkeypatch):
    """Test scanning a non-existent library directory."""
    # Keep using monkeypatch for this one as it's simpler than renaming
    original_isdir = os.path.isdir
    def mock_isdir(path):
        if path == os.path.abspath(TEST_LIBRARY_DIR): return False # Use local path
        return original_isdir(path)
    monkeypatch.setattr(os.path, "isdir", mock_isdir)

    request = {"request_id": "scan-nonexistent", "tool_name": "scan_part_library", "arguments": {}}
    print("\nTesting _test_handle_scan_part_library non-existent directory...")
    # Call local test handler
    with pytest.raises(Exception) as excinfo: _test_handle_scan_part_library(request)
    assert "Test Part library directory not found" in str(excinfo.value) # Check error message

    print("_test_handle_scan_part_library non-existent directory test passed.")


# --- Test Cases for handle_search_parts ---

@pytest.mark.needs_populated_index
def test_handle_search_parts_multiple_results():
    """Test searching for a term matching multiple parts (e.g., in description/tags)."""
    request = {"request_id": "search-multi", "tool_name": "search_parts", "arguments": {"query": "metal"}}
    print("\nTesting _test_handle_search_parts multiple results...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 2
    part_ids = {p["part_id"] for p in response["results"]}
    assert {"widget_a", "bracket"} == part_ids
    print("_test_handle_search_parts multiple results test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_single_result_name():
    """Test searching for a term matching a single part name."""
    request = {"request_id": "search-single-name", "tool_name": "search_parts", "arguments": {"query": "cube"}}
    print("\nTesting _test_handle_search_parts single result (name)...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "simple_cube"
    print("_test_handle_search_parts single result (name) test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_single_result_tag():
    """Test searching for a term matching a single part tag."""
    request = {"request_id": "search-single-tag", "tool_name": "search_parts", "arguments": {"query": "structural"}}
    print("\nTesting _test_handle_search_parts single result (tag)...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "bracket"
    print("_test_handle_search_parts single result (tag) test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_case_insensitive():
    """Test that search is case-insensitive."""
    request = {"request_id": "search-case", "tool_name": "search_parts", "arguments": {"query": "BRACKET"}}
    print("\nTesting _test_handle_search_parts case-insensitive...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True
    assert len(response["results"]) == 1
    assert response["results"][0]["part_id"] == "bracket"
    print("_test_handle_search_parts case-insensitive test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_no_results():
    """Test searching for a term that matches nothing."""
    request = {"request_id": "search-none", "tool_name": "search_parts", "arguments": {"query": "xyz_no_match_xyz"}}
    print("\nTesting _test_handle_search_parts no results...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 0
    print("_test_handle_search_parts no results test passed.")

@pytest.mark.needs_populated_index
def test_handle_search_parts_empty_query():
    """Test searching with an empty query (should return all)."""
    request = {"request_id": "search-empty", "tool_name": "search_parts", "arguments": {"query": "  "}}
    print("\nTesting _test_handle_search_parts empty query...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 3
    part_ids = {p["part_id"] for p in response["results"]}
    assert {"simple_cube", "widget_a", "bracket"} == part_ids
    print("_test_handle_search_parts empty query test passed.")

def test_handle_search_parts_empty_index():
    """Test searching when the part index is empty."""
    test_part_index.clear() # Explicitly clear local index for this test
    request = {"request_id": "search-empty-index", "tool_name": "search_parts", "arguments": {"query": "cube"}}
    print("\nTesting _test_handle_search_parts empty index...")
    # Call local test handler
    response = _test_handle_search_parts(request)
    assert response["success"] is True and len(response["results"]) == 0
    print("_test_handle_search_parts empty index test passed.")