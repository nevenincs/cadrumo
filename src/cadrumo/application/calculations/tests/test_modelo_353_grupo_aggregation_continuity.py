"""E2E continuity: Modelo 353 grupo-entidades monthly aggregation of member 322s.

Exercises the LANDED A2 ``per_grupo_member`` cross-member aggregation (contract):
``PreviousModeloSelector`` ``grouping = "per_grupo_member"`` axis, the opt-in
enumerate-then-sum resolver branch, the three ``modelo-353-prev-322-*``
bindings, and the member-NIF-widened observation storage
(:func:`save_observation` ``member_nif=...``). Distinct members' 322 filings
for the same ``(modelo, filing_year, period)`` are persisted member-distinctly
via :func:`_save_member_322_observation`; the resolver enumerates and sums them.

Modelo 353 is the agregado del grupo filed monthly by the entidad
dominante; each grupo member files its own Modelo 322 (Orden EHA/3434/2007
arts. 1-2, LIVA grupo de entidades régimen). The pair's defining identity:

    353[mes M].reconciliacion == Σ_members member-322[mes M].result

across the three result casillas the two modelos share identically —
``iva.cuota-devengada-total``, ``iva.cuota-deducible-total``,
``iva.resultado-regimen-general`` (A2 research F1) — surfaced on 353 as the
``iva.reconciliacion.{devengada,deducible,resultado}-322`` bound casillas. This
is the monthly, cross-MEMBER analogue of the annual, cross-PERIOD, single-filer
390←303 reconciliation: the 353 ``modelo-353-prev-322-*`` bindings are
``source = "previous_filing"`` with ``grouping = "per_grupo_member"``,
``source_period_offset_from_target = 0`` (same month) and
``aggregation = { op = "sum" }`` (A2 contract Part 1).

Two axes, asserted separately:
- Inv1 (cross-member): for mes 12 of year N, each 353 reconciliation casilla
  equals the sum across the two members' 322 result casillas.
- Inv2 (cross-renta isolation): the same aggregation applies independently to
  mes 12 of two distinct renta years (2025, 2026), each summing only its own
  month's members — the per-period isolation the offset-0 same-period anchor
  guarantees and the year-over-year continuity of the régimen.

Spanning years N and N+1 satisfies the foundational gate's
≥2-distinct-renta-years requirement; the recorder observes both years.

Grounding (non-tautological, A2 constraints): no public AEAT grupo workbook
exists, so the test asserts the cross-member SUM IDENTITY, the per-period
isolation, member-count (guarding the double-count pitfall the resolver no
longer catches on this path), and provenance — never a hand-computed
figure. Member 322 totals are engine-produced.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, IvaDeductionEvidenceAuthority, IvaDeductionFactKind, validated_casilla_id
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
from ....domain.iva import (
    IvaCategory,
    IvaDeductionClassificationProvenance,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._binding_prefill import resolve_bindings_from_local_store
from .._multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "353"

#: The two distinct renta years the grupo aggregation + carry spans.
_RENTA_YEARS = (2025, 2026)

#: Each member's 322 result casilla (key) maps to the 353 reconciliation casilla
#: (value) that carries the per_grupo_member cross-member SUM of it. The 353's
#: own iva.cuota-* casillas are its (ledger-derived) aggregate; the reconciliation
#: casillas are the previous_filing sum of the members' 322s — the A2 invariant
#: asserts each reconciliation casilla equals Σ members' 322 source casilla.


def _reconciliation_pair(source: object, target: object) -> tuple[CasillaId, CasillaId]:
    return (
        validated_casilla_id(source, surface="test_modelo_353_grupo_aggregation_continuity.casilla"),
        validated_casilla_id(target, surface="test_modelo_353_grupo_aggregation_continuity.casilla"),
    )


_RECONCILIATION_BY_322_CASILLA: dict[CasillaId, CasillaId] = dict(
    (
        _reconciliation_pair("iva.cuota-devengada-total", "iva.reconciliacion.devengada-322"),
        _reconciliation_pair("iva.cuota-deducible-total", "iva.reconciliacion.deducible-322"),
        _reconciliation_pair("iva.resultado-regimen-general", "iva.reconciliacion.resultado-322"),
    ),
)
_RESULT_CASILLAS: tuple[CasillaId, ...] = tuple(_RECONCILIATION_BY_322_CASILLA)

#: The two grupo members whose monthly 322s the entidad dominante aggregates.
#: Distinct NIFs so the per-member storage keeps them separate (the resolver
#: enumerates them; member identity is carried on the enrollment side).
_MEMBER_NIFS = ("A00000000", "B00000001")

#: Per-member December IVA ledger detail (repercutido, soportado) for year N.
#: Members differ so the cross-member sum is a non-trivial aggregate.
_MEMBER_DEC_IVA: dict[str, tuple[Decimal, Decimal]] = {
    "A00000000": (Decimal("210.00"), Decimal("80.00")),
    "B00000001": (Decimal("168.00"), Decimal("90.00")),
}


def _ledger_line(*, ledger_id: str, txn_date: date, flow: IvaFlowDirection, iva: Decimal) -> IvaLedgerObservation:
    is_input = flow is IvaFlowDirection.SOPORTADO
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=flow,
        base_amount=Decimal("1000.00"),
        iva_amount=iva,
        deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT if is_input else None,
        deduction_provenance=(
            IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{ledger_id}",
                evidence_digest="a" * 64,
            )
            if is_input
            else None
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _member_ledger(*, member_nif: str, filing_year: int, period: str) -> tuple[IvaLedgerObservation, ...]:
    repercutido, soportado = _MEMBER_DEC_IVA[member_nif]
    month = int(period)
    return (
        _ledger_line(
            ledger_id=f"{member_nif}-{filing_year}-{period}-out",
            txn_date=date(filing_year, month, 10),
            flow=IvaFlowDirection.REPERCUTIDO,
            iva=repercutido,
        ),
        _ledger_line(
            ledger_id=f"{member_nif}-{filing_year}-{period}-in",
            txn_date=date(filing_year, month, 20),
            flow=IvaFlowDirection.SOPORTADO,
            iva=soportado,
        ),
    )


def _calculate_322_member(*, member_nif: str, filing_year: int, period: str) -> RegistryCalculationResult:
    """Run the REAL 322 monthly calculation for one grupo member."""
    snapshot = bundled_authority().snapshot("322", filing_year=filing_year, period=period)
    binding_values = resolve_ledger_iva_aggregation_binding_values(
        snapshot.revision,
        _member_ledger(member_nif=member_nif, filing_year=filing_year, period=period),
    )
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, int(period), 28)},
    )


def _member_322_observation(
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="322",
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )


def _save_member_322_observation(
    repository: CalculationObservationRepository,
    *,
    member_nif: str,
    observation: RegistryModeloObservation,
) -> None:
    """Persist one grupo member's 322 distinctly for the same (modelo, year, period).

    Uses the landed A2 member-NIF storage extension:
    :meth:`CalculationObservationRepository.save_observation` accepts
    ``member_nif`` and widens the storage identifier (see
    :func:`member_observation_key`) so two members' filings for the same
    ``(modelo, filing_year, period)`` persist as distinct rows the resolver
    enumerates, rather than overwriting one another.
    """
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            member_nif=member_nif,
        )
    )


def _resolve_353_aggregate(
    *,
    filing_year: int,
    period: str,
    repository: CalculationObservationRepository,
) -> RegistryCalculationResult:
    """Run the REAL 353 monthly aggregate, summing members' 322 via per_grupo_member.

    The three ``modelo-353-prev-322-*`` bindings (``grouping = "per_grupo_member"``)
    resolve through :func:`resolve_bindings_from_local_store` — the same entry
    point as 390's prev-303 bindings — enumerating and summing every member's
    322 for ``(322, filing_year, period)``.
    """
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period=period)
    prefill = resolve_bindings_from_local_store(snapshot, repository=repository)
    binding_values = {
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()),
        **prefill.binding_values,
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, int(period), 28)},
    )


def _file_members_and_aggregate(
    *,
    filing_year: int,
    period: str,
    repository: CalculationObservationRepository,
) -> tuple[RegistryCalculationResult, dict[str, dict[CasillaId, Decimal]]]:
    """File both members' 322 for one month, then compute the 353 aggregate.

    Returns the 353 result and the per-member 322 result-casilla values (for the
    independent cross-member sum check).
    """
    member_results: dict[str, dict[CasillaId, Decimal]] = {}
    for member_nif in _MEMBER_NIFS:
        member_result = _calculate_322_member(member_nif=member_nif, filing_year=filing_year, period=period)
        member_results[member_nif] = {cid: member_result.values[cid] for cid in _RESULT_CASILLAS}
        _save_member_322_observation(
            repository,
            member_nif=member_nif,
            observation=_member_322_observation(filing_year=filing_year, period=period, result=member_result),
        )
    aggregate = _resolve_353_aggregate(filing_year=filing_year, period=period, repository=repository)
    return aggregate, member_results


def test_353_aggregate_equals_cross_member_sum_of_322(tmp_path: Path) -> None:
    """Inv1 (cross-member): 353[12/N] aggregate == Σ members' 322[12/N] result casillas.

    The load-bearing sum identity for one month: each of the three 353 result
    casillas equals the arithmetic sum across the two members' 322 of the same
    casilla. Member-count is asserted to guard the double-count pitfall the
    resolver no longer catches on the per_grupo_member path. Engine-produced
    member figures; non-tautological (no hand-computed aggregate).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        aggregate, member_results = _file_members_and_aggregate(
            filing_year=_RENTA_YEARS[0],
            period="12",
            repository=repository,
        )

    assert len(member_results) == len(_MEMBER_NIFS)
    for source_casilla, reconciliation_casilla in _RECONCILIATION_BY_322_CASILLA.items():
        expected = sum((member_results[nif][source_casilla] for nif in _MEMBER_NIFS), Decimal("0"))
        assert aggregate.values[reconciliation_casilla] == expected, (
            f"353 {reconciliation_casilla} must equal the cross-member sum of the two 322s' {source_casilla}"
        )


def test_353_reconciliation_isolates_renta_periods(tmp_path: Path) -> None:
    """Inv2 (cross-renta isolation): each month's 353 sums only that month's members.

    Files the two members' 322 for 12/2025 and (distinct figures) for 12/2026 into
    one store and asserts each year's 353 reconciliation reflects only its own
    month's members — the per-period isolation the same-period (offset-0)
    per_grupo_member anchor guarantees, and the cross-renta continuity (the
    aggregation applies identically across two distinct renta years).
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        agg_2025, members_2025 = _file_members_and_aggregate(
            filing_year=_RENTA_YEARS[0],
            period="12",
            repository=repository,
        )
        agg_2026, members_2026 = _file_members_and_aggregate(
            filing_year=_RENTA_YEARS[1],
            period="12",
            repository=repository,
        )

    for source_casilla, reconciliation_casilla in _RECONCILIATION_BY_322_CASILLA.items():
        exp_2025 = sum((members_2025[nif][source_casilla] for nif in _MEMBER_NIFS), Decimal("0"))
        exp_2026 = sum((members_2026[nif][source_casilla] for nif in _MEMBER_NIFS), Decimal("0"))
        assert agg_2025.values[reconciliation_casilla] == exp_2025
        assert agg_2026.values[reconciliation_casilla] == exp_2026


def test_modelo_353_grupo_aggregation_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 353 grupo aggregation across two renta years.

    Drives the REAL 353 aggregate for mes 12 of both renta years (each summing
    the two members' real 322s), records each year through the
    :class:`EnrollmentRecorder`, and cross-checks the recorded distinct-year set
    against the authorization manifest claim. The cross-member sum identity is
    re-asserted per year. Spanning N and N+1 meets the ≥2-distinct-renta-years
    gate; a single-year or stub run would raise.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        for filing_year in _RENTA_YEARS:
            repository = CalculationObservationRepository()
            aggregate, member_results = _file_members_and_aggregate(
                filing_year=filing_year,
                period="12",
                repository=repository,
            )
            for source_casilla, reconciliation_casilla in _RECONCILIATION_BY_322_CASILLA.items():
                expected = sum((member_results[nif][source_casilla] for nif in _MEMBER_NIFS), Decimal("0"))
                assert aggregate.values[reconciliation_casilla] == expected
            recorder.record_calculation_year(filing_year=filing_year, produced_value_count=len(aggregate.values))

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == _RENTA_YEARS
    assert_enrollment_matches_manifest(evidence)
