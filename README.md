# fastapi-runtime-details-collector

Prometheus metrics collector for FastAPI applications that exposes event loop health and thread pool utilization in real time.

## Why

FastAPI runs on an asyncio event loop with a thread pool for synchronous route handlers. Neither is observable out of the box. This library adds two key signals:

- **Event loop lag** — how long the loop was blocked before it could process the next iteration. Sustained lag means CPU-bound or blocking work is starving your async handlers.
- **Thread pool saturation** — how many of anyio's sync-handler threads are currently active versus the total capacity.

## Installation

```bash
pip install fastapi-runtime-details-collector
```

Requires Python 3.10+ and a FastAPI application already using `prometheus_client` to expose a `/metrics` endpoint.

## Metrics

| Metric                                              | Type  | Description                                                                           |
| --------------------------------------------------- | ----- | ------------------------------------------------------------------------------------- |
| `fastapi_eventloop_lag_seconds`                     | Gauge | Drift between a scheduled `asyncio.sleep` and its actual wake-up, in seconds          |
| `fastapi_eventloop_tasks_total`                     | Gauge | Number of asyncio tasks currently pending in the event loop                           |
| `fastapi_threadpool_capacity_tokens`                | Gauge | Total token capacity of anyio's default thread limiter (max concurrent sync handlers) |
| `fastapi_threadpool_active_threads`                 | Gauge | Number of sync handler threads currently executing (anyio borrowed tokens)            |
| `fastapi_metrics_last_collection_timestamp_seconds` | Gauge | Unix timestamp of the last successful metrics collection                              |

Metrics are collected every second by a background task. No metrics are exposed until the first successful collection.

## Setup

### 1. Expose a `/metrics` endpoint

If you don't already have one:

```bash
pip install prometheus-client
```

```python
from prometheus_client import make_asgi_app

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### 2. Register the collector in your lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi_runtime_details_collector import FastAPIRuntimeCollector, setup_lag_monitor

@asynccontextmanager
async def lifespan(app: FastAPI):
    collector = FastAPIRuntimeCollector()
    task = setup_lag_monitor(collector)
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
```

`setup_lag_monitor` must be called from within a running anyio event loop, so the FastAPI lifespan startup is the right place.

### Custom registry

If you use a custom Prometheus registry instead of the global default:

```python
from prometheus_client import CollectorRegistry
from prometheus_client import make_asgi_app
from fastapi_runtime_details_collector import FastAPIRuntimeCollector, setup_lag_monitor

registry = CollectorRegistry()

@asynccontextmanager
async def lifespan(app: FastAPI):
    collector = FastAPIRuntimeCollector(registry=registry)
    task = setup_lag_monitor(collector)
    yield
    task.cancel()

metrics_app = make_asgi_app(registry=registry)
app.mount("/metrics", metrics_app)
```

## Full example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from fastapi_runtime_details_collector import FastAPIRuntimeCollector, setup_lag_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    collector = FastAPIRuntimeCollector()
    task = setup_lag_monitor(collector)
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


@app.get("/")
async def root():
    return {"status": "ok"}
```

Run with `uvicorn main:app` and scrape `http://localhost:8000/metrics`.

## Grafana dashboard

A ready-to-import dashboard is available in [`grafana/fastapi-runtime-details.json`](grafana/fastapi-runtime-details.json).

**Panels:**
- Event loop lag, pending tasks, active threads, seconds since last collection (stat panels with color thresholds)
- Event loop lag over time (time series)
- Pending asyncio tasks over time (time series)
- Thread pool active vs capacity over time (time series)
- Thread pool saturation % (gauge)

**Import steps:**

1. In Grafana, go to **Dashboards → Import**
2. Click **Upload dashboard JSON file** and select `grafana/fastapi-runtime-details.json`
3. Select your Prometheus data source
4. Pick the `job` label that matches your app's scrape config

The dashboard auto-refreshes every 10 seconds and exposes a `$job` variable to filter by service.
