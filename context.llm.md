# MCP CadQuery Context

**Objective:** Refactor server for workspace-based execution and dependency management, allowing custom modules and packages per workspace.

**Previous Work:**
- Added `get_shape_properties` and `get_shape_description` tools.
- Integrated CQ-Editor launch.

**Workspace Refactoring Plan & Status:**

1.  ✅ **Refactor Environment Management:**
    *   Created `prepare_workspace_env` function to handle workspace venv creation/validation and dependency syncing using `uv`.
    *   Implemented `mtime` caching for workspace `requirements.txt`.
    *   Removed global server auto-re-execution logic.
2.  ✅ **Refactor Script Execution:**
    *   Modified `handle_execute_cadquery_script` to accept `workspace_path`.
    *   Created `script_runner.py` to execute user scripts in a subprocess using the workspace's Python interpreter.
    *   Runner adds `<workspace_path>/modules` to `sys.path`.
    *   Runner exports shapes to intermediate BREP files in `<workspace_path>/.cq_results/`.
    *   Handler stores dictionary result (including intermediate paths) from runner in `shape_results`.
    *   Updated relevant tests with mocking.
3.  ✅ **Refactor Dependent Handlers:**
    *   Added `workspace_path` argument where needed.
    *   Modified handlers (`export_shape`, `export_shape_to_svg`, `get_shape_properties`, `get_shape_description`) to load shapes from intermediate BREP files based on `shape_results`.
    *   Updated handlers to resolve output paths relative to the workspace.
    *   Updated tests for these handlers using mocking for prerequisite steps.
4.  ✅ **Refactor `scan_part_library`:**
    *   Added `workspace_path` argument.
    *   Updated paths to be workspace-relative.
    *   Uses in-process execution (relies on `sys.path` modification for local modules).
    *   Updated tests.
5.  ✅ **Add `save_workspace_module` Tool:**
    *   Implemented handler and core logic to save `.py` files to `<workspace_path>/modules/`.
    *   Added tests.
6.  ✅ **Add `install_workspace_package` Tool:**
    *   Implemented handler to call `uv pip install` via subprocess within the workspace venv.
    *   Added tests (mocking the install command).
7.  ✅ **Update Server CLI:**
    *   Removed global path configuration options (`--output-dir`, etc.).
    *   Updated CLI tests.
8.  ✅ **Update Example Script:**
    *   Modified `run_example.py` to use workspaces and new tools.

**Current Status:** All planned steps for the workspace refactoring are complete. Core workspace logic, script execution, module saving, package installation tools, and dependent handlers are implemented and tested (using mocks where appropriate).