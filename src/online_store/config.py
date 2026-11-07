"""Налаштування REST API з environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_base_url: str = "http://127.0.0.1:8000"
    batch_timeout: float = 10.0
    max_concurrency: int = 5
    retry_attempts: int = 3
    backoff_base: float = 0.2

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            api_base_url=env.get("STORE_API_BASE_URL", cls.api_base_url),
            batch_timeout=float(env.get("STORE_BATCH_TIMEOUT", cls.batch_timeout)),
            max_concurrency=int(env.get("STORE_MAX_CONCURRENCY", cls.max_concurrency)),
            retry_attempts=int(env.get("STORE_RETRY_ATTEMPTS", cls.retry_attempts)),
        )
