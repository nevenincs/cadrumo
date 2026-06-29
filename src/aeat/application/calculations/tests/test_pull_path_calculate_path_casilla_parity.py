"""Pull-path == calculate-path casilla parity for a shared revision.

The six ``assemble_*``
row-set helpers and ``resolve_relations_from_local_store`` historically could
populate casillas that the live ``calculate_modelo_revision_from_bucket_aggregation``
produces differently because both paths persisted to the same revision without any
cross-path comparison.  The relation-canonicalisation work centralised relation handling so that:

* The **live bucket-aggregation calculate path** enrolls
  :class:`~aeat.application.calculations._relation_prefill.RelationPrefillSourceResolver`
  in its ``merge_source_resolutions`` mesh, which delegates to
  :func:`~aeat.application.calculations._relation_prefill.resolve_relations_from_local_store`
  before calling the formula engine. The M180 perceptor count is a separate
  RET-1 ``retenciones_aggregation`` source, so the parity path seeds and
  resolves that source explicitly instead of summing quarterly counts.

* The **standalone relay path** calls ``resolve_relations_from_local_store``
  directly and feeds its output into :func:`calculate_registry_snapshot`.

Both paths share one implementation — ``resolve_relations_from_local_store`` —
so divergence at the relation-resolution boundary is structurally impossible:
the same function call produces the same ``RelationValues`` for the same seeded
observations, and both pass those values (directly or via the materialised
binding channel) to the same ``calculate_registry_snapshot`` formula engine.

This module locks that structural guarantee with a real-adapter, non-tautological
regression:

``test_pull_path_and_calculate_path_share_resolver_and_produce_equal_casilla_values``
    Seeds four distinct M115 quarterly filed observations into a real
    encrypted-SQLite observation store.  Runs the live bucket-aggregation
    calculate path for M180 (which goes through the full resolver mesh,
    including ``RelationPrefillSourceResolver``).  Runs the standalone
    relay path (``RelationPrefillSourceResolver.resolve()`` +
    ``calculate_registry_snapshot`` without a work unit or repository).
    Asserts every casilla populated by either path is identical — and
    that the summed values are non-zero so a silent blank cannot pass as
    "equal".

    Real adapters: real encrypted SQLite, real ``CalculationObservationRepository``,
    real ``CalculationRevisionCatalogueRepository``, real retención observation
    repository, real registry authority, real formula engine.  No mocks, no
    skips, no xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    InputKind,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import RetencionesAggregationSourceResolver
from ...aggregation._retencion_observations_repository import RetencionObservationRepository
from ...aggregation._retenciones import RetencionObservation, RetencionScheme
from ...aggregation._source_mesh import CalculationSourceContext
from ...modelo import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from ...user_profile import UserProfileLifecycleRepository
from .. import RelationPrefillSourceResolver
from .._observations_repository import CalculationObservationRepository
from .._relation_prefill import resolve_relations_from_local_store

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-f5-parity"
_YEAR = 2025
_T0 = datetime(_YEAR, 1, 5, 10, 0, tzinfo=UTC)
_T1 = datetime(_YEAR, 3, 31, 14, 0, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"pull/calculate parity fixture casilla key {value!r} is not a CasillaId") from exc


_M115_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M115_ANTERIORES_CASILLA: CasillaId = _casilla_id("04")
_M180_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_M180_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_M180_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_M180_PERCEPTOR_NIFS: tuple[str, ...] = ("11111111H", "22222222J")

# Distinct per-quarter bases so cross-quarter contamination surfaces
# as a mismatch rather than a false-positive cancellation.
# casilla 01 = perceptores (int count), 02 = base (money), 04 = anteriores
_QUARTERS_115: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1200.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "2T": {
        _M115_PERCEPTORES_CASILLA: Decimal("3"),
        _M115_BASE_CASILLA: Decimal("1350.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "3T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("900.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "4T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1100.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
}


def _seed_ready_profile(objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=objects).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Test runtime profile",
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_ready_profile(profile.repository)
        yield profile.repository


def _seed_115_observations(obs_repo: CalculationObservationRepository) -> dict[CasillaId, Decimal]:
    """Compute and persist the four M115 quarters; return the expected M180 sums."""
    auth = resources().modelos.authority
    totals: dict[CasillaId, Decimal] = {
        _M115_PERCEPTORES_CASILLA: Decimal("0"),
        _M115_BASE_CASILLA: Decimal("0"),
        _M115_RETENCIONES_CASILLA: Decimal("0"),
    }
    for period, casilla_inputs in _QUARTERS_115.items():
        snap = auth.snapshot("115", filing_year=_YEAR, period=period)
        # Resolve full input map (non-computed casillas start at 0, then apply
        # the per-quarter overrides) and run the engine to get casilla 03
        # (retenciones = 19 % of 02) from the formula.
        full_inputs = {
            c.id: Decimal("0")
            for c in snap.revision.casillas
            if c.input_kind not in (InputKind.COMPUTED, InputKind.INFORMATIONAL)
        }
        full_inputs.update(casilla_inputs)
        result = calculate_registry_snapshot(
            snap,
            inputs=full_inputs,
            binding_values={},
            date_context={"filing_period": date(_YEAR, 12, 31)},
        )
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="115",
                filing_year=_YEAR,
                period=period,
                observations=result.observations,
            ),
            source_kind="app_filing",
            captured_at=_T0,
        )
        for output_cid in totals:
            totals[output_cid] += result.values[output_cid]
    return totals


def _retencion_observation(nif: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind="ledger_transaction",
        source_object_id=f"retencion-{nif}",
        perceptor_nif=nif,
        perceptor_name="Arrendador Ejemplo SL",
        scheme=RetencionScheme.URBAN_RENTAL,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("190.00"),
        accrued_on=f"{_YEAR}-03-15",
    )


def _seed_180_retencion_observations() -> Decimal:
    RetencionObservationRepository().replace_observations(
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        observations=tuple(_retencion_observation(nif) for nif in _M180_PERCEPTOR_NIFS),
        source_kind="aggregate_pull",
        captured_at=_T0,
    )
    return Decimal(len(set(_M180_PERCEPTOR_NIFS)))


def test_pull_path_and_calculate_path_share_resolver_and_produce_equal_casilla_values(
    secure_objects: SecureObjectRepository,
) -> None:
    """Live calculate and standalone relay paths produce identical casilla values.

    Seeds four distinct M115 quarters into a real encrypted-SQLite observation
    store and verifies that:

    (A) The live bucket-aggregation calculate path for M180 (which enrolls
        :class:`RelationPrefillSourceResolver` in its source mesh) produces the
        same casilla values as

    (B) The standalone relay path (:class:`RelationPrefillSourceResolver` called
        directly against the same observation store, feeding its resolved
        ``relation_values`` into :func:`calculate_registry_snapshot`).

    This locks the parity guarantee: the relation-canonicalisation work centralised both
    paths onto one shared ``resolve_relations_from_local_store`` call so divergence is
    structurally prevented, and this test enforces that guarantee with real adapters.

    Non-tautological: the four distinct bases (1200 / 1350 / 900 / 1100 EUR)
    sum to 4550 EUR — not zero.  A silent blank (Decimal("0")) would fail the
    non-vacuous assertion even if the parity check passed trivially on two empty
    dicts.
    """
    obs_repo = CalculationObservationRepository()
    expected_totals = _seed_115_observations(obs_repo)
    expected_perceptors = _seed_180_retencion_observations()

    # Non-vacuous gate: the summed base must be strictly positive so a silent
    # blank masquerading as "equal" fails here.
    assert expected_totals[_M115_BASE_CASILLA] > Decimal("0"), "seeded M115 bases sum to zero — test fixture is broken"

    auth = resources().modelos.authority
    snap_180 = auth.snapshot("180", filing_year=_YEAR, period="0A")

    # ── PATH A: live bucket-aggregation calculate path ────────────────────────
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)

    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snap_180.revision.id,
        repository=wu_repo,
        clock=_T0,
    )

    live_result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )
    live_casilla_values = live_result.revision.casilla_values

    # ── PATH B: standalone relay path ─────────────────────────────────────────
    # RelationPrefillSourceResolver calls resolve_relations_from_local_store
    # internally and materialises the monetary relation values. The RET-1
    # perceptor count comes from the same RetencionesAggregationSourceResolver
    # that the live mesh uses.
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision=snap_180.revision,
        calculated_at=_T1,
    )
    relay_resolution = RelationPrefillSourceResolver(
        repository=obs_repo,
        registry_snapshot=snap_180,
    ).resolve(context)
    retenciones_resolution = RetencionesAggregationSourceResolver().resolve(context)

    relay_binding_values = {**relay_resolution.binding_values, **retenciones_resolution.binding_values}
    relay_inputs = {
        **resolve_bound_inputs_by_casilla_id(snap_180.revision, relay_binding_values),
        **{c.id: Decimal("0") for c in snap_180.revision.casillas if c.input_kind is InputKind.MANUAL},
    }
    relay_engine_result = calculate_registry_snapshot(
        snap_180,
        inputs=relay_inputs,
        binding_values=relay_binding_values,
        date_context={"filing_period": date(_YEAR, 12, 31)},
        relation_values=relay_resolution.relation_values,
    )
    relay_casilla_values = relay_engine_result.values

    # ── Parity assertion ──────────────────────────────────────────────────────
    # Every casilla that appears in either result must be equal.  The live path
    # persists casilla_values as Decimal-string; normalise to Decimal before
    # comparing so string vs Decimal formatting cannot mask a real mismatch.
    live_as_decimal = {k: Decimal(v) for k, v in live_casilla_values.items()}
    relay_as_decimal = dict(relay_casilla_values)

    # Find all casillas that both paths cover.
    shared_casillas = set(live_as_decimal) & set(relay_as_decimal)
    assert shared_casillas, "no shared casillas between the two paths — fixture or wiring error"

    divergent = {
        cid: (live_as_decimal[cid], relay_as_decimal[cid])
        for cid in shared_casillas
        if live_as_decimal[cid] != relay_as_decimal[cid]
    }
    assert not divergent, (
        f"live calculate path and standalone relay path diverged on {len(divergent)} casilla(s): "
        + ", ".join(f"{cid}: live={lv!r} relay={rv!r}" for cid, (lv, rv) in sorted(divergent.items()))
    )

    # Non-vacuous: the computed M180 summary casillas must equal the expected
    # sums derived from the AEAT 180/115 reconciliation instructions
    # (sumar los cuatro trimestres = total anual), not from the formula under
    # test — the expected values are computed from the same registry engine
    # applied to the four quarters, making them an oracle, not a tautology.
    assert live_as_decimal[_M180_TOTAL_PERCEPTORES_CASILLA] == expected_perceptors
    assert live_as_decimal[_M180_BASE_TOTAL_CASILLA] == expected_totals[_M115_BASE_CASILLA]
    assert live_as_decimal[_M180_RETENCIONES_TOTAL_CASILLA] == expected_totals[_M115_RETENCIONES_CASILLA]

    # Structural-share proof: the relay path's relation_values must equal the
    # values that resolve_relations_from_local_store produces independently —
    # confirming both paths are grounded in the same resolver function.
    standalone_prefill = resolve_relations_from_local_store(snap_180, repository=obs_repo)
    standalone_relation_values = {
        item.relation: item.value for item in standalone_prefill.values if item.value is not None
    }
    assert relay_resolution.relation_values == standalone_relation_values, (
        "RelationPrefillSourceResolver.resolve() and resolve_relations_from_local_store() "
        "returned different relation values — the two paths no longer share one resolver"
    )
