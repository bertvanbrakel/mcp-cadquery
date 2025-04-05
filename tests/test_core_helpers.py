import pytest
import os
import sys
from typing import Dict, Any, List, Optional

# Add project root to path to allow importing src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.mcp_cadquery_server.core import (
    parse_docstring_metadata,
    _substitute_parameters
)

# --- Tests for parse_docstring_metadata ---

def test_parse_metadata_basic():
    docstring = """
    Part: My Test Part
    Description: A simple part for testing.
    Tags: test, simple, example
    Author: Testy McTestface
    """
    expected = {
        "part": "My Test Part",
        "description": "A simple part for testing.",
        "tags": ["test", "simple", "example"],
        "author": "Testy McTestface"
    }
    assert parse_docstring_metadata(docstring) == expected

def test_parse_metadata_mixed_case_keys():
    docstring = """
    Part Name: Mixed Case
    DESCRIPTION: Some description.
    tAGs: mixed, CASE, tags
    """
    expected = {
        "part_name": "Mixed Case", # Key becomes snake_case
        "description": "Some description.",
        "tags": ["mixed", "case", "tags"]
    }
    assert parse_docstring_metadata(docstring) == expected

def test_parse_metadata_extra_whitespace():
    docstring = """
    Part:  Spaced Out Part
      Description :  Has extra spaces.
    Tags:  space1 , space2  ,space3
    """
    expected = {
        "part": "Spaced Out Part",
        "description": "Has extra spaces.",
        "tags": ["space1", "space2", "space3"]
    }
    assert parse_docstring_metadata(docstring) == expected

def test_parse_metadata_no_tags():
    docstring = """
    Part: No Tags Part
    Description: This one has no tags line.
    """
    expected = {
        "part": "No Tags Part",
        "description": "This one has no tags line."
        # 'tags' key should be absent
    }
    assert parse_docstring_metadata(docstring) == expected
    assert "tags" not in parse_docstring_metadata(docstring)

def test_parse_metadata_empty_tags():
    docstring = """
    Part: Empty Tags Part
    Tags: ,, ,
    """
    expected = {
        "part": "Empty Tags Part",
        "tags": [] # Should result in an empty list
    }
    assert parse_docstring_metadata(docstring) == expected

def test_parse_metadata_multiline_description():
    # Note: Current implementation only takes the first line after the key.
    # This test confirms current behavior, not necessarily desired behavior.
    docstring = """
    Part: Multiline Test
    Description: This is the first line.
                 This is the second line, likely ignored.
    Tags: multi, line
    """
    expected = {
        "part": "Multiline Test",
        "description": "This is the first line.", # Only first line captured
        "tags": ["multi", "line"]
    }
    assert parse_docstring_metadata(docstring) == expected

def test_parse_metadata_empty_string():
    assert parse_docstring_metadata("") == {}

def test_parse_metadata_none():
    assert parse_docstring_metadata(None) == {}

def test_parse_metadata_no_valid_lines():
    docstring = """
    This is just a regular docstring.
    No key: value pairs here.
    """
    assert parse_docstring_metadata(docstring) == {}

# --- Tests for _substitute_parameters ---

def test_substitute_basic():
    script_lines = [
        "import cadquery as cq",
        "length = 10 # PARAM",
        "width = 5 # PARAM",
        "height = 2",
        "result = cq.Workplane('XY').box(length, width, height)"
    ]
    params = {"length": 25.5, "width": 15}
    expected_lines = [
        "import cadquery as cq",
        "length = 25.5 # PARAM (Substituted)",
        "width = 15 # PARAM (Substituted)",
        "height = 2",
        "result = cq.Workplane('XY').box(length, width, height)"
    ]
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_string_param():
    script_lines = [
        "text = 'default' # PARAM",
        "print(text)"
    ]
    params = {"text": "new_value"}
    expected_lines = [
        "text = 'new_value' # PARAM (Substituted)",
        "print(text)"
    ]
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_boolean_param():
    script_lines = [
        "flag = False # PARAM",
        "if flag: pass"
    ]
    params = {"flag": True}
    expected_lines = [
        "flag = True # PARAM (Substituted)",
        "if flag: pass"
    ]
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_list_param():
    script_lines = [
        "points = [1, 2] # PARAM",
        "print(points)"
    ]
    params = {"points": [10, 20, 30]}
    expected_lines = [
        "points = [10, 20, 30] # PARAM (Substituted)",
        "print(points)"
    ]
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_dict_param():
    script_lines = [
        "config = {'a': 1} # PARAM",
        "print(config)"
    ]
    params = {"config": {"b": 2, "c": "hello"}}
    # Note: dict repr might have different key order
    result_lines = _substitute_parameters(script_lines, params)
    assert result_lines[0].startswith("config = {") and "'b': 2" in result_lines[0] and "'c': 'hello'" in result_lines[0] and result_lines[0].endswith("# PARAM (Substituted)")
    assert result_lines[1] == "print(config)"


def test_substitute_no_marker():
    script_lines = [
        "length = 10 # No marker here",
        "result = cq.Workplane('XY').box(length, 5, 2)"
    ]
    params = {"length": 99}
    # Expect no change
    assert _substitute_parameters(script_lines, params) == script_lines

def test_substitute_param_not_provided():
    script_lines = [
        "length = 10 # PARAM",
        "width = 5 # PARAM",
        "result = cq.Workplane('XY').box(length, width, 2)"
    ]
    params = {"length": 20} # width not provided
    expected_lines = [
        "length = 20 # PARAM (Substituted)",
        "width = 5 # PARAM", # Should remain unchanged
        "result = cq.Workplane('XY').box(length, width, 2)"
    ]
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_extra_param_provided():
    script_lines = [
        "length = 10 # PARAM",
        "result = cq.Workplane('XY').box(length, 5, 2)"
    ]
    params = {"length": 20, "unused": 100} # unused param provided
    expected_lines = [
        "length = 20 # PARAM (Substituted)",
        "result = cq.Workplane('XY').box(length, 5, 2)"
    ]
    # Expect unused param to be ignored
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_with_indentation():
    script_lines = [
        "def func():",
        "    val = 1 # PARAM",
        "    print(val)"
    ]
    params = {"val": 100}
    expected_lines = [
        "def func():",
        "    val = 100 # PARAM (Substituted)",
        "    print(val)"
    ]
    assert _substitute_parameters(script_lines, params) == expected_lines

def test_substitute_empty_params():
    script_lines = [
        "length = 10 # PARAM",
        "result = cq.Workplane('XY').box(length, 5, 2)"
    ]
    params = {}
    # Expect no change
    assert _substitute_parameters(script_lines, params) == script_lines

def test_substitute_empty_script():
    script_lines = []
    params = {"a": 1}
    assert _substitute_parameters(script_lines, params) == []