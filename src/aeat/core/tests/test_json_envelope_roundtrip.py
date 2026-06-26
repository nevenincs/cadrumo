"""Strict roundtrip across the CLI ``--json`` envelope boundary.

Every ``--json`` response from the CLI is rendered through
:class:`SchemaEnvelope` so external consumers (operator tooling, the
audit pipeline, monitoring) can rely on a stable outer shape regardless
of the inner command result. This file asserts that the envelope shape
itself survives the emit / parse cycle: a SchemaEnvelope wrapping a
populated :class:`OutputSchema` instance, written through
:func:`emit_json_success`, must re-parse into a SchemaEnvelope of the
same inner type with strict pydantic equality.

A regression that drops the ``notices`` list, mis-serialises a typed
tuple field on the inner payload, or breaks the envelope's pinned
``schema_version`` surfaces as a strict equality failure.
"""

from __future__ import annotations

import io
import json

import pytest

from .. import CasillaId, validated_casilla_id
from ..json_contract import (
    ENVELOPE_SCHEMA_VERSION,
    EnvelopeStatus,
    Notice,
    NoticeSeverity,
    OutputSchema,
    SchemaEnvelope,
    emit_json_success,
)
from ..redaction import CLI_BUCKET_ID_PLACEHOLDER, CLI_OBJECT_KEY_PLACEHOLDER, CLI_PROFILE_ID_PLACEHOLDER

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROFILE_ID = "123e4567-e89b-12d3-a456-426614174000"
_NIF = "12345678Z"
_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
_URL = "https://example.test/private/path?token=secret"
_OBJECT_KEY = "wallet:2026-secret"
_OTHER_OBJECT_KEY = "wallet:2026-other"


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"JSON envelope fixture casilla key {value!r} is not a CasillaId") from exc


_IVA_DEVENGADO_CASILLA: CasillaId = _casilla_id("iva.devengado")
_IVA_DEDUCIBLE_CASILLA: CasillaId = _casilla_id("iva.deducible")
_IVA_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_RENDIMIENTO_NETO_CASILLA: CasillaId = _casilla_id("rendimiento_neto")
_INGRESOS_CASILLA: CasillaId = _casilla_id("ingresos")
_GASTOS_DEDUCIBLES_CASILLA: CasillaId = _casilla_id("gastos_deducibles")
_SIMPLE_CASILLA: CasillaId = _casilla_id("01")
_IVA_RESULTADO_OPERANDS = (_IVA_DEVENGADO_CASILLA, _IVA_DEDUCIBLE_CASILLA)
_RENDIMIENTO_NETO_OPERANDS = (_INGRESOS_CASILLA, _GASTOS_DEDUCIBLES_CASILLA)


class _ProvenancePayload(OutputSchema):
    """Inline OutputSchema with deep-data tuple fields.

    Avoids coupling the test to a specific command's evolving payload
    shape while still exercising the kinds of fields that surface
    cross-domain data: tuple-of-str provenance, optional nullable
    str, and a non-empty default tuple field.
    """

    casilla_id: CasillaId
    value: str
    formula_id: str | None = None
    operand_refs: tuple[CasillaId, ...] = ()
    operand_casilla_refs: tuple[CasillaId, ...] = ()
    legal_refs: tuple[str, ...] = ()


class _SensitivePayload(OutputSchema):
    profile_id: str
    bucket_id: str
    object_key: str
    tax_id: str
    callback: str
    authorization: str
    keyed_lookup: dict[str, str]


def test_schema_envelope_full_roundtrip_via_json_dump_and_load() -> None:
    """A SchemaEnvelope wrapping a populated OutputSchema round-trips strictly.

    Uses ``model_dump_json`` / ``model_validate_json`` rather than
    ``emit_json_success`` so the test asserts the pydantic round-trip
    independently of the stdout-flush behaviour.
    """

    result = _ProvenancePayload(
        casilla_id=_IVA_RESULTADO_CASILLA,
        value="12345.67",
        formula_id="iva.formula.resultado",
        operand_refs=_IVA_RESULTADO_OPERANDS,
        operand_casilla_refs=_IVA_RESULTADO_OPERANDS,
        legal_refs=("LIVA.art-94",),
    )
    original = SchemaEnvelope[_ProvenancePayload](
        command="app modelo formulas",
        status=EnvelopeStatus.WARNING,
        result=result,
        notices=[
            Notice(
                severity=NoticeSeverity.WARNING,
                code="modelo.formulas.deprecated_format",
                message="deprecated: --format text",
            ),
        ],
    )

    roundtripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(
        original.model_dump_json(),
    )

    assert roundtripped == original
    assert roundtripped.schema_version == ENVELOPE_SCHEMA_VERSION
    assert roundtripped.command == "app modelo formulas"
    assert roundtripped.status is EnvelopeStatus.WARNING
    assert roundtripped.result.operand_refs == _IVA_RESULTADO_OPERANDS
    assert roundtripped.result.operand_casilla_refs == _IVA_RESULTADO_OPERANDS
    assert roundtripped.result.legal_refs == ("LIVA.art-94",)
    assert roundtripped.notices[0].message == "deprecated: --format text"


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
        casilla_id=_RENDIMIENTO_NETO_CASILLA,
        value="40000.00",
        operand_refs=_RENDIMIENTO_NETO_OPERANDS,
        operand_casilla_refs=_RENDIMIENTO_NETO_OPERANDS,
    )
    buffer = io.StringIO()
    emit_json_success(
        "app modelo work calculate",
        result,
        notices=[],
        stream=buffer,
    )

    raw = buffer.getvalue()
    assert raw, "emit_json_success wrote nothing to the stream"

    decoded = json.loads(raw)
    assert decoded["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert decoded["command"] == "app modelo work calculate"
    assert decoded["status"] == EnvelopeStatus.SUCCESS.value
    assert decoded["notices"] == []

    # The emitted bytes re-parse cleanly through SchemaEnvelope's
    # typed JSON validator. Using ``model_validate_json`` rather than
    # ``model_validate(json.loads(...))`` is intentional: the typed
    # boundary is the JSON bytes, not a pre-parsed dict, and pydantic
    # only knows to coerce list -> tuple when it owns the parse.
    roundtripped = SchemaEnvelope[_ProvenancePayload].model_validate_json(raw)
    assert roundtripped.result == result
    assert roundtripped.result.operand_refs == _RENDIMIENTO_NETO_OPERANDS
    assert roundtripped.result.operand_casilla_refs == _RENDIMIENTO_NETO_OPERANDS


def test_emit_json_success_redacts_sensitive_values_without_breaking_envelope_shape() -> None:
    result = _SensitivePayload(
        profile_id=_PROFILE_ID,
        bucket_id="bucket-alpha",
        object_key=_OBJECT_KEY,
        tax_id=_NIF,
        callback=_URL,
        authorization=f"bearer {_JWT}",
        keyed_lookup={
            _OBJECT_KEY: "first object",
            _OTHER_OBJECT_KEY: "second object",
        },
    )
    buffer = io.StringIO()
    emit_json_success(
        "app secure audit",
        result,
        notices=[
            Notice(severity=NoticeSeverity.WARNING, code="secure.audit.callback", message=f"callback {_URL}"),
            Notice(severity=NoticeSeverity.WARNING, code="secure.audit.bearer", message=f"bearer {_JWT}"),
        ],
        stream=buffer,
    )

    raw = buffer.getvalue()
    decoded = json.loads(raw)

    assert set(decoded) == {"schema_version", "command", "status", "result", "notices"}
    assert decoded["schema_version"] == ENVELOPE_SCHEMA_VERSION
    assert decoded["status"] == EnvelopeStatus.WARNING.value
    assert decoded["command"] == "app secure audit"
    assert decoded["result"] == {
        "profile_id": CLI_PROFILE_ID_PLACEHOLDER,
        "bucket_id": CLI_BUCKET_ID_PLACEHOLDER,
        "object_key": CLI_OBJECT_KEY_PLACEHOLDER,
        "tax_id": "sha256:1c9f9632",
        "callback": "https://example.test",
        "authorization": "token:sha256:0a2c77ea",
        "keyed_lookup": {
            CLI_OBJECT_KEY_PLACEHOLDER: "first object",
            f"{CLI_OBJECT_KEY_PLACEHOLDER}#2": "second object",
        },
    }
    assert decoded["notices"][0]["message"] == "callback https://example.test"
    assert decoded["notices"][1]["message"] == "token:sha256:0a2c77ea"
    assert _PROFILE_ID not in raw
    assert _NIF not in raw
    assert _JWT not in raw
    assert _URL not in raw
    assert _OBJECT_KEY not in raw
    assert _OTHER_OBJECT_KEY not in raw

    roundtripped = SchemaEnvelope[_SensitivePayload].model_validate_json(raw)
    assert roundtripped.result.profile_id == CLI_PROFILE_ID_PLACEHOLDER
    assert roundtripped.result.keyed_lookup[f"{CLI_OBJECT_KEY_PLACEHOLDER}#2"] == "second object"


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
                "schema_version": ENVELOPE_SCHEMA_VERSION,
                "command": "app modelo formulas",
                "status": EnvelopeStatus.SUCCESS.value,
                "result": {
                    "casilla_id": _SIMPLE_CASILLA,
                    "value": "100.00",
                },
                "notices": [],
                "metadata": {"hidden": "extra"},  # not in the envelope schema
            },
        )
