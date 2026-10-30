import json
from types import SimpleNamespace

from app.service import (
    load_json,
    order_from_row,
    order_summary,
    order_to_json,
    parse_order,
    with_note,
)
from app.tags import TagList

PAYLOAD = {
    "id": "o-9",
    "items": [{"sku": "abc", "quantity": 3, "unit_price_cents": 200}],
    "shipping": {"street": "2 Oak Ave", "city": "Shelbyville", "zip_code": "54321"},
}


def test_parse_order():
    order = parse_order(PAYLOAD)
    assert order.id == "o-9" and order.total_cents == 600


def test_summary_excludes_note_and_counts_items():
    summary = order_summary(parse_order({**PAYLOAD, "note": "gift"}))
    assert "note" not in summary and summary["item_count"] == 1


def test_json_keys_are_sorted():
    text = order_to_json(parse_order(PAYLOAD))
    keys = list(json.loads(text).keys())
    assert keys == sorted(keys)


def test_with_note_returns_updated_copy():
    order = parse_order(PAYLOAD)
    assert with_note(order, "rush").note == "rush" and order.note is None


def test_from_row_reads_attributes():
    row = SimpleNamespace(
        id="o-3",
        items=[SimpleNamespace(sku="abc", quantity=1, unit_price_cents=50)],
        shipping=SimpleNamespace(street="3 Elm", city="Ogdenville", zip_code="11111", country=None),
        note=None,
        total_cents=0,
    )
    assert order_from_row(row).total_cents == 50


def test_json_round_trip():
    order = parse_order(PAYLOAD)
    assert load_json(order_to_json(order)) == order


def test_tag_list_joined():
    assert TagList.parse_obj(["a", "b"]).joined() == "a,b"
