# Online Store

Лабораторна робота №8 «Мережеве та асинхронне програмування. REST API», варіант №3 — «Інтернет-магазин».
REST API побудовано поверх persistence layer із Lab 7 (SQLAlchemy, SQLite, repositories, services, Alembic).

Архітектура: `HTTP client → FastAPI → Pydantic → StoreService / Repositories → SQLAlchemy / SQLite`.

## Installation
    python -m venv .venv
    .venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
    python -m pip install -e ".[test]"

## Run
    python -m online_store.main                 # демонстрація Lab 7 (створює store.db з даними)
    uvicorn online_store.api:app --reload       # REST API

Swagger UI: http://127.0.0.1:8000/docs

## Environment variables
| Variable | Default | Description |
|---|---|---|
| STORE_API_BASE_URL | http://127.0.0.1:8000 | base URL для batch-запитів HTTPX |
| STORE_BATCH_TIMEOUT | 10 | timeout batch-операції, с |
| STORE_MAX_CONCURRENCY | 5 | розмір Semaphore |
| STORE_RETRY_ATTEMPTS | 3 | кількість спроб retry |

## Tests
    python -m pytest -v
