# Contributing

Thanks for contributing to `codex-agent-sdk`.

## Prerequisites

- Python 3.10+
- `uv`
- Codex CLI (`codex`) on PATH for integration tests

## Setup

1. `uv sync --all-extras`
2. `uv run pytest -q`
3. `uv run ruff check .`
4. `uv run mypy src`

## Integration Tests

Integration tests require a logged-in Codex CLI session.

1. `CODEX_INTEGRATION=1 uv run pytest -q`

If you want to use a custom CLI path:

1. `CODEX_CLI=/path/to/codex CODEX_INTEGRATION=1 uv run pytest -q`

## Project Structure

- `src/codex_agent_sdk`: SDK implementation
- `examples`: runnable demos
- `tests`: unit and integration tests

## Development Notes

- Keep stdout reserved for protocol messages in subprocess transport code.
- Prefer adding tests when changing JSON-RPC behavior.
