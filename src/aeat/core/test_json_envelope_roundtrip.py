"""Strict roundtrip across the CLI ``--json`` envelope boundary.

Every ``--json`` response from the CLI is rendered through
:class:`SchemaEnvelope` so external consumers (operator tooling, the
audit pipeline, monitoring) can rely on a stable outer shape regardless
of the inner command result. This file asserts that the envelope shape
itself survives the emit / parse cycle: a SchemaEnvelope wrapping a
populated :class:`OutputSchema` instance, written through
:func:`emit_json_success`, must re-parse into a SchemaEnvelope of the
same inner type with strict pydantic equality.

A regression that drops the ``warnings`` list, mis-serialises a typed
tuple field on the inner payload, or breaks the envelope's pinned
``schema_version`` surfaces as a strict equality failure.
"""

from __future__ import annotations

import io
import json

import pytest

from .json_contract import OutputSchema, SchemaEnvelope, emit_json_success

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


class _ProvenancePayload(OutputSchema):
    """Inline OutputSchema with deep-data tuple fields.

    Avoids coupling the test to a specific command's evolving payload
    shape while still exercising the kinds of fields that surface
    cross-domain data: tuple-of-str provenance, optional nullable
    str, and a non-empty default tuple field.
    """

    casilla_id: str
    value: str
    formula_id: str | None = None
    operand_refs: tuple[str, ...] = ()
    legal_refs: tuple[str, ...] = ()


def test_schema_envelope_full_roundtrip_via_json_dump_and_load() -> None:
    """A SchemaEnvelope wrapping a populated OutputSchema round-trips strictly.

    Uses ``model_dump_json`` / ``model_validate_json`` rather than
    ``emit_json_success`` so the test asserts the pydantic round-trip
    independently of the stdout-flush behaviour.
    """

    result = _ProvenancePayload(
        casilla_id="iva.resultado",
        value="12345.67",
        formula_id="iva.formula.resultado",
        operand_refs=("iva.devengado", "iva.deducible"),
        legal_refs=("LIVA.art-94",),
    )
    original = SchemaEnvelope[_ProvenancePayload](
        command="app modelo formulas",
        result=result,
        warnings=["deprecated: --format text"],
    )

    roundtripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(
        original.model_dump_json(),
    )

    assert roundtripped == original
    assert roundtripped.schema_version == "1"
    assert roundtripped.command == "app modelo formulas"
    assert roundtripped.result.operand_refs == ("iva.devengado", "iva.deducible")
    assert roundtripped.result.legal_refs == ("LIVA.art-94",)
    assert roundtripped.warnings == ["deprecated: --format text"]


def test_emit_json_success_emits_parseable_envelope_to_stream() -> None:
    """The bytes emit_json_success writes to stdout re-parse into a SchemaEnvelope.

    Captures the emitted text into an :class:`io.StringIO` stream so
    the test exercises the real :func:`emit_json_document` write path
    without touching stdout. The captured JSON must:

    * decode as a valid JSON document
    * carry the pinned schema_version and supplied command
    * round-trip back into the same SchemaEnvelope through pydantic
      validation
    """

    result = _ProvenancePayload(
        casilla_id="rendimiento_neto",
        value="40000.00",
        operand_refs=("ingresos", "gastos_deducibles"),
    )
    buffer = io.StringIO()
    emit_json_success(
        "app modelo work calculate",
        result,
        warnings=[],
        stream=buffer,
    )

    raw = buffer.getvalue()
    assert raw, "emit_json_success wrote nothing to the stream"

    decoded = json.loads(raw)
    assert decoded["schema_version"] == "1"
    assert decoded["command"] == "app modelo work calculate"
    assert decoded["warnings"] == []

    # The emitted bytes re-parse cleanly through SchemaEnvelope's
    # typed JSON validator. Using ``model_validate_json`` rather than
    # ``model_validate(json.loads(...))`` is intentional: the typed
    # boundary is the JSON bytes, not a pre-parsed dict, and pydantic
    # only knows to coerce list -> tuple when it owns the parse.
    roundtripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(raw)
    assert roundtripped.result == result
    assert roundtripped.result.operand_refs == ("ingresos", "gastos_deducibles")


def test_schema_envelope_rejects_unknown_outer_keys() -> None:
    """Extra keys on the envelope must be rejected at validate time.

    Guards the strict ``extra='forbid'`` contract. Without this,
    a producer drift that adds a top-level key would silently land
    in caller payloads instead of failing fast at the contract
    boundary.
    """

    from pydantic import ValidationError as _PydValidationError

    with pytest.raises(_PydValidationError):
        SchemaEnvelope[_ProvenancePayload].model_validate(
            {
                "schema_version": "1",
                "command": "app modelo formulas",
                "result": {
                    "casilla_id": "01",
                    "value": "100.00",
                },
                "warnings": [],
                "metadata": {"hidden": "extra"},  # not in the envelope schema
            }
        )
