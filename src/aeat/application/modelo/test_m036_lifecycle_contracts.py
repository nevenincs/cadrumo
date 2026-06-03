"""Tests for the Modelo 036 declarative-recording verb contracts.

Authority: ``2026-06-03-m036-lifecycle-verbs-research``. The
contracts MUST type the closed-value axis (CensoModeloEventKind)
as its enum per the architecture-boundaries rule, MUST accept
optional sede_justificante / note, and MUST pin the
declaration_id shape to a 64-char lowercase SHA-256 hex pattern.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ...domain.calculations.registry import CensoModeloEventKind
from ._m036_lifecycle import M036DeclarationCommand, M036DeclarationResult, derive_m036_declaration_id

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_command_accepts_minimum_fields() -> None:
    """profile_id + event_kind + declared_on construct a valid command."""
    cmd = M036DeclarationCommand(
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
    )

    assert cmd.profile_id == "profile-test"
    assert cmd.event_kind is CensoModeloEventKind.ALTA
    assert cmd.sede_justificante is None
    assert cmd.note is None


def test_command_carries_optional_justificante_and_note() -> None:
    """sede_justificante + note carry through when supplied."""
    cmd = M036DeclarationCommand(
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante="AEAT-ACUSE-2026-0000123",
        note="Modificación de domicilio fiscal",
    )

    assert cmd.sede_justificante == "AEAT-ACUSE-2026-0000123"
    assert cmd.note == "Modificación de domicilio fiscal"


def test_command_rejects_unknown_event_kind() -> None:
    """The closed-value axis rejects strings outside the AEAT-published set."""
    with pytest.raises(ValidationError):
        M036DeclarationCommand(
            profile_id="profile-test",
            event_kind="cancelacion",  # type: ignore[arg-type]
            declared_on=date(2026, 6, 3),
        )


def test_result_pins_declaration_id_to_64_char_lowercase_hex() -> None:
    """The declaration_id shape mirrors the SHA-256 hex contract."""
    digest = "a" * 64
    result = M036DeclarationResult(
        declaration_id=digest,
        profile_id="profile-test",
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
            profile_id="profile-test",
            event_kind=CensoModeloEventKind.ALTA,
            declared_on=date(2026, 6, 3),
            recorded_at=datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC),
        )


def test_derive_declaration_id_is_64_char_lowercase_hex() -> None:
    """The derived id matches the result-model declaration_id pattern."""
    declaration_id = derive_m036_declaration_id(
        profile_id="profile-test",
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
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante="ACUSE-123",
    )
    b = derive_m036_declaration_id(
        profile_id="profile-test",
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
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )
    confirmed = derive_m036_declaration_id(
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante="ACUSE-XYZ",
    )

    assert draft != confirmed


def test_derive_declaration_id_distinguishes_event_kind() -> None:
    """Same profile + same date but different event_kind → distinct ids."""
    alta = derive_m036_declaration_id(
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.ALTA,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )
    modificacion = derive_m036_declaration_id(
        profile_id="profile-test",
        event_kind=CensoModeloEventKind.MODIFICACION,
        declared_on=date(2026, 6, 3),
        sede_justificante=None,
    )

    assert alta != modificacion
