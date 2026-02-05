"""JSON schema validation for Codex app-server protocol."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from .errors import CodexSchemaValidationError

Draft7Validator: Any | None
ValidationError: type[Exception]
_IMPORT_ERROR: Exception | None

try:  # Optional dependency
    _jsonschema: Any = importlib.import_module("jsonschema")
    Draft7Validator = _jsonschema.Draft7Validator
    _jsonschema_exceptions: Any = importlib.import_module("jsonschema.exceptions")
    ValidationError = _jsonschema_exceptions.ValidationError
except Exception as exc:  # pragma: no cover - optional dependency
    Draft7Validator = None
    ValidationError = Exception
    _IMPORT_ERROR = exc
else:  # pragma: no cover - import success
    _IMPORT_ERROR = None


class CodexSchemaValidator:
    """Validate messages against Codex app-server JSON schema files."""

    def __init__(self, schema_dir: str | Path) -> None:
        if Draft7Validator is None:
            raise CodexSchemaValidationError(
                "jsonschema is not installed. Install with: pip install codex-agent-sdk[schema]"
            ) from _IMPORT_ERROR

        schema_path = Path(schema_dir)
        if not schema_path.exists():
            raise CodexSchemaValidationError(f"Schema directory not found: {schema_path}")

        self._schemas: dict[str, dict[str, Any]] = {}
        for file in schema_path.glob("*.json"):
            try:
                self._schemas[file.stem] = json.loads(file.read_text())
            except Exception as exc:  # pragma: no cover - defensive
                raise CodexSchemaValidationError(
                    f"Failed to load schema: {file} ({exc})"
                ) from exc

        self._validators = {
            name: Draft7Validator(schema)
            for name, schema in self._schemas.items()
        }

    def _validate(self, schema_name: str, obj: dict[str, Any]) -> None:
        validator = self._validators.get(schema_name)
        if validator is None:
            raise CodexSchemaValidationError(
                f"Schema not found: {schema_name}. Available: {sorted(self._validators.keys())}"
            )
        try:
            validator.validate(obj)
        except ValidationError as exc:
            raise CodexSchemaValidationError(
                f"Schema validation failed for {schema_name}: {exc}"
            ) from exc

    def validate_outgoing_request(self, obj: dict[str, Any]) -> None:
        self._validate("ClientRequest", obj)

    def validate_outgoing_notification(self, obj: dict[str, Any]) -> None:
        self._validate("ClientNotification", obj)

    def validate_incoming(self, obj: dict[str, Any]) -> None:
        if "method" in obj:
            if "id" in obj:
                self._validate("ServerRequest", obj)
            else:
                self._validate("ServerNotification", obj)
            return
        if "result" in obj and "id" in obj:
            self._validate("JSONRPCResponse", obj)
            return
        if "error" in obj and "id" in obj:
            self._validate("JSONRPCError", obj)
            return


def load_schema_validator_from_codex_cli(
    *, codex_path: str = "codex", experimental: bool = False
) -> CodexSchemaValidator:
    """Generate schema via the Codex CLI and return an in-memory validator.

    This is intended as a runtime guardrail: the schema files are generated to a
    temporary directory, loaded into memory, and then discarded.
    """

    from .schema_tools import generated_schema_dir

    with generated_schema_dir(codex_path=codex_path, experimental=experimental) as schema_dir:
        return CodexSchemaValidator(schema_dir)
