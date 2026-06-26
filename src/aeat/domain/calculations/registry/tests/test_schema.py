"""Real-behaviour tests for the registry _schema module.

Exercises InputKind validation through the CasillaDefinition pydantic
model so every claim about the StrEnum boundary is enforced by the
actual production model, not by a standalone enum construction.
"""

from __future__ import annotations

from typing import Literal, TypedDict

import pytest
from pydantic import ValidationError

from .._ids import CasillaId, validated_casilla_id
from .._schema import (
    AlgorithmBindingDefinition,
    CasillaDefinition,
    CasillaFieldKind,
    ConstructDefinition,
    ExportFieldDefinition,
    FormulaDefinition,
    FormulaExpression,
    InputKind,
    RelationDefinition,
    VerificationExpectationDefinition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Shared fixture constants — pattern mirrors test_referential_integrity
# ---------------------------------------------------------------------------

_DUMMY_LEGAL_ID = "lirpf:art-test"
_DUMMY_SOURCE_ID = "aeat-test-source-001"
_DUMMY_CASILLA_ID: CasillaId = validated_casilla_id("01", surface="_DUMMY_CASILLA_ID")


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
    # Validate TOML-shaped payloads so raw string enum coercion stays on the
    # same boundary production registry loading uses.
    if member == InputKind.COMPUTED:
        payload: dict[str, object] = {
            "id": _DUMMY_CASILLA_ID,
            "number": "01",
            "label": "Test casilla",
            "section": ("test",),
            "input_kind": raw_string,
            "formula": "test.formula",
            "legal_refs": (_DUMMY_LEGAL_ID,),
            "source_refs": (_DUMMY_SOURCE_ID,),
        }
    elif member == InputKind.BOUND:
        payload = {
            "id": _DUMMY_CASILLA_ID,
            "number": "01",
            "label": "Test casilla",
            "section": ("test",),
            "input_kind": raw_string,
            "binding": "test.binding",
            "legal_refs": (_DUMMY_LEGAL_ID,),
            "source_refs": (_DUMMY_SOURCE_ID,),
        }
    else:
        payload = {
            "id": _DUMMY_CASILLA_ID,
            "number": "01",
            "label": "Test casilla",
            "section": ("test",),
            "input_kind": raw_string,
            "legal_refs": (_DUMMY_LEGAL_ID,),
            "source_refs": (_DUMMY_SOURCE_ID,),
        }
    casilla = CasillaDefinition.model_validate(payload)

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
        CasillaDefinition.model_validate(
            {
                "id": _DUMMY_CASILLA_ID,
                "number": "01",
                "label": "Test casilla",
                "section": ("test",),
                "input_kind": "garbage",
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )


def test_casilla_rejects_empty_string_input_kind() -> None:
    """An empty string is not a valid InputKind member."""
    with pytest.raises(ValidationError):
        CasillaDefinition.model_validate(
            {
                "id": _DUMMY_CASILLA_ID,
                "number": "01",
                "label": "Test casilla",
                "section": ("test",),
                "input_kind": "",
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )


def test_casilla_rejects_numeric_input_kind() -> None:
    """A numeric value is not a valid InputKind member."""
    with pytest.raises(ValidationError):
        CasillaDefinition.model_validate(
            {
                "id": _DUMMY_CASILLA_ID,
                "number": "01",
                "label": "Test casilla",
                "section": ("test",),
                "input_kind": 42,
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )


# ---------------------------------------------------------------------------
# Default value
# ---------------------------------------------------------------------------


def test_casilla_default_input_kind_is_manual() -> None:
    """When input_kind is omitted, CasillaDefinition defaults to MANUAL."""
    casilla = CasillaDefinition(
        id=_DUMMY_CASILLA_ID,
        number="01",
        label="Test casilla",
        section=("test",),
        legal_refs=(_DUMMY_LEGAL_ID,),
        source_refs=(_DUMMY_SOURCE_ID,),
    )
    assert casilla.input_kind is InputKind.MANUAL


def test_formula_expression_rejects_generic_casilla_key() -> None:
    with pytest.raises(ValidationError):
        FormulaExpression.model_validate({"casilla": _DUMMY_CASILLA_ID})


def test_formula_definition_rejects_legacy_target_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        FormulaDefinition.model_validate(
            {
                "id": "test.formula",
                "target": _DUMMY_CASILLA_ID,
                "expression": {"literal": "0"},
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "target_casilla_id" in message
    assert "target" in message


def test_algorithm_binding_definition_rejects_legacy_target_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AlgorithmBindingDefinition.model_validate(
            {
                "id": "test.algorithm-binding",
                "provider": "test.algorithm-provider",
                "target": _DUMMY_CASILLA_ID,
                "inputs": {"value": _DUMMY_CASILLA_ID},
                "output_casilla_ids": {"result": _DUMMY_CASILLA_ID},
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "target_casilla_id" in message
    assert "target" in message


def test_algorithm_binding_definition_rejects_legacy_outputs_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AlgorithmBindingDefinition.model_validate(
            {
                "id": "test.algorithm-binding",
                "provider": "test.algorithm-provider",
                "target_casilla_id": _DUMMY_CASILLA_ID,
                "inputs": {"value": _DUMMY_CASILLA_ID},
                "outputs": {"result": _DUMMY_CASILLA_ID},
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "output_casilla_ids" in message
    assert "outputs" in message


def test_relation_definition_rejects_legacy_source_output_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RelationDefinition.model_validate(
            {
                "id": "test-rel",
                "kind": "cross_model_output",
                "dependency_role": "direct_calculation",
                "source_modelo": "303",
                "source_revision_selector": {"filing_year_delta": 0},
                "source_output": _DUMMY_CASILLA_ID,
                "target_binding": "test.binding",
                "period_alignment": {"mode": "same_period"},
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "source_casilla_id" in message
    assert "source_output" in message


def test_verification_expectation_definition_rejects_legacy_computed_casillas_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VerificationExpectationDefinition.model_validate(
            {
                "id": "test.expectation",
                "computed_casillas": (_DUMMY_CASILLA_ID,),
                "tolerance": "0.01",
                "rounding": "cent",
                "min_coverage": "1",
                "discrepancy_causes": ("rounding",),
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "computed_casilla_ids" in message
    assert "computed_casillas" in message


def test_verification_expectation_definition_rejects_legacy_reconciliation_totals_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VerificationExpectationDefinition.model_validate(
            {
                "id": "test.expectation",
                "computed_casilla_ids": (_DUMMY_CASILLA_ID,),
                "reconciliation_totals": {"ingresar": _DUMMY_CASILLA_ID},
                "tolerance": "0.01",
                "rounding": "cent",
                "min_coverage": "1",
                "discrepancy_causes": ("rounding",),
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "reconciliation_totals" in message


def test_construct_definition_rejects_legacy_casillas_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ConstructDefinition.model_validate(
            {
                "id": "test.construct",
                "title": "Test construct",
                "casillas": (_DUMMY_CASILLA_ID,),
                "legal_refs": (_DUMMY_LEGAL_ID,),
                "source_refs": (_DUMMY_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "casillas" in message
    assert "Extra inputs are not permitted" in message


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
    return ExportFieldDefinition.model_validate(
        {**_FIELD_BASE, "kind": raw_string, "literal": literal},
    )


def _make_export_field_casilla(raw_string: str, casilla_id: CasillaId) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a CASILLA kind field."""
    return ExportFieldDefinition.model_validate(
        {**_FIELD_BASE, "kind": raw_string, "casilla_id": casilla_id},
    )


def _make_export_field_binding(raw_string: str, binding: str) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a BINDING kind field."""
    return ExportFieldDefinition.model_validate(
        {**_FIELD_BASE, "kind": raw_string, "binding": binding},
    )


def _make_export_field_filler(raw_string: str, length: int) -> ExportFieldDefinition:
    """Construct an ExportFieldDefinition for a FILLER kind field."""
    return ExportFieldDefinition.model_validate(
        {**_FIELD_BASE, "kind": raw_string, "length": length},
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
        field = _make_export_field_casilla(raw_string, _DUMMY_CASILLA_ID)
    elif member == CasillaFieldKind.BINDING:
        field = _make_export_field_binding(raw_string, "some.binding")
    else:
        field = _make_export_field_filler(raw_string, 10)
    assert field.kind == member
    assert isinstance(field.kind, CasillaFieldKind)
    dumped = field.model_dump()
    assert dumped["kind"] == raw_string


def test_export_field_rejects_generic_casilla_key() -> None:
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate({**_FIELD_BASE, "kind": "casilla", "casilla": _DUMMY_CASILLA_ID})


def test_export_field_rejects_unknown_kind() -> None:
    """ExportFieldDefinition raises ValidationError for an unrecognised kind token."""
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate({**_FIELD_BASE, "kind": "bogus_kind"})


def test_export_field_rejects_empty_string_kind() -> None:
    """An empty string is not a valid CasillaFieldKind member."""
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate({**_FIELD_BASE, "kind": ""})


def test_export_field_rejects_numeric_kind() -> None:
    """A numeric value is not a valid CasillaFieldKind member."""
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate({**_FIELD_BASE, "kind": 99})
