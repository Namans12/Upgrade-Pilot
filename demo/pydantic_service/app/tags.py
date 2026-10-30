"""Tag list wrapper (pydantic v1 custom root type)."""
from typing import List

from pydantic import BaseModel


class TagList(BaseModel):
    __root__: List[str]

    def joined(self) -> str:
        return ",".join(self.__root__)
