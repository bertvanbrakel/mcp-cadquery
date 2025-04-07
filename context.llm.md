# Project Context: mcp-cadquery

## Task: Test Coverage Improvement

**Objective:** Achieve 100% test coverage for `src/mcp_cadquery_server/core.py` and `src/mcp_cadquery_server/script_runner.py`.

**Plan:**
1.  Run tests with coverage (`./run_tests.py`) to get the baseline. (DONE)
2.  Analyze coverage report for `core.py` and `script_runner.py`. (DONE)
    *   `core.py`: 46%
    *   `script_runner.py`: 0%
3.  Add tests for `core.py` to cover missing lines/branches. (DONE - Reached 97%, accepted)
4.  Fix unrelated test failures. (DONE)
5.  Investigate and implement subprocess coverage measurement for `script_runner.py`. (DONE - Implemented using `coverage.process_startup()`)
6.  Analyze coverage report for `script_runner.py`. (DONE - Reached 86%)
    *   Missing: 11, 13, 20, 22, 108-111, 120-121, 130-131, 140-141, 150-151, 160-161, 170-171, 180-181, 190-191, 199-201
7.  Add tests for `script_runner.py` to cover missing lines/branches. (NEXT STEP - Boomerang Task)
8.  Iterate until 100% coverage is achieved or deemed impractical.
9.  Final verification.

**Current Status:** Subprocess coverage is working. `script_runner.py` is at 86%. Need to add tests to cover the remaining lines.

---

## Task: Full Code Review

**Objective:** Conduct a comprehensive code review of production code, test code, and the MCP API definition, documenting findings in `code_review.llm.md`.

**Plan:**
1.  Identify scope (src, tests, server.py API). (DONE)
2.  Define review criteria (best practices, docs, actionable comments, DRY, clarity, SRP, abstraction, errors, API clarity). (DONE)
3.  Create `code_review.llm.md` to store findings. (DONE)
4.  Update `context.llm.md` (this file) to link to the review file. (DONE)
5.  Initiate review via separate Boomerang tasks (likely switching to 'code' mode), using `code_review.llm.md` as input. (NEXT STEP)

**Review Findings Document:** [code_review.llm.md](code_review.llm.md)

**Current Status:** Planning complete. Ready to start the review process by creating Boomerang tasks based on the findings document.