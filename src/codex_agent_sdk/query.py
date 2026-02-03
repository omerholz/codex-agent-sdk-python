"""One-shot query helper for Codex app-server."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .client import CodexClient
from .types import CodexClientOptions


async def query(
    prompt: str,
    options: CodexClientOptions | None = None,
    thread_params: dict[str, Any] | None = None,
    turn_params: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run a single prompt and yield notifications until turn completion."""
    thread_params = thread_params or {}
    turn_params = turn_params or {}

    async with CodexClient(options=options) as client:
        thread_resp = await client.thread_start(thread_params)
        thread_id = thread_resp.get("thread", {}).get("id")
        if not thread_id:
            raise ValueError("thread/start response missing thread.id")

        params = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
        }
        params.update(turn_params)
        await client.turn_start(params)

        async for note in client.notifications():
            yield note
            if note.get("method") == "turn/completed":
                return
