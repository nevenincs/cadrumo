"""Real-behaviour tests for the registry _schema module.

Exercises InputKind validation through the CasillaDefinition pydantic
model so every claim about the StrEnum boundary is enforced by the
actual production model, not by a standalone enum construction.
"""

from __future__ import annotations

import re
from dataclasses import fields as dataclass_fields
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypedDict

import pytest
from pydantic import TypeAdapter, ValidationError

from .....core.casilla_id import CasillaId, validated_casilla_id
from ...export_field_kind import CasillaFieldKind
from ..ids import LegalRefId, SourceRefId
from ..schema import FormulaDefinition
from ..schema_exports import ExportFieldDefinition
from ..schema_formula import FormulaExpression
from ..schema_input_kind import InputKind
from ..schema_revision_members import ConstructDefinition
from ..schema_surfaces import CasillaDefinition, RelationDefinition
from ..schema_verification import (
    DiscrepancyCause,
    RegistryVerificationPolicy,
    VerificationExpectationDefinition,
    VerificationRoundingCode,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# ---------------------------------------------------------------------------
# Shared fixture constants — pattern mirrors test_referential_integrity
# ---------------------------------------------------------------------------

_SCHEMA_LEGAL_ID: LegalRefId = "ley-35-2006:art-test"
_SCHEMA_SOURCE_ID: SourceRefId = "aeat-test-source-001"
_SCHEMA_CASILLA_ID: CasillaId = validated_casilla_id("01", surface="_SCHEMA_CASILLA_ID")


def test_source_ref_id_accepts_current_catalogue_key_shape() -> None:
    adapter = TypeAdapter(SourceRefId)

    assert adapter.validate_python("aeat-dr-303-2025-v2") == "aeat-dr-303-2025-v2"


def test_source_ref_id_rejects_generic_registry_and_legal_ref_shapes() -> None:
    adapter = TypeAdapter(SourceRefId)

    for source_ref in ("aeat.src.1", "ley-37-1992:art-1", "source"):
        with pytest.raises(ValidationError):
            adapter.validate_python(source_ref)


def _relation_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "test-rel",
        "kind": "cross_model_output",
        "dependency_role": "factual_evidence",
        "source_modelo": "303",
        "source_revision_selector": {"year_from": 2024},
        "source_casilla_id": _SCHEMA_CASILLA_ID,
        "target_binding": "test.binding",
        "period_alignment": {"source_periods": "quarters", "target_period": "0A"},
        "source_periods": ("1T", "2T", "3T", "4T"),
        "target_periods": ("0A",),
        "legal_refs": (_SCHEMA_LEGAL_ID,),
        "source_refs": (_SCHEMA_SOURCE_ID,),
    }
    payload.update(overrides)
    return payload


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


def test_casilla_roundtrip_valid_input_kind() -> None:
    """Constructor accepts each member string and model_dump round-trips it."""
    cases = (
        (InputKind.MANUAL, "manual"),
        (InputKind.BOUND, "bound"),
        (InputKind.COMPUTED, "computed"),
        (InputKind.INFORMATIONAL, "informational"),
    )

    for member, raw_string in cases:
        # Validate TOML-shaped payloads so raw string enum coercion stays on the
        # same boundary production registry loading uses.
        if member == InputKind.COMPUTED:
            payload: dict[str, object] = {
                "id": _SCHEMA_CASILLA_ID,
                "number": "01",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("test",),
                "input_kind": raw_string,
                "formula": "test.formula",
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            }
        elif member == InputKind.BOUND:
            payload = {
                "id": _SCHEMA_CASILLA_ID,
                "number": "01",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("test",),
                "input_kind": raw_string,
                "binding": "test.binding",
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            }
        else:
            payload = {
                "id": _SCHEMA_CASILLA_ID,
                "number": "01",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("test",),
                "input_kind": raw_string,
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            }
        casilla = CasillaDefinition.model_validate(payload)

        assert casilla.input_kind == member, raw_string
        assert isinstance(casilla.input_kind, InputKind), raw_string
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
                "id": _SCHEMA_CASILLA_ID,
                "number": "01",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("test",),
                "input_kind": "garbage",
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            },
        )


def test_casilla_rejects_empty_string_input_kind() -> None:
    """An empty string is not a valid InputKind member."""
    with pytest.raises(ValidationError):
        CasillaDefinition.model_validate(
            {
                "id": _SCHEMA_CASILLA_ID,
                "number": "01",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("test",),
                "input_kind": "",
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            },
        )


def test_casilla_rejects_numeric_input_kind() -> None:
    """A numeric value is not a valid InputKind member."""
    with pytest.raises(ValidationError):
        CasillaDefinition.model_validate(
            {
                "id": _SCHEMA_CASILLA_ID,
                "number": "01",
                "localization_keys": ("test.schema.casilla.label",),
                "section": ("test",),
                "input_kind": 42,
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            },
        )


# ---------------------------------------------------------------------------
# Default value
# ---------------------------------------------------------------------------


def test_casilla_default_input_kind_is_manual() -> None:
    """When input_kind is omitted, CasillaDefinition defaults to MANUAL."""
    casilla = CasillaDefinition(
        id=_SCHEMA_CASILLA_ID,
        number="01",
        localization_keys=("test.schema.casilla.label",),
        section=("test",),
        legal_refs=(_SCHEMA_LEGAL_ID,),
        source_refs=(_SCHEMA_SOURCE_ID,),
    )
    assert casilla.input_kind is InputKind.MANUAL


def test_formula_expression_rejects_generic_casilla_key() -> None:
    with pytest.raises(ValidationError):
        FormulaExpression.model_validate({"casilla": _SCHEMA_CASILLA_ID})


def test_formula_definition_rejects_legacy_target_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        FormulaDefinition.model_validate(
            {
                "id": "test.formula",
                "target": _SCHEMA_CASILLA_ID,
                "expression": {"literal": "0"},
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "target_casilla_id" in message
    assert "target" in message


def test_relation_definition_rejects_legacy_source_output_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        RelationDefinition.model_validate(
            {
                "id": "test-rel",
                "kind": "cross_model_output",
                "dependency_role": "direct_calculation",
                "source_modelo": "303",
                "source_revision_selector": {"filing_year_delta": 0},
                "source_output": _SCHEMA_CASILLA_ID,
                "target_binding": "test.binding",
                "period_alignment": {"mode": "previous_quarter"},
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "source_casilla_id" in message
    assert "source_output" in message


def test_relation_definition_rejects_invalid_source_revision_selector() -> None:
    cases = (
        ({}, "must declare year, year_from, or filing_year_delta"),
        ({"revision": "2025"}, "revision"),
        ({"revision_id": "2025"}, "revision_id"),
        ({"year": 2025, "filing_year_delta": 0}, "absolute year bounds or filing_year_delta"),
        ({"year": 2025, "year_from": 2024}, "year or year_from/year_to"),
        ({"year_to": 2025}, "year_to requires year_from"),
        ({"year_from": 2025, "year_to": 2024}, "year_to must be on or after year_from"),
    )

    for selector, expected in cases:
        with pytest.raises(ValidationError) as exc_info:
            RelationDefinition.model_validate(_relation_payload(source_revision_selector=selector))

        assert expected in str(exc_info.value), selector


def test_relation_definition_rejects_invalid_period_alignment() -> None:
    cases = (
        ({}, "must declare a current alignment shape"),
        ({"mode": "same_period"}, "same_period"),
        ({"source_periods": "quarters"}, "source_periods requires target_period"),
        ({"source_period_kind": "quarterly"}, "source_period_kind requires target_period"),
        ({"source_period": "0A", "target_period": "0A"}, "requires target_period and filing_year_delta"),
        ({"target_period": "0A"}, "declares target/delta fields without source alignment"),
    )

    for period_alignment, expected in cases:
        with pytest.raises(ValidationError) as exc_info:
            RelationDefinition.model_validate(_relation_payload(period_alignment=period_alignment))

        assert expected in str(exc_info.value), period_alignment


def test_verification_expectation_definition_rejects_legacy_computed_casillas_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VerificationExpectationDefinition.model_validate(
            {
                "id": "test.expectation",
                "computed_casillas": (_SCHEMA_CASILLA_ID,),
                "tolerance": "0.01",
                "rounding": "cent",
                "min_coverage": "1",
                "discrepancy_causes": ("rounding",),
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
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
                "computed_casilla_ids": (_SCHEMA_CASILLA_ID,),
                "reconciliation_totals": {"ingresar": _SCHEMA_CASILLA_ID},
                "tolerance": "0.01",
                "rounding": "cent",
                "min_coverage": "1",
                "discrepancy_causes": ("rounding",),
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
            },
        )

    message = str(exc_info.value)
    assert "reconciliation_totals" in message


def test_construct_definition_rejects_legacy_casillas_key() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ConstructDefinition.model_validate(
            {
                "id": "test.construct",
                "localization_key": "test.schema.construct.test.title",
                "title": "Test construct",
                "casillas": (_SCHEMA_CASILLA_ID,),
                "legal_refs": (_SCHEMA_LEGAL_ID,),
                "source_refs": (_SCHEMA_SOURCE_ID,),
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
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


_FIELD_BASE: _FieldBase = _FieldBase(
    id="f001",
    data_type="text",
    required=True,
    padding="none",
    justification="left",
    signed=False,
    legal_refs=(_SCHEMA_LEGAL_ID,),
    source_refs=(_SCHEMA_SOURCE_ID,),
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
    assert CasillaFieldKind.PROJECTION == "projection"
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


def test_export_field_roundtrip_valid_casilla_field_kind() -> None:
    """ExportFieldDefinition accepts each member string and round-trips via model_dump."""
    cases = (
        (CasillaFieldKind.LITERAL, "literal"),
        (CasillaFieldKind.CASILLA, "casilla"),
        (CasillaFieldKind.BINDING, "binding"),
        (CasillaFieldKind.FILLER, "filler"),
    )

    for member, raw_string in cases:
        if member == CasillaFieldKind.LITERAL:
            field = _make_export_field_literal(raw_string, "TEST")
        elif member == CasillaFieldKind.CASILLA:
            field = _make_export_field_casilla(raw_string, _SCHEMA_CASILLA_ID)
        elif member == CasillaFieldKind.BINDING:
            field = _make_export_field_binding(raw_string, "some.binding")
        else:
            field = _make_export_field_filler(raw_string, 10)
        assert field.kind == member, raw_string
        assert isinstance(field.kind, CasillaFieldKind), raw_string
        dumped = field.model_dump()
        assert dumped["kind"] == raw_string


def test_export_field_rejects_generic_casilla_key() -> None:
    with pytest.raises(ValidationError):
        ExportFieldDefinition.model_validate({**_FIELD_BASE, "kind": "casilla", "casilla": _SCHEMA_CASILLA_ID})


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


class TestVerificationVocabulariesAreClosed:
    """A verification expectation cannot declare a meaningless obligation.

    ``rounding`` was a bare ``str`` and the policy fold dropped both it and
    ``discrepancy_causes`` entirely, so ``rounding = "bogus"`` was accepted at
    registry build and produced exactly the same policy and verifier behaviour
    as the valid declaration. A legal verification obligation could therefore
    drift from the runtime authority with nothing to notice.

    ``none`` is a real member of the verification axis (compare the raw values
    before applying the tolerance) even though the FORMULA rounding authority
    has no such mode -- the two are different axes, which is why the
    vocabularies are separate rather than shared.
    """

    def _fields(self, **overrides: object) -> dict[str, object]:
        fields: dict[str, object] = {
            "id": "expectation-under-test",
            "computed_casilla_ids": ("01",),
            "tolerance": Decimal("0.01"),
            "rounding": "money-2",
            "min_coverage": Decimal("1"),
            "discrepancy_causes": ("rounding",),
            "legal_refs": ("ley-35-2006:art-1",),
            "source_refs": ("manual-iva-2025",),
        }
        fields.update(overrides)
        return fields

    @pytest.mark.parametrize("bad", ["bogus", "", "MONEY-2", "money_2", "integer"])
    def test_an_unknown_rounding_token_is_refused(self, bad: str) -> None:
        """``integer`` is a FORMULA mode; it is not a verification-comparison mode."""
        with pytest.raises((ValidationError, ValueError)):
            VerificationExpectationDefinition.model_validate(self._fields(rounding=bad))

    @pytest.mark.parametrize("rounding", [code.value for code in VerificationRoundingCode])
    def test_every_declared_rounding_mode_is_accepted(self, rounding: str) -> None:
        expectation = VerificationExpectationDefinition.model_validate(self._fields(rounding=rounding))

        assert expectation.rounding is VerificationRoundingCode(rounding)

    def test_the_vocabulary_matches_what_the_registry_actually_declares(self) -> None:
        """The enum is the registry's real value set, not a guess about it.

        Without this the vocabulary could be narrowed to a subset and every
        genuine declaration outside it would start failing the build.
        """
        declared = {
            match.group(1)
            for path in Path("src/cadrumo/_data/registry").rglob("verification_expectations/*.toml")
            for match in re.finditer(r'rounding = "([^"]+)"', path.read_text(encoding="utf-8"))
        }

        assert declared, "no verification rounding declarations found; the scan is not measuring anything"
        assert declared <= {code.value for code in VerificationRoundingCode}

    @pytest.mark.parametrize("bad", ["invented", "", "ROUNDING"])
    def test_an_unknown_discrepancy_cause_is_refused(self, bad: str) -> None:
        with pytest.raises((ValidationError, ValueError)):
            VerificationExpectationDefinition.model_validate(self._fields(discrepancy_causes=(bad,)))

    @pytest.mark.parametrize("cause", [cause.value for cause in DiscrepancyCause])
    def test_every_declared_cause_is_accepted(self, cause: str) -> None:
        expectation = VerificationExpectationDefinition.model_validate(self._fields(discrepancy_causes=(cause,)))

        assert expectation.discrepancy_causes == (DiscrepancyCause(cause),)

    def test_the_policy_fold_carries_the_declarations_it_used_to_drop(self) -> None:
        """The policy is the consumed projection; a dropped field is unreachable."""
        carried = {field.name for field in dataclass_fields(RegistryVerificationPolicy)}

        assert "rounding_codes" in carried
        assert "discrepancy_causes" in carried
