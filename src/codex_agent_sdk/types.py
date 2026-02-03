"""Type definitions for Codex Agent SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict


class ClientInfo(TypedDict):
    name: str
    title: str | None
    version: str


class InitializeCapabilities(TypedDict, total=False):
    experimentalApi: bool


class InitializeParams(TypedDict, total=False):
    clientInfo: ClientInfo
    capabilities: InitializeCapabilities


class JSONRPCErrorPayload(TypedDict, total=False):
    code: int
    message: str
    data: Any


class JSONRPCRequest(TypedDict):
    id: int | str
    method: str
    params: dict[str, Any] | None


class JSONRPCNotification(TypedDict):
    method: str
    params: dict[str, Any] | None


class JSONRPCResponse(TypedDict):
    id: int | str
    result: Any


class JSONRPCError(TypedDict):
    id: int | str
    error: JSONRPCErrorPayload


@dataclass
class CodexClientOptions:
    """Options for CodexClient."""

    codex_path: str = "codex"
    cwd: str | Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)
    max_buffer_size: int | None = None

    # Initialize params
    client_name: str = "codex_sdk_py"
    client_title: str | None = "Codex SDK (Python)"
    client_version: str = "0.1.0"
    experimental_api: bool = False
