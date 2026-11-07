"""Спільні fixtures: ізольована in-memory БД та ASGI-клієнт."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from online_store.api import app
from online_store.config import Settings
from online_store.dependencies import get_http_client, get_session, get_settings
from online_store.models import Base


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
async def client(session_factory):
    """AsyncClient, що звертається до застосунку через ASGI (без реальної мережі)."""

    async def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_http_client] = lambda: http
        app.dependency_overrides[get_settings] = lambda: Settings(
            batch_timeout=2.0, max_concurrency=3, retry_attempts=2, backoff_base=0.0
        )
        yield http
    app.dependency_overrides.clear()


@pytest.fixture
async def category(client):
    return (await client.post("/categories", json={"name": "Електроніка"})).json()


@pytest.fixture
async def laptop(client, category):
    response = await client.post(
        "/products",
        json={"name": "Ноутбук", "category_id": category["id"], "price": 25000,
              "quantity": 3, "description": "Робочий ноутбук"},
    )
    return response.json()


@pytest.fixture
async def catalog(client, category):
    """Три товари у двох категоріях."""
    books = (await client.post("/categories", json={"name": "Книги"})).json()
    items = [
        {"name": "Ноутбук", "category_id": category["id"], "price": 25000, "quantity": 3},
        {"name": "Миша", "category_id": category["id"], "price": 500, "quantity": 20},
        {"name": "Чистий код", "category_id": books["id"], "price": 40.5, "quantity": 100},
    ]
    for item in items:
        await client.post("/products", json=item)
    return {"electronics": category, "books": books}
