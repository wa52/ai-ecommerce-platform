from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CommerceHealth:
    ok: bool
    detail: str


class CommerceAdapter(ABC):
    """Boundary between AI Extension Layer and the Commerce Core."""

    @abstractmethod
    async def health(self) -> CommerceHealth: ...

    @abstractmethod
    async def graphql(self, query: str, variables: dict | None = None) -> dict: ...
