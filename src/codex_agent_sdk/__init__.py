"""Codex Agent SDK for Python."""

from __future__ import annotations

import logging

from .agent import Agent, Conversation, StreamingResponse, run
from .client import CodexClient
from .errors import (
    CodexConnectionError,
    CodexJSONDecodeError,
    CodexProcessError,
    CodexRPCError,
    CodexSchemaGenerationError,
    CodexSchemaValidationError,
    CodexSDKError,
)
from .models import (
    CommandApproval,
    Event,
    ExecCompleted,
    ExecStarted,
    FileChangeApproval,
    ItemCompleted,
    ItemStarted,
    McpStartupComplete,
    MessageCompleted,
    MessageDelta,
    Response,
    TaskCompleted,
    TaskStarted,
    Thread,
    ThreadStarted,
    ToolInput,
    Turn,
    TurnCompleted,
    TurnStarted,
)
from .query import query
from .schema import CodexSchemaValidator, load_schema_validator_from_codex_cli
from .types import CodexClientOptions

logging.getLogger("codex_agent_sdk").addHandler(logging.NullHandler())

__all__ = [
    # High-level API
    "Agent",
    "Conversation",
    "StreamingResponse",
    "run",
    # Models
    "Thread",
    "Turn",
    "Response",
    "Event",
    "ThreadStarted",
    "TurnStarted",
    "TurnCompleted",
    "MessageDelta",
    "MessageCompleted",
    "TaskStarted",
    "TaskCompleted",
    "ItemStarted",
    "ItemCompleted",
    "ExecStarted",
    "ExecCompleted",
    "McpStartupComplete",
    "CommandApproval",
    "FileChangeApproval",
    "ToolInput",
    # Low-level API
    "CodexClient",
    "CodexClientOptions",
    "query",
    # Errors
    "CodexSDKError",
    "CodexConnectionError",
    "CodexProcessError",
    "CodexJSONDecodeError",
    "CodexRPCError",
    "CodexSchemaGenerationError",
    "CodexSchemaValidationError",
    # Schema
    "CodexSchemaValidator",
    "load_schema_validator_from_codex_cli",
]
