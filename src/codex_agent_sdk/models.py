"""Typed models for Codex Agent SDK responses and events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Response Models
# =============================================================================


@dataclass
class Thread:
    """Represents a conversation thread."""

    id: str
    model: str | None = None
    cwd: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Thread:
        """Create Thread from API response dict."""
        thread_data = data.get("thread", data)
        return cls(
            id=thread_data.get("id", ""),
            model=thread_data.get("model"),
            cwd=thread_data.get("cwd"),
            raw=data,
        )


@dataclass
class Turn:
    """Represents a conversation turn."""

    id: str
    thread_id: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Turn:
        """Create Turn from API response dict."""
        turn_data = data.get("turn", data)
        return cls(
            id=turn_data.get("id", ""),
            thread_id=turn_data.get("threadId"),
            status=turn_data.get("status"),
            raw=data,
        )


@dataclass
class Response:
    """Accumulated response from a turn, with collected text."""

    text: str
    turn: Turn | None = None
    thread: Thread | None = None
    events: list[Event] = field(default_factory=list)

    def __str__(self) -> str:
        return self.text


# =============================================================================
# Event Models (Notifications)
# =============================================================================


@dataclass
class Event:
    """Base class for all events/notifications."""

    method: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_notification(cls, notification: dict[str, Any]) -> Event:
        """Factory to create the appropriate Event subclass."""
        method = notification.get("method", "")
        params = notification.get("params", {})

        # Map methods to event classes
        event_map: dict[str, type[Event]] = {
            "thread/started": ThreadStarted,
            "turn/started": TurnStarted,
            "turn/completed": TurnCompleted,
            "item/agentMessage/delta": MessageDelta,
            "item/agentMessage/completed": MessageCompleted,
            "codex/event/task_started": TaskStarted,
            "codex/event/task_completed": TaskCompleted,
            "codex/event/item_started": ItemStarted,
            "codex/event/item_completed": ItemCompleted,
            "codex/event/exec_started": ExecStarted,
            "codex/event/exec_completed": ExecCompleted,
            "codex/event/mcp_startup_complete": McpStartupComplete,
        }

        event_class = event_map.get(method, Event)
        if event_class is Event:
            return Event(method=method, raw=notification)

        return event_class.from_params(method, params, notification)

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> Event:
        """Override in subclasses to parse params."""
        return cls(method=method, raw=raw)


@dataclass
class ThreadStarted(Event):
    """Emitted when a thread is started."""

    thread: Thread | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> ThreadStarted:
        thread_data = params.get("thread")
        thread = Thread.from_dict({"thread": thread_data}) if thread_data else None
        return cls(method=method, raw=raw, thread=thread)


@dataclass
class TurnStarted(Event):
    """Emitted when a turn starts."""

    turn_id: str | None = None
    thread_id: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> TurnStarted:
        turn = params.get("turn", {})
        return cls(
            method=method,
            raw=raw,
            turn_id=turn.get("id"),
            thread_id=turn.get("threadId"),
        )


@dataclass
class TurnCompleted(Event):
    """Emitted when a turn completes."""

    turn_id: str | None = None
    thread_id: str | None = None
    status: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> TurnCompleted:
        turn = params.get("turn", {})
        return cls(
            method=method,
            raw=raw,
            turn_id=turn.get("id"),
            thread_id=turn.get("threadId"),
            status=turn.get("status"),
        )


@dataclass
class MessageDelta(Event):
    """Emitted for streaming text deltas."""

    delta: str = ""
    thread_id: str | None = None
    turn_id: str | None = None
    item_id: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> MessageDelta:
        return cls(
            method=method,
            raw=raw,
            delta=params.get("delta", ""),
            thread_id=params.get("threadId"),
            turn_id=params.get("turnId"),
            item_id=params.get("itemId"),
        )


@dataclass
class MessageCompleted(Event):
    """Emitted when a message is completed."""

    thread_id: str | None = None
    turn_id: str | None = None
    item_id: str | None = None
    content: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> MessageCompleted:
        return cls(
            method=method,
            raw=raw,
            thread_id=params.get("threadId"),
            turn_id=params.get("turnId"),
            item_id=params.get("itemId"),
            content=params.get("content"),
        )


@dataclass
class TaskStarted(Event):
    """Emitted when a task starts."""

    task_id: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> TaskStarted:
        return cls(method=method, raw=raw, task_id=params.get("taskId"))


@dataclass
class TaskCompleted(Event):
    """Emitted when a task completes."""

    task_id: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> TaskCompleted:
        return cls(method=method, raw=raw, task_id=params.get("taskId"))


@dataclass
class ItemStarted(Event):
    """Emitted when an item starts processing."""

    item_id: str | None = None
    item_type: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> ItemStarted:
        return cls(
            method=method,
            raw=raw,
            item_id=params.get("itemId"),
            item_type=params.get("type"),
        )


@dataclass
class ItemCompleted(Event):
    """Emitted when an item completes processing."""

    item_id: str | None = None
    item_type: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> ItemCompleted:
        return cls(
            method=method,
            raw=raw,
            item_id=params.get("itemId"),
            item_type=params.get("type"),
        )


@dataclass
class ExecStarted(Event):
    """Emitted when command execution starts."""

    command: str | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> ExecStarted:
        return cls(method=method, raw=raw, command=params.get("command"))


@dataclass
class ExecCompleted(Event):
    """Emitted when command execution completes."""

    command: str | None = None
    exit_code: int | None = None

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> ExecCompleted:
        return cls(
            method=method,
            raw=raw,
            command=params.get("command"),
            exit_code=params.get("exitCode"),
        )


@dataclass
class McpStartupComplete(Event):
    """Emitted when MCP startup is complete."""

    @classmethod
    def from_params(
        cls, method: str, params: dict[str, Any], raw: dict[str, Any]
    ) -> McpStartupComplete:
        return cls(method=method, raw=raw)


# =============================================================================
# Approval Request Models
# =============================================================================


@dataclass
class CommandApproval:
    """Request to approve a command execution."""

    command: str
    cwd: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> CommandApproval:
        return cls(
            command=params.get("command", ""),
            cwd=params.get("cwd"),
            raw=params,
        )


@dataclass
class FileChangeApproval:
    """Request to approve a file change."""

    path: str
    content: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> FileChangeApproval:
        return cls(
            path=params.get("path", ""),
            content=params.get("content"),
            raw=params,
        )


@dataclass
class ToolInput:
    """Request for user input from a tool."""

    questions: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> ToolInput:
        return cls(
            questions=params.get("questions", []),
            raw=params,
        )
