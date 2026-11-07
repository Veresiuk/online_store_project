from online_store.database import DATABASE_FILE, SessionLocal, engine
from online_store.models import Base, Product
from online_store.repositories import CategoryRepository, ProductRepository
from online_store.services import StoreService, find_products_by_category_name_dbapi


def main() -> None:
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        cat_repo = CategoryRepository(session)
        prod_repo = ProductRepository(session)
        service = StoreService(session)

        electronics = cat_repo.get_by_name("Електроніка")
        if not electronics:
            electronics = cat_repo.add("Електроніка")

        books = cat_repo.get_by_name("Книги")
        if not books:
            books = cat_repo.add("Книги")

        if not prod_repo.get_all():
            prod_repo.add(
                Product(
                    name="Ноутбук Pro 15",
                    price=45000.0,
                    quantity=8,
                    category_id=electronics.id,
                    description="Потужний робочий ноутбук",
                )
            )
            prod_repo.add(
                Product(
                    name="Бездротова миша",
                    price=950.0,
                    quantity=25,
                    category_id=electronics.id,
                    description="Ергономічна миша",
                )
            )
            prod_repo.add(
                Product(
                    name="Чистий код",
                    price=800.0,
                    quantity=12,
                    category_id=books.id,
                    description="Класика для розробників",
                )
            )

        print("=== Список товарів ===")
        for p in prod_repo.get_all():
            print(f"[{p.id}] {p.name:20} | Ціна: {p.price:8.2f} грн | Кількість: {p.quantity}")

        print(f"\nЗагальна вартість залишків: {service.get_total_stock_value():.2f} грн")
        expensive = service.get_most_expensive_product()
        if expensive:
            print(f"Найдорожчий товар: {expensive.name} ({expensive.price} грн)")

        laptop = prod_repo.find_by_name("Ноутбук")[0]
        print(f"\nКупівля 2 шт. товару '{laptop.name}'...")
        service.purchase_product(laptop.id, 2)
        print(f"Залишок після покупки: {laptop.quantity} шт.")

    print("\n=== Демонстрація DB-API (товари категорії 'Електроніка') ===")
    dbapi_rows = find_products_by_category_name_dbapi(DATABASE_FILE, "Електроніка")
    for row in dbapi_rows:
        print(f"Назва: {row[0]:20} | Ціна: {row[1]:8.2f} | Кількість: {row[2]}")


if __name__ == "__main__":
    main()