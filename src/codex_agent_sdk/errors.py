"""Error types for Codex Agent SDK."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CodexSDKError(Exception):
    """Base exception for Codex SDK errors."""


class CodexConnectionError(CodexSDKError):
    """Raised when unable to connect to Codex app-server."""


class CodexProcessError(CodexSDKError):
    """Raised when the Codex CLI process fails."""

    def __init__(self, message: str, exit_code: int | None = None):
        self.exit_code = exit_code
        super().__init__(message)


class CodexJSONDecodeError(CodexSDKError):
    """Raised when unable to decode JSON from Codex output."""

    def __init__(self, line: str, original_error: Exception):
        self.line = line
        self.original_error = original_error
        super().__init__(f"Failed to decode JSON: {line[:100]}...")


class CodexSchemaValidationError(CodexSDKError):
    """Raised when JSON schema validation fails."""


@dataclass
class CodexRPCError(CodexSDKError):
    """JSON-RPC error returned by the app-server."""

    code: int
    message: str
    data: Any | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        base = f"JSON-RPC error {self.code}: {self.message}"
        if self.data is not None:
            return f"{base} (data={self.data})"
        return base
