from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session
from online_store.models import Category, Product


class CategoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str) -> Category:
        category = Category(name=name)
        self.session.add(category)
        self.session.commit()
        self.session.refresh(category)
        return category

    def get_by_id(self, category_id: int) -> Category | None:
        return self.session.get(Category, category_id)

    def get_by_name(self, name: str) -> Category | None:
        statement = select(Category).where(Category.name == name)
        return self.session.scalar(statement)

    def get_all(self) -> list[Category]:
        return list(self.session.scalars(select(Category)))

    def delete(self, category_id: int) -> bool:
        category = self.get_by_id(category_id)
        if category is None:
            return False
        self.session.delete(category)
        self.session.commit()
        return True


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, product: Product) -> Product:
        self.session.add(product)
        self.session.commit()
        self.session.refresh(product)
        return product

    def get_by_id(self, product_id: int) -> Product | None:
        return self.session.get(Product, product_id)

    def get_all(self) -> list[Product]:
        return list(self.session.scalars(select(Product)))

    def find_by_name(self, name: str) -> list[Product]:
        statement = select(Product).where(Product.name.ilike(f"%{name}%"))
        return list(self.session.scalars(statement))

    def find_by_category(self, category_id: int) -> list[Product]:
        statement = select(Product).where(Product.category_id == category_id)
        return list(self.session.scalars(statement))

    def search(
        self,
        *,
        q: str | None = None,
        category_id: int | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort_by: Literal["name", "price", "quantity"] = "name",
        descending: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Пошук, фільтрація, сортування та пагінація (розширення Lab 7 для REST API)."""
        statement = select(Product)
        if q:
            # SQLite lower()/ILIKE нечутливі до регістру лише для ASCII, тому для
            # кирилиці порівняння виконується через casefold() у Python.
            needle = q.casefold()
            ids = [
                pid for pid, name in self.session.execute(select(Product.id, Product.name))
                if needle in name.casefold()
            ]
            statement = statement.where(Product.id.in_(ids))
        if category_id is not None:
            statement = statement.where(Product.category_id == category_id)
        if min_price is not None:
            statement = statement.where(Product.price >= min_price)
        if max_price is not None:
            statement = statement.where(Product.price <= max_price)
        column = getattr(Product, sort_by)
        statement = statement.order_by(column.desc() if descending else column.asc(), Product.id)
        return list(self.session.scalars(statement.limit(limit).offset(offset)))

    def update_price_and_quantity(
        self, product_id: int, price: float | None = None, quantity: int | None = None
    ) -> Product | None:
        product = self.get_by_id(product_id)
        if product is None:
            return None
        if price is not None:
            product.price = price
        if quantity is not None:
            product.quantity = quantity
        self.session.commit()
        self.session.refresh(product)
        return product

    def delete(self, product_id: int) -> bool:
        product = self.get_by_id(product_id)
        if product is None:
            return False
        self.session.delete(product)
        self.session.commit()
        return True