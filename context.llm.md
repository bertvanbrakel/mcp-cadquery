# MCP CadQuery Server Project

**Objective:** Create a Python-based MCP server to control CadQuery.

**Current Phase:** Planning & Implementation

**Tasks:**

1.  [x] Research CadQuery: (See `research_context.llm.md`)
    *   [x] Find official documentation.
    *   [x] Identify latest stable release (2.5.2).
    *   [x] Understand API (Workplane, Sketch, Assembly, Selectors, CQGI, Exporters, Vis).
    *   [x] Determine installation requirements (pip, Python 3.9+, uv compatible).
    *   [x] Research rendering/validation methods (vis.show screenshots, exporters).
    *   [x] Check installation via `uv` (feasible via pip).
2.  [ ] Plan MCP Server Structure: (Done - see thought process)
3.  [x] Implement MCP Server (Stdio):
    *   [x] Create project structure (`server.py`, `requirements.txt`, `run_server.sh`).
    *   [x] Implement basic MCP stdio communication loop in `server.py`.
    *   [x] Implement `execute_cadquery_script` tool using CQGI.
    *   [x] Implement `export_shape` tool using exporters.
    *   [x] Implement `render_shape_to_png` tool using `vis.show`.
    *   [x] Implement automatic dependency installation via `run_server.sh`.
4.  [ ] Add SSE Support:
    *   [ ] Add `fastapi`, `uvicorn` to `requirements.txt`.
    *   [ ] Refactor `server.py` for FastAPI & SSE.
    *   [ ] Update `run_server.sh` to use `uvicorn`.
5.  [ ] Test MCP Server (SSE).

**Relevant Info:**

*   Targeting recent CadQuery releases.
*   Use Python `uv` for environment management.
*   Server needs low-level and high-level access.
*   Server needs validation capabilities.