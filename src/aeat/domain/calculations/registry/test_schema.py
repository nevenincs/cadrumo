"""Real-behaviour tests for the registry _schema module.

Exercises InputKind validation through the CasillaDefinition pydantic
model so every claim about the StrEnum boundary is enforced by the
actual production model, not by a standalone enum construction.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ._schema import CasillaDefinition, InputKind

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

# ---------------------------------------------------------------------------
# Shared fixture constants — pattern mirrors test_referential_integrity
# ---------------------------------------------------------------------------

_DUMMY_LEGAL_ID = "lirpf:art-test"
_DUMMY_SOURCE_ID = "aeat-test-source-001"


# ---------------------------------------------------------------------------
# InputKind enum membership tests
# ---------------------------------------------------------------------------


def test_input_kind_members_have_expected_values() -> None:
    """Each InputKind member carries the TOML-authoritative string value."""
    assert InputKind.MANUAL == "manual"
    assert InputKind.BOUND == "bound"
    assert InputKind.COMPUTED == "computed"
    assert InputKind.INFORMATIONAL == "informational"


def test_input_kind_is_str() -> None:
    """StrEnum members are instances of str — serialisation-transparent."""
    for member in InputKind:
        assert isinstance(member, str), f"{member!r} is not a str instance"


# ---------------------------------------------------------------------------
# CasillaDefinition round-trip: each valid InputKind member
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "member, raw_string",
    [
        (InputKind.MANUAL, "manual"),
        (InputKind.BOUND, "bound"),
        (InputKind.COMPUTED, "computed"),
        (InputKind.INFORMATIONAL, "informational"),
    ],
)
def test_casilla_roundtrip_valid_input_kind(member: InputKind, raw_string: str) -> None:
    """Constructor accepts each member string and model_dump round-trips it."""
    # CasillaDefinition constructor (strict-mode pydantic) accepts string
    # literals for StrEnum fields — matching TOML-ingest behaviour.
    if member == InputKind.COMPUTED:
        casilla = CasillaDefinition(
            id="01",
            number="01",
            label="Test casilla",
            section=("test",),
            input_kind=raw_string,  # type: ignore[arg-type]  # tests TOML-string coercion path
            formula="test.formula",
            legal_refs=(_DUMMY_LEGAL_ID,),
            source_refs=(_DUMMY_SOURCE_ID,),
        )
    elif member == InputKind.BOUND:
        casilla = CasillaDefinition(
            id="01",
            number="01",
            label="Test casilla",
            section=("test",),
            input_kind=raw_string,  # type: ignore[arg-type]  # tests TOML-string coercion path
            binding="test.binding",
            legal_refs=(_DUMMY_LEGAL_ID,),
            source_refs=(_DUMMY_SOURCE_ID,),
        )
    else:
        casilla = CasillaDefinition(
            id="01",
            number="01",
            label="Test casilla",
            section=("test",),
            input_kind=raw_string,  # type: ignore[arg-type]  # tests TOML-string coercion path
            legal_refs=(_DUMMY_LEGAL_ID,),
            source_refs=(_DUMMY_SOURCE_ID,),
        )

    assert casilla.input_kind == member
    assert isinstance(casilla.input_kind, InputKind)
    dumped = casilla.model_dump()
    # StrEnum serialises as its string value, not the enum repr
    assert dumped["input_kind"] == raw_string


# ---------------------------------------------------------------------------
# Rejection of unknown tokens
# ---------------------------------------------------------------------------


def test_casilla_rejects_unknown_input_kind() -> None:
    """CasillaDefinition raises ValidationError for an unrecognised input_kind token."""
    with pytest.raises(ValidationError):
        CasillaDefinition(
            id="01",
            number="01",
            label="Test casilla",
            section=("test",),
            input_kind="garbage",  # type: ignore[arg-type]
            legal_refs=(_DUMMY_LEGAL_ID,),
            source_refs=(_DUMMY_SOURCE_ID,),
        )


def test_casilla_rejects_empty_string_input_kind() -> None:
    """An empty string is not a valid InputKind member."""
    with pytest.raises(ValidationError):
        CasillaDefinition(
            id="01",
            number="01",
            label="Test casilla",
            section=("test",),
            input_kind="",  # type: ignore[arg-type]
            legal_refs=(_DUMMY_LEGAL_ID,),
            source_refs=(_DUMMY_SOURCE_ID,),
        )


def test_casilla_rejects_numeric_input_kind() -> None:
    """A numeric value is not a valid InputKind member."""
    with pytest.raises(ValidationError):
        CasillaDefinition(
            id="01",
            number="01",
            label="Test casilla",
            section=("test",),
            input_kind=42,  # type: ignore[arg-type]
            legal_refs=(_DUMMY_LEGAL_ID,),
            source_refs=(_DUMMY_SOURCE_ID,),
        )


# ---------------------------------------------------------------------------
# Default value
# ---------------------------------------------------------------------------


def test_casilla_default_input_kind_is_manual() -> None:
    """When input_kind is omitted, CasillaDefinition defaults to MANUAL."""
    casilla = CasillaDefinition(
        id="01",
        number="01",
        label="Test casilla",
        section=("test",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    assert casilla.input_kind is InputKind.MANUAL
    assert casilla.input_kind == "manual"
