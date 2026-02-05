"""Tools for generating and diffing Codex app-server JSON schema."""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import CodexSchemaGenerationError


@dataclass(frozen=True)
class MethodShape:
    required: frozenset[str]
    properties: frozenset[str]


@dataclass(frozen=True)
class MethodIndexDiff:
    removed_methods: tuple[str, ...]
    added_methods: tuple[str, ...]
    required_added: dict[str, tuple[str, ...]]
    properties_removed: dict[str, tuple[str, ...]]
    properties_added: dict[str, tuple[str, ...]]

    @property
    def has_breaking_changes(self) -> bool:
        return bool(self.removed_methods or self.required_added or self.properties_removed)


def _run(
    cmd: list[str], *, timeout: float | None = 30.0, cwd: str | None = None
) -> None:
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise CodexSchemaGenerationError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CodexSchemaGenerationError(f"Command timed out: {' '.join(cmd)}") from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        details = stderr or stdout or f"exit code {completed.returncode}"
        raise CodexSchemaGenerationError(
            f"Command failed ({completed.returncode}): {' '.join(cmd)}\n{details}"
        )


def generate_json_schema(
    *, codex_path: str = "codex", out_dir: str | Path, experimental: bool = False
) -> Path:
    """Generate app-server JSON schema into `out_dir`.

    Returns the directory containing JSON schema files.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        codex_path,
        "app-server",
        "generate-json-schema",
        "--out",
        str(out_path),
    ]
    if experimental:
        cmd.append("--experimental")

    _run(cmd)
    return locate_schema_dir(out_path)


def locate_schema_dir(out_dir: Path) -> Path:
    """Return the directory that contains the JSON schema files."""
    direct = out_dir / "ClientRequest.json"
    if direct.exists():
        return out_dir

    nested = out_dir / "json" / "ClientRequest.json"
    if nested.exists():
        return out_dir / "json"

    for candidate in out_dir.rglob("ClientRequest.json"):
        return candidate.parent

    raise CodexSchemaGenerationError(
        f"Could not locate ClientRequest.json under: {out_dir}"
    )


@contextmanager
def generated_schema_dir(
    *, codex_path: str = "codex", experimental: bool = False
) -> Iterator[Path]:
    """Generate schema to a temporary directory and yield the schema directory."""
    with tempfile.TemporaryDirectory(prefix="codex-schema-") as tmp:
        schema_dir = generate_json_schema(
            codex_path=codex_path, out_dir=tmp, experimental=experimental
        )
        yield schema_dir


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise CodexSchemaGenerationError(f"Expected object schema in: {path}")
        return data
    except Exception as exc:
        raise CodexSchemaGenerationError(f"Failed to load JSON schema: {path}") from exc


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    # Only internal refs are expected here.
    prefix = "#/definitions/"
    if not ref.startswith(prefix):
        raise CodexSchemaGenerationError(f"Unsupported $ref: {ref}")
    key = ref.removeprefix(prefix)
    definitions = root.get("definitions")
    if not isinstance(definitions, dict) or key not in definitions:
        raise CodexSchemaGenerationError(f"Unresolvable $ref: {ref}")
    target = definitions[key]
    if not isinstance(target, dict):
        raise CodexSchemaGenerationError(f"$ref did not resolve to an object: {ref}")
    return target


def _resolve_schema(root: dict[str, Any], schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict) and "$ref" in schema:
        return _resolve_ref(root, str(schema["$ref"]))
    if isinstance(schema, dict):
        return schema
    raise CodexSchemaGenerationError("Unexpected schema node")


def _extract_method_names(method_node: Any) -> list[str]:
    if isinstance(method_node, dict):
        if "const" in method_node:
            return [str(method_node["const"])]
        if "enum" in method_node and isinstance(method_node["enum"], list):
            return [str(x) for x in method_node["enum"]]
    if isinstance(method_node, str):
        return [method_node]
    return []


def build_method_index(schema_path: str | Path) -> dict[str, MethodShape]:
    """Build a method -> (required fields, property keys) index from a schema file."""
    root = _load_json(Path(schema_path))
    variants = root.get("oneOf") or root.get("anyOf")
    if not isinstance(variants, list):
        raise CodexSchemaGenerationError(
            f"Expected oneOf/anyOf union in schema: {schema_path}"
        )

    index: dict[str, MethodShape] = {}
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        props = variant.get("properties")
        if not isinstance(props, dict):
            continue
        method_node = props.get("method")
        method_names = _extract_method_names(method_node)
        if not method_names:
            continue

        params_node = props.get("params")
        if params_node is None:
            shape = MethodShape(required=frozenset(), properties=frozenset())
        else:
            params_schema = _resolve_schema(root, params_node)
            required = frozenset(params_schema.get("required") or [])
            properties = frozenset((params_schema.get("properties") or {}).keys())
            shape = MethodShape(required=required, properties=properties)

        for method in method_names:
            index[method] = shape

    return index


def diff_method_indexes(old: dict[str, MethodShape], new: dict[str, MethodShape]) -> MethodIndexDiff:
    old_methods = set(old.keys())
    new_methods = set(new.keys())

    removed = tuple(sorted(old_methods - new_methods))
    added = tuple(sorted(new_methods - old_methods))

    required_added: dict[str, tuple[str, ...]] = {}
    properties_removed: dict[str, tuple[str, ...]] = {}
    properties_added: dict[str, tuple[str, ...]] = {}

    for method in sorted(old_methods & new_methods):
        old_shape = old[method]
        new_shape = new[method]

        added_req = tuple(sorted(new_shape.required - old_shape.required))
        if added_req:
            required_added[method] = added_req

        removed_props = tuple(sorted(old_shape.properties - new_shape.properties))
        if removed_props:
            properties_removed[method] = removed_props

        added_props = tuple(sorted(new_shape.properties - old_shape.properties))
        if added_props:
            properties_added[method] = added_props

    return MethodIndexDiff(
        removed_methods=removed,
        added_methods=added,
        required_added=required_added,
        properties_removed=properties_removed,
        properties_added=properties_added,
    )


def detect_breaking_changes(old_schema_dir: str | Path, new_schema_dir: str | Path) -> dict[str, MethodIndexDiff]:
    """Detect breaking changes between two schema directories.

    Returns diffs for:
    - ClientRequest
    - ServerRequest
    - ServerNotification
    """
    old_dir = Path(old_schema_dir)
    new_dir = Path(new_schema_dir)

    targets = {
        "ClientRequest": "ClientRequest.json",
        "ServerRequest": "ServerRequest.json",
        "ServerNotification": "ServerNotification.json",
    }

    diffs: dict[str, MethodIndexDiff] = {}
    for name, filename in targets.items():
        old_path = old_dir / filename
        new_path = new_dir / filename
        if not old_path.exists() or not new_path.exists():
            continue

        old_index = build_method_index(old_path)
        new_index = build_method_index(new_path)
        diffs[name] = diff_method_indexes(old_index, new_index)

    return diffs
