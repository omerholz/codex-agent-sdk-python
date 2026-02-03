"""Subprocess transport using `codex app-server`."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from subprocess import PIPE
from typing import Any

import anyio
from anyio.abc import Process

from ..errors import CodexConnectionError, CodexJSONDecodeError, CodexProcessError
from . import Transport

_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024  # 1MB
logger = logging.getLogger("codex_agent_sdk.transport")


@dataclass
class SubprocessOptions:
    codex_path: str = "codex"
    args: list[str] | None = None
    cwd: str | Path | None = None
    env: dict[str, str] | None = None
    stderr: Callable[[str], None] | None = None
    max_buffer_size: int | None = None


class SubprocessTransport(Transport):
    """Transport that runs `codex app-server` as a subprocess."""

    def __init__(self, options: SubprocessOptions) -> None:
        self._options = options
        self._process: Process | None = None
        self._ready = False
        self._stdin_lock = anyio.Lock()
        self._max_buffer_size = (
            options.max_buffer_size
            if options.max_buffer_size is not None
            else _DEFAULT_MAX_BUFFER_SIZE
        )
        self._stderr_task_group: anyio.abc.TaskGroup | None = None

    async def connect(self) -> None:
        if self._process:
            return

        cmd = [self._options.codex_path, "app-server"]
        if self._options.args:
            cmd.extend(self._options.args)

        logger.debug("Starting subprocess: %s", " ".join(cmd))
        process_env = {**os.environ}
        if self._options.env:
            process_env.update(self._options.env)

        try:
            self._process = await anyio.open_process(
                cmd,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE if self._options.stderr else None,
                cwd=str(self._options.cwd) if self._options.cwd else None,
                env=process_env,
            )
        except FileNotFoundError as exc:
            raise CodexConnectionError(
                f"Codex CLI not found at: {self._options.codex_path}"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise CodexConnectionError(f"Failed to start codex: {exc}") from exc

        if self._options.stderr and self._process.stderr:
            self._stderr_task_group = anyio.create_task_group()
            await self._stderr_task_group.__aenter__()
            self._stderr_task_group.start_soon(self._read_stderr)

        self._ready = True
        logger.debug("Subprocess transport ready")

    async def _read_stderr(self) -> None:
        if not self._process or not self._process.stderr or not self._options.stderr:
            return
        try:
            while True:
                chunk = await self._process.stderr.receive()
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                for line in text.splitlines():
                    if line:
                        self._options.stderr(line)
        except anyio.ClosedResourceError:
            return

    async def write(self, data: str) -> None:
        async with self._stdin_lock:
            if not self._ready or not self._process or not self._process.stdin:
                raise CodexConnectionError("Transport is not ready for writing")
            logger.debug("Writing %d bytes to subprocess stdin", len(data))
            await self._process.stdin.send(data.encode("utf-8"))

    async def end_input(self) -> None:
        async with self._stdin_lock:
            if self._process and self._process.stdin:
                with suppress(Exception):
                    await self._process.stdin.aclose()

    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        return self._read_messages_impl()

    async def _read_messages_impl(self) -> AsyncIterator[dict[str, Any]]:
        if not self._process or not self._process.stdout:
            raise CodexConnectionError("Not connected")

        buffer = b""
        try:
            while True:
                chunk = await self._process.stdout.receive()
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > self._max_buffer_size:
                    buffer = b""
                    raise CodexJSONDecodeError("<buffer overflow>", ValueError("buffer too large"))

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    logger.debug("Received line from subprocess")
                    try:
                        data = json.loads(line_str)
                    except json.JSONDecodeError as exc:
                        raise CodexJSONDecodeError(line_str, exc) from exc
                    yield data
        except anyio.ClosedResourceError:
            pass

        # Process exit
        returncode = None
        if self._process:
            try:
                returncode = await self._process.wait()
            except Exception:
                returncode = -1

        if returncode and returncode != 0:
            raise CodexProcessError(
                f"codex app-server exited with code {returncode}",
                exit_code=returncode,
            )

    async def close(self) -> None:
        self._ready = False
        logger.debug("Closing subprocess transport")
        if self._stderr_task_group:
            with suppress(Exception):
                self._stderr_task_group.cancel_scope.cancel()
                await self._stderr_task_group.__aexit__(None, None, None)
            self._stderr_task_group = None

        if not self._process:
            return

        with suppress(Exception):
            await self.end_input()

        if self._process.returncode is None:
            with suppress(Exception):
                self._process.terminate()
                await self._process.wait()

        self._process = None

    def is_ready(self) -> bool:
        return self._ready
