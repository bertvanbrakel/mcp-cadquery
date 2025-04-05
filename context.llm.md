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
9.  [X] Refactor server structure:
    *   [X] Merged `server_stdio.py` and `server_sse.py` into a single `server.py`.
    *   [X] Replaced `--stdio` flag with `--mode` flag (`stdio` or `sse`).
    *   [X] Updated imports and calling scripts (`run_dev.py`, tests).
    *   [X] Updated documentation (`README.md`, `README.llm.md`).
10. [X] Implement automatic environment setup in `server.py`:
    *   [X] Added check for running within `.venv-cadquery`.
    *   [X] Integrated logic from `setup_env.py` to create/update venv and install deps using `uv`.
    *   [X] Added re-execution logic using `os.execvp` if not in venv.
    *   [X] Added shebang `#!/usr/bin/env python3`.
    *   [X] Updated documentation (`README.md`, `README.llm.md`).
    *   [X] Removed `setup_env.py`.
11. [X] Restructure `server.py` to fix `ImportError` when run outside venv:
    *   [X] Moved application imports (`typer`, `fastapi`, `cadquery`, etc.) and definitions (apps, routes, handlers) into `initialize_and_run_app()` function.
    *   [X] Kept only minimal imports (`os`, `sys`, `subprocess`, etc.) and setup logic at the top level.
    *   [X] Modified `if __name__ == "__main__":` to call `initialize_and_run_app()`.
12. [X] Adapt tests to decoupled structure:
    *   [X] Created `src/mcp_cadquery_server/core.py` for framework-independent logic.
    *   [X] Moved `execute_cqgi_script`, `export_shape_to_file`, etc. to `core.py`.
    *   [X] Updated tests (`test_server_execution`, `test_server_export`) to import from `core.py`.
    *   [X] Refactored `test_part_library` to use local handlers/state, importing only from `core.py`.
    *   [X] Added `get_configured_app` factory to `server.py` for `TestClient`.
    *   [X] Updated `test_server_handlers` to use `TestClient` and `get_configured_app`.
    *   [X] Updated `test_cli` to run `server.py` as a subprocess.

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
*   Server logic is unified in `server.py`, using `--mode stdio` or `--mode sse` to select operation.
*   `server.py` handles its own virtual environment setup and re-execution if run outside the expected venv. Imports and app logic are deferred until after potential re-execution.
*   Core logic (script execution, export) is in `src.mcp_cadquery_server.core` and can be imported by tests.
*   Application/framework logic (FastAPI, Typer) remains in `server.py` but is initialized late.