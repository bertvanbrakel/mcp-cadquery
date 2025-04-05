# CadQuery MCP Server

**TL;DR: Running as MCP Server**

1.  **Prerequisites:** Ensure `python3` (3.10+) and `uv` are installed.
2.  **(Optional) Verify Environment:** If you encounter issues, you can manually run `python3 ./setup_env.py` to check/setup the environment, but `server.py` will attempt this automatically.
3.  **Run the Server:** Choose **one** method:
    *   **HTTP SSE Mode (Recommended for Dev/Web UI):**
        ```bash
        # Will automatically setup environment if needed, then starts server
        python3 server.py --mode sse --reload

        # Or run manually with options after activating venv:
        # source .venv-cadquery/bin/activate
        # python server.py --mode sse --port 8080 --reload
        ```
        **Connect MCP Client (HTTP SSE):**
        *   **SSE URL:** `http://127.0.0.1:8000/mcp` (Adjust port if used)
        *   **Execute URL:** `http://127.0.0.1:8000/mcp/execute` (Method: POST, Adjust port)

    *   **Stdio Mode:**
        ```bash
        # Activate venv first
        source .venv-cadquery/bin/activate
        # Run server.py with --stdio flag
        python server.py --mode stdio

        # Or with options:
        # python server.py --mode stdio --library-dir /path/to/libs
        ```
        **Connect MCP Client (Stdio):**
        *   Use the command `.venv-cadquery/bin/python server.py --mode stdio [OPTIONS]` in your client's Stdio connection configuration.

---

This project provides a backend server that exposes CadQuery functionality through the Model Context Protocol (MCP). It allows clients (like AI assistants or other tools) to execute CadQuery scripts, generate models, export them to various formats (currently focusing on SVG previews), and manage a searchable library of pre-defined CadQuery parts.

The server can run in two modes:
1.  **HTTP Server Mode (Default):** Uses FastAPI and communicates via Server-Sent Events (SSE) for asynchronous results. Includes a web frontend.
2.  **Stdio Mode (`--mode stdio`):** Communicates via standard input/output using line-delimited JSON, suitable for direct integration with clients like Cline/Cursor.

## Features

*   **Command-Line Interface:** Uses `typer` for easy configuration (host, port, reload, directories, stdio mode).
*   **Automatic Setup:** `server.py` automatically creates/updates the `.venv-cadquery` virtual environment and installs dependencies using `uv` if run outside the correct environment. (`setup_env.py` remains for manual checks).
*   **Convenience Scripts:** `run_frontend_dev.py` (Python) for frontend dev server, `run_tests.py` (Python) for running tests.
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

2.  **Run the Server (First Time):**
    Running `server.py` for the first time (or after changes) will automatically trigger the environment setup process using `uv`.
    ```bash
    # Example: Start in HTTP SSE mode
    python3 server.py --mode sse --reload
    ```
    Watch the console output for messages about environment setup. If it fails, you might need to install `uv` (`pip install uv`) or required system dependencies for CadQuery. You can also run `python3 ./setup_env.py` manually for detailed setup logs.

3.  **Run the Server:** Choose **one** mode:

    *   **HTTP Mode (Recommended for Dev/Web UI):**
        Use the convenience script:
        ```bash
        # Will automatically setup environment if needed
        python3 server.py --mode sse --reload
        # Pass arguments through:
        # python3 server.py --mode sse --port 8080
        ```
        Or run manually after activating the environment:
        ```bash
        source .venv-cadquery/bin/activate
        python server.py --mode sse --port 8000 --reload
        # See all options: python server.py --help
        ```
        Connect your MCP client using the HTTP SSE method (see MCP Configuration Examples below).

    *   **Stdio Mode:**
        Activate the environment first, then run `server.py` with the `--stdio` flag:
        ```bash
        source .venv-cadquery/bin/activate
        python server.py --mode stdio

        # Run stdio mode with a specific part library
        # python server.py --mode stdio --library-dir /path/to/my/parts
        ```
        Configure your MCP client to use the command `.venv-cadquery/bin/python server.py --mode stdio [OPTIONS]` for a Stdio connection.

## Configuring MCP Clients (RooCode)

To connect an MCP client like RooCode (in VS Code) to an MCP server (like this one, or any other), you need to configure the client. RooCode supports two main configuration locations:

1.  **Global Configuration:** Edit the `mcp_settings.json` file via the RooCode settings UI in VS Code. These settings apply to all your projects unless overridden.
2.  **Project-level Configuration:** Create or edit a `.roo/mcp.json` file in your project's root directory (e.g., `/home/bert/workspace/my/mcp-cadquery/.roo/mcp.json`). This file takes precedence and can be committed to version control.

Both files use a similar JSON structure.

### Configuring an SSE Connection (Remote Server)

To connect to a server running in HTTP SSE mode (like the default mode for this project, or any other remote SSE server), add an entry like this to the `mcpServers` object in your chosen configuration file:

```json
{
  "mcpServers": {
    "your-server-name": { // Choose a unique, descriptive name
      "url": "YOUR_SSE_SERVER_URL", // The base URL of the SSE server's MCP endpoint (e.g., "http://127.0.0.1:8000/mcp")
      "headers": { // Optional: Add required headers like authentication tokens
        "Authorization": "Bearer YOUR_TOKEN"
      },
      "alwaysAllow": [], // Optional: List tool names to auto-approve
      "disabled": false // Set to true to disable this server entry
    }
    // ... other server configurations
  }
}
```

*   Replace `"your-server-name"`, `"YOUR_SSE_SERVER_URL"`, and token placeholders with the actual details.
*   The `url` should typically point to the base MCP endpoint provided by the server documentation (e.g., `/mcp`). RooCode will handle appending `/events` or `/execute` as needed based on the protocol.

### Configuring a Stdio Connection (This CadQuery Server)

To connect to *this* CadQuery server running in Stdio mode, add an entry like this to the `mcpServers` object:

```json
{
  "mcpServers": {
    "cadquery_stdio": { // Or another unique name
      "name": "CadQuery Server (Stdio)", // Optional: Display name
      "command": "./.venv-cadquery/bin/python", // Relative path to python in the project's venv
      "args": [
        "server.py", // Relative path to the server script from project root
        "--mode",
        "stdio"
        // Optional: Add other server arguments here, e.g.:
        // "--library-dir", "/path/to/your/parts"
      ],
      // "env": {}, // Optional: Add environment variables if needed by your setup
      "alwaysAllow": [ // Optional: List tool names to auto-approve
         "execute_cadquery_script", "export_shape_to_svg", "scan_part_library", "search_parts", "export_shape"
      ],
      "disabled": false // Set to true to disable this server entry
    }
    // ... other server configurations
  }
}
```

*   This assumes the `.roo/mcp.json` file is in the project root, alongside the `.venv-cadquery` directory and `server.py`. Adjust paths if your structure differs.
*   The `command` points to the Python executable inside the virtual environment created by this project's setup.
*   The `args` specify the server script and the essential `--mode stdio` flag. You can add other command-line arguments supported by `server.py` to the `args` list.

---

## MCP Configuration Examples (For *This* Server)

The following examples show how to configure RooCode to connect specifically to *this* CadQuery MCP server, using the structures described above.

## MCP Configuration Examples (e.g., for Roo `.roo/mcp.json` or VSCode settings)

You can run multiple instances of the server, each configured differently (e.g., different ports, different part libraries) to support multiple projects.

### Example 1: Default HTTP SSE Connection

```json
{
  "mcpServers": {
    "cadquery_sse": {
      "name": "CadQuery Server (Default SSE)", // Optional: Display name
      "url": "http://127.0.0.1:8000/mcp", // Base URL for the MCP endpoint
      // Optional: Add headers if authentication is needed
      // "headers": {
      //   "Authorization": "Bearer YOUR_TOKEN"
      // },
      "alwaysAllow": [ // Optional: Tools Roo can use without asking
        "execute_cadquery_script", "export_shape_to_svg", "scan_part_library", "search_parts", "export_shape"
      ]
    }
    // Add other servers here
  }
}
```
*Run command (in terminal):* `python3 server.py --mode sse --reload`

### Example 2: Stdio Connection

```json
{
  "mcpServers": {
    "cadquery_stdio": {
      "name": "CadQuery Server (Stdio)", // Optional: Display name
      "command": "./.venv-cadquery/bin/python", // Path to python in venv
      "args": [
        "server.py", // Path to the server script
        "--mode",
        "stdio"
      ],
      "alwaysAllow": [ // Optional: Tools Roo can use without asking
         "execute_cadquery_script", "export_shape_to_svg", "scan_part_library", "search_parts", "export_shape"
      ]
    }
    // Add other servers here
  }
}
```
*Run command:* Managed by the MCP client. The first time the client starts the command, `server.py` will attempt automatic environment setup.

### Example 3: Multiple Projects (HTTP SSE)

```json
{
  "mcpServers": {
    "cadquery_alpha": {
      "name": "CadQuery - Project Alpha",
      "type": "http-sse",
      "sseUrl": "http://127.0.0.1:8001/mcp",
      "executeUrl": "http://127.0.0.1:8001/mcp/execute"
      // Add alwaysAllow if needed
    },
    "cadquery_beta": {
      "name": "CadQuery - Project Beta",
      "type": "http-sse",
      "sseUrl": "http://127.0.0.1:8002/mcp",
      "executeUrl": "http://127.0.0.1:8002/mcp/execute"
      // Add alwaysAllow if needed
    }
  }
}
```
*Run commands (in separate terminals):*
```bash
source .venv-cadquery/bin/activate
python server.py --mode sse --port 8001 --library-dir /path/to/project/alpha/parts --static-dir /path/to/project/alpha/static
# In another terminal:
source .venv-cadquery/bin/activate
python server.py --mode sse --port 8002 --library-dir /path/to/project/beta/cad_files --static-dir /path/to/project/beta/output
```

### Example 4: Multiple Projects (Stdio)

```json
{
  "mcpServers": {
    "cadquery_gamma": {
      "name": "CadQuery - Project Gamma (Stdio)",
      "command": "./.venv-cadquery/bin/python",
      "args": [
        "server.py", "--mode", "stdio", "--library-dir", "/path/to/project/gamma/libs"
      ]
      // Add alwaysAllow if needed
    },
    "cadquery_delta": {
      "name": "CadQuery - Project Delta (Stdio)",
      "command": "./.venv-cadquery/bin/python",
      "args": [
        "server.py", "--mode", "stdio", "--library-dir", "/another/path/delta_cq"
      ]
      // Add alwaysAllow if needed
    }
  }
}
```
*Run commands:* Managed by the MCP client. The first time the client starts the command, `server.py` will attempt automatic environment setup.

## Running the Frontend (Development Mode - HTTP Mode Only)

If you want to actively develop the frontend with hot-reloading:

1.  **Ensure backend is running:** Start the backend server first (`python3 server.py --mode sse --reload`). It will handle its own environment setup.
2.  **Install frontend dependencies:** `cd frontend && npm install && cd ..`
3.  **Start the backend server (in HTTP mode, separate terminal):** `python3 server.py --mode sse --reload`
4.  **Start the frontend development server (in another terminal):** `python3 ./run_frontend_dev.py`
    The frontend will typically be available at `http://localhost:5173`.

## Running Tests

1.  **Run Tests:** The test runner script (`run_tests.py`) uses the Python interpreter from the virtual environment. Ensure the environment exists (running `server.py` once or `setup_env.py` manually will create it).
2.  **Run tests using the script:**
    ```bash
    ./run_tests.py
    # Pass arguments to pytest:
    # ./run_tests.py -v -k "part_library"
    ```
3.  **(Manual Alternative) Activate the virtual environment:** `source .venv-cadquery/bin/activate`
4.  **(Manual Alternative) Run tests:** `pytest tests/`

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
├── run_tests.py        # Runs pytest in the correct environment
├── server.py           # Main FastAPI backend application & CLI entrypoint
└── setup_env.py        # Manual Python environment setup script (server.py does this automatically)
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
    *   `arguments`: `{"script": "...", "parameters": {...}}` or `{"script": "...", "parameter_sets": [{...}, ...]}` (See Parameter Substitution section)
*   `export_shape_to_svg`: Exports a shape from a previous script execution result to an SVG file served by the backend.
    *   `arguments`: `{"result_id": "...", "shape_index": 0, "filename": "optional_name.svg", "options": {...}}`
*   `scan_part_library`: Scans the configured part library directory, updates the index, and generates/caches SVG previews.
    *   `arguments`: `{}`
*   `search_parts`: Searches the indexed part library.
    *   `arguments`: `{"query": "search term"}`
*   `export_shape`: (Generic export) Exports a shape to a specified file format and path on the server.
    *   `arguments`: `{"result_id": "...", "shape_index": 0, "filename": "output/path/model.step", "format": "STEP", "options": {...}}`

*(Note: Tool arguments and return values are subject to change.)*