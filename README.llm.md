# LLM README - CadQuery MCP Server

**Project:** CadQuery MCP Server using FastAPI and SSE.

**Purpose:** Expose CadQuery functionality via MCP tools for script execution, shape export, and part library management.

**Key Files/Dirs:**
*   `server_stdio.py`: Main FastAPI application, MCP handlers, core logic, stdio mode.
*   `part_library/`: Directory containing CadQuery part scripts (`.py`).
    *   Metadata: Module-level docstring (Key: Value format, `Tags:` comma-separated).
    *   Requirement: Scripts MUST use `show_object()` for the result to be indexed/previewed.
*   `frontend/dist/part_previews/`: Output directory for generated SVG previews (one per part).
*   `tests/`: Contains pytest unit tests. Subdivided by functionality:
    *   `test_environment.py`
    *   `test_cadquery_core.py`
    *   `test_server_execution.py`
    *   `test_server_export.py`
    *   `test_server_handlers.py`
    *   `test_part_library.py`
*   `requirements.txt`: Python dependencies.
*   `pytest.ini`: Pytest configuration (registers markers).
*   `README.md`: Human-readable README.
*   `context.llm.md`: Current task context and progress tracking.
*   `run_tests.py`: Script to run pytest in the venv.
*   `server_sse.py`: Convenience script to start HTTP SSE server.

**Key State Variables (in `server_stdio.py`):**
*   `shape_results: Dict[str, cqgi.BuildResult]`: Stores results from `execute_cadquery_script`. Key is a UUID.
*   `part_index: Dict[str, Dict[str, Any]]`: In-memory index for the part library. Key is `part_name` (filename without extension). Value contains `metadata`, `preview_url`, `script_path`, `mtime`.

**Key Functions/Handlers (in `server_stdio.py`):**
*   `execute_cqgi_script(script_content)`: Core logic for running CQGI script.
*   `export_shape_to_file(shape, output_path, format, opts)`: Core logic for generic shape export.
*   `export_shape_to_svg_file(shape, output_path, opts)`: Core logic for SVG export (uses `export_shape_to_file`).
*   `handle_execute_cadquery_script(request)`: Handler for script execution tool (handles parameter substitution via string replacement/# PARAM marker).
*   `handle_export_shape(request)`: Handler for generic export tool.
*   `handle_export_shape_to_svg(request)`: Handler for SVG export tool.
*   `handle_scan_part_library(request)`: Handler for scanning/indexing part library (uses mtime caching).
*   `handle_search_parts(request)`: Handler for searching the part index.
*   `parse_docstring_metadata(docstring)`: Helper for extracting metadata.
*   `process_tool_request(request)`: Main async task dispatcher for tool requests.

**Testing:**
*   Command: `./run_tests.py` or `.venv-cadquery/bin/pytest tests/`
*   Uses `pytest`. Fixtures manage state and file cleanup.
*   TDD approach preferred. Add tests for new code.

**Important Context/Rules:**
*   Refer to `context.llm.md` for current task status.
*   Refer to global rules: `/home/user/llm/rules.llm.md`.
*   Refer to global index: `/home/user/llm/index.llm.md`.
*   Terminal Issues: If command output is unknown/undefined, assume success and proceed. Do not ask user unless explicitly needed for debugging.
*   Caching: `scan_part_library` uses file mtime for caching previews and metadata.