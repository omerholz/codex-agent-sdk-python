"""Quick start example for Codex Agent SDK."""

import anyio

from codex_agent_sdk import run


async def main() -> None:
    """Stream a simple prompt to the console."""
    async for chunk in run("Hello Codex!"):
        print(chunk, end="", flush=True)
    print()


if __name__ == "__main__":
    anyio.run(main)
