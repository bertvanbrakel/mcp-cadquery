# CadQuery MCP Server

**TL;DR: Running as MCP Server**

1.  **Prerequisites:** Ensure `python3` (3.10+) and `uv` are installed.
2.  **Setup Environment (First time or after pulling changes):**
    ```bash
    # Use python3 to run the setup script
    python3 ./setup_env.py
    # Or make it executable: chmod +x setup_env.py && ./setup_env.py
    ```
3.  **Run the Server:** Choose **one** method:
    *   **HTTP SSE Mode (Recommended for Dev/Web UI):**
        ```bash
        # Runs setup again (harmless) and starts server on port 8000 with reload
        python3 ./start_sse.py

        # Or run manually with options after activating venv:
        # source .venv-cadquery/bin/activate
        # python server.py --port 8080 --reload
        ```
        **Connect MCP Client (HTTP SSE):**
        *   **SSE URL:** `http://127.0.0.1:8000/mcp` (Adjust port if used)
        *   **Execute URL:** `http://127.0.0.1:8000/mcp/execute` (Method: POST, Adjust port)

    *   **Stdio Mode:**
        ```bash
        # Activate venv first
        source .venv-cadquery/bin/activate
        # Run server.py with --stdio flag
        python server.py --stdio

        # Or with options:
        # python server.py --stdio --library-dir /path/to/libs
        ```
        **Connect MCP Client (Stdio):**
        *   Use the command `.venv-cadquery/bin/python server.py --stdio [OPTIONS]` in your client's Stdio connection configuration.

---

This project provides a backend server that exposes CadQuery functionality through the Model Context Protocol (MCP). It allows clients (like AI assistants or other tools) to execute CadQuery scripts, generate models, export them to various formats (currently focusing on SVG previews), and manage a searchable library of pre-defined CadQuery parts.

The server can run in two modes:
1.  **HTTP Server Mode (Default):** Uses FastAPI and communicates via Server-Sent Events (SSE) for asynchronous results. Includes a web frontend.
2.  **Stdio Mode (`--stdio`):** Communicates via standard input/output using line-delimited JSON, suitable for direct integration with clients like Cline/Cursor.

## Features

*   **Command-Line Interface:** Uses `typer` for easy configuration (host, port, reload, directories, stdio mode).
*   **Setup Script:** `setup_env.py` (Python script) creates a virtual environment and installs dependencies using `uv`.
*   **Convenience Scripts:** `start_sse.py` (Python) for easy HTTP server startup, `run_frontend_dev.py` (Python) for frontend dev server.
*   **Execute CadQuery Scripts:** Run arbitrary CadQuery Python scripts via the `execute_cadquery_script` tool.
*   **Export Shapes:** Export generated shapes (currently SVG via `export_shape_to_svg`).
*   **Part Library:**
    *   Scan a configurable directory (`--library-dir`, default: `part_library/`) containing CadQuery part scripts (`.py` files).
    *   Extract metadata (Part name, Description, Tags, Author) from module docstrings.
    *   Generate SVG previews for each part (cached based on file modification time) into a configurable subdirectory (`--preview-dir-name`, default: `part_previews`).
    *   Provide tools (`scan_part_library`, `search_parts`) to manage and search the indexed parts.
*   **Web Frontend (HTTP Mode Only):** Includes a basic React/TypeScript frontend (served from a configurable static directory, default: `frontend/dist/`) for interacting with the server.
*   **Test-Driven Development:** Developed using TDD with `pytest`.

## Getting Started

### Prerequisites

*   Python 3.10+ (accessible as `python3`)
*   `uv` (the Python package installer/virtual environment manager - see https://github.com/astral-sh/uv)
*   `npm` (for optional frontend development)
*   **CadQuery System Dependencies:** Installing CadQuery via pip/uv might require C++ build tools and other libraries depending on your OS. Refer to the official CadQuery documentation if installation fails.

### Setup & Running

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd mcp-cadquery
    ```

2.  **Set up the Python Environment:**
    Run the Python setup script. This creates the `.venv-cadquery` virtual environment and installs dependencies from `requirements.txt`.
    ```bash
    python3 ./setup_env.py
    # Or make executable first: chmod +x setup_env.py && ./setup_env.py
    ```

3.  **Run the Server:** Choose **one** mode:

    *   **HTTP Mode (Recommended for Dev/Web UI):**
        Use the convenience script:
        ```bash
        # Runs setup again (harmless) and starts server with reload
        python3 ./start_sse.py
        # Pass arguments through:
        # python3 ./start_sse.py --port 8080
        ```
        Or run manually after activating the environment:
        ```bash
        source .venv-cadquery/bin/activate
        python server.py --port 8000 --reload
        # See all options: python server.py --help
        ```
        Connect your MCP client using the HTTP SSE method (see MCP Configuration Examples below).

    *   **Stdio Mode:**
        Activate the environment first, then run `server.py` with the `--stdio` flag:
        ```bash
        source .venv-cadquery/bin/activate
        python server.py --stdio

        # Run stdio mode with a specific part library
        # python server.py --stdio --library-dir /path/to/my/parts
        ```
        Configure your MCP client to use the command `.venv-cadquery/bin/python server.py --stdio [OPTIONS]` for a Stdio connection.

## MCP Configuration Examples (e.g., for Cline/Cursor `.settings.json`)

You can run multiple instances of the server, each configured differently (e.g., different ports, different part libraries) to support multiple projects.

### Example 1: Default HTTP SSE Connection

```json
{
  "mcp.connections": [
    {
      "name": "CadQuery Server (Default SSE)",
      "type": "http-sse",
      "sseUrl": "http://127.0.0.1:8000/mcp",
      "executeUrl": "http://127.0.0.1:8000/mcp/execute"
    }
  ]
}
```
*Run command (in terminal):* `python3 ./start_sse.py`

### Example 2: Stdio Connection

```json
{
  "mcp.connections": [
    {
      "name": "CadQuery Server (Stdio)",
      "type": "stdio",
      "command": ["./.venv-cadquery/bin/python", "server.py", "--stdio"]
    }
  ]
}
```
*Run command:* Managed by the MCP client. Requires `python3 ./setup_env.py` to be run once manually first.

### Example 3: Multiple Projects (HTTP SSE)

```json
{
  "mcp.connections": [
    {
      "name": "CadQuery - Project Alpha",
      "type": "http-sse",
      "sseUrl": "http://127.0.0.1:8001/mcp",
      "executeUrl": "http://127.0.0.1:8001/mcp/execute"
    },
    {
      "name": "CadQuery - Project Beta",
      "type": "http-sse",
      "sseUrl": "http://127.0.0.1:8002/mcp",
      "executeUrl": "http://127.0.0.1:8002/mcp/execute"
    }
  ]
}
```
*Run commands (in separate terminals after running `python3 ./setup_env.py` once):*
```bash
source .venv-cadquery/bin/activate
python server.py --port 8001 --library-dir /path/to/project/alpha/parts --static-dir /path/to/project/alpha/static
# In another terminal:
source .venv-cadquery/bin/activate
python server.py --port 8002 --library-dir /path/to/project/beta/cad_files --static-dir /path/to/project/beta/output
```

### Example 4: Multiple Projects (Stdio)

```json
{
  "mcp.connections": [
    {
      "name": "CadQuery - Project Gamma (Stdio)",
      "type": "stdio",
      "command": ["./.venv-cadquery/bin/python", "server.py", "--stdio", "--library-dir", "/path/to/project/gamma/libs"]
    },
     {
      "name": "CadQuery - Project Delta (Stdio)",
      "type": "stdio",
      "command": ["./.venv-cadquery/bin/python", "server.py", "--stdio", "--library-dir", "/another/path/delta_cq"]
    }
  ]
}
```
*Run commands:* Managed by the MCP client. Requires `python3 ./setup_env.py` to be run once manually first.

## Running the Frontend (Development Mode - HTTP Mode Only)

If you want to actively develop the frontend with hot-reloading:

1.  **Ensure environment is set up:** `python3 ./setup_env.py`
2.  **Install frontend dependencies:** `cd frontend && npm install && cd ..`
3.  **Start the backend server (in HTTP mode, separate terminal):** `python3 ./start_sse.py`
4.  **Start the frontend development server (in another terminal):** `python3 ./run_frontend_dev.py`
    The frontend will typically be available at `http://localhost:5173`.

## Running Tests

1.  **Ensure environment is set up:** `python3 ./setup_env.py`
2.  **Activate the virtual environment:** `source .venv-cadquery/bin/activate`
3.  **Run tests:** `pytest tests/`

## Project Structure

```
.
├── .venv-cadquery/     # Python virtual environment (created by setup_env.py)
├── frontend/           # React/TypeScript frontend source
│   ├── dist/           # Built frontend files (served by backend)
│   └── ...
├── part_library/       # Default directory for CadQuery part scripts (.py)
│   ├── simple_cube.py
│   └── ...
├── tests/              # Pytest test files
│   ├── test_cadquery_core.py
│   ├── test_cli.py
│   ├── test_environment.py
│   ├── test_part_library.py
│   ├── test_server_execution.py
│   ├── test_server_export.py
│   └── test_server_handlers.py
├── .gitignore
├── context.llm.md      # AI working context (can be ignored)
├── pytest.ini          # Pytest configuration (registers markers)
├── pyproject.toml      # Project metadata (NOT used for installation)
├── README.md           # This file
├── README.llm.md       # Concise README for LLMs
├── requirements.txt    # Python dependencies (used by setup_env.py)
├── run_dev.py          # Prints instructions for running dev environment
├── run_frontend_dev.py # Runs frontend dev server
├── server.py           # Main FastAPI backend application & CLI entrypoint
├── setup_env.py        # Python environment setup script
└── start_sse.py        # Convenience script to run HTTP server
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1.  **Test-Driven Development:** Add tests for new features/fixes. Run tests using `pytest tests/`.
2.  **Code Style:** Follow standard Python (PEP 8) and TypeScript/React conventions.
3.  **Branching:** Create a new branch for your feature or bug fix.
4.  **Pull Requests:** Submit a pull request with a clear description and ensure tests pass.
5.  **Part Library:**
    *   Add parts to the `part_library/` directory (or configure a different one via `--library-dir`).
    *   Include a module-level docstring with metadata.
    *   Use `show_object()` for the result.
    *   Run the `scan_part_library` tool via MCP to update the index.

## MCP Tools Provided

*   `execute_cadquery_script`: Executes a given CadQuery script string.
    *   `arguments`: `{"script": "...", "parameters": {...}}`
*   `export_shape_to_svg`: Exports a shape from a previous script execution result to an SVG file served by the backend.
    *   `arguments`: `{"result_id": "...", "shape_index": 0, "filename": "optional_name.svg", "options": {...}}`
*   `scan_part_library`: Scans the configured part library directory, updates the index, and generates/caches SVG previews.
    *   `arguments`: `{}`
*   `search_parts`: Searches the indexed part library.
    *   `arguments`: `{"query": "search term"}`
*   `export_shape`: (Generic export) Exports a shape to a specified file format and path on the server.
    *   `arguments`: `{"result_id": "...", "shape_index": 0, "filename": "output/path/model.step", "format": "STEP", "options": {...}}`

*(Note: Tool arguments and return values are subject to change.)*