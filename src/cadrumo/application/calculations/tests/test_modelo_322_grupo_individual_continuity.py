"""E2E continuity: Modelo 322 individual monthly REGE autoliquidación, two renta years.

Modelo 322 is the individual monthly autoliquidación a member of an IVA
grupo de entidades files under the régimen especial del grupo (REGE,
Orden EHA/3434/2007 art. 1, LIVA arts. 163 quinquies–nonies, RD 1624/1992
art. 71). Each grupo member computes its own monthly régimen-general
result (cuota devengada − cuota deducible); the agregado flows into the
grupo's Modelo 353. Modelo 322 itself carries no compensación carry and no
cross-period relation — it is a self-contained monthly calculation whose
inputs are the period's IVA ledger.

This module is the multi-year-renta authorization enrollment for Modelo
322. The ≥2-distinct-renta-years contract is met by driving the REAL
registry calculation engine for the same monthly period (December) of two
distinct renta years (2025, 2026) over a real encrypted-SQLite-backed
isolated profile, feeding the five ledger_iva_aggregation cuota bindings
from real IVA ledger observations. Both years are recorded through the
:class:`EnrollmentRecorder` and cross-checked against the authorization
manifest via :func:`assert_enrollment_matches_manifest`.

The ``2008-2023`` revision is genuinely year-stable: it resolves
for both 2025 and 2026 with identical structure and rates (the REGE
individual form and the general/reduced/super-reduced rate set are
unchanged across the two ejercicios), so the second year is a real
filing, never a faked duplicate.

Grounding (non-tautological): the per-rate cuotas are produced by the real
ledger aggregation and the engine, never hand-computed; the load-bearing
assertion is the engine wiring invariant — ``iva.resultado-regimen-general``
equals ``iva.cuota-devengada-total`` minus ``iva.cuota-deducible-total`` —
which Orden EHA/3434/2007 defines as the monthly régimen-general result.
Modelo 322 carries no profile-source binding, so no R2-style workaround is
needed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ....tests.secure_sql import isolated_runtime_profile
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "322"

#: The two distinct renta years the enrollment spans, and the monthly period.
_RENTA_YEARS = (2025, 2026)
_PERIOD = "12"

#: Per-year IVA ledger detail (one repercutido + one soportado general-rate
#: line). Values differ per year so the second year is a distinct real filing.
_YEAR_IVA: dict[int, tuple[Decimal, Decimal]] = {
    # filing_year: (repercutido_cuota, soportado_cuota)
    2025: (Decimal("210.00"), Decimal("80.00")),
    2026: (Decimal("168.00"), Decimal("105.00")),
}


_IVA_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_IVA_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_IVA_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")


def _ledger_line(*, ledger_id: str, txn_date: date, flow: IvaFlowDirection, iva: Decimal) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal("1000.00"),
        iva_amount=iva,
        # An INPUT fact must state how its deduction was classified: the model
        # refuses a soportado or inversion-sujeto-pasivo line carrying neither a
        # fact kind nor provenance, which is what keeps an undocumented deduction
        # out of the ledger. Output lines must carry NEITHER, so this is supplied
        # only for the input direction.
        deduction_fact_kind=(
            IvaDeductionFactKind.DOMESTIC_CURRENT
            if flow in {IvaFlowDirection.SOPORTADO, IvaFlowDirection.INVERSION_SUJETO_PASIVO}
            else None
        ),
        deduction_provenance=(
            IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{ledger_id}",
                evidence_digest="a" * 64,
            )
            if flow in {IvaFlowDirection.SOPORTADO, IvaFlowDirection.INVERSION_SUJETO_PASIVO}
            else None
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _year_ledger(filing_year: int) -> tuple[IvaLedgerObservation, ...]:
    repercutido, soportado = _YEAR_IVA[filing_year]
    return (
        _ledger_line(
            ledger_id=f"{filing_year}-12-out",
            txn_date=date(filing_year, 12, 10),
            flow=IvaFlowDirection.REPERCUTIDO,
            iva=repercutido,
        ),
        _ledger_line(
            ledger_id=f"{filing_year}-12-in",
            txn_date=date(filing_year, 12, 20),
            flow=IvaFlowDirection.SOPORTADO,
            iva=soportado,
        ),
    )


def _calculate_322(*, filing_year: int) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL registry 322 monthly calculation for one renta year.

    Resolves the five ledger_iva_aggregation cuota bindings from the month's
    IVA ledger lines, resolves bound casilla inputs, and evaluates the engine.
    Returns the result plus its produced-value count (the enrollment evidence).
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=_PERIOD)
    binding_values = resolve_ledger_iva_aggregation_binding_values(snapshot.revision, _year_ledger(filing_year))
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def test_322_monthly_result_is_devengada_minus_deducible(tmp_path: Path) -> None:
    """The 322 monthly régimen-general result equals devengada minus deducible.

    The load-bearing engine wiring invariant for one renta year: the computed
    ``iva.resultado-regimen-general`` equals ``iva.cuota-devengada-total`` minus
    ``iva.cuota-deducible-total``, and the devengada total equals the
    ledger-aggregated repercutido cuota. Engine-produced; non-tautological.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, produced = _calculate_322(filing_year=_RENTA_YEARS[0])

    assert produced > 0
    devengada = result.values[_IVA_CUOTA_DEVENGADA_TOTAL_CASILLA]
    deducible = result.values[_IVA_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
    assert result.values[_IVA_RESULTADO_REGIMEN_GENERAL_CASILLA] == devengada - deducible
    repercutido, soportado = _YEAR_IVA[_RENTA_YEARS[0]]
    assert devengada == repercutido
    assert deducible == soportado


def test_modelo_322_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 322 individual monthly REGE across two renta years.

    Drives the REAL 322 backend for December of both renta years (the
    ``2008-2023`` revision resolves identically for each), records each
    through the :class:`EnrollmentRecorder` (calculation mode, evidence =
    produced-value count from a real engine run), and cross-checks the recorded
    distinct-year set against the authorization manifest claim. A single-year or
    stub run would raise, turning the gate RED.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        for filing_year in _RENTA_YEARS:
            result, produced = _calculate_322(filing_year=filing_year)
            # Wiring invariant per year: result == devengada - deducible.
            assert result.values[_IVA_RESULTADO_REGIMEN_GENERAL_CASILLA] == (
                result.values[_IVA_CUOTA_DEVENGADA_TOTAL_CASILLA] - result.values[_IVA_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
            )
            recorder.record_calculation_year(filing_year=filing_year, produced_value_count=produced)

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == _RENTA_YEARS
    assert_enrollment_matches_manifest(evidence)
