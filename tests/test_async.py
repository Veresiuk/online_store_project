"""Async tests: Task, gather, Semaphore, timeout, retry, HTTPX."""
import asyncio

import httpx
import pytest

from online_store import api
from online_store.external_api import fetch_many, fetch_with_retry


def mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://upstream")


def ok(request: httpx.Request) -> httpx.Response:
    product_id = int(request.url.path.rsplit("/", 1)[1])
    return httpx.Response(200, json={"id": product_id})


# ------------------------------------------------------------- HTTPX / gather
async def test_fetch_many_returns_results_in_request_order():
    async with mock_client(ok) as client:
        result = await fetch_many(client, [3, 1, 2])
    assert [item["id"] for item in result] == [3, 1, 2]


async def test_fetch_many_runs_requests_in_parallel():
    async def slow(request):
        await asyncio.sleep(0.1)
        return ok(request)

    async with mock_client(slow) as client:
        started = asyncio.get_running_loop().time()
        await fetch_many(client, list(range(1, 6)), max_concurrency=5)
        elapsed = asyncio.get_running_loop().time() - started
    assert elapsed < 0.3  # sequential execution would take about 0.5 s


# ------------------------------------------------------------------ Semaphore
async def test_semaphore_limits_concurrency():
    active = peak = 0

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return ok(request)

    async with mock_client(handler) as client:
        result = await fetch_many(client, list(range(1, 11)), max_concurrency=3)
    assert len(result) == 10
    assert peak == 3


# ---------------------------------------------------------------------- retry
async def test_retry_succeeds_after_temporary_failures():
    calls = 0

    def flaky(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls < 3 else ok(request)

    async with mock_client(flaky) as client:
        result = await fetch_with_retry(client, 7, attempts=3, backoff_base=0)
    assert result == {"id": 7}
    assert calls == 3


async def test_retry_gives_up_after_all_attempts():
    calls = 0

    def always_down(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    async with mock_client(always_down) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_with_retry(client, 1, attempts=3, backoff_base=0)
    assert calls == 3


async def test_client_errors_are_not_retried():
    calls = 0

    def not_found(request):
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async with mock_client(not_found) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_with_retry(client, 1, attempts=3, backoff_base=0)
    assert calls == 1


async def test_network_errors_are_retried():
    calls = 0

    def network_error(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("refused")

    async with mock_client(network_error) as client:
        with pytest.raises(httpx.ConnectError):
            await fetch_with_retry(client, 1, attempts=2, backoff_base=0)
    assert calls == 2


async def test_failed_task_cancels_the_other_tasks():
    cancelled = 0

    async def handler(request):
        nonlocal cancelled
        if request.url.path.endswith("/1"):
            return httpx.Response(404)
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled += 1
            raise
        return ok(request)

    async with mock_client(handler) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_many(client, [1, 2, 3], attempts=1)
    assert cancelled == 2


# ---------------------------------------------------- batch endpoint (API+HTTPX)
async def test_batch_endpoint_fetches_products_through_httpx(client, catalog):
    response = await client.post("/products/batch", json={"product_ids": [3, 1, 2]})
    assert response.status_code == 200
    assert [p["name"] for p in response.json()] == ["Чистий код", "Ноутбук", "Миша"]


async def test_batch_endpoint_returns_404_for_missing_product(client, catalog):
    response = await client.post("/products/batch", json={"product_ids": [1, 999]})
    assert response.status_code == 404


@pytest.mark.parametrize("ids", [[], list(range(1, 52)), ["a"]], ids=["empty", "too-many", "not-int"])
async def test_batch_endpoint_validation(client, ids):
    assert (await client.post("/products/batch", json={"product_ids": ids})).status_code == 422


async def test_batch_endpoint_timeout_returns_504(client, monkeypatch):
    async def very_slow(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(api, "fetch_many", very_slow)
    from online_store.config import Settings
    from online_store.dependencies import get_settings
    api.app.dependency_overrides[get_settings] = lambda: Settings(batch_timeout=0.05)
    response = await client.post("/products/batch", json={"product_ids": [1]})
    assert response.status_code == 504
    assert response.json()["detail"] == "Batch operation timed out"


@pytest.mark.parametrize(
    "error, status_code",
    [(httpx.ConnectError("down"), 503), (httpx.HTTPStatusError("x", request=None, response=httpx.Response(500)), 502)],
    ids=["upstream-unavailable", "upstream-500"],
)
async def test_batch_endpoint_maps_upstream_failures(client, monkeypatch, error, status_code):
    async def failing(*args, **kwargs):
        raise error

    monkeypatch.setattr(api, "fetch_many", failing)
    response = await client.post("/products/batch", json={"product_ids": [1]})
    assert response.status_code == status_code


# ----------------------------------------------------------------- lifespan
async def test_lifespan_creates_tables_and_closes_http_client(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, inspect

    from online_store import database

    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(database, "engine", engine)
    async with api.lifespan(api.app):
        assert not api.app.state.http_client.is_closed
        http_client = api.app.state.http_client
        assert {"products", "categories"} <= set(inspect(engine).get_table_names())
    assert http_client.is_closed
