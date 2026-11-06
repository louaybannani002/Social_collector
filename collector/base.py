"""Common interface for platform collectors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Sequence

from .models import Post


class BaseCollector(ABC):
    platform: str

    @abstractmethod
    def collect(self, keywords: Sequence[str], limit: int) -> Iterator[Post]:
        """Yield at most `limit` posts (with images and comments) about the topic."""
