"""Tests for registry-backed formula runtime."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import cast

import pytest

from ._formula_runtime import calculate_registry_snapshot
from ._schema import (
    CasillaDefinition,
    DatedValue,
    FormulaDefinition,
    FormulaExpression,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    PeriodSelector,
    RegistrySnapshot,
    SourceReference,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _snapshot(formulas: tuple[FormulaDefinition, ...]) -> RegistrySnapshot:
    legal_ref = LegalReference(
        id="ley-37-1992:art-90",
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/ley-37-1992.json#art-90",
        document_id="BOE-A-1992-28740",
        article="90",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90",
        effective_from=date(1992, 12, 29),
        review_status="reviewed",
    )
    source_ref = SourceReference(
        id="aeat-dr-303",
        authority="aeat",
        kind="record_design",
        corpus_path="corpus/source.xlsx",
        sha256=hashlib.sha256(b"x").hexdigest(),
        bytes=1,
        retrieved_at=date(2026, 5, 3),
        source_url="https://sede.agenciatributaria.gob.es/source.xlsx",
        review_status="reviewed",
    )
    revision = ModeloRevision(
        id="2026",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2026,), periods=("1T",)),
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
        parameters=(
            ParameterDefinition(
                id="iva.rate",
                data_type="ratio",
                unit="percent",
                values=(
                    DatedValue(
                        value=Decimal("21"),
                        date_axis="transaction_date",
                        valid_from=date(2026, 1, 1),
                    ),
                ),
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        ),
        casillas=(
            CasillaDefinition(
                id="01",
                number="01",
                label="Base",
                section=("iva",),
                data_type="money",
                required=True,
                input_kind="manual",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
            CasillaDefinition(
                id="02",
                number="02",
                label="Quota",
                section=("iva",),
                data_type="money",
                required=True,
                input_kind="computed",
                formula="quota",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
            CasillaDefinition(
                id="03",
                number="03",
                label="Total",
                section=("iva",),
                data_type="money",
                required=True,
                input_kind="computed",
                formula="total",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        ),
        formulas=formulas,
    )
    modelo = ModeloDefinition(
        id="303",
        title="IVA",
        official_name="IVA",
        tax_domain="iva",
        cadence="quarterly",
        jurisdiction="ES-AEAT",
        legal_refs=("ley-37-1992:art-90",),
        source_refs=("aeat-dr-303",),
        revisions={"2026": revision},
    )
    return RegistrySnapshot(
        modelo=modelo,
        revision=revision,
        legal={legal_ref.id: legal_ref},
        sources={source_ref.id: source_ref},
    )


def test_registry_formula_runtime_calculates_in_dependency_order() -> None:
    snapshot = _snapshot(
        (
            FormulaDefinition(
                id="quota",
                target="02",
                expression=FormulaExpression(
                    op="percent",
                    args=(FormulaExpression(casilla="01"), FormulaExpression(parameter="iva.rate")),
                ),
                rounding="money-2",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
            FormulaDefinition(
                id="total",
                target="03",
                expression=FormulaExpression(
                    op="add",
                    args=(FormulaExpression(casilla="01"), FormulaExpression(casilla="02")),
                ),
                rounding="money-2",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        )
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={"01": Decimal("100")},
        date_context={"transaction_date": date(2026, 1, 15)},
    )

    assert result.values["02"] == Decimal("21.00")
    assert result.values["03"] == Decimal("121.00")
    assert [entry.target for entry in result.entries] == ["02", "03"]
    assert result.entries[0].operand_refs == ("01", "iva.rate")
    assert result.entries[0].legal_refs == ("ley-37-1992:art-90",)


def test_registry_formula_runtime_rejects_non_decimal_input() -> None:
    snapshot = _snapshot(())

    with pytest.raises(Exception, match="must be a Decimal"):
        calculate_registry_snapshot(
            snapshot,
            inputs=cast("dict[str, Decimal]", {"01": 100}),
            date_context={"transaction_date": date(2026, 1, 15)},
        )


def test_registry_formula_runtime_rejects_missing_parameter_axis() -> None:
    snapshot = _snapshot(
        (
            FormulaDefinition(
                id="quota",
                target="02",
                expression=FormulaExpression(op="lookup_parameter", args=(FormulaExpression(parameter="iva.rate"),)),
                rounding="money-2",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        )
    )

    with pytest.raises(Exception, match="requires date axis"):
        calculate_registry_snapshot(snapshot, inputs={"01": Decimal("100")}, date_context={})


def test_registry_formula_runtime_uses_relation_values() -> None:
    snapshot = _snapshot(
        (
            FormulaDefinition(
                id="quota",
                target="02",
                expression=FormulaExpression(
                    op="previous_period_value",
                    args=(FormulaExpression(relation="previous-result"),),
                ),
                rounding="money-2",
                legal_refs=("ley-37-1992:art-90",),
                source_refs=("aeat-dr-303",),
            ),
        )
    )

    result = calculate_registry_snapshot(
        snapshot,
        inputs={"01": Decimal("0")},
        date_context={"transaction_date": date(2026, 1, 15)},
        relation_values={"previous-result": Decimal("7.50")},
    )

    assert result.values["02"] == Decimal("7.50")
