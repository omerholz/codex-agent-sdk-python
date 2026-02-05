"""High-level Agent API with Pythonic syntactic sugar."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, overload

from .client import CodexClient
from .models import (
    CommandApproval,
    Event,
    FileChangeApproval,
    MessageDelta,
    Response,
    Thread,
    ToolInput,
    Turn,
    TurnCompleted,
)
from .types import CodexClientOptions

# Type aliases for handlers
CommandHandler = Callable[[CommandApproval], Awaitable[str | dict[str, Any]]]
FileChangeHandler = Callable[[FileChangeApproval], Awaitable[str | dict[str, Any]]]
ToolInputHandler = Callable[[ToolInput], Awaitable[dict[str, Any]]]
EventHandler = Callable[[Event], Awaitable[None]]


@dataclass
class AgentConfig:
    """Configuration for an Agent."""

    model: str = "gpt-5.2-codex"
    cwd: str | Path | None = None
    codex_path: str = "codex"
    client_name: str = "codex_agent_sdk"
    client_version: str = "0.1.0"
    approval_policy: str | None = None
    effort: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    args: list[str] = field(default_factory=list)


class Conversation:
    """A conversation thread with context manager support."""

    def __init__(
        self,
        agent: Agent,
        thread: Thread,
        client: CodexClient,
    ) -> None:
        self._agent = agent
        self._thread = thread
        self._client = client
        self._events: list[Event] = []

    @property
    def id(self) -> str:
        """Thread ID."""
        return self._thread.id

    @property
    def thread(self) -> Thread:
        """The underlying thread object."""
        return self._thread

    async def send(self, prompt: str, **kwargs: Any) -> Response:
        """Send a message and get the full response."""
        text_parts: list[str] = []
        events: list[Event] = []
        turn: Turn | None = None

        async for event in self.stream(prompt, **kwargs):
            events.append(event)
            if isinstance(event, MessageDelta):
                text_parts.append(event.delta)
            elif isinstance(event, TurnCompleted):
                turn = Turn(
                    id=event.turn_id or "",
                    thread_id=event.thread_id,
                    status=event.status,
                )

        return Response(
            text="".join(text_parts),
            turn=turn,
            thread=self._thread,
            events=events,
        )

    async def stream(self, prompt: str, **kwargs: Any) -> AsyncIterator[Event]:
        """Send a message and stream events."""
        params = {"threadId": self._thread.id, "input": [{"type": "text", "text": prompt}]}

        # Add agent-level defaults
        if self._agent._config.approval_policy:
            params.setdefault("approvalPolicy", self._agent._config.approval_policy)
        if self._agent._config.effort:
            params.setdefault("effort", self._agent._config.effort)
        if self._agent._config.cwd:
            params.setdefault("cwd", str(self._agent._config.cwd))

        params.update(kwargs)

        response = await self._client.turn_start(params)
        turn_id = response.get("turn", {}).get("id")

        async for note in self._client.notifications():
            event = Event.from_notification(note)
            self._events.append(event)
            yield event

            if isinstance(event, TurnCompleted) and (
                turn_id is None or event.turn_id == turn_id
            ):
                return

    async def stream_text(self, prompt: str, **kwargs: Any) -> AsyncIterator[str]:
        """Send a message and stream only text deltas."""
        async for event in self.stream(prompt, **kwargs):
            if isinstance(event, MessageDelta):
                yield event.delta


class StreamingResponse:
    """A streaming response that can be iterated or awaited."""

    def __init__(
        self,
        agent: Agent,
        prompt: str,
        kwargs: dict[str, Any],
    ) -> None:
        self._agent = agent
        self._prompt = prompt
        self._kwargs = kwargs
        self._events: list[Event] = []
        self._text_parts: list[str] = []
        self._consumed = False

    def __aiter__(self) -> AsyncIterator[str]:
        """Iterate over text chunks."""
        return self._stream_text()

    async def _stream_text(self) -> AsyncIterator[str]:
        """Internal text streaming."""
        async for event in self._stream_events():
            if isinstance(event, MessageDelta):
                yield event.delta

    async def _stream_events(self) -> AsyncIterator[Event]:
        """Internal event streaming."""
        if self._consumed:
            raise RuntimeError("Response already consumed")
        self._consumed = True

        async with self._agent._create_client() as client:
            thread_resp = await client.thread_start({"model": self._agent._config.model})
            thread = Thread.from_dict(thread_resp)

            params: dict[str, Any] = {
                "threadId": thread.id,
                "input": [{"type": "text", "text": self._prompt}],
            }

            if self._agent._config.approval_policy:
                params["approvalPolicy"] = self._agent._config.approval_policy
            if self._agent._config.effort:
                params["effort"] = self._agent._config.effort
            if self._agent._config.cwd:
                params["cwd"] = str(self._agent._config.cwd)

            params.update(self._kwargs)

            response = await client.turn_start(params)
            turn_id = response.get("turn", {}).get("id")

            async for note in client.notifications():
                event = Event.from_notification(note)
                self._events.append(event)
                if isinstance(event, MessageDelta):
                    self._text_parts.append(event.delta)
                yield event

                if isinstance(event, TurnCompleted) and (
                    turn_id is None or event.turn_id == turn_id
                ):
                    return

    async def text(self) -> str:
        """Consume the stream and return full text."""
        async for _ in self._stream_text():
            pass
        return "".join(self._text_parts)

    async def response(self) -> Response:
        """Consume the stream and return full Response object."""
        turn: Turn | None = None
        async for event in self._stream_events():
            if isinstance(event, TurnCompleted):
                turn = Turn(
                    id=event.turn_id or "",
                    thread_id=event.thread_id,
                    status=event.status,
                )
        return Response(
            text="".join(self._text_parts),
            turn=turn,
            events=self._events,
        )

    def events(self) -> AsyncIterator[Event]:
        """Iterate over typed Event objects."""
        return self._stream_events()


class Agent:
    """
    High-level Pythonic interface for Codex agents.

    Examples
    --------
    Simple one-shot:

        agent = Agent(model="gpt-5.1-codex")
        async for chunk in agent.run("Hello!"):
            print(chunk, end="")

    With builder pattern:

        agent = (
            Agent()
            .model("gpt-5.1-codex")
            .cwd("/path/to/project")
            .auto_approve_commands()
        )

    With decorator handlers:

        agent = Agent()

        @agent.on_command_approval
        async def handle_command(cmd: CommandApproval) -> str:
            print(f"Running: {cmd.command}")
            return "accept"

    With conversation context:

        async with agent.conversation() as conv:
            response = await conv.send("Hello!")
            print(response.text)
            response = await conv.send("Tell me more")

    """

    def __init__(
        self,
        model: str = "gpt-5.2-codex",
        *,
        cwd: str | Path | None = None,
        codex_path: str = "codex",
        client_name: str = "codex_agent_sdk",
        client_version: str = "0.1.0",
        approval_policy: str | None = None,
        effort: str | None = None,
        auto_approve: bool = False,
    ) -> None:
        self._config = AgentConfig(
            model=model,
            cwd=cwd,
            codex_path=codex_path,
            client_name=client_name,
            client_version=client_version,
            approval_policy=approval_policy,
            effort=effort,
        )
        self._command_handler: CommandHandler | None = None
        self._file_change_handler: FileChangeHandler | None = None
        self._tool_input_handler: ToolInputHandler | None = None
        self._event_handlers: list[EventHandler] = []

        if auto_approve:
            self.auto_approve_commands()
            self.auto_approve_file_changes()

    # =========================================================================
    # Builder methods (return self for chaining)
    # =========================================================================

    def model(self, model: str) -> Agent:
        """Set the model to use."""
        self._config.model = model
        return self

    def cwd(self, path: str | Path) -> Agent:
        """Set the working directory."""
        self._config.cwd = path
        return self

    def codex_path(self, path: str) -> Agent:
        """Set the path to the codex CLI."""
        self._config.codex_path = path
        return self

    def approval_policy(self, policy: str) -> Agent:
        """Set the approval policy (e.g., 'on-request', 'auto-approve')."""
        self._config.approval_policy = policy
        return self

    def effort(self, level: str) -> Agent:
        """Set the effort level (e.g., 'low', 'medium', 'high')."""
        self._config.effort = level
        return self

    def env(self, **kwargs: str) -> Agent:
        """Set environment variables."""
        self._config.env.update(kwargs)
        return self

    def args(self, *args: str) -> Agent:
        """Add CLI arguments."""
        self._config.args.extend(args)
        return self

    # =========================================================================
    # Handler registration (decorators and methods)
    # =========================================================================

    def auto_approve_commands(self) -> Agent:
        """Automatically approve all command executions."""

        async def _auto_approve(_: CommandApproval) -> str:
            return "accept"

        self._command_handler = _auto_approve
        return self

    def auto_approve_file_changes(self) -> Agent:
        """Automatically approve all file changes."""

        async def _auto_approve(_: FileChangeApproval) -> str:
            return "accept"

        self._file_change_handler = _auto_approve
        return self

    @overload
    def on_command_approval(self, handler: CommandHandler) -> CommandHandler: ...

    @overload
    def on_command_approval(self) -> Callable[[CommandHandler], CommandHandler]: ...

    def on_command_approval(
        self, handler: CommandHandler | None = None
    ) -> CommandHandler | Callable[[CommandHandler], CommandHandler]:
        """
        Register a command approval handler.

        Can be used as a decorator or method:

            @agent.on_command_approval
            async def handle(cmd: CommandApproval) -> str:
                return "accept"

            # or

            agent.on_command_approval(my_handler)
        """

        def decorator(fn: CommandHandler) -> CommandHandler:
            self._command_handler = fn
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    @overload
    def on_file_change(self, handler: FileChangeHandler) -> FileChangeHandler: ...

    @overload
    def on_file_change(self) -> Callable[[FileChangeHandler], FileChangeHandler]: ...

    def on_file_change(
        self, handler: FileChangeHandler | None = None
    ) -> FileChangeHandler | Callable[[FileChangeHandler], FileChangeHandler]:
        """Register a file change approval handler."""

        def decorator(fn: FileChangeHandler) -> FileChangeHandler:
            self._file_change_handler = fn
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    @overload
    def on_tool_input(self, handler: ToolInputHandler) -> ToolInputHandler: ...

    @overload
    def on_tool_input(self) -> Callable[[ToolInputHandler], ToolInputHandler]: ...

    def on_tool_input(
        self, handler: ToolInputHandler | None = None
    ) -> ToolInputHandler | Callable[[ToolInputHandler], ToolInputHandler]:
        """Register a tool input handler."""

        def decorator(fn: ToolInputHandler) -> ToolInputHandler:
            self._tool_input_handler = fn
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    @overload
    def on_event(self, handler: EventHandler) -> EventHandler: ...

    @overload
    def on_event(self) -> Callable[[EventHandler], EventHandler]: ...

    def on_event(
        self, handler: EventHandler | None = None
    ) -> EventHandler | Callable[[EventHandler], EventHandler]:
        """Register an event handler that receives all events."""

        def decorator(fn: EventHandler) -> EventHandler:
            self._event_handlers.append(fn)
            return fn

        if handler is not None:
            return decorator(handler)
        return decorator

    # =========================================================================
    # Execution methods
    # =========================================================================

    def run(self, prompt: str, **kwargs: Any) -> StreamingResponse:
        """
        Run a prompt and return a streaming response.

        Examples
        --------
        Stream text chunks:

            async for chunk in agent.run("Hello"):
                print(chunk, end="")

        Get full text:

            text = await agent.run("Hello").text()

        Get full response with metadata:

            response = await agent.run("Hello").response()
            print(response.text)
            print(response.turn.id)

        Stream typed events:

            async for event in agent.run("Hello").events():
                if isinstance(event, MessageDelta):
                    print(event.delta)

        """
        return StreamingResponse(self, prompt, kwargs)

    @asynccontextmanager
    async def conversation(self, **thread_kwargs: Any) -> AsyncIterator[Conversation]:
        """
        Start a conversation with context manager support.

        Examples
        --------
            async with agent.conversation() as conv:
                response = await conv.send("Hello!")
                print(response.text)

                # Continue the conversation
                response = await conv.send("Tell me more")
                print(response.text)

        """
        async with self._create_client() as client:
            params = {"model": self._config.model}
            if self._config.cwd:
                params["cwd"] = str(self._config.cwd)
            params.update(thread_kwargs)

            thread_resp = await client.thread_start(params)
            thread = Thread.from_dict(thread_resp)

            yield Conversation(self, thread, client)

    # Alias for conversation
    thread = conversation

    # =========================================================================
    # Internal methods
    # =========================================================================

    @asynccontextmanager
    async def _create_client(self) -> AsyncIterator[CodexClient]:
        """Create a configured CodexClient."""
        options = CodexClientOptions(
            codex_path=self._config.codex_path,
            cwd=str(self._config.cwd) if self._config.cwd else None,
            env=self._config.env,
            args=self._config.args,
            client_name=self._config.client_name,
            client_version=self._config.client_version,
        )

        # Wrap handlers to convert typed objects
        async def command_handler(params: dict[str, Any]) -> str | dict[str, Any]:
            if self._command_handler is None:
                return "reject"
            approval = CommandApproval.from_params(params)
            return await self._command_handler(approval)

        async def file_change_handler(params: dict[str, Any]) -> str | dict[str, Any]:
            if self._file_change_handler is None:
                return "reject"
            approval = FileChangeApproval.from_params(params)
            return await self._file_change_handler(approval)

        async def tool_input_handler(params: dict[str, Any]) -> dict[str, Any]:
            if self._tool_input_handler is None:
                return {"answers": {}}
            tool_input = ToolInput.from_params(params)
            return await self._tool_input_handler(tool_input)

        async with CodexClient(
            options=options,
            command_approval_handler=command_handler if self._command_handler else None,
            file_change_approval_handler=file_change_handler if self._file_change_handler else None,
            tool_input_handler=tool_input_handler if self._tool_input_handler else None,
        ) as client:
            yield client


# =============================================================================
# Module-level convenience function
# =============================================================================


def run(
    prompt: str,
    *,
    model: str = "gpt-5.2-codex",
    cwd: str | Path | None = None,
    auto_approve: bool = False,
    **kwargs: Any,
) -> StreamingResponse:
    """
    One-liner to run a prompt.

    Examples
    --------
        from codex_agent_sdk import run

        # Stream text
        async for chunk in run("Hello", model="gpt-5.1-codex"):
            print(chunk, end="")

        # Get full text
        text = await run("Hello").text()

    """
    agent = Agent(model=model, cwd=cwd, auto_approve=auto_approve)
    return agent.run(prompt, **kwargs)
