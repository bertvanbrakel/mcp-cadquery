# Task: Fix skipped test `test_sse_connection_sends_server_info`

**Objective:** Fix the skipped test `test_sse_connection_sends_server_info` in `tests/test_server_handlers.py`. Find a reliable way to verify that the `server_info` message is sent upon SSE connection, addressing potential issues with `TestClient` and background tasks.

**Status:** Completed

**Steps:**
1.  Update `context.llm.md`. [DONE]
2.  Read `tests/test_server_handlers.py` to locate the test. [DONE]
3.  Analyze the test and SSE handling code. [DONE]
4.  Determine a reliable testing strategy for SSE messages. [DONE] (Mock `asyncio.Queue` class and check `put` call)
5.  Refactor the test (remove skip, implement strategy, add assertions). [DONE]
6.  Apply changes. [DONE]
7.  Confirm completion. [DONE]