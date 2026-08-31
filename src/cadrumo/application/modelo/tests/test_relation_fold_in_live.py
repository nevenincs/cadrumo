"""Relation cross-modelo fold-in fires on the LIVE calculate path.

Previously the registry relations were dead on the live operator calculate
path: ``RelationPrefillSourceResolver`` was not enrolled in the
``merge_source_resolutions`` mesh, so a cross-modelo fold-in (M180 annual ←
M115 quarterly, M100 pagos-fraccionados ← M130, the M180/M190/M193
reconciliations, the M200/M202 carries) resolved to a silent blank. The relation
became canonical for cross-modelo fold-in (aggregation-taxonomy rulings 2-4):
the resolver is enrolled, it folds prior filed observations through each declared
relation's aggregation op, and it materialises the result into the relation's
``target_binding`` slot (re-stamped from ``previous_filing`` to
``relation_prefill``). The materialised binding rides in the resolution's
``binding_values`` so the mesh ``_claim_binding`` exclusive-ownership guard
adjudicates any collision loudly.

These are real-behaviour tests against the REAL backend (real encrypted-SQLite
observation store, real registry authority, real calculation engine, real
relation resolver, real source mesh — no mocks/skips/xfail):

* ``test_modelo_180_115_fold_in_fires_on_live_calculate`` proves the fold-in now
  populates the M180 monetary annual output casillas from the four filed M115
  quarters, while the perceptor count comes from the dedicated per-perceptor
  retención store.

* ``test_relation_target_collision_refused_by_mesh_guard`` proves a second
  resolver claiming the same relation-materialised target binding is refused
  loudly by the mesh ``_claim_binding`` guard (an ``AggregationValidationError``)
  rather than silently overridden — the double-write closure.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.aggregation import AggregationCaptureKind
from ....core.aggregation import BindingSourceKind
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.snapshot import build_snapshot
from ....domain.calculations.registry.temporal import select_revision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_tree import bundled_registry_tree
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    AggregationValidationError,
    CalculationSourceContext,
    CalculationSourceResolution,
    RetencionObservation,
    RetencionObservationRepository,
    RetencionScheme,
    merge_source_resolutions,
)
from ...calculations import CalculationObservationRepository, RelationPrefillSourceResolver
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000180"
_PROFILE_LABEL = "Relation fold-in profile"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2025


_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M115_ANTERIORES_CASILLA: CasillaId = validated_casilla_id("04")
_M180_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("decl.total-perceptores")
_M180_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.base-total")
_M180_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")

# Distinct per-quarter bases so a cross-quarter contamination surfaces as a
# mismatch. Casillas 01/02 resolve through the M115 retenciones aggregation
# bindings, 03 = retenciones (computed 19% of 02), 04 = anteriores (manual zero).
_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1200.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "2T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1350.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "3T": {
        _M115_PERCEPTORES_CASILLA: Decimal("3"),
        _M115_BASE_CASILLA: Decimal("900.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "4T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1100.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
}

_M180_PERCEPTOR_NIFS: tuple[str, ...] = ("11111111H", "22222222J")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_PROFILE_LABEL) as profile:
        _seed_ready_profile(profile.repository)
        yield profile.repository


def _seed_ready_profile(objects: SecureObjectRepository) -> None:
    """Persist a filing-ready profile for the annual M180 work-unit gate."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="rental withholding activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _seed_115_quarters(*, obs_repo: CalculationObservationRepository) -> dict[CasillaId, Decimal]:
    """Calculate + persist the four 115 quarters; return the summed 01/02/03 totals."""
    auth = bundled_authority()
    totals: dict[CasillaId, Decimal] = {
        _M115_PERCEPTORES_CASILLA: Decimal("0"),
        _M115_BASE_CASILLA: Decimal("0"),
        _M115_RETENCIONES_CASILLA: Decimal("0"),
    }
    for period, casilla_inputs in _QUARTERS.items():
        snapshot = auth.snapshot("115", filing_year=_YEAR, period=period)
        binding_values = {
            "modelo-115-perceptores": casilla_inputs[_M115_PERCEPTORES_CASILLA],
            "modelo-115-base-retenciones": casilla_inputs[_M115_BASE_CASILLA],
        }
        inputs = {
            **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            _M115_ANTERIORES_CASILLA: casilla_inputs[_M115_ANTERIORES_CASILLA],
        }
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            binding_values=binding_values,
            date_context={"filing_period": date(_YEAR, 12, 31)},
        )
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="115",
                    filing_year=_YEAR,
                    period=period,
                    observations=result.observations,
                ),
                source_kind="app_filing",
                captured_at=_T0,
            )
        )
        for cid in totals:
            totals[cid] += result.values[cid]
    return totals


def _retencion_observation(nif: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"retencion-{nif}",
        perceptor_nif=nif,
        perceptor_name="Arrendador Ejemplo SL",
        scheme=RetencionScheme.URBAN_RENTAL,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("190.00"),
        accrued_on=f"{_YEAR}-03-15",
    )


def _seed_180_retencion_observations() -> Decimal:
    period = Period.from_year_and_code(_YEAR, "0A")
    RetencionObservationRepository().replace_observations(
        modelo="180",
        filing_year=_YEAR,
        period=period,
        observations=[_retencion_observation(nif) for nif in _M180_PERCEPTOR_NIFS],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    return Decimal(len(set(_M180_PERCEPTOR_NIFS)))


def test_modelo_180_115_fold_in_fires_on_live_calculate(secure_objects: SecureObjectRepository) -> None:
    """The M180 annual ← M115 quarterly fold-in populates on the live calculate path.

    With four 115 quarters recorded as filed observations, a live calculate of
    the M180 annual draws the monetary relation values through the enrolled
    ``RelationPrefillSourceResolver``. The count casilla is resolved separately
    through the ``retenciones_aggregation`` source.
    """
    obs_repo = CalculationObservationRepository()
    expected = _seed_115_quarters(obs_repo=obs_repo)
    expected_perceptor_count = _seed_180_retencion_observations()

    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    modelos_180, _catalogues_180 = bundled_registry_tree()
    modelo_180 = next(candidate for candidate in modelos_180 if candidate.id == "180")
    revision_180 = select_revision(modelo_180, filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=revision_180.id,
        repository=wu_repo,
        clock=_T0,
    )

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    casilla_values = result.revision.casilla_values
    # Fold-in fires for the monetary outputs. The perceptor count is a separate
    # retenciones_aggregation binding over the real per-perceptor store.
    assert casilla_values[_M180_TOTAL_PERCEPTORES_CASILLA] == expected_perceptor_count
    assert casilla_values[_M180_BASE_TOTAL_CASILLA] == expected[_M115_BASE_CASILLA]
    assert casilla_values[_M180_RETENCIONES_TOTAL_CASILLA] == expected[_M115_RETENCIONES_CASILLA]
    # Non-vacuous: the summed base must be strictly positive so a silent blank
    # (0) would fail the assertion above.
    assert expected[_M115_BASE_CASILLA] > Decimal("0")

    # The M180 dep-115 dependency classification declares this fold-in a
    # direct_annual_settlement figure, not a fact to reconcile against. That real,
    # non-default treatment must reach the PERSISTED revision's source_provenance
    # trace on the live calculate path, end to end from the resolver to the
    # encrypted-catalogue-bound domain record — not merely at the in-memory
    # resolution the resolver-level tests already cover.
    relation_prefill_provenance = [
        item for item in result.revision.source_provenance if item.contributor_source_kind == "relation_prefill"
    ]
    assert relation_prefill_provenance, "the live calculate revision must persist relation_prefill provenance rows"
    assert all(item.dependency_treatment == "direct_annual_settlement" for item in relation_prefill_provenance)


def test_relation_target_collision_refused_by_mesh_guard(secure_objects: SecureObjectRepository) -> None:
    """A second resolver claiming a relation-materialised target binding is refused loudly.

    The relation resolver materialises its resolved relation values into the
    relation's ``target_binding`` slot and emits them in ``binding_values``. If
    another resolver in the mesh also claims that binding id, the mesh
    ``_claim_binding`` exclusive-ownership guard raises rather than silently
    out-ranking one of the two (the double-write closure, aggregation-taxonomy ruling 4).
    """
    obs_repo = CalculationObservationRepository()
    _seed_115_quarters(obs_repo=obs_repo)

    modelos_180, catalogues_180 = bundled_registry_tree()
    modelo_180 = next(candidate for candidate in modelos_180 if candidate.id == "180")
    snapshot_180 = build_snapshot(
        modelo_180,
        catalogues_180,
        source_root=bundled_path(),
        filing_year=_YEAR,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision=snapshot_180.revision,
        calculated_at=_T1,
    )
    relation_resolution = RelationPrefillSourceResolver(
        repository=obs_repo,
        registry_snapshot=snapshot_180,
    ).resolve(context)
    # Non-vacuous: the relation resolution must have materialised at least one
    # target binding for the collision to be possible.
    assert relation_resolution.binding_values, "relation resolver materialised no target bindings"

    colliding_binding_id = next(iter(relation_resolution.binding_values))
    rival = CalculationSourceResolution(
        resolver_id="rival_resolver",
        owned_sources=(BindingSourceKind.MANUAL_INPUT,),
        binding_values={colliding_binding_id: Decimal("99999.99")},
    )

    with pytest.raises(AggregationValidationError):
        merge_source_resolutions((relation_resolution, rival))
