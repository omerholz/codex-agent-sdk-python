# Codex Agent SDK for Python

Python SDK for Codex app-server. This SDK wraps the `codex app-server` CLI via a
subprocess and speaks JSON-RPC over stdio (newline-delimited JSON).

## Installation

```bash
pip install codex-agent-sdk
```

Using `uv`:

```bash
uv pip install codex-agent-sdk
```

## Quick Start

The simplest way to use the SDK:

```python
import anyio
from codex_agent_sdk import run

async def main() -> None:
    async for chunk in run("Hello Codex!"):
        print(chunk, end="", flush=True)

anyio.run(main)
```

## Using the Agent Class

```python
import anyio
from codex_agent_sdk import Agent

async def main() -> None:
    agent = Agent(model="gpt-5.2-codex", auto_approve=True)

    # Stream text
    async for chunk in agent.run("Explain Python decorators"):
        print(chunk, end="", flush=True)

anyio.run(main)
```

### Get Full Response

```python
# Get full text
text = await agent.run("What is 2+2?").text()
print(text)

# Get full response with metadata
response = await agent.run("Hello").response()
print(response.text)
print(response.turn.id)
```

## Builder Pattern

Configure agents with a fluent API:

```python
agent = (
    Agent()
    .model("gpt-5.2-codex")
    .cwd("/path/to/project")
    .effort("medium")
    .auto_approve_commands()
    .auto_approve_file_changes()
)
```

## Decorator-Based Handlers

Register approval handlers using decorators:

```python
from codex_agent_sdk import Agent, CommandApproval, FileChangeApproval

agent = Agent()

@agent.on_command_approval
async def handle_command(cmd: CommandApproval) -> str:
    print(f"Approving: {cmd.command}")
    return "accept"  # or "reject"

@agent.on_file_change
async def handle_file_change(change: FileChangeApproval) -> str:
    print(f"File change: {change.path}")
    return "accept"

async for chunk in agent.run("List files in current directory"):
    print(chunk, end="")
```

## Multi-Turn Conversations

Maintain conversation context across multiple messages:

```python
async with agent.conversation() as conv:
    response = await conv.send("Hi, my name is Alice")
    print(response.text)

    response = await conv.send("What's my name?")
    print(response.text)  # Agent remembers "Alice"
```

## Typed Events

Access rich event objects with pattern matching:

```python
from codex_agent_sdk import (
    Agent,
    MessageDelta,
    TurnCompleted,
    ExecStarted,
    ExecCompleted,
)

async for event in agent.run("Run ls -la").events():
    match event:
        case MessageDelta(delta=text):
            print(text, end="")
        case ExecStarted(command=cmd):
            print(f"\n> Running: {cmd}")
        case ExecCompleted(exit_code=code):
            print(f"\n> Exit code: {code}")
        case TurnCompleted(status=status):
            print(f"\nCompleted: {status}")
```

## Real-World Example

Analyze a local project:

```bash
uv run python examples/real_world_project_analysis.py --project /path/to/project
```

Or set environment variables:

```bash
CODEX_PROJECT=/path/to/project \
CODEX_MODEL=gpt-5.2-codex \
CODEX_EFFORT=medium \
uv run python examples/real_world_project_analysis.py
```

## Schema Validation

Optionally validate messages against JSON schemas:

```bash
pip install codex-agent-sdk[schema]
```

CLI tools for schema management:

```bash
# Validate SDK <-> installed Codex CLI compatibility
codex-agent-sdk validate

# Generate schema to a directory
codex-agent-sdk schema generate --out ./codex-schema

# Detect breaking schema changes
codex-agent-sdk schema diff --baseline ./codex-schema
codex-agent-sdk schema check-breaking --baseline ./codex-schema
```

## Logging

Enable debug logs:

```python
import logging

logging.getLogger("codex_agent_sdk").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.INFO)
```

## Development

```bash
# Create dev environment
uv sync --all-extras

# Run tests
uv run pytest -q

# Run integration tests (requires Codex CLI auth)
CODEX_INTEGRATION=1 uv run pytest -q
```

## Contributing

See `docs/CONTRIBUTING.md`.

## License

MIT
