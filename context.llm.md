# CadQuery MCP Server TDD Build

**Goal:** Create a reliable backend server first, verifying each piece of functionality with tests using `pytest`. Ignore UI for now.

**Status:** Core backend logic refactored and tested.

**Completed Steps:**
1.  [X] Review existing project files (`requirements.txt`, `server.py`, `tests/test_environment.py`).
    *   [X] `requirements.txt` (Corrected duplicate entry)
    *   [X] `server.py`
    *   [X] `tests/test_environment.py` (Corrected assertion)
2.  [X] Ensure the environment test (`tests/test_environment.py`) passes reliably. (Passed using `.venv-cadquery/bin/pytest`)
3.  [X] Write tests for core CadQuery functionality (box creation, SVG export) in `tests/test_cadquery_core.py`. (Existing tests passed)
4.  [X] Write tests for the CQGI script execution logic (Refactored `handle_execute_cadquery_script` into `execute_cqgi_script`, tests passed).
5.  [X] Write tests for the SVG export logic (Refactored `handle_export_shape_to_svg` into `export_shape_to_svg_file`, tests passed).

**Next Steps (Beyond Initial Request):**
*   Consider refactoring/testing `handle_export_shape`.
*   Add tests for the FastAPI endpoint handlers (`handle_execute_cadquery_script`, `handle_export_shape_to_svg`, etc.) using a test client like `httpx`.
*   Implement parameter injection logic if needed in `handle_execute_cadquery_script`.
*   Integrate with the frontend UI (later phase).

**Relevant Info:**
*   Focus on backend logic and testing.
*   Assume unattended execution (no user interaction needed for tests).
*   Use `pytest` for testing (run via `.venv-cadquery/bin/pytest`).
*   Refactored CQGI execution logic into `execute_cqgi_script(script_content: str)`.
*   Refactored SVG export logic into `export_shape_to_svg_file(shape_to_render: cq.Shape, output_path: str, svg_opts: dict)`.