# CadQuery Research Context

**Source:** [CadQuery Docs Index](https://cadquery.readthedocs.io/en/latest/index.html) (Fetched 2025-05-04)

**Key Findings:**

*   **Version:** Latest stable release is **2.5.2** (confirmed via PyPI). Documentation refers to "CadQuery 2". `master` branch is `2.6-dev`.
*   **Installation (via `installation.html`):**
    *   **Method:** `pip install cadquery` is supported and recommended within a virtual environment (compatible with `uv`).
    *   **Python Version:** Requires Python 3.9+. Stable versions (e.g., 3.10, 3.11) recommended due to complex dependencies.
    *   **Dependencies:** Base pip install handles core dependencies. No need for `[ipython]` or `[dev]` extras for the server. `uv` will manage these.
    *   **Testing:** `import cadquery; cadquery.Workplane(...).toSvg()` confirms basic install and SVG export.
*   **API (from `apireference.html`):**
    *   **Core Objects:** `Workplane` (fluent 3D), `Sketch` (2D + constraints), `Assembly` (parts + constraints), `Selector` (geometry querying).
    *   **High-Level:** Direct `Workplane` methods for primitives (`box`, `sphere`), operations (`extrude`, `cut`, `revolve`, `loft`, `fillet`, `chamfer`).
    *   **Lower-Level:**
        *   `Workplane` 2D methods (`lineTo`, `hLine`, `spline`, `threePointArc`).
        *   `Sketch` API for constraint-based 2D.
        *   Powerful `Selector` classes/strings for identifying faces, edges, vertices.
        *   Methods to access geometry components (`vertices`, `edges`, `faces`).
    *   **Import/Export:** `importers` (STEP, DXF), `exporters.export` (STEP, STL, SVG, AMF, 3MF, etc.).
    *   **Assemblies:** Supported via `Assembly` object and constraints.
*   **Validation/Rendering:**
    *   `vis.html`: Describes visualization (`vis.show()`) including non-interactive PNG screenshot generation (`screenshot=...`, `interact=False`) with camera/size control. Useful for visual validation.
    *   `importexport.html`: Details exporting via `exporters.export()` to STEP, STL, AMF, 3MF, SVG, DXF, TJS, VRML, VTP, glTF. Provides options for mesh quality (STL, etc.), appearance (SVG), assembly structure (STEP). Useful for validation (STEP analysis, SVG checks) and final output. Also covers STEP/DXF import.
*   **Interfacing:**
    *   `cqgi.html`: Describes CadQuery Gateway Interface (CQGI) for external execution - **Highly relevant for MCP server**.
        *   **Mechanism:** `cqgi.parse(script)` -> `model.build(params)` -> `BuildResult`.
        *   **Input:** Scripts define parameters via top-level assignments; server overrides via `build_parameters`.
        *   **Output:** Scripts use `show_object(shape)` to return geometry; server accesses via `BuildResult.results`.
        *   **Export:** Server can use `cadquery.exporters.export(shape, ...)` on results.
        *   **Debugging:** Scripts can use `debug(obj)` for intermediate output.
*   **Dependencies (from `master` branch `setup.py`, likely similar for 2.5.2):**
    *   `cadquery-ocp>=7.8.1,<7.9` (Core OpenCASCADE wrapper)
    *   `ezdxf>=1.3.0`
    *   `multimethod>=1.11,<2.0`
    *   `nlopt>=2.9.0,<3.0`
    *   `typish`
    *   `casadi`
    *   `path`
    *   Managed by `pip`/`uv` during `cadquery` installation. Core requirement is Python 3.9+.
**Next Steps:**

1.  ~~Check `installation.html` for dependencies and specific install commands.~~ (Done)
2.  ~~Check PyPI page (`https://pypi.org/project/cadquery/`) for latest version number confirmation and dependency overview.~~ (Done - Version 2.5.2 confirmed, dependencies found via `setup.py`)
3.  ~~Investigate `cqgi.html` further.~~ (Done)
4.  ~~Review `apireference.html` for API details.~~ (Done)
5.  ~~Review `vis.html` and `importexport.html` for rendering/validation methods.~~ (Done)