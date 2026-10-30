"""Tag list wrapper (pydantic v2 root model)."""
from typing import List

from pydantic import RootModel


class TagList(RootModel[List[str]]):
    def joined(self) -> str:
        return ",".join(self.root)
