"""Modelo 390 apartado 7, "Resultado de la liquidación anual", end to end.

The four quarterly Modelo 303 autoliquidaciones of a year are calculated from
ledger rows through the compiled registry, chained through their compensation
carry, and folded into the annual Modelo 390. Every expected figure below is
worked by hand from the quarter bases at 21 %, following the Manual práctico de
IVA, capítulo 9: [84] = [65] + [83] + [658] and [86] = [84] + [659] - [85], with
[85] the credit of earlier ejercicios that the year's autoliquidaciones applied.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.modelo.verification_predicates import evaluate_verification_predicates
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult
from cadrumo.domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.deadlines.models import IVARegime, TaxpayerProfile
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind
from dev.registry.compiler.authority import compiled_bundled_authority

from .ledger_iva_aggregation_support import (
    _calculate_303_from_observations,
    _calculate_390_from_observations_and_303_filings,
    _deduction_kind,
    _flow,
    _observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_SURFACE = "test_modelo_390_resultado_liquidacion_anual"
_SUPPORTED_YEARS = (2022, 2023, 2024, 2025)
_RATE = Decimal("0.21")
_QUARTER_MONTH = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}


def _casilla(raw: str) -> CasillaId:
    return validated_casilla_id(raw, surface=_SURFACE)


_M303_PENDIENTE_FIN_PERIODO = _casilla("iva.compensacion-disponible-fin-periodo")
_M303_REGULARIZACION_ART_80 = _casilla("76")
_M303_IVA_IMPORTACION_ADUANA = _casilla("77")
_M303_RESULTADO_LIQUIDACION = _casilla("71")

_M390_RESULTADO_REGIMEN_GENERAL = _casilla("iva.anual.resultado-regimen-general")
_M390_REGULARIZACION_ART_80 = _casilla("iva.anual.regularizacion-cuotas-art-80-cinco-5")
_M390_SUMA_RESULTADOS = _casilla("iva.anual.suma-resultados")
_M390_IVA_IMPORTACION_ADUANA = _casilla("iva.anual.iva-importacion-diferimiento")
_M390_COMPENSACION_EJERCICIO_ANTERIOR = _casilla("iva.anual.compensacion-cuotas-ejercicio-anterior")
_M390_RESULTADO_LIQUIDACION = _casilla("iva.anual.resultado-liquidacion")
_M390_COMPENSACION_ULTIMO_PERIODO = _casilla("iva.anual.compensacion-ultimo-periodo-97")
_M390_COMPENSACION_GENERADA_NO_97 = _casilla("iva.anual.compensacion-generada-ejercicio-no-97")
_M390_TOTAL_A_INGRESAR = _casilla("iva.anual.liquidaciones.total-a-ingresar")
_M390_ULTIMO_PERIODO_A_DEVOLVER = _casilla("iva.anual.liquidaciones.ultimo-periodo-a-devolver")
_M390_RECONCILIACION_LIQUIDACIONES = _casilla("iva.anual.reconciliacion.resultados-liquidaciones")

_IDENTITY_PREDICATE_ID = "modelo-390-resultado-liquidacion-equals-resultados-liquidaciones"

#: Apartado 7 boxes by their official number. Each is a derivation of the
#: year's autoliquidaciones, so none may be operator input.
_APARTADO_7_BOXES = frozenset({"658", "84", "659", "85", "86"})
#: Apartado 9 boxes that stay operator input: the sign of each period's result,
#: a monthly-refund register, the modelo 308 and the modelo 322 are not in the
#: sources the calculation reads. [97] and [662] are derived.
_APARTADO_9_OPERATOR_INPUT_BOXES = frozenset({"95", "96", "524", "98", "525", "526"})


@dataclass(frozen=True, slots=True)
class _Quarter:
    """One quarter's 21 % sales and purchases bases plus its operator boxes."""

    sales_base: Decimal
    purchases_base: Decimal
    operator_inputs: Mapping[CasillaId, Decimal] | None = None


@dataclass(frozen=True, slots=True)
class _AnnualFiling:
    quarters: dict[str, RegistryCalculationResult]
    annual: RegistryCalculationResult


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _quarter_rows(year: int, period: str, quarter: _Quarter) -> tuple[IvaLedgerObservation, ...]:
    month = _QUARTER_MONTH[period]
    sale_date = date(year, month, 10)
    purchase_date = date(year, month, 11)
    return (
        _observation(
            ledger_id=f"{year}-{period}-sale",
            txn_date=sale_date,
            base=quarter.sales_base,
            iva=(quarter.sales_base * _RATE).quantize(Decimal("0.01")),
            applied_rate=_RATE,
        ),
        _observation(
            ledger_id=f"{year}-{period}-purchase",
            txn_date=purchase_date,
            flow=_flow("soportado", effective_date=purchase_date),
            base=quarter.purchases_base,
            iva=(quarter.purchases_base * _RATE).quantize(Decimal("0.01")),
            applied_rate=_RATE,
            deduction_fact_kind=_deduction_kind("domestic_current", effective_date=purchase_date),
        ),
    )


def _file_year(
    year: int,
    quarters: dict[str, _Quarter],
    *,
    credit_from_earlier_years: Decimal,
    annual_operator_inputs: Mapping[CasillaId, Decimal] | None = None,
) -> _AnnualFiling:
    """Calculate the four 303s, each opening on the previous one's closing credit."""
    pending = credit_from_earlier_years
    results: dict[str, RegistryCalculationResult] = {}
    observations: tuple[IvaLedgerObservation, ...] = ()
    for period, quarter in quarters.items():
        rows = _quarter_rows(year, period, quarter)
        observations += rows
        result = _calculate_303_from_observations(
            filing_year=year,
            period=period,
            observations=rows,
            compensacion_pendiente_anteriores=pending,
            operator_inputs=quarter.operator_inputs,
        )
        results[period] = result
        pending = result.values[_M303_PENDIENTE_FIN_PERIODO]
    annual = _calculate_390_from_observations_and_303_filings(
        filing_year=year,
        observations=observations,
        quarterly_results=results,
        operator_inputs=annual_operator_inputs,
    )
    return _AnnualFiling(quarters=results, annual=annual)


def _identity_findings(filing_year: int, annual: RegistryCalculationResult) -> list[ModeloVerificationFinding]:
    revision = compiled_bundled_authority().snapshot("390", filing_year=filing_year, period="0A").revision
    predicate = next(
        predicate for predicate in revision.verification_predicates if predicate.predicate_id == _IDENTITY_PREDICATE_ID
    )
    return evaluate_verification_predicates((predicate,), annual.values, _profile())


# Credit of 1000.00 brought from the previous ejercicio. Quarter results at 21 %:
# 1T 210 - 105 = 105, 2T 840 - 210 = 630, 3T 210 - 630 = -420, 4T 1050 - 420 = 630.
# The carry applies 105 (1T) and 630 (2T) of the old credit, generates 420 in 3T,
# and 4T applies the remaining 265 of the old credit first, then 365 of the new.
_WITH_PRIOR_YEAR_CREDIT = {
    "1T": _Quarter(Decimal("1000"), Decimal("500")),
    "2T": _Quarter(Decimal("4000"), Decimal("1000")),
    "3T": _Quarter(Decimal("1000"), Decimal("3000")),
    "4T": _Quarter(Decimal("5000"), Decimal("2000")),
}

# No credit from earlier years. 1T 420 - 105 = 315 (paid), 2T 210 - 630 = -420,
# 3T 105 - 840 = -735, 4T 210 - 210 = 0: 1155 of credit is still pending at the
# end of the year.
_WITHOUT_PRIOR_YEAR_CREDIT = {
    "1T": _Quarter(Decimal("2000"), Decimal("500")),
    "2T": _Quarter(Decimal("1000"), Decimal("3000")),
    "3T": _Quarter(Decimal("500"), Decimal("4000")),
    "4T": _Quarter(Decimal("1000"), Decimal("1000")),
}


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_apartado_7_applies_the_credit_brought_from_the_previous_year(filing_year: int) -> None:
    filing = _file_year(
        filing_year,
        _WITH_PRIOR_YEAR_CREDIT,
        credit_from_earlier_years=Decimal("1000.00"),
        annual_operator_inputs={_M390_TOTAL_A_INGRESAR: Decimal("0.00")},
    )
    values = filing.annual.values

    assert values[_M390_RESULTADO_REGIMEN_GENERAL] == Decimal("945.00")
    assert values[_M390_SUMA_RESULTADOS] == Decimal("945.00")
    # 105 + 630 + 265: every euro of the old credit was applied during the year.
    assert values[_M390_COMPENSACION_EJERCICIO_ANTERIOR] == Decimal("1000.00")
    assert values[_M390_RESULTADO_LIQUIDACION] == Decimal("-55.00")
    # 420 generated in 3T less the 365 of it applied in 4T.
    assert values[_M390_COMPENSACION_ULTIMO_PERIODO] + values[_M390_COMPENSACION_GENERADA_NO_97] == Decimal("55.00")
    assert values[_M390_RECONCILIACION_LIQUIDACIONES] == values[_M390_RESULTADO_LIQUIDACION]
    assert _identity_findings(filing_year, filing.annual) == []


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_apartado_7_without_previous_year_credit_reaches_a_negative_result(filing_year: int) -> None:
    filing = _file_year(
        filing_year,
        _WITHOUT_PRIOR_YEAR_CREDIT,
        credit_from_earlier_years=Decimal("0.00"),
        annual_operator_inputs={_M390_TOTAL_A_INGRESAR: Decimal("315.00")},
    )
    values = filing.annual.values

    assert [filing.quarters[period].values[_M303_RESULTADO_LIQUIDACION] for period in ("1T", "2T", "3T", "4T")] == [
        Decimal("315.00"),
        Decimal("-420.00"),
        Decimal("-735.00"),
        Decimal("0.00"),
    ]
    assert values[_M390_SUMA_RESULTADOS] == Decimal("-840.00")
    # A proven zero read from the first quarter's opening carry, not a blank box.
    assert values[_M390_COMPENSACION_EJERCICIO_ANTERIOR] == Decimal("0.00")
    assert values[_M390_RESULTADO_LIQUIDACION] == Decimal("-840.00")
    assert values[_M390_COMPENSACION_ULTIMO_PERIODO] + values[_M390_COMPENSACION_GENERADA_NO_97] == Decimal("1155.00")
    # [95] - [97] - [98] - [662] = 315 - 1155 = -840.
    assert values[_M390_RECONCILIACION_LIQUIDACIONES] == Decimal("-840.00")
    assert _identity_findings(filing_year, filing.annual) == []


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_a_blank_apartado_9_total_that_contradicts_the_result_is_reported(filing_year: int) -> None:
    filing = _file_year(filing_year, _WITHOUT_PRIOR_YEAR_CREDIT, credit_from_earlier_years=Decimal("0.00"))
    values = filing.annual.values

    # The 315.00 paid in 1T is missing from [95]: 0 - 1155 = -1155 against -840.
    assert values[_M390_RECONCILIACION_LIQUIDACIONES] == Decimal("-1155.00")
    findings = _identity_findings(filing_year, filing.annual)
    assert len(findings) == 1
    assert findings[0].kind is ModeloVerificationFindingKind.ADVISORY
    assert findings[0].message_facts == {"predicate_id": _IDENTITY_PREDICATE_ID}


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_apartado_7_restates_the_quarterly_regularisation_and_customs_import_boxes(filing_year: int) -> None:
    # 1T 420 - 210 = 210; the other quarters net to zero. 2T declares 70.00 of
    # import IVA settled by the Aduana ([77]) and 4T a 30.00 art. 80.Cinco.5a
    # regularisation ([76]).
    quarters = {
        "1T": _Quarter(Decimal("2000"), Decimal("1000")),
        "2T": _Quarter(
            Decimal("1000"), Decimal("1000"), operator_inputs={_M303_IVA_IMPORTACION_ADUANA: Decimal("70.00")}
        ),
        "3T": _Quarter(Decimal("1000"), Decimal("1000")),
        "4T": _Quarter(
            Decimal("1000"), Decimal("1000"), operator_inputs={_M303_REGULARIZACION_ART_80: Decimal("30.00")}
        ),
    }
    values = _file_year(filing_year, quarters, credit_from_earlier_years=Decimal("0.00")).annual.values

    assert values[_M390_RESULTADO_REGIMEN_GENERAL] == Decimal("210.00")
    assert values[_M390_REGULARIZACION_ART_80] == Decimal("30.00")
    assert values[_M390_IVA_IMPORTACION_ADUANA] == Decimal("70.00")
    assert values[_M390_SUMA_RESULTADOS] == Decimal("240.00")
    assert values[_M390_COMPENSACION_EJERCICIO_ANTERIOR] == Decimal("0.00")
    assert values[_M390_RESULTADO_LIQUIDACION] == Decimal("310.00")


def _operator_input_boxes(revision: ModeloRevision, numbers: frozenset[str]) -> frozenset[str]:
    return frozenset(
        casilla.number
        for casilla in revision.casillas
        if casilla.number in numbers and casilla.input_kind is InputKind.MANUAL
    )


def _apartado_7_boxes_by_number(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(casilla.number for casilla in revision.casillas if casilla.number in _APARTADO_7_BOXES)


@pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
def test_no_apartado_7_result_box_is_operator_input(filing_year: int) -> None:
    revision = compiled_bundled_authority().snapshot("390", filing_year=filing_year, period="0A").revision

    assert _apartado_7_boxes_by_number(revision) == _APARTADO_7_BOXES
    assert _operator_input_boxes(revision, _APARTADO_7_BOXES) == frozenset()
    assert _operator_input_boxes(revision, frozenset({"97", "662", *_APARTADO_9_OPERATOR_INPUT_BOXES})) == (
        _APARTADO_9_OPERATOR_INPUT_BOXES
    )
    assert any(predicate.predicate_id == _IDENTITY_PREDICATE_ID for predicate in revision.verification_predicates)


def test_an_apartado_7_result_box_turned_into_operator_input_is_caught() -> None:
    revision = compiled_bundled_authority().snapshot("390", filing_year=2025, period="0A").revision
    defective = revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"input_kind": InputKind.MANUAL, "formula": None})
                if casilla.number == "86"
                else casilla
                for casilla in revision.casillas
            ),
        },
    )

    assert _operator_input_boxes(defective, _APARTADO_7_BOXES) == frozenset({"86"})
