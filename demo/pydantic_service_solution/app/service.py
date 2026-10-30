"""Order service: parsing and serialisation helpers."""
import json
from typing import Any, Dict

from .models import Order


def parse_order(payload: Dict[str, Any]) -> Order:
    return Order.model_validate(payload)


def order_to_json(order: Order) -> str:
    """Stable JSON for storage/diffing: sorted keys."""
    return json.dumps(order.model_dump(mode="json"), sort_keys=True)


def order_summary(order: Order) -> dict:
    data = order.model_dump(exclude={"note"})
    data["item_count"] = len(order.items)
    return data


def with_note(order: Order, note: str) -> Order:
    return order.model_copy(update={"note": note})


def order_from_row(row: object) -> Order:
    """Build an Order from an attribute-style row object (e.g. an ORM record)."""
    return Order.model_validate(row)


def load_json(text: str) -> Order:
    return Order.model_validate_json(text)
