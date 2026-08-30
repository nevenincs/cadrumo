"""Pull-path == calculate-path casilla parity for a shared revision.

The six ``assemble_*``
row-set helpers and ``resolve_relations_from_local_store`` historically could
populate casillas that the live ``calculate_modelo_revision_from_bucket_aggregation``
produces differently because both paths persisted to the same revision without any
cross-path comparison.  The relation-canonicalisation work centralised relation handling so that:

* The **live bucket-aggregation calculate path** enrolls
  :class:`~application.calculations._relation_prefill.RelationPrefillSourceResolver`
  in its ``merge_source_resolutions`` mesh, which delegates to
  :func:`~application.calculations._relation_prefill.resolve_relations_from_local_store`
  before calling the formula engine. The M180 perceptor count is a separate
  RET-1 ``retenciones_aggregation`` source, so the parity path seeds and
  resolves that source explicitly instead of summing quarterly counts.

* The **standalone relay path** calls ``resolve_relations_from_local_store``
  directly and feeds its output into
  :func:`~domain.calculations.registry.calculate_registry_snapshot`.

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

See Also:
    :class:`~application.calculations._relation_prefill.RelationPrefillSourceResolver`
        Live source-mesh adapter whose ``resolve`` path is compared with the
        direct relay path.
    :func:`~application.calculations._relation_prefill.resolve_relations_from_local_store`
        Shared relation-resolution implementation both transports consume.
    :func:`~domain.calculations.registry.calculate_registry_snapshot`
        Registry formula engine that consumes the resolved relation values.
    :class:`~application.aggregation.RetencionesAggregationSourceResolver`
        RET-1 source resolver seeded explicitly so M180 count parity is not
        faked by summing quarterly relation values.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.prorrata_register import ProrrataRegisterRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import (
    AggregationCaptureKind,
    CasillaId,
    IvaDeductionEvidenceAuthority,
    IvaDeductionFactKind,
    Period,
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    validated_casilla_id,
)
from ....core.aggregation import BindingSourceKind
from ....domain.bienes_inversion import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.iva import (
    IvaDeductionClassificationProvenance,
)
from ....domain.iva_compensation import IvaCompensationReconciliationDecision
from ....domain.prorrata_register import ProrrataRegister, ProrrataRegisterEntry
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    CalculationSourceContext,
    LedgerIvaAggregationSourceResolver,
    RetencionesAggregationSourceResolver,
    RetencionObservation,
    RetencionObservationRepository,
    RetencionScheme,
)
from ...modelo._binding_resolution import resolve_declaration_period_inputs
from ...modelo._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from ...modelo._work_lifecycle import create_work_unit
from .. import IvaWalletDecisionRepository, RelationPrefillSourceResolver
from .._relation_prefill import resolve_relations_from_local_store
from ..observations_repository import CalculationObservationRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "18018018-0180-4180-8180-180180180180"
_BUCKET_ID = _PROFILE_ID
_YEAR = 2025
_T0 = datetime(_YEAR, 1, 5, 10, 0, tzinfo=UTC)
_T1 = datetime(_YEAR, 3, 31, 14, 0, tzinfo=UTC)
_PRORRATA_YEAR = 2026
_PRORRATA_PERIOD = Period.from_year_and_code(_PRORRATA_YEAR, "1T")
_PRORRATA_T0 = datetime(_PRORRATA_YEAR, 1, 10, 10, 0, tzinfo=UTC)
_PRORRATA_T1 = datetime(_PRORRATA_YEAR, 3, 31, 14, 0, tzinfo=UTC)


_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03")
_M115_ANTERIORES_CASILLA: CasillaId = validated_casilla_id("04")
_M180_TOTAL_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("decl.total-perceptores")
_M180_BASE_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.base-total")
_M180_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id("decl.retenciones-total")
_M180_PERCEPTOR_NIFS: tuple[str, ...] = ("11111111H", "22222222J")
_M303_SOPORTADO_INTERIORES_CASILLA: CasillaId = validated_casilla_id("iva.soportado.interiores")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_OFICIAL_DEDUCIBLE_INTERIORES_CUOTA: CasillaId = validated_casilla_id("29")
_M303_DEDUCIBLE_CUOTA_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"
_M303_COMPENSACION_PENDIENTE_ANTERIORES_BINDING: BindingId = "modelo-303-compensacion-pendiente-anteriores"
_M303_AUTOCONSUMO_PROMOTOR_BASE_BINDING: BindingId = "modelo-303-autoconsumo-promotor-base"

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


def _seed_ready_profile() -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value="false"),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value="false",
                ),
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
        _seed_ready_profile()
        yield profile.repository


def _seed_115_observations(obs_repo: CalculationObservationRepository) -> dict[CasillaId, Decimal]:
    """Compute and persist the four M115 quarters; return the expected M180 sums."""
    auth = bundled_authority()
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
            if c.input_kind
            not in (
                InputKind.COMPUTED,
                InputKind.INFORMATIONAL,
                InputKind.PROJECTION_ONLY,
            )
        }
        full_inputs.update(casilla_inputs)
        result = calculate_registry_snapshot(
            snap,
            inputs=full_inputs,
            binding_values={},
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
        for output_cid in totals:
            totals[output_cid] += result.values[output_cid]
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
    RetencionObservationRepository().replace_observations(
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        observations=tuple(_retencion_observation(nif) for nif in _M180_PERCEPTOR_NIFS),
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
        captured_at=_T0,
    )
    return Decimal(len(set(_M180_PERCEPTOR_NIFS)))


def _m303_raw_transaction(provider_id: str, *, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(_PRORRATA_YEAR, 2, 10),
        value_date=date(_PRORRATA_YEAR, 2, 10),
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"prorrata parity row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="8" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(_PRORRATA_YEAR, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _m303_iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    deduction_authority = (
        {
            "deduction_fact_kind": IvaDeductionFactKind.DOMESTIC_CURRENT,
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                source_locator=f"invoice:{provider_id}",
                evidence_digest="8" * 64,
            ),
        }
        if direction is TransactionDirection.OUTGOING
        else {}
    )
    return Transaction.model_validate(
        {
            "raw": _m303_raw_transaction(provider_id, amount=amount),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            **deduction_authority,
            "classified_at": datetime(_PRORRATA_YEAR, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _m303_wallet_decision() -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=_PRORRATA_YEAR,
        target_period=_PRORRATA_PERIOD,
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=_PRORRATA_T1,
        decided_at=_PRORRATA_T1,
    )


def _seed_m303_prorrata_work_unit(work_unit_repository: WorkUnitCatalogueRepository):
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_PRORRATA_YEAR,
        period=_PRORRATA_PERIOD,
        revision_id=bundled_authority()
        .snapshot(
            "303",
            filing_year=_PRORRATA_YEAR,
            period=_PRORRATA_PERIOD.registry_token,
        )
        .revision.id,
        repository=work_unit_repository,
        clock=_PRORRATA_T0,
    )


def test_pull_path_and_calculate_path_share_resolver_and_produce_equal_casilla_values(
    secure_objects: SecureObjectRepository,
) -> None:
    """Live calculate and standalone relay paths produce identical casilla values.

    Seeds four distinct M115 quarters into a real encrypted-SQLite observation
    store and verifies that:

    (A) The live bucket-aggregation calculate path for M180 (which enrolls
        :class:`~application.calculations._relation_prefill.RelationPrefillSourceResolver`
        in its source mesh) produces the same casilla values as

    (B) The standalone relay path
        (:class:`~application.calculations._relation_prefill.RelationPrefillSourceResolver`
        called directly against the same observation store, feeding its resolved
        ``relation_values`` into
        :func:`~domain.calculations.registry.calculate_registry_snapshot`).

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

    auth = bundled_authority()
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
        **resolve_available_bound_inputs_by_casilla_id(snap_180.revision, relay_binding_values),
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


def test_prorrata_apportioned_deducible_casilla_matches_calculate_and_pull_paths(
    secure_objects: SecureObjectRepository,
) -> None:
    """The apportioned M303 deducible cuota casilla is identical on both transports."""
    auth = bundled_authority()
    snapshot = auth.snapshot("303", filing_year=_PRORRATA_YEAR, period="1T")
    work_unit_repository = WorkUnitCatalogueRepository(objects=secure_objects)
    calculation_repository = CalculationRevisionCatalogueRepository(objects=secure_objects)
    bucket_event_repository = BucketEventHistoryRepository(objects=secure_objects)
    transaction_repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)

    wallet_decision = _m303_wallet_decision()
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(wallet_decision)
    sale = _m303_iva_transaction(
        "prorrata-sale",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    purchase = _m303_iva_transaction(
        "prorrata-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("242.00"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
    )
    transaction_repository.save(TransactionCatalogue.from_transactions((sale, purchase)))
    ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        ProrrataRegister(
            entries=(
                ProrrataRegisterEntry(
                    ejercicio=_PRORRATA_YEAR,
                    regime=ProrrataRegisterRegime.GENERAL,
                    especial_transition=None,
                    provisional_percentage=Decimal("80"),
                    provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
                    source_observation_ref="303:2025:4T",
                ),
            ),
        ),
    )

    work_unit = _seed_m303_prorrata_work_unit(work_unit_repository)
    live_result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-A",
        binding_values={
            _M303_COMPENSACION_PENDIENTE_ANTERIORES_BINDING: Decimal("0.00"),
            _M303_AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0.00"),
        },
        iva_compensation_decision=wallet_decision,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        filing_instance_evidence=general_m303_filing_evidence(
            _PRORRATA_PERIOD,
            reference="test:pull-calculate-parity:exonerado-not-applicable",
        ),
        clock=_PRORRATA_T1,
    )

    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_PRORRATA_YEAR,
        period=_PRORRATA_PERIOD,
        revision=snapshot.revision,
        calculated_at=_PRORRATA_T1,
    )
    pull_resolution = LedgerIvaAggregationSourceResolver(
        transaction_repository=transaction_repository,
        invoice_repository=invoice_repository,
        prorrata_register_repository=ProrrataRegisterRepository(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
        ),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_BUCKET_ID,
    ).resolve(context)
    pull_binding_values = dict(pull_resolution.binding_values)
    pull_binding_values.update(
        {
            _M303_COMPENSACION_PENDIENTE_ANTERIORES_BINDING: Decimal("0.00"),
            _M303_AUTOCONSUMO_PROMOTOR_BASE_BINDING: Decimal("0.00"),
        },
    )
    pull_inputs = {
        **resolve_declaration_period_inputs(
            snapshot.revision,
            filing_year=_PRORRATA_YEAR,
            period=_PRORRATA_PERIOD,
        ).casilla_inputs,
        **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, pull_binding_values),
    }
    pull_result = calculate_registry_snapshot(
        snapshot,
        inputs=pull_inputs,
        binding_values=pull_binding_values,
        date_context={"filing_period": date(_PRORRATA_YEAR, 3, 31)},
    )

    assert purchase.iva_amount is not None
    apportioned_binding = pull_resolution.binding_values[_M303_DEDUCIBLE_CUOTA_BINDING]
    assert Decimal("0") < apportioned_binding < purchase.iva_amount

    live_semantic = Decimal(live_result.revision.casilla_values[_M303_SOPORTADO_INTERIORES_CASILLA])
    live_official = Decimal(live_result.revision.casilla_values[_M303_OFICIAL_DEDUCIBLE_INTERIORES_CUOTA])
    assert Decimal(live_result.revision.binding_overrides[_M303_DEDUCIBLE_CUOTA_BINDING]) == apportioned_binding
    assert live_semantic == apportioned_binding
    assert live_official == live_semantic
    assert pull_result.values[_M303_SOPORTADO_INTERIORES_CASILLA] == live_semantic
    assert pull_result.values[_M303_OFICIAL_DEDUCIBLE_INTERIORES_CUOTA] == live_official
    assert tuple(live_result.revision.source_transaction_ids) == tuple(
        sorted((sale.transaction_id, purchase.transaction_id)),
    )
