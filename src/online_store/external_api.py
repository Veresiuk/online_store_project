"""Асинхронний HTTP-клієнт: HTTPX + Task + gather + Semaphore + retry."""
from __future__ import annotations

import asyncio

import httpx


async def fetch_product(client: httpx.AsyncClient, product_id: int) -> dict:
    """Один GET-запит до REST API."""
    response = await client.get(f"/products/{product_id}")
    response.raise_for_status()
    return response.json()


def _is_retryable(exc: Exception) -> bool:
    """Мережеві помилки та 5xx повторюються; 4xx (наприклад, 404) — ні."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.RequestError)


async def fetch_with_retry(
    client: httpx.AsyncClient,
    product_id: int,
    *,
    attempts: int = 3,
    backoff_base: float = 0.2,
) -> dict:
    """Retry з exponential backoff: 0.2 c, 0.4 c, 0.8 c ..."""
    for attempt in range(1, attempts + 1):
        try:
            return await fetch_product(client, product_id)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            if attempt == attempts or not _is_retryable(exc):
                raise
            await asyncio.sleep(backoff_base * 2 ** (attempt - 1))
    raise RuntimeError("Unexpected retry state")  # pragma: no cover


async def limited_fetch(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    product_id: int,
    *,
    attempts: int = 3,
    backoff_base: float = 0.2,
) -> dict:
    """Semaphore обмежує кількість одночасних запитів."""
    async with semaphore:
        return await fetch_with_retry(
            client, product_id, attempts=attempts, backoff_base=backoff_base
        )


async def fetch_many(
    client: httpx.AsyncClient,
    product_ids: list[int],
    *,
    max_concurrency: int = 5,
    attempts: int = 3,
    backoff_base: float = 0.2,
) -> list[dict]:
    """Паралельне отримання кількох товарів (Task + gather + Semaphore)."""
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = [
        asyncio.create_task(
            limited_fetch(
                client, semaphore, pid, attempts=attempts, backoff_base=backoff_base
            )
        )
        for pid in product_ids
    ]
    try:
        return list(await asyncio.gather(*tasks))
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
