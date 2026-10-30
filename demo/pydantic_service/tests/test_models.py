import pytest
from pydantic import ValidationError

from app.models import Address, LineItem, Order

ADDR = {"street": "1 Main St", "city": "Springfield", "zip_code": "12345"}
ITEM = {"sku": "abc", "quantity": 2, "unit_price_cents": 500}


def make_order(**over):
    base = {"id": "o-1", "items": [ITEM], "shipping": ADDR}
    base.update(over)
    return Order(**base)


def test_address_country_is_optional():
    assert Address(**ADDR).country is None


def test_address_rejects_bad_zip():
    with pytest.raises(ValidationError):
        Address(**{**ADDR, "zip_code": "ABCDE"})


def test_sku_is_uppercased():
    assert LineItem(**ITEM).sku == "ABC"


def test_quantity_defaults_to_one():
    assert LineItem(sku="xyz", unit_price_cents=10).quantity == 1


def test_order_requires_at_least_one_item():
    with pytest.raises(ValidationError):
        make_order(items=[])


def test_order_note_is_optional():
    assert make_order().note is None


def test_numeric_id_is_coerced_to_string():
    assert make_order(id=1001).id == "1001"


def test_strings_are_stripped():
    assert make_order(note="  hello  ").note == "hello"


def test_total_is_computed():
    assert make_order().total_cents == 1000


def test_order_is_immutable():
    order = make_order()
    with pytest.raises((TypeError, ValueError)):
        order.id = "changed"
