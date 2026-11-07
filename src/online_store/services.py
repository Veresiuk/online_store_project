import sqlite3
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from online_store.exceptions import InsufficientStockError, ProductNotFoundError
from online_store.models import Product


class StoreService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_total_stock_value(self) -> float:
        """Обчислення загальної вартості залишків на складі (SUM(price * quantity))."""
        statement = select(func.sum(Product.price * Product.quantity))
        result = self.session.scalar(statement)
        return float(result) if result is not None else 0.0

    def get_most_expensive_product(self) -> Product | None:
        """Пошук найдорожчого товару."""
        statement = select(Product).order_by(Product.price.desc()).limit(1)
        return self.session.scalar(statement)

    def purchase_product(self, product_id: int, count_to_buy: int) -> Product:
        """
        Транзакція покупки товару:
        Перевіряє залишок, зменшує quantity та виконує commit.
        У разі нестачі залишків або збою виконується rollback (гарантія Atomicity).
        """
        if count_to_buy <= 0:
            raise ValueError("Кількість для покупки має бути більшою за нуль.")

        try:
            product = self.session.get(Product, product_id)
            if product is None:
                raise ProductNotFoundError("Товар не знайдено.")

            if product.quantity < count_to_buy:
                raise InsufficientStockError(
                    f"Недостатньо товару на складі. Доступно: {product.quantity}, запитано: {count_to_buy}"
                )

            product.quantity -= count_to_buy
            self.session.commit()
            self.session.refresh(product)
            return product
        except Exception:
            self.session.rollback()
            raise


def find_products_by_category_name_dbapi(
    database_path: str, category_name: str
) -> list[tuple]:
    """
    Параметризований пошук товарів через стандартний модуль sqlite3 (DB-API).
    Використовує '?' для запобігання SQL Injection.
    """
    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                products.name,
                products.price,
                products.quantity,
                categories.name
            FROM products
            JOIN categories ON products.category_id = categories.id
            WHERE categories.name = ?
            ORDER BY products.price DESC
            """,
            (category_name,),
        )
        return cursor.fetchall()