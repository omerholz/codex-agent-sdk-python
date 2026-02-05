"""Command line interface for codex-agent-sdk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anyio

from .client import CodexClient
from .errors import (
    CodexConnectionError,
    CodexRPCError,
    CodexSchemaGenerationError,
    CodexSchemaValidationError,
)
from .schema import CodexSchemaValidator
from .schema_tools import (
    detect_breaking_changes,
    generate_json_schema,
    generated_schema_dir,
    locate_schema_dir,
)
from .types import CodexClientOptions


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-agent-sdk")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser(
        "validate",
        help="Validate protocol compatibility against the installed Codex CLI.",
    )
    validate.add_argument("--codex", default="codex", help="Path to codex CLI")
    validate.add_argument(
        "--experimental",
        action="store_true",
        help="Include experimental protocol fields/methods.",
    )

    schema = sub.add_parser("schema", help="Schema generation and diff tools")
    schema_sub = schema.add_subparsers(dest="schema_command", required=True)

    gen = schema_sub.add_parser(
        "generate", help="Generate app-server JSON schema to a directory"
    )
    gen.add_argument("--codex", default="codex", help="Path to codex CLI")
    gen.add_argument("--out", required=True, help="Output directory")
    gen.add_argument("--experimental", action="store_true")

    diff = schema_sub.add_parser(
        "diff",
        help="Diff a baseline schema directory against the currently installed Codex CLI.",
    )
    diff.add_argument("--baseline", required=True, help="Baseline schema directory")
    diff.add_argument("--new", default=None, help="New schema directory (optional)")
    diff.add_argument("--codex", default="codex", help="Path to codex CLI")
    diff.add_argument("--experimental", action="store_true")
    diff.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    check = schema_sub.add_parser(
        "check-breaking",
        help="Exit non-zero if breaking schema changes are detected versus baseline.",
    )
    check.add_argument("--baseline", required=True, help="Baseline schema directory")
    check.add_argument("--new", default=None, help="New schema directory (optional)")
    check.add_argument("--codex", default="codex", help="Path to codex CLI")
    check.add_argument("--experimental", action="store_true")

    return parser


async def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        with generated_schema_dir(
            codex_path=args.codex, experimental=bool(args.experimental)
        ) as schema_dir:
            validator = CodexSchemaValidator(schema_dir)

        options = CodexClientOptions(codex_path=args.codex)
        async with CodexClient(options=options, schema_validator=validator) as client:
            await client.request("thread/loaded/list")

        print("OK")
        return 0
    except (CodexSchemaGenerationError, CodexSchemaValidationError) as exc:
        print(f"Schema error: {exc}", file=sys.stderr)
        return 2
    except CodexRPCError as exc:
        print(f"Protocol error: {exc}", file=sys.stderr)
        return 3
    except CodexConnectionError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 4


def _format_diff(name: str, diff: Any) -> str:
    lines: list[str] = [f"{name}:"]

    if diff.removed_methods:
        lines.append(f"  removed methods: {', '.join(diff.removed_methods)}")
    if diff.added_methods:
        lines.append(f"  added methods: {', '.join(diff.added_methods)}")

    if diff.required_added:
        lines.append("  required fields added:")
        for method, fields in sorted(diff.required_added.items()):
            lines.append(f"    {method}: {', '.join(fields)}")

    if diff.properties_removed:
        lines.append("  properties removed:")
        for method, fields in sorted(diff.properties_removed.items()):
            lines.append(f"    {method}: {', '.join(fields)}")

    if diff.properties_added:
        lines.append("  properties added:")
        for method, fields in sorted(diff.properties_added.items()):
            lines.append(f"    {method}: {', '.join(fields)}")

    if len(lines) == 1:
        lines.append("  (no changes)")

    return "\n".join(lines)


def _load_schema_dir(path: str) -> Path:
    p = locate_schema_dir(Path(path))
    return p


def _diff_schemas(args: argparse.Namespace) -> dict[str, Any]:
    baseline_dir = _load_schema_dir(args.baseline)

    if args.new:
        new_dir = _load_schema_dir(args.new)
        diffs = detect_breaking_changes(baseline_dir, new_dir)
    else:
        with generated_schema_dir(
            codex_path=args.codex, experimental=bool(args.experimental)
        ) as new_dir:
            diffs = detect_breaking_changes(baseline_dir, new_dir)

    out: dict[str, Any] = {}
    for kind, diff in diffs.items():
        out[kind] = {
            "removed_methods": list(diff.removed_methods),
            "added_methods": list(diff.added_methods),
            "required_added": {k: list(v) for k, v in diff.required_added.items()},
            "properties_removed": {k: list(v) for k, v in diff.properties_removed.items()},
            "properties_added": {k: list(v) for k, v in diff.properties_added.items()},
            "has_breaking_changes": diff.has_breaking_changes,
        }

    return out


def _cmd_schema_generate(args: argparse.Namespace) -> int:
    try:
        out_dir = Path(args.out)
        schema_dir = generate_json_schema(
            codex_path=args.codex, out_dir=out_dir, experimental=bool(args.experimental)
        )
        print(str(schema_dir))
        return 0
    except CodexSchemaGenerationError as exc:
        print(f"Schema generation error: {exc}", file=sys.stderr)
        return 2


def _cmd_schema_diff(args: argparse.Namespace) -> int:
    try:
        out = _diff_schemas(args)
    except CodexSchemaGenerationError as exc:
        print(f"Schema error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0

    any_breaking = False
    for kind, diff_obj in out.items():
        # Re-hydrate a small object for formatting.
        class _D:
            removed_methods = tuple(diff_obj["removed_methods"])
            added_methods = tuple(diff_obj["added_methods"])
            required_added = {
                k: tuple(v) for k, v in diff_obj["required_added"].items()
            }
            properties_removed = {
                k: tuple(v) for k, v in diff_obj["properties_removed"].items()
            }
            properties_added = {
                k: tuple(v) for k, v in diff_obj["properties_added"].items()
            }

        diff = _D()
        any_breaking = any_breaking or bool(diff_obj["has_breaking_changes"])
        print(_format_diff(kind, diff))

    if any_breaking:
        print("\nBreaking changes detected.")
    else:
        print("\nNo breaking changes detected.")

    return 0


def _cmd_schema_check_breaking(args: argparse.Namespace) -> int:
    try:
        out = _diff_schemas(args)
    except CodexSchemaGenerationError as exc:
        print(f"Schema error: {exc}", file=sys.stderr)
        return 2

    any_breaking = any(v.get("has_breaking_changes") for v in out.values())
    if any_breaking:
        print("Breaking changes detected.")
        return 1

    print("No breaking changes detected.")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        raise SystemExit(anyio.run(_cmd_validate, args))

    if args.command == "schema" and args.schema_command == "generate":
        raise SystemExit(_cmd_schema_generate(args))

    if args.command == "schema" and args.schema_command == "diff":
        raise SystemExit(_cmd_schema_diff(args))

    if args.command == "schema" and args.schema_command == "check-breaking":
        raise SystemExit(_cmd_schema_check_breaking(args))

    parser.error("Unsupported command")
