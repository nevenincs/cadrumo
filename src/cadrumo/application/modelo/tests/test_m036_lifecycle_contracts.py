"""Tests for the Modelo 036 declarative-recording verb contracts.

The contracts MUST type the closed-value axis (CensoModeloEventKind)
as its enum, MUST accept optional sede_justificante / note, and MUST
pin the declaration_id shape to a 64-char lowercase SHA-256 hex pattern.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from .._m036_lifecycle import M036DeclarationCommand, M036DeclarationResult, derive_m036_declaration_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE_ID = "31313131-3131-4131-8131-313131313131"


def test_command_accepts_minimum_fields() -> None:
    """profile_id + event_kind + declared_on construct a valid command."""
    cmd = M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
    )

    assert cmd.profile_id == _PROFILE_ID
    assert cmd.event_kind is CensoModeloEventKind.ALTA
    assert cmd.sede_justificante is None
    assert cmd.note is None


def test_command_carries_optional_justificante_and_note() -> None:
    """sede_justificante + note carry through when supplied."""
    cmd = M036DeclarationCommand(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante="AEAT-ACUSE-2026-0000123",
        note="Modificación de domicilio fiscal",
    )

    assert cmd.sede_justificante == "AEAT-ACUSE-2026-0000123"
    assert cmd.note == "Modificación de domicilio fiscal"


def test_command_schema_exposes_external_filing_routes_and_optional_electronic_justificante() -> None:
    """The public command schema keeps office filings distinct from electronic receipt evidence."""
    schema = M036DeclarationCommand.model_json_schema()
    description = " ".join(schema["description"].split())

    assert "through AEAT Sede or in person at a competent AEAT office" in description
    assert schema["properties"]["sede_justificante"]["description"] == (
        "Optional electronic AEAT justificante identifier; omit it for an office filing or when unavailable."
    )
    assert "sede_justificante" not in schema["required"]


def test_command_rejects_unknown_event_kind() -> None:
    """The closed-value axis rejects strings outside the AEAT-published set."""
    with pytest.raises(ValidationError):
        M036DeclarationCommand.model_validate(
            {
                "profile_id": _PROFILE_ID,
                "event_kind": "cancelacion",
                "declared_on": date(2026, 6, 3),
            },
        )


def test_result_pins_declaration_id_to_64_char_lowercase_hex() -> None:
    """The declaration_id shape mirrors the SHA-256 hex contract."""
    digest = "a" * 64
    result = M036DeclarationResult(
        declaration_id=digest,
        bucket_id="bucket-test",
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=date(2026, 6, 3),
        recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
    )

    assert len(result.declaration_id) == 64
    assert result.declaration_id == result.declaration_id.lower()


@pytest.mark.parametrize(
    "bad_id",
    [
        "short",  # too short
        "z" * 64,  # invalid hex char
        "A" * 64,  # uppercase not allowed
        "a" * 63,  # off-by-one
        "a" * 65,  # off-by-one
    ],
)
def test_result_rejects_non_sha256_declaration_id(bad_id: str) -> None:
    """Anything that is not a 64-char lowercase hex string is refused."""
    with pytest.raises(ValidationError):
        M036DeclarationResult(
            declaration_id=bad_id,
            bucket_id="bucket-test",
            profile_id=_PROFILE_ID,
            event_kind=CensoModeloEventKind.ALTA,
            declared_on=date(2026, 6, 3),
            recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
        )


def test_derive_declaration_id_is_64_char_lowercase_hex() -> None:
    """The derived id matches the result-model declaration_id pattern."""
    declaration_id = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )

    assert len(declaration_id) == 64
    assert declaration_id == declaration_id.lower()
    int(declaration_id, 16)


def test_derive_declaration_id_is_deterministic() -> None:
    """Same tuple → same id (idempotent re-declaration writes the same row)."""
    a = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante="ACUSE-123",
    )
    b = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante="ACUSE-123",
    )

    assert a == b


def test_derive_declaration_id_distinguishes_justificante_presence() -> None:
    """Pre-acuse draft and post-acuse record hash to distinct ids.

    A second invocation with the acuse acquired must NOT silently
    coalesce with the pre-acuse draft — it's a new declaration record.
    """
    draft = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )
    confirmed = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante="ACUSE-XYZ",
    )

    assert draft != confirmed


def test_derive_declaration_id_distinguishes_event_kind() -> None:
    """Same profile + same date but different event_kind → distinct ids."""
    alta = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )
    modificacion = derive_m036_declaration_id(
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )

    assert alta != modificacion


def test_result_carries_bucket_id_field() -> None:
    """``bucket_id`` is a typed, non-optional field on the result."""
    result = M036DeclarationResult(
        declaration_id="a" * 64,
        bucket_id="bucket-test",
        profile_id="31313131-3131-4131-8131-313131313131",
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
    )
    assert result.bucket_id == "bucket-test"


def test_result_rejects_missing_bucket_id() -> None:
    """A result authored without bucket_id fails validation."""
    with pytest.raises(ValidationError):
        M036DeclarationResult.model_validate(
            {
                "declaration_id": "a" * 64,
                "profile_id": _PROFILE_ID,
                "event_kind": CensoModeloEventKind.ALTA,
                "declared_on": date(2026, 6, 3),
                "recorded_at": datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
            },
        )


def test_snapshot_id_computed_field_aliases_declaration_id() -> None:
    """``snapshot_id`` is a read-only computed-field alias of ``declaration_id``."""
    declaration_id = "b" * 64
    result = M036DeclarationResult(
        declaration_id=declaration_id,
        bucket_id="bucket-test",
        profile_id="31313131-3131-4131-8131-313131313131",
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
    )
    assert result.snapshot_id == declaration_id
    assert result.snapshot_id == result.declaration_id


def test_result_roundtrips_through_strict_json_with_bucket_id() -> None:
    """A populated record round-trips through model_validate_json with no drift."""
    original = M036DeclarationResult(
        declaration_id=derive_m036_declaration_id(
            profile_id="31313131-3131-4131-8131-313131313131",
            event_kind=CensoModeloEventKind.ALTA,
            declared_on=date(2026, 6, 3),
            sede_justificante="ACUSE-RT-001",
        ),
        bucket_id="bucket-rt-001",
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante="ACUSE-RT-001",
        recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
    )
    serialised = original.model_dump_json()
    restored = M036DeclarationResult.model_validate_json(serialised)
    assert restored == original
    assert restored.snapshot_id == original.declaration_id


def test_result_serialisation_omits_snapshot_id_runtime_alias() -> None:
    """The runtime ``snapshot_id`` alias does NOT appear in the JSON envelope.

    The alias is a Python-side property for ``SecureSnapshotRepository``
    attribute access; serialising it into the envelope would duplicate the
    declaration_id key on the wire and break the symmetric strict-JSON
    round-trip (``extra="forbid"`` refuses the duplicate on load).
    """
    import json as _json

    result = M036DeclarationResult(
        declaration_id="c" * 64,
        bucket_id="bucket-test",
        profile_id=_PROFILE_ID,
        event_kind=CensoModeloEventKind.BAJA,
        declared_on=date(2026, 6, 3),
        recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
    )
    payload = _json.loads(result.model_dump_json())
    assert "snapshot_id" not in payload
    assert payload["declaration_id"] == "c" * 64
    assert payload["bucket_id"] == "bucket-test"
    # The runtime attribute is still reachable post-load via the property.
    assert result.snapshot_id == result.declaration_id


def test_result_anti_tautology_proof_load_refuses_missing_bucket_id() -> None:
    """A serialised record mutated to drop bucket_id MUST refuse re-validation.

    Boundary anti-tautology proof per the roundtrip-discipline rule:
    bucket-scope cannot be a defaultable field or the storage cross-check
    silently passes against an unscoped payload.
    """
    import json as _json

    result = M036DeclarationResult(
        declaration_id="d" * 64,
        bucket_id="bucket-tautology-test",
        profile_id="31313131-3131-4131-8131-313131313131",
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
    )
    payload = _json.loads(result.model_dump_json())
    del payload["bucket_id"]
    with pytest.raises(ValidationError):
        M036DeclarationResult.model_validate(payload)
