"""Synchronous wrappers over the async Postgres repositories.

``OrderService`` (and the location-search helpers it shares style with)
call the repository synchronously. Running the poller loop and FastAPI
handlers in one event loop means we must not call ``asyncio.run`` inside
a running loop — so these shims execute the coroutine on a dedicated
worker loop via ``anyio.from_thread``-style bridging kept dependency-free:

    - from the main event loop  -> run in a thread via ``asyncio.run``
      is unsafe; we instead use the module-level ``run_sync`` helper that
      detects a running loop and offloads to ``loop.run_in_executor``.
"""

import asyncio
import concurrent.futures
from typing import Any, Coroutine

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="pg-sync")
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once at app startup so sync code can bridge back to the loop."""
    global _main_loop
    _main_loop = loop


def run_sync(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async repository call from sync code, safely.

    asyncpg connections are bound to the event loop that created them,
    calling from the main-thread of the app (the loop thread) — sync
    handlers/bridged code run there — hop to a worker thread so the
    coroutine gets its own loop and its own (NullPool) DB connection.
    Called from other threads, run on a private loop as well.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        # We're inside the main loop: hop to the executor with a fresh loop.
        return _execute_in_worker(coro)

    # Called from a plain thread (sync context) — private loop is fine with NullPool.
    return asyncio.run(coro)


def _execute_in_worker(coro: Coroutine[Any, Any, Any]) -> Any:
    future = _executor.submit(asyncio.run, coro)
    return future.result()
