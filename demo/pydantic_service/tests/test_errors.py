import pytest
from pydantic import ValidationError

from app.errors import api_errors
from app.service import parse_order


def _errors(payload):
    with pytest.raises(ValidationError) as info:
        parse_order(payload)
    return api_errors(info.value)


GOOD_ADDR = {"street": "s", "city": "c", "zip_code": "12345"}


def test_missing_field_code():
    assert "id:required" in _errors({"items": [{"sku": "abc", "unit_price_cents": 1}], "shipping": GOOD_ADDR})


def test_not_integer_code():
    payload = {"id": "x", "items": [{"sku": "abc", "quantity": "many", "unit_price_cents": 1}], "shipping": GOOD_ADDR}
    assert "items.0.quantity:not_integer" in _errors(payload)


def test_too_short_code():
    payload = {"id": "x", "items": [{"sku": "ab", "unit_price_cents": 1}], "shipping": GOOD_ADDR}
    assert "items.0.sku:too_short" in _errors(payload)


def test_bad_zip_code():
    payload = {"id": "x", "items": [{"sku": "abc", "unit_price_cents": 1}], "shipping": {**GOOD_ADDR, "zip_code": "xx"}}
    assert "shipping.zip_code:bad_format" in _errors(payload)
