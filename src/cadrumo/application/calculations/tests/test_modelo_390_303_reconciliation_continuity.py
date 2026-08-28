"""E2E continuity: Modelo 390 annual IVA resumen reconciles the year's 303s.

The annual IVA resumen (Modelo 390) reconciles the four quarterly Modelo
303 autoliquidaciones filed during the ejercicio (Orden EHA/3111/2009 art.
1, RD 1624/1992 art. 71). The registry models this with ``relation_prefill``
bindings backed by ``cross_model_output`` relations that fold a 303 result
casilla across the four quarters of the same filing year:

- ``modelo-390-prev-303-cuota-devengada-total`` → casilla
  ``iva.anual.reconciliacion.devengada-303`` (sum of the four 303
  ``iva.cuota-devengada-total``)
- ``modelo-390-prev-303-cuota-deducible-total`` →
  ``iva.anual.reconciliacion.deducible-303``
- ``modelo-390-prev-303-resultado-regimen-general`` →
  ``iva.anual.reconciliacion.resultado-303``

These bindings resolve through :func:`resolve_relations_from_local_store`
and :func:`materialize_relation_binding_values` (the relation path), not
the ``previous_filing`` path.

This module is the multi-year-renta authorization enrollment for Modelo
390. It drives the REAL backend (real encrypted-SQLite observation store,
the real registry authority, the real registry calculation engine, the
real relation resolver — no mocks) across two distinct renta years: for
each of 2024 and 2025 it computes the four 303 quarters, persists them as
filed observations, then computes the 390/0A annual and asserts the annual
reconciliation casillas equal the sum of the four quarters. Both annual
computations are recorded through the :class:`EnrollmentRecorder` and
cross-checked against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

Grounding (non-tautological): each 303 quarter's totals are produced by
the engine, never hand-computed; the load-bearing assertion is the
reconciliation invariant — the 390 annual computed total equals the
relation-resolved reconciliation casilla, which is exactly the 390↔303
consistency the resumen exists to express. The R2 registry-gap workaround
(``modelo-303-autoconsumo-promotor-base = 0`` and
``modelo-303-profile-state-attribution-ratio = 100``) is applied when
building the source 303 quarters; 390's own casillas carry no
profile-source binding. Official 303 boxes [27] and [45] are projections
from the semantic totals and are not supplied as inputs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import (
    CasillaId,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
    derive_result_disposition,
    result_disposition_casilla_ids,
    validated_casilla_id,
)
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from ....domain.calculations.registry.relations import materialize_relation_binding_values
from ....domain.iva import (
    IvaCategory,
    IvaDeductionClassificationProvenance,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .._iva_compensation_annual_partition import IvaCompensationAnnualPartitionSourceResolver
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from .._relation_prefill import resolve_relations_from_local_store
from ..observations_repository import CalculationObservationRepository, ResultDispositionProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "390"

#: The two distinct renta years the resumen reconciliation spans.
_RENTA_YEARS = (2024, 2025)

#: Quarterly periods of a renta year, summed by the 390 previous_filing bindings.
_QUARTERS = ("1T", "2T", "3T", "4T")


#: 390 annual computed totals and the parallel reconciliation casillas filled
#: from the four 303 quarters via the relation resolver. The wiring invariant
#: asserts each pair is equal.
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.anual.resultado-regimen-general")
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")
_RECONCILIATION_PAIRS: tuple[tuple[CasillaId, CasillaId], ...] = (
    (_M390_CUOTA_DEVENGADA_TOTAL_CASILLA, _M390_RECONCILIACION_DEVENGADA_303_CASILLA),
    (_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA, _M390_RECONCILIACION_DEDUCIBLE_303_CASILLA),
    (_M390_RESULTADO_REGIMEN_GENERAL_CASILLA, _M390_RECONCILIACION_RESULTADO_303_CASILLA),
)
_M390_BIENES_INVERSION_REGULARIZACION_BINDING = "modelo-390-bienes-inversion-regularizacion-casilla-63"

#: 303 profile-gap workaround bindings (see module docstring / R2). Supplied
#: when building the source quarters because the direct-calculate path does not
#: run the profile resolver.
_303_AUTOCONSUMO_PROMOTOR_BASE_BINDING = "modelo-303-autoconsumo-promotor-base"
_303_STATE_ATTRIBUTION_RATIO_BINDING = "modelo-303-profile-state-attribution-ratio"
_303_CARRY_BINDING = "modelo-303-compensacion-pendiente-anteriores"

_CLOCK = datetime(2026, 1, 20, 9, 0, 0, tzinfo=UTC)

# Per-quarter IVA ledger detail for one renta year: one repercutido (output)
# and one soportado (input) line per quarter, both general-rate 21%. The 303
# ledger_iva_aggregation bindings populate iva.cuota-devengada-total (from
# repercutido) and iva.cuota-deducible-total (from soportado); the 390 sums the
# four quarters' computed totals. Values vary per quarter so the annual sum is a
# non-trivial aggregate, not a single repeated figure. Engine-derived totals.
_QUARTER_IVA: dict[str, tuple[Decimal, Decimal]] = {
    # period: (repercutido_cuota, soportado_cuota)
    "1T": (Decimal("100.00"), Decimal("40.00")),
    "2T": (Decimal("80.00"), Decimal("30.00")),
    "3T": (Decimal("120.00"), Decimal("50.00")),
    "4T": (Decimal("90.00"), Decimal("60.00")),
}


def _ledger_line(*, ledger_id: str, txn_date: date, flow: IvaFlowDirection, iva: Decimal) -> IvaLedgerObservation:
    """Build one quarter-ledger row, carrying deduction authority on input flows only.

    The observation model splits the two directions: an input row (``soportado``,
    ``inversion_sujeto_pasivo``) MUST carry the exact statutory deduction family
    and its evidence provenance, and an output row MUST NOT carry either. A
    fixture that supplied both unconditionally, or neither, is refused by the
    model rather than silently recorded -- which is the point, since the 390
    annual return reconciles against the summed quarters and an input row with
    invented authority would reconcile just as cleanly as a real one.
    """
    is_input_flow = flow in {IvaFlowDirection.SOPORTADO, IvaFlowDirection.INVERSION_SUJETO_PASIVO}
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal("100.00"),
        iva_amount=iva,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT if is_input_flow else None,
        deduction_provenance=(
            IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{ledger_id}",
                evidence_digest="d" * 64,
            )
            if is_input_flow
            else None
        ),
    )


def _quarter_ledger(filing_year: int, period: str) -> tuple[IvaLedgerObservation, ...]:
    repercutido, soportado = _QUARTER_IVA[period]
    month = {"1T": 2, "2T": 5, "3T": 8, "4T": 11}[period]
    return (
        _ledger_line(
            ledger_id=f"{filing_year}-{period}-out",
            txn_date=date(filing_year, month, 10),
            flow=IvaFlowDirection.REPERCUTIDO,
            iva=repercutido,
        ),
        _ledger_line(
            ledger_id=f"{filing_year}-{period}-in",
            txn_date=date(filing_year, month, 20),
            flow=IvaFlowDirection.SOPORTADO,
            iva=soportado,
        ),
    )


def _calculate_303_quarter(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    """Run the REAL registry 303 calculation for one quarter from IVA ledger detail.

    Resolves the ledger_iva_aggregation cuota bindings from the quarter's IVA
    ledger lines (so iva.cuota-devengada-total / -deducible-total are populated),
    supplies the R2 profile-gap workaround facts and a zero prior-period carry,
    resolves bound casilla inputs, then evaluates the engine.
    """
    snapshot = bundled_authority().snapshot("303", filing_year=filing_year, period=period)
    binding_values = {
        _303_CARRY_BINDING: Decimal("0"),
        _303_AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0"),
        _303_STATE_ATTRIBUTION_RATIO_BINDING: Decimal("100"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = {
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        relation_values={},
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def _registry_observation(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )


def _filing_result_disposition(result: RegistryCalculationResult):
    """Use the production result-disposition resolver at this test filing boundary."""
    casilla_ids = result_disposition_casilla_ids("303")
    assert casilla_ids is not None
    disposition = derive_result_disposition(
        "303",
        {casilla_id: Decimal(result.values[casilla_id]) for casilla_id in casilla_ids},
    )
    assert disposition is not None
    return disposition


def _calculate_390_annual(
    *,
    filing_year: int,
    annual_ledger: tuple[IvaLedgerObservation, ...],
    repository: CalculationObservationRepository,
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL 390/0A annual calculation reconciling the year's 303 quarters.

    Resolves the ``relation_prefill`` bindings (the 303-quarter sums) from
    the local observation store via the relation resolver and the 390 annual
    ledger_iva_aggregation bindings from the full year's IVA ledger (the union
    of the four quarters' lines), resolves bound casilla inputs, and evaluates
    the engine. The annual computed totals (from the ledger) and the
    reconciliation casillas (from the 303 quarter sums via relation resolver)
    describe the same ejercicio, so they must agree. Returns the result plus
    its produced-value count (the enrollment evidence).
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period="0A")
    relation_vals = resolve_relations_from_local_store(snapshot, repository=repository)
    relation_values_map = {rv.relation: rv.value for rv in relation_vals.values if rv.value is not None}
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values_map, period="0A")
    annual_partition = IvaCompensationAnnualPartitionSourceResolver(
        repository=repository,
        registry_snapshot=snapshot,
    ).resolve(
        CalculationSourceContext(
            bucket_id="m390-reconciliation-continuity",
            modelo=_MODELO,
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "0A"),
            revision=snapshot.revision,
        ),
    )
    binding_values = {
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, annual_ledger),
        **relation_binding_values,
        **annual_partition.binding_values,
        # This reconciliation fixture has no capital-goods register entries; the
        # annual casilla 63 binding is therefore an explicit zero fact.
        _M390_BIENES_INVERSION_REGULARIZACION_BINDING: Decimal("0"),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def _file_year_quarters_and_reconcile(
    *,
    filing_year: int,
    repository: CalculationObservationRepository,
) -> tuple[RegistryCalculationResult, int, dict[str, Decimal]]:
    """File the four 303 quarters of one renta year, then compute the 390 annual.

    Returns the 390 result, its produced-value count, and the per-quarter
    devengada totals (for an independent sum check of the reconciliation).
    """
    quarter_devengada: dict[str, Decimal] = {}
    annual_ledger: list[IvaLedgerObservation] = []
    for period in _QUARTERS:
        ledger = _quarter_ledger(filing_year, period)
        annual_ledger.extend(ledger)
        q_result = _calculate_303_quarter(filing_year=filing_year, period=period, observations=ledger)
        quarter_devengada[period] = q_result.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        repository.save(
            repository.prepare_observation_envelope(
                _registry_observation(modelo="303", filing_year=filing_year, period=period, result=q_result),
                source_kind="app_filing",
                captured_at=_CLOCK,
                result_disposition=ResultDispositionProjection(
                    disposition=_filing_result_disposition(q_result),
                    provenance_kind="app_filing",
                    provenance_locator=f"test-local-filing:{filing_year}:{period}",
                ),
                normalize_m303_carry=True,
            )
        )
    annual_result, produced = _calculate_390_annual(
        filing_year=filing_year,
        annual_ledger=tuple(annual_ledger),
        repository=repository,
    )
    return annual_result, produced, quarter_devengada


def test_390_annual_reconciles_to_sum_of_303_quarters(tmp_path: Path) -> None:
    """The 390 annual reconciliation casillas equal the sum of the four 303 quarters.

    The load-bearing wiring invariant: for each (computed annual total,
    relation-resolved reconciliation) casilla pair the two are equal, and the
    devengada reconciliation independently equals the arithmetic sum of the
    four quarters' ``iva.cuota-devengada-total``. Engine-produced quarter
    values; non-tautological.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        annual_result, produced, quarter_devengada = _file_year_quarters_and_reconcile(
            filing_year=_RENTA_YEARS[0],
            repository=repository,
        )

    assert produced > 0
    for computed_total, reconciliation in _RECONCILIATION_PAIRS:
        assert annual_result.values[computed_total] == annual_result.values[reconciliation], (
            f"390 {computed_total} must reconcile to {reconciliation} from the four 303 quarters"
        )
    assert annual_result.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA] == sum(
        quarter_devengada.values(),
        Decimal("0"),
    )


def test_390_reconciliation_isolates_renta_years(tmp_path: Path) -> None:
    """A year's 390 reconciliation sums only that year's 303 quarters.

    Files distinct quarter sets for two renta years into one store and asserts
    each year's 390 reconciliation reflects only its own quarters — the
    cross-renta isolation that the relation's ``source_revision_selector``
    and ``filing_year`` derivation guarantees.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        annual_earlier, _, devengada_earlier = _file_year_quarters_and_reconcile(
            filing_year=_RENTA_YEARS[0],
            repository=repository,
        )
        annual_later, _, devengada_later = _file_year_quarters_and_reconcile(
            filing_year=_RENTA_YEARS[1],
            repository=repository,
        )

    assert annual_earlier.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA] == sum(
        devengada_earlier.values(),
        Decimal("0"),
    )
    assert annual_later.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA] == sum(
        devengada_later.values(),
        Decimal("0"),
    )


def test_modelo_390_reconciliation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 390 annual reconciliation across two renta years.

    Drives the REAL 390 backend for both renta years (each reconciling its own
    four 303 quarters), records each annual computation through the
    :class:`EnrollmentRecorder` (calculation mode, evidence = produced-value
    count from a real engine run), and cross-checks the recorded distinct-year
    set against the authorization manifest claim. A single-year or stub run
    would raise, turning the gate RED.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        for filing_year in _RENTA_YEARS:
            annual_result, produced, quarter_devengada = _file_year_quarters_and_reconcile(
                filing_year=filing_year,
                repository=repository,
            )
            # Wiring invariant per year: annual computed total == 303-quarter sum.
            assert (
                annual_result.values[_M390_CUOTA_DEVENGADA_TOTAL_CASILLA]
                == annual_result.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA]
            )
            assert annual_result.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA] == sum(
                quarter_devengada.values(),
                Decimal("0"),
            )
            recorder.record_calculation_year(filing_year=filing_year, produced_value_count=produced)

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == _RENTA_YEARS
    assert_enrollment_matches_manifest(evidence)
