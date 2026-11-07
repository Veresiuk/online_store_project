"""Тести REST API: status codes, validation, фільтри, транзакції."""
import pytest
from sqlalchemy.orm import Session

from online_store.exceptions import InsufficientStockError, ProductNotFoundError
from online_store.models import Product
from online_store.repositories import CategoryRepository, ProductRepository
from online_store.services import StoreService


async def test_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Online Store API"


# ---------------------------------------------------------------- categories
async def test_create_category_returns_201(client):
    response = await client.post("/categories", json={"name": "Книги"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "name": "Книги"}


async def test_duplicate_category_returns_409(client, category):
    response = await client.post("/categories", json={"name": "Електроніка"})
    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_category"


async def test_create_category_with_short_name_returns_422(client):
    assert (await client.post("/categories", json={"name": "A"})).status_code == 422


async def test_list_categories(client, catalog):
    names = {c["name"] for c in (await client.get("/categories")).json()}
    assert names == {"Електроніка", "Книги"}


async def test_category_products(client, catalog):
    response = await client.get(f"/categories/{catalog['electronics']['id']}/products")
    assert response.status_code == 200
    assert {p["name"] for p in response.json()} == {"Ноутбук", "Миша"}


async def test_category_products_unknown_category_returns_404(client):
    response = await client.get("/categories/999/products")
    assert response.status_code == 404
    assert response.json()["code"] == "category_not_found"


# ------------------------------------------------------------------ products
async def test_create_product_returns_201_and_json(client, category):
    payload = {"name": "Ноутбук", "category_id": category["id"], "price": 25000, "quantity": 3}
    response = await client.post("/products", json=payload)
    assert response.status_code == 201
    assert response.json() == {
        "id": 1, "name": "Ноутбук", "category_id": 1, "price": 25000.0,
        "quantity": 3, "description": None,
    }


async def test_create_product_with_description(client, laptop):
    assert laptop["description"] == "Робочий ноутбук"


@pytest.mark.parametrize(
    "patch",
    [
        {"price": 0}, {"price": -5}, {"quantity": -1}, {"name": "A"}, {"name": ""},
        {"category_id": 0}, {"price": "abc"}, {"description": "x" * 256},
    ],
    ids=["zero-price", "negative-price", "negative-quantity", "short-name", "empty-name",
         "bad-category", "price-not-number", "long-description"],
)
async def test_create_product_validation_errors_return_422(client, category, patch):
    payload = {"name": "Ноутбук", "category_id": category["id"], "price": 10, "quantity": 1, **patch}
    assert (await client.post("/products", json=payload)).status_code == 422


async def test_create_product_missing_field_returns_422(client):
    assert (await client.post("/products", json={"name": "Ноутбук"})).status_code == 422


async def test_create_product_unknown_category_returns_404(client):
    payload = {"name": "Ноутбук", "category_id": 42, "price": 10, "quantity": 1}
    assert (await client.post("/products", json=payload)).status_code == 404


async def test_get_product(client, laptop):
    response = await client.get(f"/products/{laptop['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Ноутбук"


async def test_get_missing_product_returns_404(client):
    response = await client.get("/products/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Товар 999 не знайдено", "code": "product_not_found"}


async def test_get_product_with_non_integer_id_returns_422(client):
    assert (await client.get("/products/abc")).status_code == 422


async def test_list_products_sorted_by_name_by_default(client, catalog):
    names = [p["name"] for p in (await client.get("/products")).json()]
    assert names == sorted(names)
    assert len(names) == 3


async def test_filter_by_category(client, catalog):
    response = await client.get("/products", params={"category_id": catalog["books"]["id"]})
    assert [p["name"] for p in response.json()] == ["Чистий код"]


async def test_search_by_name_is_case_insensitive(client, catalog):
    response = await client.get("/products", params={"q": "НОУТ"})
    assert [p["name"] for p in response.json()] == ["Ноутбук"]


async def test_filter_by_price_range(client, catalog):
    response = await client.get("/products", params={"min_price": 100, "max_price": 1000})
    assert [p["name"] for p in response.json()] == ["Миша"]


async def test_invalid_price_range_returns_400(client, catalog):
    response = await client.get("/products", params={"min_price": 500, "max_price": 100})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_price_range"


async def test_sort_by_price_descending(client, catalog):
    response = await client.get("/products", params={"sort_by": "price", "descending": "true"})
    assert [p["price"] for p in response.json()] == [25000.0, 500.0, 40.5]


async def test_pagination(client, catalog):
    response = await client.get("/products", params={"sort_by": "price", "limit": 1, "offset": 1})
    assert [p["name"] for p in response.json()] == ["Миша"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"sort_by": "color"}])
async def test_invalid_query_parameters_return_422(client, params):
    assert (await client.get("/products", params=params)).status_code == 422


async def test_patch_price_and_quantity(client, laptop):
    response = await client.patch(f"/products/{laptop['id']}", json={"price": 23999.99, "quantity": 7})
    assert response.status_code == 200
    body = response.json()
    assert (body["price"], body["quantity"], body["name"]) == (23999.99, 7, "Ноутбук")


async def test_patch_only_price_keeps_quantity(client, laptop):
    body = (await client.patch(f"/products/{laptop['id']}", json={"price": 1})).json()
    assert (body["price"], body["quantity"]) == (1.0, 3)


async def test_patch_with_empty_body_returns_400(client, laptop):
    response = await client.patch(f"/products/{laptop['id']}", json={})
    assert response.status_code == 400
    assert response.json()["code"] == "empty_update"


async def test_patch_invalid_value_returns_422(client, laptop):
    assert (await client.patch(f"/products/{laptop['id']}", json={"quantity": -3})).status_code == 422


async def test_patch_missing_product_returns_404(client):
    assert (await client.patch("/products/999", json={"price": 5})).status_code == 404


async def test_delete_product_returns_204_then_404(client, laptop):
    response = await client.delete(f"/products/{laptop['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(f"/products/{laptop['id']}")).status_code == 404


async def test_delete_missing_product_returns_404(client):
    assert (await client.delete("/products/999")).status_code == 404


# ------------------------------------------------------------------- summary
async def test_summary_total_value_and_most_expensive(client, catalog):
    body = (await client.get("/products/summary")).json()
    assert body["products_count"] == 3
    assert body["total_stock_value"] == pytest.approx(25000 * 3 + 500 * 20 + 40.5 * 100)
    assert body["most_expensive"]["name"] == "Ноутбук"


async def test_summary_of_empty_store(client):
    body = (await client.get("/products/summary")).json()
    assert body == {"products_count": 0, "total_stock_value": 0.0, "most_expensive": None}


# ------------------------------------------------------- transactional logic
async def test_purchase_decreases_stock(client, laptop):
    response = await client.post(f"/products/{laptop['id']}/purchase", json={"quantity": 2})
    assert response.status_code == 200
    assert response.json() == {
        "product_id": laptop["id"], "quantity": 2, "total_price": 50000.0, "remaining_quantity": 1,
    }
    assert (await client.get(f"/products/{laptop['id']}")).json()["quantity"] == 1


async def test_purchase_all_remaining_stock_is_allowed(client, laptop):
    response = await client.post(f"/products/{laptop['id']}/purchase", json={"quantity": 3})
    assert response.status_code == 200
    assert response.json()["remaining_quantity"] == 0


async def test_purchase_more_than_stock_returns_409_and_keeps_stock(client, laptop):
    response = await client.post(f"/products/{laptop['id']}/purchase", json={"quantity": 4})
    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_stock"
    assert (await client.get(f"/products/{laptop['id']}")).json()["quantity"] == 3


@pytest.mark.parametrize("quantity", [0, -1, 1001, "x"])
async def test_purchase_invalid_quantity_returns_422(client, laptop, quantity):
    response = await client.post(f"/products/{laptop['id']}/purchase", json={"quantity": quantity})
    assert response.status_code == 422


async def test_purchase_unknown_product_returns_404(client):
    response = await client.post("/products/999/purchase", json={"quantity": 1})
    assert response.status_code == 404
    assert response.json()["code"] == "product_not_found"


async def test_purchase_is_rolled_back_when_commit_fails(client, laptop, monkeypatch):
    """Транзакція: якщо commit не вдався, залишок не змінюється (rollback з Lab 7)."""
    def broken_commit(self):
        raise RuntimeError("database failure")

    monkeypatch.setattr(Session, "commit", broken_commit)
    response = await client.post(f"/products/{laptop['id']}/purchase", json={"quantity": 1})
    assert response.status_code == 500
    monkeypatch.undo()
    assert (await client.get(f"/products/{laptop['id']}")).json()["quantity"] == 3


# ------------------------------------- сумісність із сервісним шаром Lab 7
def test_lab7_service_errors_are_still_value_errors(db_session):
    category = CategoryRepository(db_session).add("Електроніка")
    product = ProductRepository(db_session).add(
        Product(name="Миша", price=10, quantity=1, category_id=category.id)
    )
    service = StoreService(db_session)
    with pytest.raises(ValueError):
        service.purchase_product(product.id, 5)
    with pytest.raises(InsufficientStockError):
        service.purchase_product(product.id, 5)
    with pytest.raises(ProductNotFoundError):
        service.purchase_product(999, 1)
    with pytest.raises(ValueError, match="більшою за нуль"):
        service.purchase_product(product.id, 0)


# ----------------------------------------------- dependencies and demo main()
async def test_get_session_dependency_yields_and_closes_session():
    from online_store.dependencies import get_session

    generator = get_session()
    session = await generator.__anext__()
    assert isinstance(session, Session)
    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()


def test_get_settings_dependency_reads_environment(monkeypatch):
    from online_store.dependencies import get_settings

    monkeypatch.setenv("STORE_RETRY_ATTEMPTS", "7")
    assert get_settings().retry_attempts == 7


def test_lab7_demo_main_runs_on_temporary_database(monkeypatch, tmp_path, capsys):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from online_store import main as demo

    db_file = tmp_path / "store.db"
    engine = create_engine(f"sqlite:///{db_file}")
    monkeypatch.setattr(demo, "engine", engine)
    monkeypatch.setattr(demo, "DATABASE_FILE", str(db_file))
    monkeypatch.setattr(demo, "SessionLocal", sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
    demo.main()
    output = capsys.readouterr().out
    assert "Загальна вартість залишків" in output
    assert "Залишок після покупки: 6 шт." in output
