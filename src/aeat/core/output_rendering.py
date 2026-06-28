"""Central command-output rendering contract.

:func:`render_command_output` is the shared text/JSON transport boundary
for command handlers that do not need a full :class:`SchemaEnvelope`.
It returns :class:`RenderedCommandOutput`, chooses an :class:`OutputFormat`,
and applies :func:`aeat.core.redaction.redact_for_cli_output` or
:func:`aeat.core.redaction.redact_structured_for_cli_output` before text
reaches stdout.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG
from .errors import AeatError
from .redaction import redact_for_cli_output, redact_structured_for_cli_output


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

    model_config = STRICT_FROZEN_CONFIG

    format: OutputFormat
    text: str = Field(default="")


def render_command_output(
    *,
    format_name: str,
    payload: object,
    lines: Iterable[str],
) -> RenderedCommandOutput:
    """Render a payload or line iterator according to the root output format.

    Returns:
        A :class:`RenderedCommandOutput` containing the format and the
        rendered, redacted text body.
    """
    try:
        output_format = OutputFormat(format_name.strip().lower() or OutputFormat.TEXT.value)
    except ValueError as exc:
        raise OutputFormatRefusedError(
            context={"format_name": format_name, "expected": "text,json"},
            translated_message="errors.refused.refused_output_format",
        ) from exc
    reveal_identifiers = reveal_cli_identifiers_opt_in()
    if output_format is OutputFormat.JSON:
        redacted_payload = redact_structured_for_cli_output(
            jsonable_output_payload(payload),
            reveal_identifiers=reveal_identifiers,
        )
        return RenderedCommandOutput(
            format=output_format,
            text=json.dumps(redacted_payload, default=_json_default, ensure_ascii=False),
        )
    return RenderedCommandOutput(
        format=output_format,
        text="\n".join(redact_for_cli_output(line, reveal_identifiers=reveal_identifiers) for line in lines),
    )


def reveal_cli_identifiers_opt_in() -> bool:
    """Resolve the profile/bucket identifier reveal opt-out at the output boundary.

    Reading :func:`aeat.core.config.load_settings` here keeps the policy
    decision at the central success-output privacy boundary (per the
    centralized-output-redaction ADR) and keeps the pure redaction module free
    of a Settings dependency. Default off preserves the paste-safe placeholder
    behaviour; an operator sets ``AEAT_CLI_REVEAL_IDENTIFIERS=1`` to opt out.
    Both success-output emitters — :func:`render_command_output` and the JSON
    envelope :func:`aeat.core.json_contract.emit_json_success` — consult this
    one resolver so the two transports cannot diverge.
    """
    from .config import load_settings

    return load_settings().aeat_cli_reveal_identifiers


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, set | frozenset):
        return sorted(value)
    raise OutputRenderingError(
        context={"type_name": type(value).__name__},
        translated_message="errors.internal.internal_output_rendering",
    )


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
    "reveal_cli_identifiers_opt_in",
]
