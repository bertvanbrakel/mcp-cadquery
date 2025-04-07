# Code Review Findings: mcp-cadquery

This document outlines findings from the code review based on the agreed plan. Each finding should ideally lead to a separate task for resolution.

## Review Criteria Reminder

*   **Best Practices:** PEP 8, idiomatic Python, types, context managers, etc.
*   **Documentation:** Clarity/completeness of docstrings, necessary inline comments.
*   **Actionable Comments:** Identification of `TODO`, `FIXME`, etc.
*   **Duplication (DRY):** Repeated code/logic.
*   **Clarity & Intent:** Readability, naming, logical flow.
*   **Single Responsibility Principle (SRP):** Focused functions/classes.
*   **Abstraction Levels:** Consistency within methods/functions.
*   **Error Handling:** Specific exceptions, contextual info, try/except usage.
*   **API Clarity (MCP):** Consistency in naming, parameters, descriptions, schemas.

---

## Production Code (`src/` and `server.py`)

### `server.py`

*   **File & Line(s):** Entire file (1315 lines)
*   **Category:** SRP / Clarity / Maintainability
*   **Description:** The `server.py` file is very long and handles multiple distinct responsibilities: environment setup (`uv`, venv), subprocess execution helpers, FastAPI web server setup (routes, static files, SSE), MCP tool request processing logic, individual tool handlers, stdio mode implementation, and Typer CLI definition.
*   **Recommendation:** Refactor `server.py` into smaller, more focused modules. For example:
    *   `env_setup.py` for `prepare_workspace_env`, `_run_command_helper`.
    *   `web_server.py` or `api/` directory for FastAPI app, routes, SSE logic.
    *   `handlers.py` or `api/handlers/` for individual `handle_...` functions.
    *   `mcp_api.py` for `get_server_info`, `get_tool_schemas`.
    *   `stdio_server.py` for `run_stdio_mode`.
    *   `cli.py` for Typer app definition (`main`).
    *   Keep `server.py` as a minimal entry point or orchestrator if needed.
*   **Boomerang Task Title:** Refactor server.py into smaller modules

*   **File & Line(s):** 12, 85
*   **Category:** Clarity / Consistency
*   **Description:** The constant `VENV_DIR` is defined as ".venv-cadquery" (line 12) but the actual directory created/checked in `prepare_workspace_env` is ".venv" (line 85).
*   **Recommendation:** Use the constant consistently or update the constant definition to match the implementation (".venv").
*   **Boomerang Task Title:** Align VENV_DIR constant and usage in server.py

*   **File & Line(s):** 190, 191, 208, 209 (and usage throughout)
*   **Category:** Best Practices / State Management
*   **Description:** The server relies on global dictionaries (`shape_results`, `part_index`, `sse_connections`, `workspace_reqs_mtime_cache`) to maintain state across requests and connections. This can lead to issues with testing, concurrency (if async tasks modify shared state unexpectedly), and long-term state management (memory leaks, stale data if server runs long). `part_index` specifically seems vulnerable if multiple workspaces are scanned.
*   **Recommendation:** Encapsulate state within classes or application context (e.g., FastAPI dependencies, dedicated state management objects) instead of using raw global variables. Consider workspace-specific state management for `part_index` and `shape_results`.
*   **Boomerang Task Title:** Refactor global state management in server.py

*   **File & Line(s):** 51, 364, 622, 698, 768, 906, 961, 1007, 1036, 1056, 1059, 1107, 1157, etc.
*   **Category:** Error Handling
*   **Description:** Many functions and handlers use broad `except Exception as e:` clauses. While they log the error, they often re-raise a generic `Exception` or `RuntimeError`, potentially hiding the original exception type and making specific error handling by callers difficult.
*   **Recommendation:** Catch more specific exceptions where possible. If re-raising, consider preserving the original exception type or using custom exception classes with more context.
*   **Boomerang Task Title:** Improve specificity of exception handling in server.py

*   **File & Line(s):** 367-369 (`process_tool_request`)
*   **Category:** Error Handling / Clarity
*   **Description:** `process_tool_request` can return `None` if a handler runs without error but doesn't produce a `result_message`. This seems like an unexpected state and is only logged as a warning. Callers (stdio/SSE push) might expect a dictionary always.
*   **Recommendation:** Ensure `process_tool_request` always returns a dictionary, perhaps with a default success message or status if the handler didn't provide specific results but also didn't error.
*   **Boomerang Task Title:** Ensure process_tool_request always returns a response dict

*   **File & Line(s):** 664-672, 737-744, 1092-1099, 1142-1149
*   **Category:** Duplication (DRY)
*   **Description:** The logic for retrieving a result dictionary, getting the intermediate path, and importing the shape using `cq.importers.importBrep` is repeated in `handle_export_shape`, `handle_export_shape_to_svg`, `handle_get_shape_properties`, and `handle_get_shape_description`.
*   **Recommendation:** Create a helper function `_get_shape_from_result(result_id: str, shape_index: int) -> cq.Shape` that encapsulates this logic (retrieving from `shape_results`, checking validity, importing from intermediate path) and handles associated errors.
*   **Boomerang Task Title:** Refactor shape import logic into a helper function

*   **File & Line(s):** Throughout `handle_...` functions (e.g., 495-513, 633-645, 708-718)
*   **Category:** Duplication (DRY) / Clarity
*   **Description:** Argument retrieval (`args = request.get("arguments", {})`) and subsequent validation (`if not arg: raise ValueError(...)`) is boilerplate repeated in almost every tool handler.
*   **Recommendation:** Leverage FastAPI's Pydantic model integration for automatic request body parsing and validation. Define Pydantic models matching the `input_schema` for each tool. This eliminates manual parsing and validation code within the handlers, making them cleaner and leveraging FastAPI's built-in error responses.
*   **Boomerang Task Title:** Use Pydantic models for request validation in handlers

*   **File & Line(s):** 379, 582, 683, 990, 996
*   **Category:** Actionable Comments
*   **Description:** Several `TODO` comments exist indicating known areas for improvement or incomplete implementation:
    *   Line 379: Replace placeholder schemas with proper definitions (e.g., Pydantic).
    *   Line 582: Define the exact structure returned by `script_runner.py`.
    *   Line 683: Consider making the default output subdir name ("shapes") configurable.
    *   Line 990: Consider adding package whitelisting for security in `handle_install_workspace_package`.
    *   Line 996: Add logic to update workspace `requirements.txt` after installing a package.
*   **Recommendation:** Address these TODO items in separate tasks.
*   **Boomerang Task Title:** Address TODO comments in server.py

*   **File & Line(s):** 770-913 (`handle_scan_part_library`)
*   **Category:** Best Practices / Security / Consistency
*   **Description:** This handler executes library scripts (`.py` files) directly within the main server process using `cqgi.parse().build()` (lines 843-845). This differs from `handle_execute_cadquery_script` which uses an isolated subprocess and the workspace environment. Running potentially untrusted code from the library in the main server process is a security risk and doesn't guarantee access to the correct dependencies (it uses the server's venv + temporary `sys.path` modification, not the workspace's venv). `sys.path` modification is also generally discouraged.
*   **Recommendation:** Refactor `handle_scan_part_library` to use the same subprocess-based execution mechanism as `handle_execute_cadquery_script` (via `script_runner.py`) to ensure isolation, security, and use of the correct workspace environment for executing part scripts. This might require adjustments to `script_runner.py` to handle metadata parsing or return necessary info.
*   **Boomerang Task Title:** Refactor handle_scan_part_library to use subprocess execution

*   **File & Line(s):** `handle_execute_cadquery_script`, `handle_scan_part_library`, etc.
*   **Category:** Documentation
*   **Description:** While most handlers have basic docstrings, complex functions like `handle_execute_cadquery_script` and `handle_scan_part_library` could benefit from more detailed explanations of their logic, assumptions (e.g., script runner JSON structure), error conditions, and interactions with global state or subprocesses.
*   **Recommendation:** Enhance docstrings for complex handlers and core logic functions to improve maintainability and understanding.
*   **Boomerang Task Title:** Improve docstrings in server.py handlers

### `src/mcp_cadquery_server/__init__.py`

*   Standard package marker file. No specific findings based on review criteria.

### `src/mcp_cadquery_server/core.py`

*   **File & Line(s):** 16-51 (`parse_docstring_metadata`)
*   **Category:** Clarity / Robustness
*   **Description:** The metadata parsing logic relies on simple string splitting and explicit checks for known multi-word keys like "part name". This could be brittle if new multi-word keys are introduced or if values contain colons. The snake_case conversion is also basic.
*   **Recommendation:** Consider using a more robust parsing approach, perhaps regular expressions or a simple state machine, to handle keys and values more reliably, especially if values might contain colons. Alternatively, clearly document the expected format (single word keys or specific known multi-word keys).
*   **Boomerang Task Title:** Improve robustness of docstring metadata parsing

*   **File & Line(s):** 65-84 (`_substitute_parameters`)
*   **Category:** Clarity / Best Practices
*   **Description:** This function substitutes parameters based on a `# PARAM` comment marker. While functional, this approach is less standard than using function arguments or dedicated templating engines. It also relies on `repr()` for formatting, which might not be ideal for all types or complex objects. The function is marked as private (`_`) but is imported and used in `server.py` (line 178).
*   **Recommendation:** Evaluate if this parameter substitution mechanism is still the best approach. If kept, improve the documentation significantly to explain its usage and limitations. Consider renaming it to remove the leading underscore if it's intended for external use by `server.py`. Explore alternatives like passing parameters directly to `model.build(parameters=...)` if CQGI supports it, or using a lightweight templating approach if more complex substitutions are needed.
*   **Boomerang Task Title:** Review and potentially refactor parameter substitution logic

*   **File & Line(s):** 86-100 (`export_shape_to_file`), 102-122 (`export_shape_to_svg_file`)
*   **Category:** Duplication (DRY) / Error Handling
*   **Description:** Both export functions repeat the logic for extracting the `cq.Shape` from a potential `cq.Workplane`, checking the type, ensuring the output directory exists, and the broad `except Exception` block.
*   **Recommendation:** Create a helper function or decorator to handle the shape extraction/validation and directory creation. Refine the exception handling to catch more specific errors from `exporters.export` if possible (e.g., `IOError`, specific CadQuery export errors).
*   **Boomerang Task Title:** Refactor common logic in export functions

*   **File & Line(s):** 124-195 (`get_shape_properties`), 197-286 (`get_shape_description`)
*   **Category:** Error Handling / Clarity
*   **Description:** Both functions calculate multiple properties/description parts within nested `try...except Exception` blocks. While this prevents one failed calculation from stopping others, it logs only warnings and continues. The final return value might contain `None` for several properties without a clear overall error indication unless the outer `try...except` is hit. `get_shape_description` calls `get_shape_properties`, potentially duplicating warnings.
*   **Recommendation:** Improve error aggregation. Instead of just logging warnings, consider collecting specific errors encountered during property calculation (e.g., in a separate 'errors' dictionary within the result). This gives the caller more insight into *what* failed. In `get_shape_description`, check for errors returned by `get_shape_properties` before attempting to use potentially missing values.
*   **Boomerang Task Title:** Improve error reporting in shape property/description functions

*   **File & Line(s):** 187, 278
*   **Category:** Actionable Comments
*   **Description:** TODO comments exist:
    *   Line 187: Add more properties to `get_shape_properties`.
    *   Line 278: Add more sophisticated analysis to `get_shape_description`.
*   **Recommendation:** Address these TODOs in separate tasks if the additional features are desired.
*   **Boomerang Task Title:** Address TODO comments in core.py

*   **File & Line(s):** General
*   **Category:** Documentation
*   **Description:** Docstrings are generally good, explaining purpose, args, and returns. Some could be slightly enhanced with more detail on potential failure modes or edge cases (e.g., `parse_docstring_metadata` format assumptions).
*   **Recommendation:** Minor enhancements to docstrings for clarity on assumptions and potential errors. (Low priority)
*   **Boomerang Task Title:** Minor docstring enhancements in core.py

### `src/mcp_cadquery_server/main.py`

*   **File & Line(s):** Entire file
*   **Category:** Duplication (DRY) / Maintainability
*   **Description:** This file appears to contain a large amount of duplicated or potentially outdated code compared to `server.py` and `src/mcp_cadquery_server/core.py`. It redefines FastAPI setup, state management, SSE logic, tool handlers, helper functions, and CLI definitions. It seems likely that `server.py` is the intended main entry point, making this file redundant.
*   **Recommendation:** Verify if this file is still used or intended as an alternative entry point. If it's redundant, remove it to avoid confusion and maintenance overhead. If it serves a specific purpose, document it clearly and refactor heavily to remove duplication by importing shared logic from other modules (like `core.py`, and potentially the refactored modules proposed for `server.py`).
*   **Boomerang Task Title:** Investigate and remove/refactor redundant main.py

### `src/mcp_cadquery_server/script_runner.py`

*   **File & Line(s):** 1, 14
*   **Category:** Best Practices
*   **Description:** Duplicate shebang lines (`#!/usr/bin/env python3` and `#!/usr/bin/env python`). Only the first one is effective.
*   **Recommendation:** Remove the second shebang (line 14).
*   **Boomerang Task Title:** Remove duplicate shebang in script_runner.py

*   **File & Line(s):** 45-67 (`_substitute_parameters`)
*   **Category:** Duplication (DRY)
*   **Description:** The `_substitute_parameters` function is duplicated from `src/mcp_cadquery_server/core.py`.
*   **Recommendation:** Remove this duplicated function. If parameter substitution is needed *before* calling the script runner, it should happen in the calling process (`server.py`). If substitution needs to happen *within* the isolated environment, the logic should ideally be part of the CQGI execution itself or a shared utility module importable by both `core.py` and `script_runner.py` (though the latter might be complex given the separate environments). The current approach in `server.py` already performs substitution before calling the runner, making this duplicate unnecessary.
*   **Boomerang Task Title:** Remove duplicated parameter substitution logic from script_runner.py

*   **File & Line(s):** 70-211 (`run`)
*   **Category:** SRP / Clarity
*   **Description:** The `run()` function handles multiple responsibilities: reading/parsing stdin, modifying `sys.path`, parameter substitution (using the duplicated function), importing CadQuery, running CQGI, processing results, exporting intermediate files, and formatting JSON output.
*   **Recommendation:** Break down `run()` into smaller, more focused functions (e.g., `_read_input`, `_setup_environment`, `_execute_script`, `_process_results`, `_write_output`).
*   **Boomerang Task Title:** Refactor run() function in script_runner.py

*   **File & Line(s):** 196-201, 207-211
*   **Category:** Error Handling
*   **Description:** Uses broad `except Exception` clauses for the main execution block and JSON serialization fallback.
*   **Recommendation:** Catch more specific exceptions where possible (e.g., `json.JSONDecodeError`, `ValueError` for input validation, `ImportError`, specific CQGI or exporter errors, `IOError`/`OSError` for file operations).
*   **Boomerang Task Title:** Improve specificity of exception handling in script_runner.py

*   **File & Line(s):** 147-194 (Result processing and export)
*   **Category:** Best Practices / Resource Management
*   **Description:** The script exports intermediate BREP files to a `.cq_results/<result_id>/` directory within the workspace. There is no mechanism apparent in this script or `server.py` to clean up these intermediate files after they are used (e.g., for export or property calculation). This could lead to accumulation of files over time.
*   **Recommendation:** Implement a cleanup strategy. Options include:
    *   The script runner could delete the intermediate file/directory after successfully sending the result JSON.
    *   The main server process (`server.py`) could delete the directory after processing the result (e.g., after exports are done).
    *   A periodic cleanup task could remove old directories from `.cq_results`.
*   **Boomerang Task Title:** Implement cleanup for intermediate result files (.cq_results)

*   **File & Line(s):** General (Output JSON structure)
*   **Category:** Clarity / API Definition
*   **Description:** The structure of the JSON dictionary printed to stdout (lines 205-211) serves as the API contract between the runner and the main server. This structure (containing `success`, `results`, `exception_str`, `intermediate_path`, `export_error`) should be clearly defined and documented, ideally matching the TODO in `server.py` (line 582).
*   **Recommendation:** Define a clear schema (e.g., using comments, or ideally aligning with future Pydantic models used in the server) for the output JSON structure and ensure the implementation consistently adheres to it.
*   **Boomerang Task Title:** Define and document script_runner.py output JSON schema

---

## Test Code (`tests/`)

### `tests/test_cadquery_core.py`

*   **File & Line(s):** 6, 8
*   **Category:** Best Practices
*   **Description:** Duplicate import of `unittest.mock.patch` and `unittest.mock.MagicMock`.
*   **Recommendation:** Remove the second import line (line 8).
*   **Boomerang Task Title:** Remove duplicate mock imports in test_cadquery_core.py

*   **File & Line(s):** 14
*   **Category:** Best Practices
*   **Description:** Line 14 contains a comment "# Removed incorrect import line" but no actual code.
*   **Recommendation:** Remove the comment line if it's no longer relevant.
*   **Boomerang Task Title:** Remove obsolete comment in test_cadquery_core.py

*   **File & Line(s):** 25, 28, 33, 37, 41, 46, 48, 52, 59, 60, 71, 86, 91, 96, 100, 104, 111, 115, 122, 126, 133, 137, 145, 149, 153, 160, 168, 173, 178, 182, 186, 198, 206, 223, 227, 248, 252, 269, 272, 274, 281, 284, 292, 295, 304, 307, 316, 323, 334, 344
*   **Category:** Best Practices / Clarity
*   **Description:** Extensive use of `print()` statements for test progress/debugging. While useful during development, these should ideally be removed or replaced with logging for cleaner test output, especially in CI environments.
*   **Recommendation:** Remove `print()` statements or replace them with `logging.debug()` if detailed tracing is needed during test runs (ensure logging is configured appropriately for tests, perhaps via `pytest.ini` or fixtures).
*   **Boomerang Task Title:** Replace print statements with logging in test_cadquery_core.py

*   **File & Line(s):** 106-153, 277-307, 311-323, 327-344
*   **Category:** Best Practices / Test Structure
*   **Description:** Several tests rely heavily on patching internal methods (`cadquery.Shape.BoundingBox`, `cadquery.Shape.Volume`, etc.) or the logger (`src.mcp_cadquery_server.core.log`) to test specific exception paths within `get_shape_properties` and `get_shape_description`. While necessary for unit testing error handling, excessive patching can make tests brittle and tightly coupled to implementation details.
*   **Recommendation:** Review if some error conditions could be tested with carefully crafted input shapes instead of patching internal calls. For example, testing `get_shape_properties` with a `cq.Edge` or `cq.Face` should naturally result in `Volume` being `None`. Keep patching where necessary for specific internal error simulation but minimize where possible.
*   **Boomerang Task Title:** Review patching strategy in test_cadquery_core.py

*   **File & Line(s):** 151-153
*   **Category:** Duplication (DRY)
*   **Description:** The assertion `assert any("Could not calculate center of mass" in call.args[0] for call in mock_log.warning.call_args_list)` is duplicated.
*   **Recommendation:** Remove the duplicate assertion line (153).
*   **Boomerang Task Title:** Remove duplicate assertion in test_get_shape_properties_center_exception

*   **File & Line(s):** 325, 346
*   **Category:** Best Practices
*   **Description:** Lines 325 and 346 contain comments "# Removed duplicated code block" and "# Removed failing test_export_box_tjs" respectively, but no actual code.
*   **Recommendation:** Remove these comment lines if they are no longer relevant.
*   **Boomerang Task Title:** Remove obsolete comments in test_cadquery_core.py

### `tests/test_cli.py`

*   **File & Line(s):** 6-8, 10-12
*   **Category:** Best Practices
*   **Description:** Commented-out code related to `sys.path` modification and `CliRunner` usage.
*   **Recommendation:** Remove the commented-out lines if they are no longer needed.
*   **Boomerang Task Title:** Remove commented-out code in test_cli.py

*   **File & Line(s):** 16
*   **Category:** Clarity / Consistency
*   **Description:** The `VENV_DIR` constant is defined as ".venv-cadquery", which might be inconsistent with the actual directory used by `server.py` (".venv"). This could cause tests to fail if the venv path is incorrect.
*   **Recommendation:** Ensure this path matches the actual venv directory created and used by `server.py`. Align the constant definition if necessary (potentially define it once globally or in a shared test config).
*   **Boomerang Task Title:** Align VENV_DIR constant in test_cli.py with server.py usage

*   **File & Line(s):** 27, 36-38, 69-74, 88-90
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_cli.py

*   **File & Line(s):** 41-57, 94-102 (`test_cli_help`, `test_cli_default_invocation_help`)
*   **Category:** Duplication (DRY)
*   **Description:** The assertions checking the content of the `--help` output are largely duplicated between these two tests.
*   **Recommendation:** Create a helper function `_check_help_output(output: str)` that performs the common assertions, and call it from both tests.
*   **Boomerang Task Title:** Refactor help output assertions in test_cli.py

*   **File & Line(s):** 70 (`test_cli_stdio_invocation`)
*   **Category:** Best Practices / Robustness
*   **Description:** The test relies on a hardcoded `timeout=3` to check if the stdio mode starts without crashing. This might be unreliable depending on system load or environment setup time.
*   **Recommendation:** Explore alternative ways to verify stdio mode startup. Perhaps send a simple, valid JSON request immediately after starting the process and check for a valid JSON response (or a specific error if the request is invalid) within the timeout, rather than just relying on the timeout itself.
*   **Boomerang Task Title:** Improve robustness of stdio invocation test in test_cli.py

*   **File & Line(s):** 105
*   **Category:** Actionable Comments
*   **Description:** Comment suggests adding more specific CLI tests (e.g., invalid args).
*   **Recommendation:** Add tests for invalid arguments or edge cases for the CLI options if desired.
*   **Boomerang Task Title:** Add tests for invalid CLI arguments

### `tests/test_core_helpers.py`

*   **File & Line(s):** General
*   **Category:** Documentation / Clarity
*   **Description:** Tests are clear and cover many cases for the two helper functions (`parse_docstring_metadata`, `_substitute_parameters`). Test names accurately reflect the scenario being tested. No major issues found.
*   **Recommendation:** No specific actions required. Good test coverage for these helpers.

### `tests/test_environment.py`

*   **File & Line(s):** 6, 16
*   **Category:** Clarity / Consistency
*   **Description:** The `VENV_DIR` constant is defined as ".venv-cadquery", which might be inconsistent with the actual directory used by `server.py` (".venv"). This could cause tests to fail if the venv path is incorrect.
*   **Recommendation:** Ensure this path matches the actual venv directory created and used by `server.py`. Align the constant definition if necessary (potentially define it once globally or in a shared test config).
*   **Boomerang Task Title:** Align VENV_DIR constant in test_environment.py with server.py usage

*   **File & Line(s):** 8
*   **Category:** Best Practices
*   **Description:** Commented-out code `SETUP_SCRIPT = "./setup_env.py"`.
*   **Recommendation:** Remove the commented-out line.
*   **Boomerang Task Title:** Remove commented-out code in test_environment.py

*   **File & Line(s):** 17-31
*   **Category:** Best Practices / Maintainability
*   **Description:** Complex `try...except ImportError` block to handle importing `server` components depending on how pytest is run (from root or tests dir). This indicates potential issues with project structure or PYTHONPATH setup for testing.
*   **Recommendation:** Standardize the test execution environment (e.g., always run pytest from the project root) and ensure the `src` directory is correctly added to PYTHONPATH (e.g., via `pytest.ini` `pythonpath` setting or `conftest.py`) to simplify imports. Remove the `try...except` block once imports are reliable.
*   **Boomerang Task Title:** Simplify imports in test_environment.py by standardizing test setup

*   **File & Line(s):** 41, 51-53, 57-58, 84, 92, 134, 151, 163, 188, 211, 254, 280, 296, 312, 337, 354, 379, 403, 412, 427, 443, 459, 464
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_environment.py

*   **File & Line(s):** 70-134, 137-188, 192-254, 258-312, 316-379, 383-443
*   **Category:** Duplication (DRY) / Test Structure
*   **Description:** Significant duplication exists across the tests for `prepare_workspace_env`. Each test repeats:
    *   Mocking `_run_command_helper` and `shutil.which`.
    *   Defining expected paths (`venv_dir`, `expected_python_exe`).
    *   Defining a `side_effect_run_helper` function (often with minor variations).
    *   Clearing the `workspace_reqs_mtime_cache`.
    *   Calling `prepare_workspace_env`.
    *   Asserting the returned path and `mock_which` call.
    *   Asserting the calls made to `mock_run_helper`.
*   **Recommendation:** Refactor using pytest fixtures and helper functions:
    *   Create a fixture (e.g., `mocked_env_setup`) that patches `_run_command_helper` and `shutil.which`, clears the cache, and potentially returns the mocks.
    *   Create helper functions for common actions like setting up dummy venv structures or requirements files within `tmp_path`.
    *   Create helper functions for asserting common call patterns to `mock_run_helper`.
    *   This will significantly reduce boilerplate and make tests easier to read and maintain.
*   **Boomerang Task Title:** Refactor test_environment.py using fixtures and helpers

*   **File & Line(s):** 82-99, 154-161, 209-223, 277-288, 335-346, 401-414
*   **Category:** Clarity / Test Structure
*   **Description:** The `side_effect_run_helper` functions defined within each test are complex and contain test-specific logic (e.g., creating dummy files, raising specific errors, asserting call arguments). This makes the tests harder to follow.
*   **Recommendation:** Simplify the side effect functions. They should primarily focus on returning appropriate `CompletedProcess` objects or raising predefined exceptions based on the input command. File creation/setup should happen in the test setup or fixtures. Assertions about *which* commands were called should happen *after* the function under test is executed, using `mock_run_helper.assert_has_calls` or similar, rather than within the side effect function itself.
*   **Boomerang Task Title:** Simplify side_effect functions in test_environment.py

### `tests/test_examples.py`

*   **File & Line(s):** 5, 6
*   **Category:** Best Practices
*   **Description:** Imports `requests` and `uuid` but they are not used in the file.
*   **Recommendation:** Remove the unused imports.
*   **Boomerang Task Title:** Remove unused imports in test_examples.py

*   **File & Line(s):** 11
*   **Category:** Clarity / Consistency
*   **Description:** The `VENV_DIR` constant is defined as ".venv-cadquery", which might be inconsistent with the actual directory used by `server.py` (".venv").
*   **Recommendation:** Ensure this path matches the actual venv directory created and used by `server.py`. Align the constant definition if necessary (potentially define it once globally or in a shared test config).
*   **Boomerang Task Title:** Align VENV_DIR constant in test_examples.py with server.py usage

*   **File & Line(s):** 27, 45, 51-53, 62, 69, 75-77, 86
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_examples.py

*   **File & Line(s):** 43, 66-67
*   **Category:** Test Structure / Clarity
*   **Description:** `test_run_example_script` does not mock `requests.post`, while `test_run_samples_script` does. Both tests seem designed to test the scenario where the server is *not* running, relying on the underlying `requests` library to raise a connection error which the scripts are expected to handle. Mocking `requests.post` in `test_run_samples_script` seems unnecessary for testing the connection error handling path and might hide potential issues if the script's error handling relies on specific `requests` exception types.
*   **Recommendation:** Remove the `@patch('requests.post')` and the `mock_post` argument from `test_run_samples_script` if the goal is purely to test the script's behavior when the server connection fails. If the intention was different (e.g., testing the script's logic *after* a successful mock connection), the test needs significant changes.
*   **Boomerang Task Title:** Review/remove unnecessary patching in test_run_samples_script

*   **File & Line(s):** General
*   **Category:** Test Structure / Scope
*   **Description:** These tests act more like integration tests, running external scripts via subprocess and checking output. They only cover the failure path (server not running). They don't test the successful execution path of the example scripts (which would require a running server or more complex mocking).
*   **Recommendation:** Consider if these tests provide sufficient value as they are (testing connection error handling). If testing the success path is desired, a different approach involving a running test server (e.g., using `FastAPI.TestClient` or running the server in a separate thread/process fixture) and potentially mocking the `subprocess.run` call within the example scripts would be needed. Alternatively, keep these as basic "script runs without crashing on connection error" checks.
*   **Boomerang Task Title:** Evaluate scope and approach of example script tests

### `tests/test_part_library.py`

*   **File & Line(s):** 38-90 (`_test_handle_scan_part_library`), 93-113 (`_test_handle_search_parts`)
*   **Category:** Duplication (DRY) / Test Structure
*   **Description:** These functions duplicate the logic of the actual handlers in `server.py` to allow testing against a local, in-memory `test_part_index`. While enabling isolated testing, this creates significant maintenance overhead, as changes in the real handlers must be manually mirrored here.
*   **Recommendation:** Refactor these tests to test the *actual* handlers from `server.py`. This likely requires:
    *   Refactoring `server.py` to make handlers and state management more easily importable and testable (see `server.py` findings).
    *   Using pytest fixtures to manage the state (`part_index`) and potentially mock dependencies (like file system access or `execute_cqgi_script` if focusing purely on the handler logic vs. the full scan process).
    *   Alternatively, if testing the full scan process including file I/O is desired, keep the fixture that creates temporary files but call the *real* `handle_scan_part_library` function, potentially patching the global `part_index` it uses or refactoring state management.
*   **Boomerang Task Title:** Refactor test_part_library.py to test actual handlers

*   **File & Line(s):** 118-186 (`manage_library_state_and_files` fixture)
*   **Category:** Clarity / Test Structure
*   **Description:** The fixture hardcodes example part script content (lines 134-139). It also contains complex logic for creating/checking/updating these files based on content and mtime, and cleaning up directories.
*   **Recommendation:** Move the example part script content to separate files within the `tests/` directory (e.g., `tests/fixtures/part_library/`). The fixture can then copy these files to the temporary test library directory (`TEST_LIBRARY_DIR`). This improves readability and makes the example parts easier to manage. Simplify the file writing logic if possible (e.g., always overwrite).
*   **Boomerang Task Title:** Externalize example part scripts in test_part_library.py fixture

*   **File & Line(s):** 179, 183, 186 (Fixture Teardown)
*   **Category:** Best Practices / Error Handling
*   **Description:** Error handling during teardown (removing test files/dirs) uses `print` instead of logging or raising an error that would fail the test. While teardown failures can sometimes be ignored, hiding `OSError` might mask underlying issues.
*   **Recommendation:** Consider logging errors during teardown or using a more robust cleanup mechanism (e.g., pytest's `tmp_path` fixture handles cleanup automatically). If manual cleanup is kept, log errors properly.
*   **Boomerang Task Title:** Improve error handling in test_part_library.py fixture teardown

*   **File & Line(s):** 86, 156, 162, 166, 196, 224, 232, 241, 260, 272, 287, 298, 317, 327, 337, 350, 355, 364, 371, 377, 383, 389, 395, 401, 407, 413, 417, 423, 429, 435, 439
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_part_library.py

*   **File & Line(s):** 301-337 (`test_handle_scan_part_library_empty_dir`)
*   **Category:** Test Structure / Clarity
*   **Description:** This test uses `os.rename` to temporarily move the test library directory, create an empty one, run the scan, and then restore the original. This is complex and potentially fragile.
*   **Recommendation:** Simplify the test setup. Use the `tmp_path` fixture provided by pytest. Create an empty directory within `tmp_path` and pass that path to the scan handler. This avoids renaming and potential cleanup issues.
*   **Boomerang Task Title:** Simplify empty directory test setup in test_part_library.py

### `tests/test_script_runner.py`

*   **File & Line(s):** 25, 29, 42-43, 55-57
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_script_runner.py

*   **File & Line(s):** 160-163 (`test_script_runner_export_failure`)
*   **Category:** Test Structure / Clarity
*   **Description:** This test simulates an export failure by creating a *file* named `.cq_results` to block directory creation. This is clever but might be slightly obscure.
*   **Recommendation:** Consider if mocking `os.makedirs` within the `script_runner` process (if possible via patching or environment variables) would be a clearer way to simulate this specific failure. Keep the current approach if mocking is too complex, but add a comment explaining the technique.
*   **Boomerang Task Title:** Clarify or refactor export failure test setup in test_script_runner.py

*   **File & Line(s):** 186-198 (`test_script_runner_general_exception`)
*   **Category:** Test Structure / Clarity
*   **Description:** This test mocks `json.loads` to simulate an error during input reading. It then runs the script runner directly using `subprocess.run` instead of the `run_script_runner` helper, because the helper itself uses `json.dumps` which would interfere.
*   **Recommendation:** This approach is reasonable given the need to bypass the helper. Ensure comments clearly explain why the helper isn't used here.
*   **Boomerang Task Title:** Add comment explaining direct subprocess use in test_script_runner_general_exception

*   **File & Line(s):** 214-234 (`test_script_runner_coverage_import_error`)
*   **Category:** Test Structure / Clarity
*   **Description:** Tests that the runner doesn't crash if `coverage` import fails when the `COVERAGE_RUN_SUBPROCESS` environment variable is set. This relies on patching the `builtins.__import__` function.
*   **Recommendation:** This is a valid way to test the `try...except ImportError` block. Ensure the test name and docstring clearly state the purpose.
*   **Boomerang Task Title:** No action needed for test_script_runner_coverage_import_error

*   **File & Line(s):** General
*   **Category:** Test Coverage
*   **Description:** The tests cover success cases, syntax errors, CadQuery errors, export errors, input errors, and import errors. This seems like good coverage for the script runner's core functionality and error handling paths.
*   **Recommendation:** No specific actions required regarding coverage based on this review (though coverage reports should be the definitive source).

### `tests/test_server_execution.py`

*   **File & Line(s):** 17-28
*   **Category:** Best Practices / Maintainability
*   **Description:** Complex `try...except ImportError` block to handle importing `server` components. Similar to `test_environment.py`.
*   **Recommendation:** Standardize test execution environment and imports (see recommendation for `test_environment.py`).
*   **Boomerang Task Title:** Simplify imports in test_server_execution.py by standardizing test setup

*   **File & Line(s):** 50, 66, 70, 75, 80, 86, 94, 100, 106, 114, 118, 142, 155, 170, 190, 200, 219, 250, 283, 303, 329, 353, 364, 390, 404, 445, 469
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_server_execution.py

*   **File & Line(s):** 62-118 (`test_execute_...` functions)
*   **Category:** Test Structure / Scope
*   **Description:** These tests target the `execute_cqgi_script` function imported directly from `core.py`. They test the in-process execution logic, not the full API handler (`handle_execute_cadquery_script`) which involves subprocesses.
*   **Recommendation:** Rename these tests or the test file (e.g., `test_core_execution.py`) to clarify they are testing the core execution function, not the server handler or the full integration path. Keep them as valuable unit tests for the core logic.
*   **Boomerang Task Title:** Clarify scope of execute_cqgi_script tests

*   **File & Line(s):** 121-122
*   **Category:** Best Practices
*   **Description:** Comment indicates parameter injection tests were removed.
*   **Recommendation:** Remove the comment lines if parameter injection is no longer relevant or tested elsewhere.
*   **Boomerang Task Title:** Remove obsolete comment in test_server_execution.py

*   **File & Line(s):** 132, 192, 252, 331, 420
*   **Category:** Best Practices / Test Structure
*   **Description:** Several integration tests are marked with `@pytest.mark.skip(reason="Integration test unstable under coverage")`. This indicates potential flakiness or issues when run under code coverage analysis, possibly due to timing, subprocess interaction, or coverage tool interference.
*   **Recommendation:** Investigate the root cause of the instability under coverage. Skipping tests reduces confidence. Potential causes:
    *   Timing issues: Increase `time.sleep()` values or implement more robust checks for background task completion (e.g., polling an expected file or state).
    *   Coverage tool interaction: Ensure coverage is configured correctly for subprocesses (seems to be handled in `script_runner.py`, but verify). Check for known issues with the coverage tool and subprocesses/asyncio.
    *   Resource contention: Running multiple subprocesses might cause issues in constrained CI environments.
    *   If the instability cannot be easily fixed, consider alternative testing strategies (e.g., more focused integration tests with mocks, separate performance/stress tests).
*   **Boomerang Task Title:** Investigate and fix skipped integration tests instability under coverage

*   **File & Line(s):** 133-469 (Integration Tests)
*   **Category:** Test Structure / Maintainability
*   **Description:** These integration tests use `FastAPI.TestClient` to call API endpoints (`/mcp/execute`). They mock `prepare_workspace_env` but let the actual `handle_execute_cadquery_script` run, which in turn calls `script_runner.py` via `subprocess.run`. They rely on `time.sleep()` to wait for the background task and subprocess to complete, then check the global `shape_results` state and potentially created files.
*   **Recommendation:**
    *   Replace `time.sleep()` with more reliable synchronization methods if possible (e.g., if the server provided status updates or completion events). If not feasible, ensure sleep times are generous but document the potential flakiness.
    *   Checking global state (`shape_results`) makes tests dependent on server implementation details. Ideally, tests should verify results based on API responses or observable side effects (like file creation), although this might be difficult if the API only returns "processing". Consider if the API could be enhanced to provide final results later (e.g., via another endpoint or SSE message).
    *   Mocking `prepare_workspace_env` to return `sys.executable` (lines 141, 198, 259, 338, 426) assumes the test environment has the necessary dependencies (like CadQuery) installed globally. This might not be true in all environments and couples the test to the system Python. A better approach for true integration testing might involve letting `prepare_workspace_env` run (or mocking `_run_command_helper` within it) to create a dedicated, isolated venv for the test workspace. This would be slower but more realistic.
*   **Boomerang Task Title:** Improve reliability and isolation of integration tests in test_server_execution.py

*   **File & Line(s):** 332-368 (`test_integration_execute_with_installed_package`)
*   **Category:** Test Structure / Clarity
*   **Description:** This test mocks `_run_command_helper` to simulate the package install step, then resets the mock before the execution step. This works but adds complexity. The script executed (lines 371-378) doesn't actually *use* the installed package (`path.py`) due to the print being commented out; it just imports `pathlib`.
*   **Recommendation:** Simplify the test. If the goal is to test that the script runner can import packages installed in the workspace venv, the `install_workspace_package` tool doesn't necessarily need to be called via the API in the *same* test. A simpler test could:
    1.  Use a fixture or setup step to manually install a test package (like `path.py`) into a temporary workspace venv using `uv`.
    2.  Run the `execute_cadquery_script` handler (via API or direct call if refactored) with a script that *actually* imports and uses the test package.
    3.  Verify successful execution.
    Alternatively, modify the script content (line 371-378) to actually use `path.py` if the current structure is kept.
*   **Boomerang Task Title:** Refactor or fix package usage in test_integration_execute_with_installed_package

### `tests/test_server_export.py`

*   **File & Line(s):** 35-36
*   **Category:** Best Practices
*   **Description:** Comment indicates fixture `stored_build_result_id` was removed.
*   **Recommendation:** Remove the comment lines.
*   **Boomerang Task Title:** Remove obsolete comment in test_server_export.py

*   **File & Line(s):** 48, 50, 58
*   **Category:** Best Practices / Error Handling
*   **Description:** Error handling during fixture setup/teardown uses `print` instead of logging or failing the test.
*   **Recommendation:** Log errors properly or allow exceptions to propagate to fail the test if directory creation/removal is critical.
*   **Boomerang Task Title:** Improve error handling in test_server_export.py fixture

*   **File & Line(s):** 66, 71, 76, 81, 86, 89, 97, 103, 109, 119, 125, 130, 136, 141, 150, 159
*   **Category:** Best Practices / Clarity
*   **Description:** Use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_server_export.py

*   **File & Line(s):** 113-118 (`test_export_workplane_to_stl_success`)
*   **Category:** Best Practices / Robustness
*   **Description:** Test checks for binary STL by catching `UnicodeDecodeError` and checking `len(bytes) > 80`. This is a reasonable heuristic but not guaranteed to be correct for all valid binary STL files.
*   **Recommendation:** If precise validation is needed, consider using a dedicated STL parsing library or more specific checks on the binary header format. For current purposes, the heuristic might be sufficient, but add a comment explaining its limitations.
*   **Boomerang Task Title:** Add comment or improve validation for binary STL check

*   **File & Line(s):** 161-163
*   **Category:** Best Practices
*   **Description:** Comment indicates tests for `handle_export_shape_to_svg` were removed because the handler isn't directly testable here.
*   **Recommendation:** Remove the comment lines. Handler tests should reside in `test_server_handlers.py`.
*   **Boomerang Task Title:** Remove obsolete comment in test_server_export.py

### `tests/test_server_handlers.py`

*   **File & Line(s):** 17-32
*   **Category:** Best Practices / Maintainability
*   **Description:** Complex `try...except ImportError` block to handle importing `server` components. Similar to `test_environment.py` and `test_server_execution.py`.
*   **Recommendation:** Standardize test execution environment and imports (see recommendation for `test_environment.py`).
*   **Boomerang Task Title:** Simplify imports in test_server_handlers.py by standardizing test setup

*   **File & Line(s):** 50, 66, 70, 75, 80, 86, 94, 100, 106, 114, 118, 142, 155, 170, 190, 200, 219, 250, 283, 303, 329, 353, 364, 390, 404, 445, 469, etc. (Throughout file)
*   **Category:** Best Practices / Clarity
*   **Description:** Extensive use of `print()` statements for debugging/progress.
*   **Recommendation:** Remove `print()` statements or replace with logging for cleaner test output.
*   **Boomerang Task Title:** Replace print statements with logging in test_server_handlers.py

*   **File & Line(s):** 54-159 (`manage_state_and_test_files` fixture)
*   **Category:** Duplication (DRY) / Test Structure
*   **Description:** This fixture is very similar to the one in `test_part_library.py`. It sets up temporary directories, patches global paths, and creates dummy part files.
*   **Recommendation:** Consolidate common test setup logic into a shared `conftest.py` file at the `tests/` directory level. This fixture could provide the temporary paths and potentially the `TestClient`. Individual test files can then have smaller, more specific fixtures if needed.
*   **Boomerang Task Title:** Consolidate common test setup into conftest.py

*   **File & Line(s):** 175-441 (API Tests using TestClient)
*   **Category:** Test Structure / Scope
*   **Description:** These tests use `TestClient` to make POST requests to `/mcp/execute`, simulating MCP client calls. They mock underlying functions (`prepare_workspace_env`, `subprocess.run`, `cq.importers.importBrep`, `export_shape_to_file`, etc.) to isolate the handler logic being tested. They check the immediate "processing" response and then wait using `time.sleep()` before checking the expected side effects (e.g., changes in global state like `shape_results`, calls to mocks).
*   **Recommendation:**
    *   This approach of testing handlers via `TestClient` while mocking deeper dependencies is valid for unit/integration testing of the handlers themselves.
    *   As noted previously, `time.sleep()` is potentially flaky. Explore if the background tasks created by the endpoint (`asyncio.create_task(_process_and_push)`) can be awaited or monitored more directly in the test environment. If using `pytest-asyncio`, it might offer utilities for this.
    *   Checking global state (`shape_results`) couples tests to implementation. Where possible, assert based on the *intended* outcome (e.g., was the correct export function called with the right arguments?) rather than the intermediate state variable.
*   **Boomerang Task Title:** Improve async task handling and state checking in test_server_handlers.py

*   **File & Line(s):** 344-368 (`test_mcp_execute_export_svg_success`)
*   **Category:** Test Structure / Clarity
*   **Description:** This test mocks both `cadquery.importers.importBrep` and `server.export_shape_to_svg_file`. This effectively tests that the handler correctly retrieves the intermediate path, calls import, and then calls the export function with the right arguments, without actually performing the import or export.
*   **Recommendation:** This is a good example of isolating the handler logic. Ensure test names and docstrings clearly reflect what is being mocked and tested.
*   **Boomerang Task Title:** No action needed for test_mcp_execute_export_svg_success mocking strategy

*   **File & Line(s):** 1460-1486 (`test_sse_connection_sends_server_info`)
*   **Category:** Test Structure / Clarity
*   **Description:** Mocks `asyncio.Queue` to intercept the message put onto the queue when an SSE connection is established.
*   **Recommendation:** This is a valid approach for testing the SSE connection logic without needing a full SSE client.
*   **Boomerang Task Title:** No action needed for test_sse_connection_sends_server_info mocking strategy

*   **File & Line(s):** 1490-1582 (`test_stdio_mode_sends_server_info`)
*   **Category:** Test Structure / Clarity
*   **Description:** Tests the stdio mode startup by running `server.run_stdio_mode()` in a separate thread and capturing stdout. It mocks `asyncio.StreamReader.readline` to simulate EOF after the initial `server_info` is sent.
*   **Recommendation:** This is a reasonable way to test the stdio startup sequence and `server_info` output without fully blocking or needing complex input simulation.
*   **Boomerang Task Title:** No action needed for test_stdio_mode_sends_server_info structure

### `tests/test_server_logic.py`

*   **File & Line(s):** General
*   **Category:** Best Practices
*   **Description:** File is intentionally empty, indicating tests were refactored.
*   **Recommendation:** Consider removing the empty file if it serves no purpose, or keep it with the comment if it helps document the refactoring history.
*   **Boomerang Task Title:** Consider removing empty test_server_logic.py

---

## MCP API Definition (`server.py`)

*   **File & Line(s):** 376-456 (`get_tool_schemas`)
*   **Category:** API Clarity / Best Practices
*   **Description:** The MCP tool input schemas are defined as simple dictionaries with basic type hints and placeholder descriptions. There's a TODO acknowledging this needs replacement (line 379). This lacks robust validation, default value handling, and clear documentation generation.
*   **Recommendation:** Define input schemas using Pydantic models. This allows FastAPI to automatically handle request validation, data conversion, and generate accurate OpenAPI documentation (which can potentially be used to generate the `server_info` message more reliably). Each tool should have its own Pydantic model for arguments.
*   **Boomerang Task Title:** Implement Pydantic models for MCP tool input schemas

*   **File & Line(s):** 461, 462 (`get_server_info`)
*   **Category:** API Clarity / Maintainability
*   **Description:** Server name and version are hardcoded. There's a TODO asking if the version should be dynamic.
*   **Recommendation:** Load the server name and version from a configuration file or potentially `pyproject.toml` (if using standard Python packaging) to make it easier to manage and update.
*   **Boomerang Task Title:** Load server name/version dynamically in get_server_info

*   **File & Line(s):** 468-469 (`get_server_info`)
*   **Category:** API Clarity
*   **Description:** Tool descriptions are derived only from the first line of the handler's docstring. This might be insufficient for complex tools.
*   **Recommendation:** Consider using the full docstring or a dedicated description field within the tool definition (perhaps alongside Pydantic models) to provide more comprehensive explanations in the `server_info`.
*   **Boomerang Task Title:** Improve MCP tool description generation

*   **File & Line(s):** Tool handlers (`handle_...`)
*   **Category:** API Clarity / Consistency
*   **Description:** While handlers generally return `{"success": True/False, "message": ..., ...}`, the exact structure of the data within the `result` field of the MCP message varies (e.g., `results` list in execute, `filename` in export, `properties` dict, `description` string).
*   **Recommendation:** Define clear, consistent Pydantic models for the *output* of each tool as well. This improves predictability for clients consuming the API. The `process_tool_request` function could then validate the handler's output against these models before sending.
*   **Boomerang Task Title:** Define Pydantic models for MCP tool output/results