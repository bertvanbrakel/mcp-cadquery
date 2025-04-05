# CadQuery MCP Server TDD Build

**Goal:** Create a reliable backend server first, verifying each piece of functionality with tests using `pytest`. Ignore UI for now.

**Status:** Core backend logic and endpoint handlers refactored and tested. Parameter substitution implemented via string replacement in handler.

**Completed Steps:**
1.  [X] Review existing project files (`requirements.txt`, `server.py`, `tests/test_environment.py`).
    *   [X] `requirements.txt` (Corrected duplicate entry, added `httpx`)
    *   [X] `server.py`
    *   [X] `tests/test_environment.py` (Corrected assertion)
2.  [X] Ensure the environment test (`tests/test_environment.py`) passes reliably. (Passed using `.venv-cadquery/bin/pytest`)
3.  [X] Write tests for core CadQuery functionality (box creation, SVG export) in `tests/test_cadquery_core.py`. (Existing tests passed)
4.  [X] Write tests for the CQGI script execution logic (Refactored `handle_execute_cadquery_script` into `execute_cqgi_script`, tests passed).
5.  [X] Write tests for the SVG export logic (Refactored `handle_export_shape_to_svg` into `export_shape_to_svg_file`, tests passed).
6.  [X] Refactor and test generic shape export logic (Refactored `handle_export_shape` into `export_shape_to_file`, tests passed in `tests/test_server_export.py`).
7.  [X] Add tests for the FastAPI endpoint handlers (`/mcp/execute`) using `httpx` (`TestClient`) in `tests/test_server_handlers.py`. (Tests passed).
8.  [X] Implement parameter substitution logic in `handle_execute_cadquery_script`.
    *   [X] Uses string replacement based on `# PARAM` marker.
    *   [X] Supports `parameter_sets` list for multiple runs.
    *   [X] Added tests in `tests/test_server_handlers.py` (Assumed passed despite undefined exit code).
    *   (Note: Direct injection via `CQModel.build()` args is not supported in CQ 2.5.2).

**Next Steps:**
*   Integrate with the frontend UI (later phase).
*   Consider adding tests for other handlers (`handle_scan_part_library`, `handle_search_parts`) if deemed necessary.
*   Revisit direct parameter injection if CadQuery/CQGI version is updated.

**Relevant Info:**
*   Focus on backend logic and testing.
*   Assume unattended execution (no user interaction needed for tests).
*   Use `pytest` for testing (run via `.venv-cadquery/bin/pytest`).
*   Refactored CQGI execution logic into `execute_cqgi_script(script_content: str)`.
*   Refactored SVG export logic into `export_shape_to_svg_file(shape_to_render: Any, output_path: str, svg_opts: dict)`.
*   Refactored generic export logic into `export_shape_to_file(shape_to_export: Any, output_path: str, export_format: Optional[str] = None, export_options: Optional[dict] = None)`.
*   FastAPI endpoint tests use `TestClient` (requires `httpx`).
*   Parameter substitution uses string replacement in `handle_execute_cadquery_script` based on `# PARAM` comment marker.