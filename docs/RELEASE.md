# Release Guide

This project uses `uv` for build and publish.

## Checklist

1. Update version in `pyproject.toml`.
2. Update `README.md` if public behavior changed.
3. Run tests: `uv run pytest -q`.
4. Build: `uv build`.
5. Publish: `uv publish`.

## Publishing Notes

- Set PyPI credentials via environment variables supported by `uv`.
- If you use TestPyPI, configure the repository URL in the publish command.
