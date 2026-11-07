"""Pydantic schemas (request bodies and responses)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class CategoryResponse(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category_id: int = Field(gt=0)
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)
    description: str | None = Field(default=None, max_length=255)


class ProductUpdate(BaseModel):
    price: float | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, ge=0)


class ProductResponse(BaseModel):
    id: int
    name: str
    category_id: int
    price: float
    quantity: int
    description: str | None = None
    model_config = {"from_attributes": True}


class PurchaseRequest(BaseModel):
    quantity: int = Field(gt=0, le=1000)


class PurchaseResponse(BaseModel):
    product_id: int
    quantity: int
    total_price: float
    remaining_quantity: int


class StockSummary(BaseModel):
    products_count: int
    total_stock_value: float
    most_expensive: ProductResponse | None


class BatchRequest(BaseModel):
    product_ids: list[int] = Field(min_length=1, max_length=50)
