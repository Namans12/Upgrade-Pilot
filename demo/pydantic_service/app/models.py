"""Order domain models (written against pydantic v1)."""
from typing import List, Optional

from pydantic import BaseModel, Field, root_validator, validator


class Address(BaseModel):
    street: str
    city: str
    zip_code: str = Field(..., regex=r"^\d{5}$")
    country: Optional[str]

    class Config:
        orm_mode = True


class LineItem(BaseModel):
    sku: str = Field(..., min_length=3)
    quantity: int = Field(1, ge=1)
    unit_price_cents: int = Field(..., ge=0)

    @validator("sku")
    def sku_upper(cls, v):
        return v.upper()

    class Config:
        orm_mode = True


class Order(BaseModel):
    id: str
    items: List[LineItem] = Field(..., min_items=1)
    shipping: Address
    note: Optional[str]
    total_cents: int = 0

    @root_validator
    def compute_total(cls, values):
        items = values.get("items") or []
        values["total_cents"] = sum(i.quantity * i.unit_price_cents for i in items)
        return values

    class Config:
        allow_mutation = False
        anystr_strip_whitespace = True
        orm_mode = True
