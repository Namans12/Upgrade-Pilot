"""Order domain models (pydantic v2)."""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class Address(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    street: str
    city: str
    zip_code: str = Field(..., pattern=r"^\d{5}$")
    country: Optional[str] = None


class LineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str = Field(..., min_length=3)
    quantity: int = Field(1, ge=1)
    unit_price_cents: int = Field(..., ge=0)

    @field_validator("sku")
    @classmethod
    def sku_upper(cls, v):
        return v.upper()


class Order(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        from_attributes=True,
        coerce_numbers_to_str=True,
    )

    id: str
    items: List[LineItem] = Field(..., min_length=1)
    shipping: Address
    note: Optional[str] = None

    @computed_field
    @property
    def total_cents(self) -> int:
        return sum(i.quantity * i.unit_price_cents for i in self.items)
