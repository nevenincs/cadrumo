"""Central command-output rendering contract."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .errors import AeatError


class OutputRenderingError(AeatError):
    """Raised when command output cannot be rendered safely."""


class OutputFormatRefusedError(AeatError):
    """Raised when a command requests an unsupported output format."""


class OutputFormat(StrEnum):
    """Accepted command output formats."""

    TEXT = "text"
    JSON = "json"


class RenderedCommandOutput(BaseModel):
    """Rendered output document returned to CLI transports."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    format: OutputFormat
    text: str = Field(default="")


def render_command_output(
    *,
    format_name: str,
    payload: object,
    lines: Iterable[str],
) -> RenderedCommandOutput:
    """Render a payload or line iterator according to the root output format."""

    try:
        output_format = OutputFormat(format_name.strip().lower() or OutputFormat.TEXT.value)
    except ValueError as exc:
        raise OutputFormatRefusedError(f"unsupported output format {format_name!r}; expected 'text' or 'json'") from exc
    if output_format is OutputFormat.JSON:
        return RenderedCommandOutput(
            format=output_format,
            text=json.dumps(jsonable_output_payload(payload), default=_json_default, ensure_ascii=False),
        )
    return RenderedCommandOutput(format=output_format, text="\n".join(lines))


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, set | frozenset):
        return sorted(value)
    raise OutputRenderingError(f"output rendering cannot JSON-encode {type(value).__name__}")


def jsonable_output_payload(payload: object) -> object:
    """Convert command payload values into JSON-serialisable primitives.

    Tuples / sets / frozensets are flattened to JSON arrays (list)
    because JSON has no native tuple or set type. Downstream consumers
    that need to round-trip a typed payload back into its declared
    schema MUST use ``ModelClass.model_validate_json(raw_bytes)``
    rather than ``ModelClass.model_validate(json.loads(raw))``: pydantic
    coerces list -> tuple when it owns the JSON parse, but not when
    handed a pre-parsed dict. The roundtrip tests in
    ``aeat.core.test_json_envelope_roundtrip`` pin the correct usage.
    """

    if isinstance(payload, BaseModel):
        return jsonable_output_payload(payload.model_dump(mode="python"))
    if isinstance(payload, dict):
        return {key: jsonable_output_payload(value) for key, value in payload.items()}
    if isinstance(payload, list | tuple | set | frozenset):
        return [jsonable_output_payload(item) for item in payload]
    if isinstance(payload, Path):
        return payload.as_posix()
    if isinstance(payload, date | datetime):
        return payload.isoformat()
    if isinstance(payload, Decimal):
        return format(payload, "f")
    return payload


__all__ = [
    "OutputFormat",
    "OutputFormatRefusedError",
    "OutputRenderingError",
    "RenderedCommandOutput",
    "jsonable_output_payload",
    "render_command_output",
]
