import logging
from dataclasses import dataclass
from typing import Optional

from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import CollectorRegistry

logger = logging.getLogger(__name__)


@dataclass
class _Cache:
    eventloop_lag_seconds: float = 0.0
    eventloop_tasks_total: int = 0
    threadpool_capacity_tokens: float = 0.0
    threadpool_active_threads: float = 0.0
    last_collection_timestamp_seconds: Optional[int] = None


class FastAPIRuntimeCollector:
    """
    Prometheus collector for FastAPI runtime metrics.

    Values are cached by the background task (setup_lag_monitor) which runs in the
    proper anyio context. collect() reads from that cache at scrape time.

    Usage:
        collector = FastAPIRuntimeCollector()       # auto-registers in default registry
        task = setup_lag_monitor(collector)         # feed the collector
        # on shutdown:
        task.cancel()
    """

    def __init__(self, registry: CollectorRegistry = REGISTRY) -> None:
        self._cache = _Cache()
        registry.register(self)

    def _update(
        self,
        eventloop_lag_seconds: float,
        eventloop_tasks_total: int,
        threadpool_capacity_tokens: float,
        threadpool_active_threads: float,
        last_collection_timestamp_seconds: int,
    ) -> None:
        self._cache.eventloop_lag_seconds = eventloop_lag_seconds
        self._cache.eventloop_tasks_total = eventloop_tasks_total
        self._cache.threadpool_capacity_tokens = threadpool_capacity_tokens
        self._cache.threadpool_active_threads = threadpool_active_threads
        self._cache.last_collection_timestamp_seconds = last_collection_timestamp_seconds

    def collect(self):
        c = self._cache

        if c.last_collection_timestamp_seconds is None:
            return

        lag = GaugeMetricFamily(
            "fastapi_eventloop_lag_seconds",
            "Event loop lag in seconds: measured drift between a scheduled sleep and its actual wake-up",
        )
        lag.add_metric([], c.eventloop_lag_seconds)
        yield lag

        tasks = GaugeMetricFamily(
            "fastapi_eventloop_tasks_total",
            "Number of asyncio tasks currently pending in the event loop",
        )
        tasks.add_metric([], c.eventloop_tasks_total)
        yield tasks

        capacity = GaugeMetricFamily(
            "fastapi_threadpool_capacity_tokens",
            "Total token capacity of anyio's default thread limiter (max concurrent sync handlers)",
        )
        capacity.add_metric([], c.threadpool_capacity_tokens)
        yield capacity

        active = GaugeMetricFamily(
            "fastapi_threadpool_active_threads",
            "Number of sync handler threads currently executing (anyio borrowed tokens)",
        )
        active.add_metric([], c.threadpool_active_threads)
        yield active

        ts = GaugeMetricFamily(
            "fastapi_metrics_last_collection_timestamp_seconds",
            "Unix timestamp (seconds since epoch) of the last successful metrics collection",
        )
        ts.add_metric([], c.last_collection_timestamp_seconds)
        yield ts
