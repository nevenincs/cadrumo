"""Central command-output rendering contract.

:func:`render_command_output` is the shared text/JSON transport boundary
for command handlers that do not need a full :class:`SchemaEnvelope`.
It returns :class:`RenderedCommandOutput`, chooses an :class:`OutputFormat`,
and applies :func:`cadrumo.core.redaction.redact_for_cli_output` or
:func:`cadrumo.core.redaction.redact_structured_for_cli_output` before text
reaches stdout.

Envelope-aware commands bypass this bare renderer in JSON mode through
:func:`cadrumo.core.json_contract.emit_json_success`, but both paths consult
:func:`reveal_cli_identifiers_opt_in` so profile and bucket identifier redaction
cannot drift between direct payload rendering and the
:class:`~cadrumo.core.json_contract.SchemaEnvelope` path.

This module returns rendered text only; CLI transports own stdout/stderr writes
and exit-code handling. It also owns success-output redaction only. Error
envelopes, log records, and observability sinks use their own redaction
boundaries.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from .errors.hierarchy import CadrumoError
from .models import STRICT_FROZEN_CONFIG
from .redaction.rules import redact_for_cli_output, redact_structured_for_cli_output


class OutputRenderingError(CadrumoError):
    """Raised when command output cannot be rendered safely.

    Used after payload normalization when a value still cannot be serialized as
    CLI success output. It is not the invalid-format error; unsupported format
    strings raise :class:`OutputFormatRefusedError` before rendering starts.
    """


class OutputFormatRefusedError(CadrumoError):
    """Raised when a command requests an unsupported :class:`OutputFormat`."""


class OutputFormat(StrEnum):
    """Accepted command output formats."""

    TEXT = "text"
    JSON = "json"


class RenderedCommandOutput(BaseModel):
    """Rendered, already-redacted output document returned to CLI transports.

    ``text`` is the complete body to emit. The original payload is deliberately
    not retained so downstream transports cannot accidentally bypass the central
    success-output redaction pass.
    """

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

    JSON output normalises ``payload`` through :func:`jsonable_output_payload`
    and applies structured CLI redaction before serialization. Text output
    ignores ``payload`` and joins the supplied ``lines`` after applying
    line-oriented CLI redaction.

    The helper does not write to stdout, translate messages, choose exit codes,
    or register JSON schemas. Callers supply localized text lines or typed
    payloads, then emit the returned :class:`RenderedCommandOutput` through the
    CLI transport layer.

    Returns:
        A :class:`RenderedCommandOutput` containing the format and the
        rendered, redacted text body.

    Raises:
        OutputFormatRefusedError: If ``format_name`` is not one of the accepted
            :class:`OutputFormat` values.
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

    Reading :func:`cadrumo.core.config.load_settings` here keeps the policy
    decision at the central success-output privacy boundary and keeps the
    pure redaction module free of a Settings dependency. Default off
    preserves the paste-safe placeholder
    behaviour; an operator sets ``CADRUMO_CLI_REVEAL_IDENTIFIERS=1`` to opt out.
    Both success-output emitters — :func:`render_command_output` and the JSON
    envelope :func:`cadrumo.core.json_contract.emit_json_success` — consult this
    one resolver so the two transports cannot diverge.

    The opt-in reveals only opaque profile and bucket identifiers. Tax
    identities, URLs, tokens, and secure-object keys remain redacted by the
    CLI redaction profile.
    """
    from .config import load_settings
    from .config_state_root import FormerProductStateError

    try:
        return load_settings().cadrumo_cli_reveal_identifiers
    except FormerProductStateError:
        # The privacy default is fail-closed. Metadata output remains available
        # while Cadrumo refuses a former product-state directory.
        return False


def _json_default(value: object) -> object:
    """Serialize residual safe scalar types or raise a typed rendering error.

    Most project payloads are normalized by :func:`jsonable_output_payload`
    before ``json.dumps`` reaches this hook. Reaching this function with an
    unknown object means the command result escaped its declared JSON shape, so
    the renderer fails closed with :class:`OutputRenderingError`.
    """
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, set | frozenset):
        # Element types are heterogeneous scalars by construction (this is the
        # last-resort JSON fallback for whatever residual set/frozenset content
        # reaches here), so there is no single comparable element type to sort
        # on directly; the string form is genuinely the deterministic ordering
        # key for an otherwise-unordered, possibly-mixed-type set.
        return sorted(value, key=str)
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
    :mod:`cadrumo.core.tests.test_json_envelope_roundtrip` pin the correct usage.

    This is a transport normalization helper, not a domain contract authority.
    Command-specific payload classes own field semantics and ordering; this
    helper only prepares already-selected output values for redaction and JSON
    serialization.
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
