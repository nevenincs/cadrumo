"""Exact Modelo 194 record totals: losses never cancel the positive subtotal."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.aggregation import RetencionClave
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_values,
)

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _transaction(index: int, year: int, base: str, retention: str) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"fictional-asset-{index}",
        perceptor_tax_id="11111111H",
        perceptor_legal_name="PERCEPTOR SINTETICO",
        transaction_date=date(year, 6, 1),
        clave=RetencionClave.from_registry("G"),
        financial_asset_origin="A",
        base_retenciones=Decimal(base),
        retencion_practicada=Decimal(retention),
        incapacity_cash_perception=Decimal("0"),
        incapacity_cash_withholding=Decimal("0"),
        incapacity_kind_value=Decimal("0"),
        incapacity_kind_ingreso_a_cuenta=Decimal("0"),
        incapacity_kind_repercutido=Decimal("0"),
        foral_retention_estatal=Decimal("0"),
        foral_retention_navarra=Decimal("0"),
        foral_retention_araba=Decimal("0"),
        foral_retention_gipuzkoa=Decimal("0"),
        foral_retention_bizkaia=Decimal("0"),
    )


@pytest.mark.parametrize("epoch", ["2019", "2023", "2024"])
def test_official_five_box_summary_uses_the_actual_registry_formulas(epoch: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/194")).revisions[epoch]
    observations = tuple(
        _transaction(i, int(epoch), base, retention)
        for i, (base, retention) in enumerate((("100", "19"), ("25", "5"), ("0", "0"), ("-40", "0"), ("-10", "0")))
    )
    bindings = resolve_withholding_binding_values(revision, observations)
    actual = {
        str(c.id): bindings[c.binding] for c in revision.casillas if c.binding is not None and str(c.id) in ("01", "04")
    }
    for formula in revision.formulas:
        assert f"aeat-dr-194-{epoch}" in formula.source_refs
        actual[str(formula.target_casilla_id)] = evaluate_expression(
            formula.expression,
            values={},
            binding_values=bindings,
            parameters={},
            date_context={},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
        )
    # Five operations, one recipient. Zero belongs to 04; losses are shown unsigned in 05.
    assert actual == {
        "01": Decimal("2"),
        "02": Decimal("125"),
        "03": Decimal("24"),
        "04": Decimal("3"),
        "05": Decimal("50"),
    }
    for binding in revision.bindings:
        if str(binding.id).startswith("modelo-194-resumen-"):
            assert tuple(binding.source_refs) == (f"aeat-dr-194-{epoch}", "aeat-modelo-194-procedure")
