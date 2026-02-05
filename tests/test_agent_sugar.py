"""Tests for the high-level Agent API syntactic sugar."""

from __future__ import annotations

from typing import Any

import pytest

from codex_agent_sdk import (
    Agent,
    CommandApproval,
    Event,
    FileChangeApproval,
    MessageDelta,
    Response,
    Thread,
    ThreadStarted,
    ToolInput,
    Turn,
    TurnCompleted,
    TurnStarted,
    run,
)
from codex_agent_sdk.models import (
    ExecCompleted,
    ExecStarted,
    ItemCompleted,
    ItemStarted,
    McpStartupComplete,
    MessageCompleted,
    TaskCompleted,
    TaskStarted,
)


class TestModels:
    """Test dataclass models."""

    def test_thread_from_dict(self) -> None:
        data = {
            "thread": {
                "id": "thread-123",
                "model": "gpt-5.2-codex",
                "cwd": "/tmp",
            }
        }
        thread = Thread.from_dict(data)
        assert thread.id == "thread-123"
        assert thread.model == "gpt-5.2-codex"
        assert thread.cwd == "/tmp"
        assert thread.raw == data

    def test_thread_from_flat_dict(self) -> None:
        data = {"id": "thread-456", "model": "gpt-4"}
        thread = Thread.from_dict(data)
        assert thread.id == "thread-456"
        assert thread.model == "gpt-4"

    def test_turn_from_dict(self) -> None:
        data = {
            "turn": {
                "id": "turn-789",
                "threadId": "thread-123",
                "status": "completed",
            }
        }
        turn = Turn.from_dict(data)
        assert turn.id == "turn-789"
        assert turn.thread_id == "thread-123"
        assert turn.status == "completed"

    def test_response_str(self) -> None:
        response = Response(text="Hello, world!")
        assert str(response) == "Hello, world!"

    def test_command_approval_from_params(self) -> None:
        params = {"command": "ls -la", "cwd": "/home/user"}
        approval = CommandApproval.from_params(params)
        assert approval.command == "ls -la"
        assert approval.cwd == "/home/user"

    def test_file_change_approval_from_params(self) -> None:
        params = {"path": "/tmp/test.txt", "content": "hello"}
        approval = FileChangeApproval.from_params(params)
        assert approval.path == "/tmp/test.txt"
        assert approval.content == "hello"

    def test_tool_input_from_params(self) -> None:
        params = {"questions": [{"id": "q1", "text": "What?"}]}
        tool_input = ToolInput.from_params(params)
        assert len(tool_input.questions) == 1
        assert tool_input.questions[0]["id"] == "q1"


class TestEventParsing:
    """Test Event.from_notification factory."""

    def test_generic_event(self) -> None:
        notification = {"method": "unknown/method", "params": {"foo": "bar"}}
        event = Event.from_notification(notification)
        assert isinstance(event, Event)
        assert event.method == "unknown/method"

    def test_thread_started(self) -> None:
        notification = {
            "method": "thread/started",
            "params": {"thread": {"id": "t1", "model": "gpt-5"}},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, ThreadStarted)
        assert event.thread is not None
        assert event.thread.id == "t1"

    def test_turn_started(self) -> None:
        notification = {
            "method": "turn/started",
            "params": {"turn": {"id": "turn1", "threadId": "t1"}},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, TurnStarted)
        assert event.turn_id == "turn1"
        assert event.thread_id == "t1"

    def test_turn_completed(self) -> None:
        notification = {
            "method": "turn/completed",
            "params": {"turn": {"id": "turn1", "threadId": "t1", "status": "completed"}},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, TurnCompleted)
        assert event.turn_id == "turn1"
        assert event.status == "completed"

    def test_message_delta(self) -> None:
        notification = {
            "method": "item/agentMessage/delta",
            "params": {
                "delta": "Hello",
                "threadId": "t1",
                "turnId": "turn1",
                "itemId": "item1",
            },
        }
        event = Event.from_notification(notification)
        assert isinstance(event, MessageDelta)
        assert event.delta == "Hello"
        assert event.thread_id == "t1"
        assert event.turn_id == "turn1"

    def test_message_completed(self) -> None:
        notification = {
            "method": "item/agentMessage/completed",
            "params": {"threadId": "t1", "content": "Full message"},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, MessageCompleted)
        assert event.content == "Full message"

    def test_task_started(self) -> None:
        notification = {"method": "codex/event/task_started", "params": {"taskId": "task1"}}
        event = Event.from_notification(notification)
        assert isinstance(event, TaskStarted)
        assert event.task_id == "task1"

    def test_task_completed(self) -> None:
        notification = {"method": "codex/event/task_completed", "params": {"taskId": "task1"}}
        event = Event.from_notification(notification)
        assert isinstance(event, TaskCompleted)
        assert event.task_id == "task1"

    def test_item_started(self) -> None:
        notification = {
            "method": "codex/event/item_started",
            "params": {"itemId": "item1", "type": "message"},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, ItemStarted)
        assert event.item_id == "item1"
        assert event.item_type == "message"

    def test_item_completed(self) -> None:
        notification = {
            "method": "codex/event/item_completed",
            "params": {"itemId": "item1", "type": "message"},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, ItemCompleted)
        assert event.item_id == "item1"

    def test_exec_started(self) -> None:
        notification = {"method": "codex/event/exec_started", "params": {"command": "ls -la"}}
        event = Event.from_notification(notification)
        assert isinstance(event, ExecStarted)
        assert event.command == "ls -la"

    def test_exec_completed(self) -> None:
        notification = {
            "method": "codex/event/exec_completed",
            "params": {"command": "ls -la", "exitCode": 0},
        }
        event = Event.from_notification(notification)
        assert isinstance(event, ExecCompleted)
        assert event.command == "ls -la"
        assert event.exit_code == 0

    def test_mcp_startup_complete(self) -> None:
        notification = {"method": "codex/event/mcp_startup_complete", "params": {}}
        event = Event.from_notification(notification)
        assert isinstance(event, McpStartupComplete)


class TestAgentBuilder:
    """Test Agent builder pattern."""

    def test_default_config(self) -> None:
        agent = Agent()
        assert agent._config.model == "gpt-5.2-codex"
        assert agent._config.cwd is None

    def test_constructor_config(self) -> None:
        agent = Agent(model="gpt-4", cwd="/tmp", effort="high")
        assert agent._config.model == "gpt-4"
        assert agent._config.cwd == "/tmp"
        assert agent._config.effort == "high"

    def test_builder_chaining(self) -> None:
        agent = (
            Agent()
            .model("gpt-4")
            .cwd("/tmp")
            .effort("high")
            .approval_policy("on-request")
            .env(FOO="bar")
            .args("--verbose")
        )
        assert agent._config.model == "gpt-4"
        assert agent._config.cwd == "/tmp"
        assert agent._config.effort == "high"
        assert agent._config.approval_policy == "on-request"
        assert agent._config.env == {"FOO": "bar"}
        assert agent._config.args == ["--verbose"]

    def test_auto_approve(self) -> None:
        agent = Agent(auto_approve=True)
        assert agent._command_handler is not None
        assert agent._file_change_handler is not None

    def test_auto_approve_commands_method(self) -> None:
        agent = Agent().auto_approve_commands()
        assert agent._command_handler is not None
        assert agent._file_change_handler is None

    def test_auto_approve_file_changes_method(self) -> None:
        agent = Agent().auto_approve_file_changes()
        assert agent._command_handler is None
        assert agent._file_change_handler is not None


class TestAgentDecorators:
    """Test Agent decorator-based handler registration."""

    def test_on_command_approval_decorator(self) -> None:
        agent = Agent()

        @agent.on_command_approval
        async def handler(cmd: CommandApproval) -> str:
            return "accept"

        assert agent._command_handler is handler

    def test_on_command_approval_method(self) -> None:
        agent = Agent()

        async def handler(cmd: CommandApproval) -> str:
            return "accept"

        agent.on_command_approval(handler)
        assert agent._command_handler is handler

    def test_on_file_change_decorator(self) -> None:
        agent = Agent()

        @agent.on_file_change
        async def handler(change: FileChangeApproval) -> str:
            return "accept"

        assert agent._file_change_handler is handler

    def test_on_tool_input_decorator(self) -> None:
        agent = Agent()

        @agent.on_tool_input
        async def handler(tool_input: ToolInput) -> dict[str, Any]:
            return {"answers": {}}

        assert agent._tool_input_handler is handler

    def test_on_event_decorator(self) -> None:
        agent = Agent()

        @agent.on_event
        async def handler(event: Event) -> None:
            pass

        assert len(agent._event_handlers) == 1
        assert agent._event_handlers[0] is handler

    def test_multiple_event_handlers(self) -> None:
        agent = Agent()

        @agent.on_event
        async def handler1(event: Event) -> None:
            pass

        @agent.on_event
        async def handler2(event: Event) -> None:
            pass

        assert len(agent._event_handlers) == 2


class TestRunFunction:
    """Test module-level run() function."""

    def test_run_returns_streaming_response(self) -> None:
        response = run("Hello")
        # Just check it returns a StreamingResponse without actually running
        assert response._prompt == "Hello"
        assert response._agent._config.model == "gpt-5.2-codex"

    def test_run_with_options(self) -> None:
        response = run("Hello", model="gpt-4", cwd="/tmp", auto_approve=True)
        assert response._agent._config.model == "gpt-4"
        assert response._agent._config.cwd == "/tmp"
        assert response._agent._command_handler is not None
