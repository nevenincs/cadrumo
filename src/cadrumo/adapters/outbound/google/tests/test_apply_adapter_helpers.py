"""Pure-function contract tests for the apply adapter's coercion + constraint helpers.

Three load-bearing helpers turn the engine's typed records into
Sheets API request bodies:

  * ``_coerce_cell_value`` — Decimal | str | bool | None → the JSON
    cell value Sheets accepts. Errors here render wrong values on
    the operator's screen.
  * ``_condition_for_constraint`` — SheetCellConstraint → Sheets
    BooleanCondition (NUMBER_BETWEEN / NUMBER_GREATER_THAN_EQ /
    NUMBER_LESS_THAN_EQ). Errors here render the wrong data
    validation rule on the cell.
  * ``_input_message_for_constraint`` — SheetCellConstraint → the
    cell note text the operator sees. Errors here surface
    misleading bounds to the operator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import pytest

from .....application.storage.calc_sheets import (
    RelationValue,
    RelationValues,
    SheetCellAddress,
    SheetCellConstraint,
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    SheetProtectedRange,
    TabName,
)
from .....core import CasillaId, Period, validated_casilla_id
from .....domain.calculations.registry.ids import LegalRefId
from .._calc_sheets_apply import (
    _build_structural_cleanup_requests,
    _coerce_cell_value,
    _condition_for_constraint,
    _developer_metadata_pairs,
    _input_message_for_constraint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_Sign = Literal["any", "non_negative", "non_positive"]


_TEST_CASILLA: CasillaId = validated_casilla_id("test.casilla")
_ANY_CASILLA: CasillaId = validated_casilla_id("any.casilla")
_SOME_CASILLA: CasillaId = validated_casilla_id("some.casilla")
_IVA_COMPENSACION_ANTERIORES_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-anteriores")
_IVA_PRORRATA_PORCENTAJE_CASILLA: CasillaId = validated_casilla_id("iva.prorrata-porcentaje")
_IVA_RESULTADO_NEGATIVO_CASILLA: CasillaId = validated_casilla_id("iva.resultado-negativo")
_DEFAULT_CONSTRAINT_LEGAL_REFS: tuple[LegalRefId, ...] = ("ley-37-1992:art-99",)


def _make_constraint(
    *,
    sign: _Sign = "any",
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
    casilla_id: CasillaId = _TEST_CASILLA,
    legal_refs: tuple[LegalRefId, ...] = _DEFAULT_CONSTRAINT_LEGAL_REFS,
) -> SheetCellConstraint:
    return SheetCellConstraint(
        address=SheetCellAddress.at(TabName.ENTRADAS, 1, 1),
        sign=sign,
        min_value=min_value,
        max_value=max_value,
        casilla_id=casilla_id,
        legal_refs=legal_refs,
    )


# ---------------------------------------------------------------------------
# _coerce_cell_value
# ---------------------------------------------------------------------------


def test_coerce_cell_value_none_becomes_empty_string() -> None:
    assert _coerce_cell_value(None) == ""


def test_coerce_cell_value_preserves_bool() -> None:
    assert _coerce_cell_value(True) is True
    assert _coerce_cell_value(False) is False


def test_coerce_cell_value_decimal_renders_as_fixed_string() -> None:
    """Very large / very small Decimals must not round through float."""
    assert _coerce_cell_value(Decimal("1500.55")) == "1500.55"
    assert _coerce_cell_value(Decimal("0.00000001")) == "0.00000001"
    assert _coerce_cell_value(Decimal("1234567890.99")) == "1234567890.99"


def test_coerce_cell_value_negative_decimal_preserved() -> None:
    assert _coerce_cell_value(Decimal("-500")) == "-500"


def test_coerce_cell_value_passes_string_through() -> None:
    assert _coerce_cell_value("Concepto") == "Concepto"


# ---------------------------------------------------------------------------
# _condition_for_constraint
# ---------------------------------------------------------------------------


def test_condition_non_negative_no_bounds_emits_greater_than_eq_zero() -> None:
    constraint = _make_constraint(sign="non_negative", casilla_id=_IVA_COMPENSACION_ANTERIORES_CASILLA)
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_GREATER_THAN_EQ"
    assert condition["values"] == [{"userEnteredValue": "0"}]


def test_condition_min_and_max_emit_number_between() -> None:
    constraint = _make_constraint(
        sign="any",
        min_value=Decimal("10"),
        max_value=Decimal("100"),
        casilla_id=_IVA_PRORRATA_PORCENTAJE_CASILLA,
    )
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_BETWEEN"
    assert condition["values"] == [
        {"userEnteredValue": "10"},
        {"userEnteredValue": "100"},
    ]


def test_condition_non_negative_with_max_emits_number_between_at_zero_lower() -> None:
    """non_negative + max=100 should yield NUMBER_BETWEEN(0, 100), not BETWEEN(None, 100)."""

    constraint = _make_constraint(
        sign="non_negative",
        max_value=Decimal("100"),
        casilla_id=_IVA_PRORRATA_PORCENTAJE_CASILLA,
    )
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_BETWEEN"
    assert condition["values"][0] == {"userEnteredValue": "0"}
    assert condition["values"][1] == {"userEnteredValue": "100"}


def test_condition_non_positive_no_bounds_emits_less_than_eq_zero() -> None:
    constraint = _make_constraint(sign="non_positive", casilla_id=_IVA_RESULTADO_NEGATIVO_CASILLA)
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_LESS_THAN_EQ"
    assert condition["values"] == [{"userEnteredValue": "0"}]


def test_condition_unconstrained_returns_none() -> None:
    """sign='any' with no min / max → no data-validation rule needed."""

    constraint = _make_constraint(sign="any", casilla_id=_ANY_CASILLA)
    assert _condition_for_constraint(constraint) is None


# ---------------------------------------------------------------------------
# _input_message_for_constraint
# ---------------------------------------------------------------------------


def test_input_message_renders_non_negative_sign() -> None:
    constraint = _make_constraint(
        sign="non_negative",
        casilla_id=_IVA_COMPENSACION_ANTERIORES_CASILLA,
        legal_refs=("ley-37-1992:art-99",),
    )
    message = _input_message_for_constraint(constraint)
    assert _IVA_COMPENSACION_ANTERIORES_CASILLA in message
    assert "≥ 0" in message
    assert "ley-37-1992:art-99" in message


def test_input_message_renders_min_and_max_bounds() -> None:
    constraint = _make_constraint(
        sign="any",
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        casilla_id=_IVA_PRORRATA_PORCENTAJE_CASILLA,
        legal_refs=("ley-37-1992:art-104",),
    )
    message = _input_message_for_constraint(constraint)
    assert _IVA_PRORRATA_PORCENTAJE_CASILLA in message
    assert "≥ 0" in message
    assert "≤ 100" in message


def test_input_message_renders_any_when_no_bounds() -> None:
    constraint = _make_constraint(sign="any", casilla_id=_SOME_CASILLA)
    message = _input_message_for_constraint(constraint)
    assert "any" in message


def test_developer_metadata_pairs_preserve_relation_grounding() -> None:
    """Relation metadata keeps the registry-declared source identity and refs."""

    resolved_at = datetime(2026, 6, 30, 12, 0, tzinfo=UTC)
    plan = SheetExportPlan(
        metadata=SheetExportMetadata(
            modelo_id="180",
            revision_id="2023-y-siguientes",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            engine_version="calc-sheets/0.1.0",
            registry_sha="da9952e1610f7db6",
            exported_at=datetime(2026, 6, 30, 12, 1, tzinfo=UTC),
        ),
        relation_provenance=RelationValues(
            values=(
                RelationValue(
                    relation="modelo-180-rel-115-base-anual",
                    value=Decimal("190.00"),
                    provenance="local_filing",
                    source_modelo="115",
                    source_filing_year=2026,
                    source_periods=("1T", "2T", "3T", "4T"),
                    source_casilla_ids=("02",),
                    legal_refs=("ley-35-2006:art-99",),
                    source_refs=("boe-modelo-180-2023-form",),
                    resolved_at=resolved_at,
                ),
            ),
        ),
        guide=SheetGuideContent(title="Guide", paragraphs=("Line.",)),
    )

    pairs = dict(_developer_metadata_pairs(plan))

    assert pairs["cadrumo_relation:modelo-180-rel-115-base-anual"] == (
        "value=190.00; provenance=local_filing; source_modelo=115; source_filing_year=2026; "
        "source_periods=1T+2T+3T+4T; source_casilla_ids=02; legal_refs=ley-35-2006:art-99; "
        f"source_refs=boe-modelo-180-2023-form; resolved_at={resolved_at.isoformat()}"
    )


def test_developer_metadata_pairs_preserve_blank_relation_grounding() -> None:
    """Blank operator-entered relation cells still carry registry grounding."""

    plan = SheetExportPlan(
        metadata=SheetExportMetadata(
            modelo_id="180",
            revision_id="2023-y-siguientes",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
            engine_version="calc-sheets/0.1.0",
            registry_sha="da9952e1610f7db6",
            exported_at=datetime(2026, 6, 30, 12, 1, tzinfo=UTC),
        ),
        relation_provenance=RelationValues(
            values=(
                RelationValue(
                    relation="modelo-180-rel-115-base-anual",
                    value=None,
                    provenance="operator_manual",
                    source_modelo="115",
                    source_filing_year=2026,
                    source_periods=("1T", "2T", "3T", "4T"),
                    source_casilla_ids=("02",),
                    legal_refs=("ley-35-2006:art-99",),
                    source_refs=("boe-modelo-180-2023-form",),
                ),
            ),
        ),
        guide=SheetGuideContent(title="Guide", paragraphs=("Line.",)),
    )

    pairs = dict(_developer_metadata_pairs(plan))

    assert pairs["cadrumo_relation:modelo-180-rel-115-base-anual"] == (
        "provenance=operator_manual; source_modelo=115; source_filing_year=2026; "
        "source_periods=1T+2T+3T+4T; source_casilla_ids=02; legal_refs=ley-35-2006:art-99; "
        "source_refs=boe-modelo-180-2023-form"
    )


# ---------------------------------------------------------------------------
# Structural cleanup before re-apply
# ---------------------------------------------------------------------------


def test_structural_cleanup_deletes_only_adapter_managed_metadata_and_protected_ranges() -> None:
    """Re-applying a workbook must not accumulate duplicate AEAT structural state."""

    protected = SheetProtectedRange(
        tab=TabName.CALCULOS,
        start_row=1,
        end_row=12,
        start_column=1,
        end_column=4,
        description="Cálculos derivados — protegido para preservar paridad",
    )
    plan = SheetExportPlan(
        metadata=SheetExportMetadata(
            modelo_id="130",
            revision_id="2019-y-siguientes",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            engine_version="calc-sheets/0.1.0",
            registry_sha="da9952e1610f7db6",
            exported_at=datetime(2026, 6, 2, 17, 55, tzinfo=UTC),
        ),
        protected_ranges=(protected,),
        guide=SheetGuideContent(title="Guide", paragraphs=("Line.",)),
    )
    spreadsheet = {
        "developerMetadata": [
            {"metadataId": 101, "metadataKey": "cadrumo_registry_sha", "metadataValue": "old"},
            {"metadataId": 102, "metadataKey": "foreign_key", "metadataValue": "keep"},
            {"metadataId": 103, "metadataKey": "cadrumo_relation:prior", "metadataValue": "old"},
            {"metadataKey": "cadrumo_modelo_id", "metadataValue": "missing-id"},
        ],
        "sheets": [
            {
                "properties": {"title": "Cálculos"},
                "protectedRanges": [
                    {
                        "protectedRangeId": 201,
                        "description": protected.description,
                    },
                    {
                        "protectedRangeId": 202,
                        "description": "operator protected range",
                    },
                ],
            },
        ],
    }

    requests = _build_structural_cleanup_requests(spreadsheet, plan)

    assert requests == [
        {
            "deleteDeveloperMetadata": {
                "dataFilter": {
                    "developerMetadataLookup": {
                        "metadataId": 101,
                    },
                },
            },
        },
        {
            "deleteDeveloperMetadata": {
                "dataFilter": {
                    "developerMetadataLookup": {
                        "metadataId": 103,
                    },
                },
            },
        },
        {
            "deleteProtectedRange": {
                "protectedRangeId": 201,
            },
        },
    ]
