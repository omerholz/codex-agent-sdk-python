# Release Guide

This project uses `uv` for build and publish.

## Checklist

1. Update version in `pyproject.toml`.
2. Update `README.md` if public behavior changed.
3. Run tests: `uv run pytest -q`.
4. Build: `uv build`.
5. Publish (TestPyPI first, then PyPI).

## Publishing Notes

- To avoid interactive prompts, set `UV_PUBLISH_TOKEN` (recommended) or `UV_PUBLISH_USERNAME` /
  `UV_PUBLISH_PASSWORD`.
- TestPyPI and PyPI are separate sites with separate accounts and tokens.

## Commands

Build artifacts:

```bash
uv build
```

Optional validation:

```bash
uv tool run twine check dist/*
```

Publish to TestPyPI:

```bash
export UV_PUBLISH_TOKEN="pypi-...<testpypi token>..."
uv publish --publish-url https://test.pypi.org/legacy/ --check-url https://test.pypi.org/simple
```

Publish to PyPI:

```bash
export UV_PUBLISH_TOKEN="pypi-...<pypi token>..."
uv publish --check-url https://pypi.org/simple
```
