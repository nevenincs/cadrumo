"""Real-behaviour tests for the registry _schema module.

Exercises InputKind validation through the CasillaDefinition pydantic
model so every claim about the StrEnum boundary is enforced by the
actual production model, not by a standalone enum construction.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import pytest
from pydantic import ValidationError

from .._schema import CasillaDefinition, CasillaFieldKind, ExportFieldDefinition, InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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
            input_kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
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
            input_kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
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
            input_kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
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
            input_kind="garbage",  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
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
            input_kind="",  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
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
            input_kind=42,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
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


# ---------------------------------------------------------------------------
# CasillaFieldKind enum surface — contract
# ---------------------------------------------------------------------------


class _FieldBase(TypedDict):
    """Typed kwargs shared by every ExportFieldDefinition test construction."""

    id: str
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"]
    required: bool
    padding: Literal["left_zero", "left_space", "right_space", "none"]
    justification: Literal["left", "right", "none"]
    signed: bool
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


_FIELD_BASE: _FieldBase = _FieldBase(
    id="f001",
    data_type="text",
    required=True,
    padding="none",
    justification="left",
    signed=False,
    legal_refs=(_DUMMY_LEGAL_ID,),
    source_refs=(_DUMMY_SOURCE_ID,),
)


def test_casilla_field_kind_members_have_expected_values() -> None:
    """Each CasillaFieldKind member carries the TOML-authoritative string value."""
    assert CasillaFieldKind.LITERAL == "literal"
    assert CasillaFieldKind.CASILLA == "casilla"
    assert CasillaFieldKind.BINDING == "binding"
    assert CasillaFieldKind.COMPUTED == "computed"
    assert CasillaFieldKind.DRAFT == "draft"
    assert CasillaFieldKind.FILLER == "filler"
    assert CasillaFieldKind.HEADER == "header"
    assert CasillaFieldKind.CHECKSUM == "checksum"


def test_casilla_field_kind_is_str() -> None:
    """StrEnum members are instances of str — serialisation-transparent."""
    for member in CasillaFieldKind:
        assert isinstance(member, str), f"{member!r} is not a str instance"


def _make_export_field_literal(raw_string: str, literal: str) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a LITERAL kind field."""
    return ExportFieldDefinition(
        **_FIELD_BASE,
        kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
        literal=literal,
    )


def _make_export_field_casilla(raw_string: str, casilla: str) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a CASILLA kind field."""
    return ExportFieldDefinition(
        **_FIELD_BASE,
        kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
        casilla=casilla,
    )


def _make_export_field_binding(raw_string: str, binding: str) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a BINDING kind field."""
    return ExportFieldDefinition(
        **_FIELD_BASE,
        kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
        binding=binding,
    )


def _make_export_field_filler(raw_string: str, length: int) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a FILLER kind field."""
    return ExportFieldDefinition(
        **_FIELD_BASE,
        kind=raw_string,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # tests TOML-string coercion path
        length=length,
    )


@pytest.mark.parametrize(
    "member, raw_string",
    [
        (CasillaFieldKind.LITERAL, "literal"),
        (CasillaFieldKind.CASILLA, "casilla"),
        (CasillaFieldKind.BINDING, "binding"),
        (CasillaFieldKind.FILLER, "filler"),
    ],
)
def test_export_field_roundtrip_valid_casilla_field_kind(
    member: CasillaFieldKind,
    raw_string: str,
) -> None:
    """ExportFieldDefinition accepts each member string and round-trips via model_dump."""
    if member == CasillaFieldKind.LITERAL:
        field = _make_export_field_literal(raw_string, "TEST")
    elif member == CasillaFieldKind.CASILLA:
        field = _make_export_field_casilla(raw_string, "01")
    elif member == CasillaFieldKind.BINDING:
        field = _make_export_field_binding(raw_string, "some.binding")
    else:
        field = _make_export_field_filler(raw_string, 10)
    assert field.kind == member
    assert isinstance(field.kind, CasillaFieldKind)
    dumped = field.model_dump()
    assert dumped["kind"] == raw_string


def test_export_field_rejects_unknown_kind() -> None:
    """ExportFieldDefinition raises ValidationError for an unrecognised kind token."""
    with pytest.raises(ValidationError):
        ExportFieldDefinition(**_FIELD_BASE, kind="bogus_kind")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_export_field_rejects_empty_string_kind() -> None:
    """An empty string is not a valid CasillaFieldKind member."""
    with pytest.raises(ValidationError):
        ExportFieldDefinition(**_FIELD_BASE, kind="")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_export_field_rejects_numeric_kind() -> None:
    """A numeric value is not a valid CasillaFieldKind member."""
    with pytest.raises(ValidationError):
        ExportFieldDefinition(**_FIELD_BASE, kind=99)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
