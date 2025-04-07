# CadQuery MCP Server

**TL;DR: Running as MCP Server**

1.  **Prerequisites:** Ensure `git`, `python3` (3.10+), and `uv` are installed.
2.  **Clone:** `git clone <repository-url> && cd mcp-cadquery`
3.  **Run:** Choose **one**:
    *   **HTTP SSE Mode (Recommended):** `./server_sse.sh` (Starts server on default port 8000)
    *   **Stdio Mode:** `./server_stdio.sh` (For direct client integration)
    *   *(First run automatically sets up the Python environment using `uv`)*
4.  **Configure MCP Client:** See "Configuring MCP Clients" section below. Use `./server_stdio.sh` as the command for Stdio connections.

---

This project provides a backend server that exposes CadQuery functionality through the Model Context Protocol (MCP). It allows clients (like AI assistants or other tools) to execute CadQuery scripts, generate models, export them to various formats, and manage a searchable library of pre-defined CadQuery parts.

The server can run in two modes, started via convenience scripts:

1.  **HTTP Server Mode (`./server_sse.sh`):** Uses FastAPI and communicates via Server-Sent Events (SSE) for asynchronous results. Includes an optional web frontend. Recommended for development and web UI access.
2.  **Stdio Mode (`./server_stdio.sh`):** Communicates via standard input/output using line-delimited JSON, suitable for direct integration with clients like Cline/Cursor.

## Features

*   **Simplified Startup:** Use `./server_sse.sh` or `./server_stdio.sh` to run.
*   **Automatic Environment Setup:** The startup scripts automatically create/update the `.venv-cadquery` virtual environment and install dependencies using `uv` on the first run or when needed.
*   **Command-Line Arguments:** Pass arguments directly to the server scripts (e.g., `./server_sse.sh --port 8081 --reload`). Use `--help` for options (e.g., `./server_sse.sh --help`).
*   **Execute CadQuery Scripts:** Run arbitrary CadQuery Python scripts via the `execute_cadquery_script` tool. Supports parameter substitution.
*   **Export Shapes:** Export generated shapes (e.g., SVG previews via `export_shape_to_svg`, STEP/STL via `export_shape`).
*   **Workspaces & Part Library:**
    *   Organize your CadQuery scripts (`.py` files) into directories (e.g., `part_library/`, `my_cq_workspace/`).
    *   Specify a workspace using the `--library-dir` argument (e.g., `./server_stdio.sh --library-dir my_cq_workspace`). Default: `part_library/`.
    *   Scan the library using the `scan_part_library` tool to index parts based on metadata in docstrings (Name, Description, Tags, Author).
    *   Generate SVG previews (cached based on file modification time).
    *   Search indexed parts using the `search_parts` tool.
*   **Web Frontend (HTTP Mode Only):** Includes a basic React/TypeScript frontend for interacting with the server.
*   **Testing:** Developed using TDD with `pytest`. Run tests via `./run_tests.py`.

## Getting Started

### Prerequisites

*   `git`
*   Python 3.10+ (accessible as `python3`)
*   `uv` (Python package installer/manager - see https://github.com/astral-sh/uv)
*   **CadQuery System Dependencies:** Installing CadQuery via `uv pip install` might require C++ build tools and other OS-specific libraries. Refer to the official CadQuery documentation if the automatic environment setup fails during the first run.

### Setup & Running

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd mcp-cadquery
    ```

2.  **Run the Server:**
    Choose the appropriate script for your desired mode. The script will handle creating the virtual environment (`.venv-cadquery/`) and installing dependencies automatically the first time you run it.

    *   **HTTP SSE Mode (Recommended):**
        ```bash
        # Start with default settings (port 8000, no reload)
        ./server_sse.sh

        # Start with hot-reloading enabled (useful for development)
        ./server_sse.sh --reload

        # Start on a different port
        ./server_sse.sh --port 8081
        ```
        Connect your MCP client using the HTTP SSE method (see Configuration below). The server is typically available at `http://127.0.0.1:8000` (or the specified port).

    *   **Stdio Mode:**
        ```bash
        # Start with default settings (using part_library/)
        ./server_stdio.sh

        # Start with a specific workspace/library directory
        ./server_stdio.sh --library-dir my_cq_workspace

        # Pass other arguments as needed
        ./server_stdio.sh --library-dir /path/to/another/lib --preview-dir-name .previews
        ```
        Configure your MCP client to use the `./server_stdio.sh` command for a Stdio connection (see Configuration below).

## Configuring MCP Clients (e.g., RooCode)

Configure your MCP client (like RooCode in VS Code) to connect to the server. You can use global settings or a project-specific `.roo/mcp.json` file.

### Example 1: HTTP SSE Connection

Add this to your `mcpServers` configuration:

```json
{
  "mcpServers": {
    "cadquery_sse": {
      "name": "CadQuery Server (SSE)", // Optional: Display name
      "url": "http://127.0.0.1:8000/mcp", // Adjust port if you used --port
      // Optional: Add headers if authentication is needed
      // "headers": { "Authorization": "Bearer YOUR_TOKEN" },
      "alwaysAllow": [ // Optional: Tools Roo can use without asking
        "execute_cadquery_script", "export_shape_to_svg", "scan_part_library", "search_parts", "export_shape"
      ]
    }
    // Add other servers here
  }
}
```
*Run command (in terminal):* `./server_sse.sh [OPTIONS]` (e.g., `./server_sse.sh --reload`)

### Example 2: Stdio Connection

Add this to your `mcpServers` configuration:

```json
{
  "mcpServers": {
    "cadquery_stdio": {
      "name": "CadQuery Server (Stdio)", // Optional: Display name
      "command": "./server_stdio.sh", // Use the script directly
      "args": [
         // Optional: Add server arguments here, e.g.:
         // "--library-dir", "my_cq_workspace"
         // "--preview-dir-name", ".previews"
      ],
      // "env": {}, // Optional: Add environment variables if needed
      "alwaysAllow": [ // Optional: Tools Roo can use without asking
         "execute_cadquery_script", "export_shape_to_svg", "scan_part_library", "search_parts", "export_shape"
      ]
    }
    // Add other servers here
  }
}
```
*Run command:* Managed by the MCP client using the specified `command` and `args`. The script handles environment setup automatically on first launch by the client.

## Workspaces

You can organize your CadQuery part scripts (`.py` files) into different directories, referred to as workspaces. Examples in this repository include `part_library/`, `my_cq_workspace/`, and `sample_house_workspace/`.

Use the `--library-dir` command-line argument when starting the server to specify which workspace to use:

```bash
# Use the 'my_cq_workspace' directory
./server_sse.sh --library-dir my_cq_workspace

# Use a custom path
./server_stdio.sh --library-dir /path/to/my/cad_projects/project_alpha
```

The `scan_part_library` and `search_parts` tools operate on the currently configured library directory.

## MCP Tools Provided

*   `execute_cadquery_script`: Executes a given CadQuery script string.
    *   `arguments`: `{"script": "...", "parameters": {...}}` or `{"script": "...", "parameter_sets": [{...}, ...]}`
*   `export_shape_to_svg`: Exports a shape from a previous script execution result to an SVG file served by the backend.
    *   `arguments`: `{"result_id": "...", "shape_index": 0, "filename": "optional_name.svg", "options": {...}}`
*   `scan_part_library`: Scans the configured part library directory, updates the index, and generates/caches SVG previews.
    *   `arguments`: `{}`
*   `search_parts`: Searches the indexed part library.
    *   `arguments`: `{"query": "search term"}`
*   `export_shape`: (Generic export) Exports a shape to a specified file format and path on the server.
    *   `arguments`: `{"result_id": "...", "shape_index": 0, "filename": "output/path/model.step", "format": "STEP", "options": {...}}`

*(Note: Tool arguments and return values are subject to change.)*

## Running the Frontend (Development Mode - HTTP Mode Only)

If you want to actively develop the frontend with hot-reloading:

1.  **Ensure backend is running:** Start the backend server first using `./server_sse.sh --reload` (in a separate terminal).
2.  **Install frontend dependencies:** `cd frontend && npm install && cd ..` (only needed once or after `package.json` changes).
3.  **Start the frontend development server (in another terminal):** `python3 ./run_frontend_dev.py`
    The frontend will typically be available at `http://localhost:5173` and will connect to the backend running on port 8000 (or as configured).

## Running Tests

1.  **Ensure environment exists:** Run one of the server scripts (`./server_sse.sh` or `./server_stdio.sh`) at least once to set up the environment.
2.  **Run tests using the script:**
    ```bash
    ./run_tests.py
    # Pass arguments to pytest:
    # ./run_tests.py -v -k "part_library"
    ```
    The script ensures tests run within the correct virtual environment.

## Project Structure

```
.
├── .venv-cadquery/     # Python virtual environment (managed by uv via scripts)
├── frontend/           # React/TypeScript frontend source
│   ├── dist/           # Built frontend files (served by backend in SSE mode)
│   └── ...
├── my_cq_workspace/    # Example user workspace for CadQuery scripts
├── part_library/       # Default workspace for CadQuery part scripts (.py)
├── sample_house_workspace/ # Example user workspace
├── shapes/             # Example shapes (e.g., STEP files)
├── src/                # Python source code for the server
├── tests/              # Pytest test files
├── .gitignore
├── context.llm.md      # AI working context (can be ignored)
├── pytest.ini          # Pytest configuration
├── pyproject.toml      # Project metadata (NOT used for installation directly)
├── README.md           # This file
├── README.llm.md       # Concise README for LLMs
├── requirements.txt    # Python dependencies (used by uv via scripts)
├── run_frontend_dev.py # Runs frontend dev server (requires backend running)
├── run_tests.py        # Runs pytest in the correct environment
├── server.py           # Main backend application & CLI entrypoint (used by .sh scripts)
├── server_sse.sh       # **Recommended script to run SSE server**
└── server_stdio.sh     # **Recommended script to run Stdio server**
```

## Contributing

Contributions are welcome! Please follow these guidelines:

1.  **Test-Driven Development:** Add tests for new features/fixes. Run tests using `./run_tests.py`.
2.  **Code Style:** Follow standard Python (PEP 8) and TypeScript/React conventions.
3.  **Branching:** Create a new branch for your feature or bug fix.
4.  **Pull Requests:** Submit a pull request with a clear description and ensure tests pass.
5.  **Part Library:**
    *   Add parts to a workspace directory (e.g., `part_library/`).
    *   Include a module-level docstring with metadata (Name, Description, Tags, Author).
    *   Use `show_object()` for the result in your script.
    *   Run the `scan_part_library` tool via MCP to update the index after adding/modifying parts.