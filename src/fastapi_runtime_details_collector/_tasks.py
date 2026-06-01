import asyncio
import logging
import time

import anyio.to_thread

from fastapi_runtime_details_collector._collector import FastAPIRuntimeCollector

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.0


async def _poll(collector: FastAPIRuntimeCollector) -> None:
    loop = asyncio.get_running_loop()
    while True:
        t0 = loop.time()
        await asyncio.sleep(_POLL_INTERVAL)
        lag = loop.time() - t0 - _POLL_INTERVAL
        limiter = anyio.to_thread.current_default_thread_limiter()
        collector._update(
            eventloop_lag_seconds=max(0.0, lag),
            eventloop_tasks_total=len(asyncio.all_tasks()),
            threadpool_capacity_tokens=limiter.total_tokens,
            threadpool_active_threads=limiter.borrowed_tokens,
            last_collection_timestamp_seconds=int(time.time()),
        )


def setup_lag_monitor(collector: FastAPIRuntimeCollector | None = None) -> asyncio.Task:
    """
    Starts a background asyncio task that samples event loop lag and anyio thread pool
    state every second, feeding the results into a FastAPIRuntimeCollector.

    Must be called from inside a running anyio event loop (e.g. FastAPI lifespan startup).
    Returns the task — cancel it on shutdown:

        task = setup_lag_monitor(collector)
        # on shutdown:
        task.cancel()
    """
    if collector is None:
        collector = FastAPIRuntimeCollector()
    return asyncio.create_task(_poll(collector), name="fastapi-runtime-metrics-poll")
