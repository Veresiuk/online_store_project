"""Доменні exceptions. Наслідують ValueError, тому код Lab 7 (except ValueError) працює без змін."""


class StoreError(ValueError):
    code = "store_error"
    status_code = 400


class ProductNotFoundError(StoreError):
    code = "product_not_found"
    status_code = 404


class CategoryNotFoundError(StoreError):
    code = "category_not_found"
    status_code = 404


class DuplicateCategoryError(StoreError):
    code = "duplicate_category"
    status_code = 409


class InsufficientStockError(StoreError):
    code = "insufficient_stock"
    status_code = 409


class EmptyUpdateError(StoreError):
    code = "empty_update"
    status_code = 400


class InvalidPriceRangeError(StoreError):
    code = "invalid_price_range"
    status_code = 400
