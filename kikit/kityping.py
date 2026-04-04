from __future__ import annotations
from abc import abstractmethod
from typing import Tuple, TypeVar, Protocol


Box = Tuple[float, float, float, float]

class Comparable(Protocol):
    """Protocol for annotating comparable types."""

    @abstractmethod
    def __lt__(self, other: Any) -> bool:
        pass

T = TypeVar("T")
ComparableT = TypeVar("ComparableT", bound=Comparable)
U = TypeVar("U")
ComparableU = TypeVar("ComparableU", bound=Comparable)
