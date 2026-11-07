"""FastAPI application: REST API інтернет-магазину (Lab 8) поверх persistence layer із Lab 7."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from online_store import database
from online_store.config import Settings
from online_store.dependencies import get_http_client, get_session, get_settings
from online_store.exceptions import (
    CategoryNotFoundError,
    DuplicateCategoryError,
    EmptyUpdateError,
    InvalidPriceRangeError,
    ProductNotFoundError,
    StoreError,
)
from online_store.external_api import fetch_many
from online_store.models import Base, Category, Product
from online_store.repositories import CategoryRepository, ProductRepository
from online_store.schemas import (
    BatchRequest,
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
    PurchaseRequest,
    PurchaseResponse,
    StockSummary,
)
from online_store.services import StoreService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Створює таблиці та один спільний AsyncClient на весь час роботи застосунку."""
    Base.metadata.create_all(database.engine)
    settings = Settings.from_env()
    app.state.http_client = httpx.AsyncClient(
        base_url=settings.api_base_url,
        timeout=httpx.Timeout(5.0, connect=2.0),
    )
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(
    title="Online Store API",
    version="0.8.0",
    description="Асинхронний REST API інтернет-магазину (лабораторна робота №8).",
    lifespan=lifespan,
)


@app.exception_handler(StoreError)
async def store_error_handler(request: Request, exc: StoreError) -> JSONResponse:
    """Доменні помилки → структурована JSON-відповідь із відповідним status code."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc), "code": exc.code},
    )


def _product_or_404(session: Session, product_id: int) -> Product:
    product = ProductRepository(session).get_by_id(product_id)
    if product is None:
        raise ProductNotFoundError(f"Товар {product_id} не знайдено")
    return product


def _category_or_404(session: Session, category_id: int) -> Category:
    category = CategoryRepository(session).get_by_id(category_id)
    if category is None:
        raise CategoryNotFoundError(f"Категорію {category_id} не знайдено")
    return category


@app.get("/", tags=["service"])
async def root() -> dict[str, str]:
    return {"service": "Online Store API", "version": app.version, "docs": "/docs"}


# ---------------------------------------------------------------- categories
@app.get("/categories", response_model=list[CategoryResponse], tags=["categories"])
async def list_categories(session: Session = Depends(get_session)):
    return CategoryRepository(session).get_all()


@app.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["categories"],
)
async def create_category(data: CategoryCreate, session: Session = Depends(get_session)):
    repository = CategoryRepository(session)
    if repository.get_by_name(data.name):
        raise DuplicateCategoryError(f"Категорія '{data.name}' вже існує")
    return repository.add(data.name)


@app.get(
    "/categories/{category_id}/products",
    response_model=list[ProductResponse],
    tags=["categories"],
)
async def category_products(category_id: int, session: Session = Depends(get_session)):
    _category_or_404(session, category_id)
    return ProductRepository(session).find_by_category(category_id)


# ------------------------------------------------------------------ products
@app.get("/products", response_model=list[ProductResponse], tags=["products"])
async def list_products(
    q: str | None = Query(default=None, min_length=1, description="Пошук за назвою"),
    category_id: int | None = Query(default=None, gt=0),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    sort_by: Literal["name", "price", "quantity"] = "name",
    descending: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise InvalidPriceRangeError("min_price не може бути більшою за max_price")
    return ProductRepository(session).search(
        q=q, category_id=category_id, min_price=min_price, max_price=max_price,
        sort_by=sort_by, descending=descending, limit=limit, offset=offset,
    )


@app.get("/products/summary", response_model=StockSummary, tags=["products"])
async def stock_summary(session: Session = Depends(get_session)):
    """Загальна вартість залишків і найдорожчий товар (StoreService із Lab 7)."""
    service = StoreService(session)
    return StockSummary(
        products_count=len(ProductRepository(session).get_all()),
        total_stock_value=round(service.get_total_stock_value(), 2),
        most_expensive=service.get_most_expensive_product(),
    )


@app.post("/products/batch", response_model=list[ProductResponse], tags=["async"])
async def batch_products(
    body: BatchRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
):
    """Паралельне отримання кількох товарів через HTTPX (Task, gather, Semaphore, timeout, retry)."""
    try:
        return await asyncio.wait_for(
            fetch_many(
                client,
                body.product_ids,
                max_concurrency=settings.max_concurrency,
                attempts=settings.retry_attempts,
                backoff_base=settings.backoff_base,
            ),
            timeout=settings.batch_timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "Batch operation timed out")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "One of the products was not found")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Upstream request failed")
    except httpx.RequestError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Upstream is unavailable")


@app.get("/products/{product_id}", response_model=ProductResponse, tags=["products"])
async def get_product(product_id: int, session: Session = Depends(get_session)):
    return _product_or_404(session, product_id)


@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
async def create_product(data: ProductCreate, session: Session = Depends(get_session)):
    _category_or_404(session, data.category_id)
    return ProductRepository(session).add(Product(**data.model_dump()))


@app.patch("/products/{product_id}", response_model=ProductResponse, tags=["products"])
async def update_product(
    product_id: int, data: ProductUpdate, session: Session = Depends(get_session)
):
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise EmptyUpdateError("Немає полів для оновлення")
    product = ProductRepository(session).update_price_and_quantity(product_id, **changes)
    if product is None:
        raise ProductNotFoundError(f"Товар {product_id} не знайдено")
    return product


@app.delete(
    "/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["products"]
)
async def delete_product(product_id: int, session: Session = Depends(get_session)) -> None:
    if not ProductRepository(session).delete(product_id):
        raise ProductNotFoundError(f"Товар {product_id} не знайдено")


@app.post(
    "/products/{product_id}/purchase", response_model=PurchaseResponse, tags=["products"]
)
async def purchase_product(
    product_id: int, body: PurchaseRequest, session: Session = Depends(get_session)
):
    """Транзакційна покупка: StoreService.purchase_product (commit / rollback з Lab 7)."""
    product = StoreService(session).purchase_product(product_id, body.quantity)
    return PurchaseResponse(
        product_id=product.id,
        quantity=body.quantity,
        total_price=round(product.price * body.quantity, 2),
        remaining_quantity=product.quantity,
    )
