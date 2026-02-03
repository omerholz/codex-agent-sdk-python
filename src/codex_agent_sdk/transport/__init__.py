"""Transport interface for Codex SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class Transport(ABC):
    """Abstract transport for Codex communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect the transport and prepare for communication."""

    @abstractmethod
    async def write(self, data: str) -> None:
        """Write raw data to the transport."""

    @abstractmethod
    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Read JSON messages from the transport."""

    @abstractmethod
    async def close(self) -> None:
        """Close the transport and clean up resources."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True if the transport is ready to send/receive messages."""

    @abstractmethod
    async def end_input(self) -> None:
        """End the input stream (close stdin for process transports)."""


__all__ = ["Transport"]
