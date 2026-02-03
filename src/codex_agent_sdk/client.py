"""Codex app-server client."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

import anyio

from .errors import CodexConnectionError, CodexRPCError
from .schema import CodexSchemaValidator
from .transport import Transport
from .transport.subprocess import SubprocessOptions, SubprocessTransport
from .types import CodexClientOptions

RequestHandler = Callable[[str, dict[str, Any] | None], Awaitable[Any]]
NotificationHandler = Callable[[str, dict[str, Any] | None], Awaitable[None]]
ApprovalHandler = Callable[[dict[str, Any]], Awaitable[str | dict[str, Any]]]
ToolInputHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
DynamicToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | tuple[str, bool]]]

logger = logging.getLogger("codex_agent_sdk.client")


@dataclass
class _PendingRequest:
    event: anyio.Event
    result: Any | Exception | None = None


class CodexClient:
    """Client for interacting with `codex app-server` over JSON-RPC."""

    def __init__(
        self,
        options: CodexClientOptions | None = None,
        transport: Transport | None = None,
        request_handler: RequestHandler | None = None,
        notification_handler: NotificationHandler | None = None,
        command_approval_handler: ApprovalHandler | None = None,
        file_change_approval_handler: ApprovalHandler | None = None,
        tool_input_handler: ToolInputHandler | None = None,
        dynamic_tool_handler: DynamicToolHandler | None = None,
        schema_validator: CodexSchemaValidator | None = None,
    ) -> None:
        self.options = options or CodexClientOptions()
        self._transport = transport
        self._request_handler = request_handler
        self._notification_handler = notification_handler
        self._command_approval_handler = command_approval_handler
        self._file_change_approval_handler = file_change_approval_handler
        self._tool_input_handler = tool_input_handler
        self._dynamic_tool_handler = dynamic_tool_handler
        self._schema_validator = schema_validator

        self._pending: dict[int | str, _PendingRequest] = {}
        self._next_id = 0
        self._tg: anyio.abc.TaskGroup | None = None
        self._closed = False

        self._notification_send, self._notification_receive = (
            anyio.create_memory_object_stream[dict[str, Any]](max_buffer_size=100)
        )

    async def connect(self) -> None:
        if self._transport is None:
            sub_opts = SubprocessOptions(
                codex_path=self.options.codex_path,
                cwd=self.options.cwd,
                env=self.options.env,
                args=self.options.args,
                max_buffer_size=self.options.max_buffer_size,
            )
            self._transport = SubprocessTransport(sub_opts)

        logger.debug("Connecting to codex app-server")
        await self._transport.connect()

        self._tg = anyio.create_task_group()
        await self._tg.__aenter__()
        self._tg.start_soon(self._reader_loop)

        await self._initialize()

    async def _initialize(self) -> None:
        logger.debug("Initializing app-server protocol")
        params: dict[str, Any] = {
            "clientInfo": {
                "name": self.options.client_name,
                "title": self.options.client_title,
                "version": self.options.client_version,
            },
        }
        if self.options.experimental_api:
            params["capabilities"] = {"experimentalApi": True}

        await self.request("initialize", params)
        await self.notify("initialized")
        logger.debug("Initialization complete")

    async def _reader_loop(self) -> None:
        assert self._transport is not None
        try:
            async for message in self._transport.read_messages():
                await self._handle_message(message)
        except Exception as exc:
            # Fail any pending requests
            for pending in self._pending.values():
                if pending.result is None:
                    pending.result = exc
                    pending.event.set()
        finally:
            with suppress(Exception):
                await self._notification_send.aclose()

    async def _handle_message(self, message: dict[str, Any]) -> None:
        if self._schema_validator is not None:
            self._schema_validator.validate_incoming(message)

        if "method" in message:
            method = str(message["method"])
            params = message.get("params")
            if "id" in message:
                logger.debug("Received server request: %s", method)
                await self._handle_request(method, message["id"], params)
            else:
                logger.debug("Received notification: %s", method)
                await self._notification_send.send(message)
                if self._notification_handler:
                    await self._notification_handler(method, params)
            return

        if "id" in message and "result" in message:
            req_id = message["id"]
            pending = self._pending.get(req_id)
            if pending:
                logger.debug("Received response for request id %s", req_id)
                pending.result = message["result"]
                pending.event.set()
            return

        if "id" in message and "error" in message:
            req_id = message["id"]
            error = message["error"] or {}
            pending = self._pending.get(req_id)
            if pending:
                logger.debug("Received error response for request id %s", req_id)
                pending.result = CodexRPCError(
                    code=int(error.get("code", -32000)),
                    message=str(error.get("message", "Unknown error")),
                    data=error.get("data"),
                )
                pending.event.set()
            return

    async def _handle_request(self, method: str, req_id: int | str, params: Any) -> None:
        if not self._transport:
            raise CodexConnectionError("Not connected")

        handler = self._request_handler
        if handler is not None:
            try:
                result = await handler(method, params)
                await self._send_response(req_id, result)
            except Exception as exc:  # pragma: no cover - defensive
                await self._send_error(req_id, -32000, str(exc))
            return

        try:
            if method == "item/commandExecution/requestApproval":
                await self._handle_command_approval(req_id, params)
                return
            if method == "item/fileChange/requestApproval":
                await self._handle_file_change_approval(req_id, params)
                return
            if method == "item/tool/requestUserInput":
                await self._handle_tool_input(req_id, params)
                return
            if method == "item/tool/call":
                await self._handle_dynamic_tool(req_id, params)
                return
        except Exception as exc:  # pragma: no cover - defensive
            await self._send_error(req_id, -32000, str(exc))
            return

        await self._send_error(req_id, -32601, f"No handler for {method}")

    async def _handle_command_approval(self, req_id: int | str, params: Any) -> None:
        if self._command_approval_handler is None:
            await self._send_error(req_id, -32601, "No command approval handler")
            return
        decision = await self._command_approval_handler(params or {})
        result = decision if isinstance(decision, dict) else {"decision": decision}
        await self._send_response(req_id, result)

    async def _handle_file_change_approval(self, req_id: int | str, params: Any) -> None:
        if self._file_change_approval_handler is None:
            await self._send_error(req_id, -32601, "No file-change approval handler")
            return
        decision = await self._file_change_approval_handler(params or {})
        result = decision if isinstance(decision, dict) else {"decision": decision}
        await self._send_response(req_id, result)

    async def _handle_tool_input(self, req_id: int | str, params: Any) -> None:
        if self._tool_input_handler is None:
            await self._send_error(req_id, -32601, "No tool input handler")
            return
        result = await self._tool_input_handler(params or {})
        await self._send_response(req_id, result)

    async def _handle_dynamic_tool(self, req_id: int | str, params: Any) -> None:
        if self._dynamic_tool_handler is None:
            await self._send_error(req_id, -32601, "No dynamic tool handler")
            return
        result = await self._dynamic_tool_handler(params or {})
        if isinstance(result, tuple):
            output, success = result
            payload = {"output": output, "success": bool(success)}
        else:
            payload = result
        await self._send_response(req_id, payload)

    async def _send_response(self, req_id: int | str, result: Any) -> None:
        if not self._transport:
            return
        response = {"id": req_id, "result": result}
        await self._transport.write(json.dumps(response) + "\n")

    async def _send_error(self, req_id: int | str, code: int, message: str) -> None:
        if not self._transport:
            return
        response = {"id": req_id, "error": {"code": code, "message": message}}
        await self._transport.write(json.dumps(response) + "\n")

    async def request(
        self, method: str, params: dict[str, Any] | None = None, timeout: float | None = 60.0
    ) -> Any:
        if not self._transport:
            raise CodexConnectionError("Not connected")

        if params is None:
            params = {}

        logger.debug("Sending request: %s", method)
        self._next_id += 1
        req_id = self._next_id
        pending = _PendingRequest(event=anyio.Event())
        self._pending[req_id] = pending

        request_obj = {"id": req_id, "method": method, "params": params}
        if self._schema_validator is not None:
            self._schema_validator.validate_outgoing_request(request_obj)
        await self._transport.write(json.dumps(request_obj) + "\n")

        try:
            if timeout is None:
                await pending.event.wait()
            else:
                with anyio.fail_after(timeout):
                    await pending.event.wait()
        except TimeoutError as exc:
            self._pending.pop(req_id, None)
            raise CodexConnectionError(f"Request timeout: {method}") from exc

        self._pending.pop(req_id, None)
        if isinstance(pending.result, Exception):
            raise pending.result
        return pending.result

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if not self._transport:
            raise CodexConnectionError("Not connected")
        msg = {"method": method}
        if params is not None:
            msg["params"] = params
        if self._schema_validator is not None:
            self._schema_validator.validate_outgoing_notification(msg)
        logger.debug("Sending notification: %s", method)
        await self._transport.write(json.dumps(msg) + "\n")

    async def notifications(self) -> AsyncIterator[dict[str, Any]]:
        try:
            async for note in self._notification_receive:
                yield note
        except anyio.EndOfStream:
            return

    async def stream_prompt_text(
        self, thread_id: str, prompt: str, **turn_params: Any
    ) -> AsyncIterator[str]:
        """Start a turn and stream assistant text deltas."""
        items = [{"type": "text", "text": prompt}]
        async for delta in self.stream_turn_text(thread_id, items, **turn_params):
            yield delta

    async def stream_turn_text(
        self, thread_id: str, items: list[dict[str, Any]], **turn_params: Any
    ) -> AsyncIterator[str]:
        """Start a turn and yield text deltas until completion."""
        params = {"threadId": thread_id, "input": items}
        params.update(turn_params)
        response = await self.turn_start(params)
        turn_id = response.get("turn", {}).get("id")

        async for note in self.notifications():
            method = note.get("method")
            params = note.get("params") or {}

            if method == "item/agentMessage/delta" and (
                params.get("threadId") == thread_id
                and (turn_id is None or params.get("turnId") == turn_id)
            ):
                delta = params.get("delta")
                if isinstance(delta, str):
                    yield delta

            if method == "turn/completed":
                turn = params.get("turn") or {}
                if turn_id is None or turn.get("id") == turn_id:
                    return

    # Convenience wrappers
    async def thread_start(self, params: dict[str, Any]) -> Any:
        return await self.request("thread/start", params)

    async def thread_resume(self, params: dict[str, Any]) -> Any:
        return await self.request("thread/resume", params)

    async def thread_fork(self, params: dict[str, Any]) -> Any:
        return await self.request("thread/fork", params)

    async def turn_start(self, params: dict[str, Any]) -> Any:
        return await self.request("turn/start", params)

    async def turn_interrupt(self, params: dict[str, Any]) -> Any:
        return await self.request("turn/interrupt", params)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        logger.debug("Closing codex client")
        if self._tg:
            self._tg.cancel_scope.cancel()
            with suppress(Exception):
                await self._tg.__aexit__(None, None, None)
        if self._transport:
            await self._transport.close()

    async def __aenter__(self) -> CodexClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        await self.close()
        return False
