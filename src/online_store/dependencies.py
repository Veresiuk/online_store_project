"""FastAPI dependencies."""
from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from online_store import database
from online_store.config import Settings


async def get_session() -> AsyncGenerator[Session, None]:
    """Одна Session SQLAlchemy на один HTTP-запит (SessionLocal із Lab 7)."""
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_settings() -> Settings:
    return Settings.from_env()


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Спільний AsyncClient, створений у lifespan застосунку."""
    return request.app.state.http_client
