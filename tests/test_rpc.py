import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import anyio
import pytest

from codex_agent_sdk import CodexClient
from codex_agent_sdk.transport import Transport


class FakeTransport(Transport):
    def __init__(self) -> None:
        self._send, self._recv = anyio.create_memory_object_stream[dict[str, Any]](
            max_buffer_size=100
        )
        self.writes: list[dict[str, Any]] = []
        self._ready = False
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def on_request(
        self, method: str, handler: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> None:
        self._handlers[method] = handler

    async def push(self, message: dict[str, Any]) -> None:
        await self._send.send(message)

    async def connect(self) -> None:
        self._ready = True

    async def write(self, data: str) -> None:
        for line in data.splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            self.writes.append(msg)

            # Auto-handle requests if configured
            if "id" in msg and "method" in msg:
                handler = self._handlers.get(msg["method"])
                if handler:
                    result = handler(msg)
                    await self._send.send({"id": msg["id"], "result": result})

    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        return self._recv

    async def close(self) -> None:
        self._ready = False
        await self._send.aclose()

    def is_ready(self) -> bool:
        return self._ready

    async def end_input(self) -> None:
        return None


@pytest.mark.anyio
async def test_initialize_handshake() -> None:
    transport = FakeTransport()
    transport.on_request("initialize", lambda _: {"userAgent": "codex"})

    client = CodexClient(transport=transport)
    await client.connect()

    methods = [m["method"] for m in transport.writes if "method" in m]
    assert methods[0] == "initialize"
    assert "initialized" in methods

    await client.close()


@pytest.mark.anyio
async def test_request_response_roundtrip() -> None:
    transport = FakeTransport()
    transport.on_request("initialize", lambda _: {"userAgent": "codex"})
    transport.on_request("thread/start", lambda _: {"thread": {"id": "thr_123"}})

    client = CodexClient(transport=transport)
    await client.connect()

    resp = await client.thread_start({"model": "gpt-5.1-codex"})
    assert resp["thread"]["id"] == "thr_123"

    await client.close()


@pytest.mark.anyio
async def test_server_request_command_approval() -> None:
    transport = FakeTransport()
    transport.on_request("initialize", lambda _: {"userAgent": "codex"})

    async def approve(_params: dict[str, Any]) -> str:
        return "accept"

    client = CodexClient(transport=transport, command_approval_handler=approve)
    await client.connect()

    await transport.push(
        {
            "id": 99,
            "method": "item/commandExecution/requestApproval",
            "params": {"threadId": "thr", "turnId": "turn", "itemId": "item"},
        }
    )

    async def wait_for_response() -> dict[str, Any]:
        with anyio.fail_after(1):
            while True:
                for msg in transport.writes:
                    if msg.get("id") == 99 and "result" in msg:
                        return msg
                await anyio.sleep(0)

    response = await wait_for_response()
    assert response["result"]["decision"] == "accept"

    await client.close()


@pytest.mark.anyio
async def test_notifications_stream() -> None:
    transport = FakeTransport()
    transport.on_request("initialize", lambda _: {"userAgent": "codex"})

    client = CodexClient(transport=transport)
    await client.connect()

    await transport.push({"method": "turn/started", "params": {"threadId": "thr"}})

    async for note in client.notifications():
        assert note["method"] == "turn/started"
        break

    await client.close()


@pytest.mark.anyio
async def test_stream_prompt_text() -> None:
    transport = FakeTransport()
    transport.on_request("initialize", lambda _: {"userAgent": "codex"})
    transport.on_request("thread/start", lambda _: {"thread": {"id": "thr_1"}})
    transport.on_request("turn/start", lambda _: {"turn": {"id": "turn_1"}})

    client = CodexClient(transport=transport)
    await client.connect()

    deltas: list[str] = []

    async def run_stream() -> None:
        async for delta in client.stream_prompt_text("thr_1", "Hi"):
            deltas.append(delta)

    async with anyio.create_task_group() as tg:
        tg.start_soon(run_stream)
        await transport.push(
            {
                "method": "item/agentMessage/delta",
                "params": {
                    "threadId": "thr_1",
                    "turnId": "turn_1",
                    "itemId": "item_1",
                    "delta": "Hello",
                },
            }
        )
        await transport.push(
            {
                "method": "turn/completed",
                "params": {"threadId": "thr_1", "turn": {"id": "turn_1"}},
            }
        )

    assert "".join(deltas) == "Hello"

    await client.close()
