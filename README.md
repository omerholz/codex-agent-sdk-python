# Codex Agent SDK for Python

Python SDK for Codex app-server. This SDK wraps the `codex app-server` CLI via a
subprocess and speaks JSON-RPC over stdio (newline-delimited JSON).

Inspired by the Claude Agent SDK for Python and its subprocess + JSON streaming design.

## Installation

```bash
pip install codex-agent-sdk
```

Using `uv`:

```bash
uv pip install codex-agent-sdk
```

## Quick Start

```python
import anyio
from codex_agent_sdk import CodexClient, CodexClientOptions

async def main() -> None:
    options = CodexClientOptions(client_name="codex_sdk_py", client_version="0.1.0")
    async with CodexClient(options=options) as client:
        thread = await client.thread_start({"model": "gpt-5.1-codex"})
        async for delta in client.stream_prompt_text(
            thread["thread"]["id"], "Hello Codex"
        ):
            print(delta, end="", flush=True)

anyio.run(main)
```

## Real-World Example

Analyze a local project with the agent (defaults to current directory):

```bash
CODEX_PROJECT=/path/to/project \
CODEX_MODEL=gpt-5.1-codex \
CODEX_CLI=codex \
CODEX_EFFORT=high \
uv run python examples/real_world_project_analysis.py
```

Or pass the project path explicitly:

```bash
uv run python examples/real_world_project_analysis.py --project /path/to/project
```

## Handling Approvals

```python
async def approve_commands(params: dict) -> str:
    # Accept or decline based on your policy.
    return "accept"

async with CodexClient(
    options=CodexClientOptions(),
    command_approval_handler=approve_commands,
) as client:
    ...
```

## Schema Validation

```python
from codex_agent_sdk import CodexSchemaValidator

schema = CodexSchemaValidator("/path/to/schema/json")
async with CodexClient(schema_validator=schema) as client:
    ...
```

Install the optional dependency:

```bash
pip install codex-agent-sdk[schema]
```

Generate schema with the Codex CLI:

```bash
codex app-server generate-json-schema --out ./codex-schema
```

## Logging

This library logs under the `codex_agent_sdk` logger namespace. To enable debug logs:

```python
import logging

logging.getLogger("codex_agent_sdk").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.INFO)
```

To silence library logs while keeping your app logs:

```python
logging.getLogger("codex_agent_sdk").setLevel(logging.WARNING)
```

## Development

Create a dev environment:

```bash
uv sync --all-extras
```

Run tests:

```bash
uv run pytest -q
```

Run integration tests (requires Codex CLI auth):

```bash
CODEX_INTEGRATION=1 uv run pytest -q
```

## Release (PyPI)

Build:

```bash
uv build
```

Publish:

```bash
uv publish
```

## Contributing

See `docs/CONTRIBUTING.md`.

## Notes

- The SDK requires `codex` to be installed and available on PATH.
- The SDK initializes the app-server with an `initialize` request and sends an
  `initialized` notification before issuing other requests.

## License

MIT
