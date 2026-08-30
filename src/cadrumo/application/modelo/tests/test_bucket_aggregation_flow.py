"""Modelo calculation from bucket-local ledger aggregation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.errors.error_codes import resolve_error_message
from ....domain.buckets.event import BucketEventType
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva_compensation.reconciliation import IvaCompensationDecisionReason, IvaCompensationReconciliationDecision
from ....domain.modelos.calculation_revision import CalculationRevision, FilingInstanceEvidence
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.filing_evidence import general_m303_filing_evidence
from ....tests.profile_capsule import seed_test_profile_record
from ...calculations import IvaWalletDecisionRepository
from .._action_errors import ModeloAggregationBindingError
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_BUCKET_ID = "26262626-2626-4262-8262-262626262626"


_M303_REPERCUTIDO_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.repercutido.general")
_M303_SOPORTADO_INTERIORES_CASILLA: CasillaId = validated_casilla_id("iva.soportado.interiores")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_COMPENSACION_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_2009_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = validated_casilla_id("27")
_M303_2009_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = validated_casilla_id("45")
_M303_BUCKET_SOURCE_CASILLAS: tuple[CasillaId, CasillaId] = (
    _M303_REPERCUTIDO_GENERAL_CASILLA,
    _M303_SOPORTADO_INTERIORES_CASILLA,
)
_M303_2009_RESULT_OPERAND_CASILLAS: set[CasillaId] = {
    _M303_2009_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_2009_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
}
_M303_RESULT_OPERAND_CASILLAS: set[CasillaId] = {
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
}


def _repositories(objects: SecureObjectRepository):
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        BucketEventHistoryRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
    )


def _m303_filing_evidence(period: Period) -> FilingInstanceEvidence:
    return general_m303_filing_evidence(period, reference="test:bucket-flow:exonerado-390")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 2, 10),
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
    booked_date: date = date(2026, 2, 10),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, amount=amount, booked_date=booked_date),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            # Input IVA carries exact deduction authority; without it the
            # aggregation gate drops the row as MISSING_DEDUCTION_CLASSIFICATION
            # and the deducible casillas silently stay at zero.
            "deduction_fact_kind": (
                IvaDeductionFactKind.DOMESTIC_CURRENT if direction is TransactionDirection.OUTGOING else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _seed_303_work_unit(
    work_unit_repository: WorkUnitCatalogueRepository,
    *,
    period: str = "1T",
):
    typed_period = Period.from_year_and_code(2026, period)
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=typed_period,
        # The law-determined M303 revision for filing_year 2026 is
        # ``2026-y-siguientes`` (``2022`` covers only 2022).
        # The calc-time assertion (snapshot.revision.id ==
        # work_unit.revision_id) refuses the stale pin.
        revision_id="2026-y-siguientes",
        repository=work_unit_repository,
        clock=_T0,
    )


def _store_profile(objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Ready"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="design"),
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
                UserProfileFact(path="censo.activity_start_date", value=date(2025, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _store_first_period_profile(objects: SecureObjectRepository) -> None:
    """Store a profile whose IVA activity begins inside the 2026 1T filing period.

    A taxpayer whose ``censo.activity_start_date`` falls within the target period
    has no in-scope prior Modelo 303 period, so the prior-compensation dependency
    is pre-activity and the IVA wallet gate grounds a ``first_period_zero``
    decision instead of blocking. This is the genuine new-filer / sin-actividad
    scenario: the first Modelo 303 with an empty ledger.
    """
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Ready"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="design"),
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
                UserProfileFact(path="censo.activity_start_date", value=date(2026, 1, 15)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _wallet_decision(*, period: str, selected_amount: Decimal) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, period),
        selected_authority="aeat_wallet",
        selected_amount=selected_amount,
        wallet_amount=selected_amount,
        local_recurrence_amount=selected_amount,
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        wallet_captured_at=_T1,
        decided_at=_T1,
    )


def _assert_modelo_303_trace(revision: CalculationRevision) -> None:
    observations = {observation.casilla_id: observation for observation in revision.observations}
    for casilla_id in _M303_BUCKET_SOURCE_CASILLAS:
        observation = observations[casilla_id]
        assert observation.formula_id is None
        assert observation.operand_refs == ()
        assert observation.operand_casilla_refs == ()
        assert observation.legal_refs
        assert observation.source_refs

    computed_result = observations[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    assert computed_result.formula_id == "modelo-303-iva-resultado-regimen-general"
    # See note in test_calculate_modelo_revision_from_bucket_aggregation_uses_bucket_transaction_catalogue.
    operand_refs = set(computed_result.operand_refs)
    assert operand_refs >= _M303_2009_RESULT_OPERAND_CASILLAS or operand_refs >= _M303_RESULT_OPERAND_CASILLAS
    operand_casilla_refs = set(computed_result.operand_casilla_refs)
    assert (
        operand_casilla_refs >= _M303_2009_RESULT_OPERAND_CASILLAS
        or operand_casilla_refs >= _M303_RESULT_OPERAND_CASILLAS
    )
    assert computed_result.legal_refs
    assert computed_result.source_refs


def test_calculate_modelo_revision_from_bucket_aggregation_uses_bucket_transaction_catalogue(
    secure_objects: SecureObjectRepository,
) -> None:
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)
    incoming = _transaction(
        "sale-general",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    outgoing = _transaction(
        "purchase-general",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((incoming, outgoing)))

    wallet_decision = _wallet_decision(period="1T", selected_amount=Decimal("0.00"))
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(wallet_decision)

    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="operator-A",
        filing_instance_evidence=_m303_filing_evidence(work_unit.period),
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=wallet_decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=_BUCKET_ID,
            objects=secure_objects,
        ),
        clock=_T1,
    )

    assert Decimal(revision.input_values_by_casilla_id[_M303_REPERCUTIDO_GENERAL_CASILLA]) == incoming.iva_amount
    assert Decimal(revision.input_values_by_casilla_id[_M303_SOPORTADO_INTERIORES_CASILLA]) == outgoing.iva_amount
    assert Decimal(revision.binding_overrides["modelo-303-iva-repercutido-general-cuota"]) == incoming.iva_amount
    assert Decimal(revision.binding_overrides["modelo-303-iva-soportado-interiores-cuota"]) == outgoing.iva_amount
    assert revision.casilla_values[_M303_REPERCUTIDO_GENERAL_CASILLA] == incoming.iva_amount
    assert revision.casilla_values[_M303_SOPORTADO_INTERIORES_CASILLA] == outgoing.iva_amount
    assert revision.source_transaction_ids == tuple(sorted((incoming.transaction_id, outgoing.transaction_id)))

    observations = {observation.casilla_id: observation for observation in revision.observations}
    bound_output = observations[_M303_REPERCUTIDO_GENERAL_CASILLA]
    bound_input = observations[_M303_SOPORTADO_INTERIORES_CASILLA]
    assert bound_output.formula_id is None
    assert bound_input.formula_id is None
    assert bound_output.operand_refs == ()
    assert bound_output.operand_casilla_refs == ()
    assert bound_input.operand_refs == ()
    assert bound_input.operand_casilla_refs == ()
    assert bound_output.legal_refs
    assert bound_output.source_refs
    assert bound_input.legal_refs
    assert bound_input.source_refs

    computed_result = observations[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    assert computed_result.formula_id == "modelo-303-iva-resultado-regimen-general"
    # 2009 revision references operands by canonical numeric casilla.id
    # values; 2023 revision uses semantic ids. Accept either to keep this assertion
    # tied to the formula wiring, not the registry revision generation.
    operand_refs = set(computed_result.operand_refs)
    assert operand_refs >= _M303_2009_RESULT_OPERAND_CASILLAS or operand_refs >= _M303_RESULT_OPERAND_CASILLAS
    operand_casilla_refs = set(computed_result.operand_casilla_refs)
    assert (
        operand_casilla_refs >= _M303_2009_RESULT_OPERAND_CASILLAS
        or operand_casilla_refs >= _M303_RESULT_OPERAND_CASILLAS
    )
    assert computed_result.legal_refs
    assert computed_result.source_refs

    events = event_repo.load().for_bucket(_BUCKET_ID)
    calculation_events = [event for event in events if event.event_type == BucketEventType.MODELO_CALCULATION_CREATED]
    assert len(calculation_events) == 1
    assert calculation_events[0].payload["casilla_count"] == str(len(revision.casilla_values))
    assert calculation_events[0].payload["source_transaction_count"] == "2"


def test_calculate_modelo_revision_from_bucket_aggregation_refuses_when_ledger_preflight_blocks(
    secure_objects: SecureObjectRepository,
) -> None:
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)
    incomplete = _transaction(
        "purchase-missing-category",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    ).model_copy(update={"category_id": None})
    tx_repo.save(TransactionCatalogue.from_transactions((incomplete,)))

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            filing_instance_evidence=_m303_filing_evidence(work_unit.period),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked"
    rendered = resolve_error_message(exc_info.value)
    assert "%{detail}" not in rendered
    assert "deductible-expense ledger transaction has no category_id" in rendered

    assert len(cr_repo.load()) == 0


def test_m303_still_blocks_base_only_rows_missing_iva_facts(
    secure_objects: SecureObjectRepository,
) -> None:
    """IVA-owned modelos still require IVA amount/rate facts for equivalent base-only rows."""
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)
    base_only = _transaction(
        "purchase-base-only",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    ).model_copy(update={"iva_amount": None, "iva_rate": None})
    tx_repo.save(TransactionCatalogue.from_transactions((base_only,)))

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            filing_instance_evidence=_m303_filing_evidence(work_unit.period),
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )

    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked"
    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == "missing_iva_amount"
    assert len(cr_repo.load()) == 0


def test_modelo_303_bucket_aggregation_traces_positive_negative_zero_and_compensation_periods(
    secure_objects: SecureObjectRepository,
) -> None:
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    ledger_rows = (
        _transaction(
            "q1-sale",
            direction=TransactionDirection.INCOMING,
            amount=Decimal("242.00"),
            taxable_base=Decimal("200.00"),
            iva_amount=Decimal("42.00"),
            booked_date=date(2026, 2, 10),
        ),
        _transaction(
            "q1-purchase",
            direction=TransactionDirection.OUTGOING,
            amount=Decimal("60.50"),
            taxable_base=Decimal("50.00"),
            iva_amount=Decimal("10.50"),
            booked_date=date(2026, 2, 12),
        ),
        _transaction(
            "q2-sale",
            direction=TransactionDirection.INCOMING,
            amount=Decimal("60.50"),
            taxable_base=Decimal("50.00"),
            iva_amount=Decimal("10.50"),
            booked_date=date(2026, 5, 10),
        ),
        _transaction(
            "q2-purchase",
            direction=TransactionDirection.OUTGOING,
            amount=Decimal("121.00"),
            taxable_base=Decimal("100.00"),
            iva_amount=Decimal("21.00"),
            booked_date=date(2026, 5, 12),
        ),
        _transaction(
            "q3-sale",
            direction=TransactionDirection.INCOMING,
            amount=Decimal("121.00"),
            taxable_base=Decimal("100.00"),
            iva_amount=Decimal("21.00"),
            booked_date=date(2026, 8, 10),
        ),
        _transaction(
            "q3-purchase",
            direction=TransactionDirection.OUTGOING,
            amount=Decimal("121.00"),
            taxable_base=Decimal("100.00"),
            iva_amount=Decimal("21.00"),
            booked_date=date(2026, 8, 12),
        ),
        _transaction(
            "q4-sale",
            direction=TransactionDirection.INCOMING,
            amount=Decimal("242.00"),
            taxable_base=Decimal("200.00"),
            iva_amount=Decimal("42.00"),
            booked_date=date(2026, 11, 10),
        ),
        _transaction(
            "q4-purchase",
            direction=TransactionDirection.OUTGOING,
            amount=Decimal("121.00"),
            taxable_base=Decimal("100.00"),
            iva_amount=Decimal("21.00"),
            booked_date=date(2026, 11, 12),
        ),
    )
    tx_repo.save(TransactionCatalogue.from_transactions(ledger_rows))

    wallet_decision_repo = IvaWalletDecisionRepository(objects=secure_objects)
    _baseline_303_bindings = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        # State attribution: common-regime fixture supplies the full 100%
        # the M303 C65 profile binding would derive from the operator's
        # `tax_residence.jurisdiction_scope`. Without it, the
        # iva-atribuible-estado formula resolves to 64 × 0 / 100 = 0 and
        # the whole iva.resultado chain collapses to zero.
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }

    q1_decision = _wallet_decision(period="1T", selected_amount=Decimal("0.00"))
    wallet_decision_repo.save_decision(q1_decision)
    q1_positive = calculate_modelo_revision_from_bucket_aggregation(
        _seed_303_work_unit(wu_repo, period="1T").work_unit_id,
        actor="operator-A",
        filing_instance_evidence=_m303_filing_evidence(Period.from_year_and_code(2026, "1T")),
        binding_values=_baseline_303_bindings,
        iva_compensation_decision=q1_decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )
    q2_decision = _wallet_decision(period="2T", selected_amount=Decimal("0.00"))
    wallet_decision_repo.save_decision(q2_decision)
    q2_negative = calculate_modelo_revision_from_bucket_aggregation(
        _seed_303_work_unit(wu_repo, period="2T").work_unit_id,
        actor="operator-A",
        filing_instance_evidence=_m303_filing_evidence(Period.from_year_and_code(2026, "2T")),
        binding_values=_baseline_303_bindings,
        iva_compensation_decision=q2_decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )
    q3_decision = _wallet_decision(period="3T", selected_amount=Decimal("0.00"))
    wallet_decision_repo.save_decision(q3_decision)
    q3_zero = calculate_modelo_revision_from_bucket_aggregation(
        _seed_303_work_unit(wu_repo, period="3T").work_unit_id,
        actor="operator-A",
        filing_instance_evidence=_m303_filing_evidence(Period.from_year_and_code(2026, "3T")),
        binding_values=_baseline_303_bindings,
        iva_compensation_decision=q3_decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )
    wallet_decision = _wallet_decision(period="4T", selected_amount=Decimal("7.00"))
    wallet_decision_repo.save_decision(wallet_decision)
    q4_compensated = calculate_modelo_revision_from_bucket_aggregation(
        _seed_303_work_unit(wu_repo, period="4T").work_unit_id,
        actor="operator-A",
        filing_instance_evidence=_m303_filing_evidence(Period.from_year_and_code(2026, "4T")),
        binding_values={
            **_baseline_303_bindings,
            "modelo-303-compensacion-pendiente-anteriores": Decimal("7.00"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        iva_compensation_decision=wallet_decision,
        iva_compensation_decision_repository=wallet_decision_repo,
        clock=_T1,
    )

    for revision in (q1_positive, q2_negative, q3_zero, q4_compensated):
        _assert_modelo_303_trace(revision)

    assert q1_positive.casilla_values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA] > Decimal("0")
    assert q1_positive.casilla_values[_M303_RESULTADO_CASILLA] > Decimal("0")
    assert q1_positive.casilla_values[_M303_COMPENSACION_GENERADA_CASILLA] == Decimal("0")

    assert q2_negative.casilla_values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA] < Decimal("0")
    assert q2_negative.casilla_values[_M303_RESULTADO_CASILLA] < Decimal("0")
    assert q2_negative.casilla_values[_M303_COMPENSACION_GENERADA_CASILLA] > Decimal("0")

    assert q3_zero.casilla_values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA] == Decimal("0")
    assert q3_zero.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("0")
    assert q3_zero.casilla_values[_M303_COMPENSACION_GENERADA_CASILLA] == Decimal("0")

    assert q4_compensated.casilla_values[_M303_COMPENSACION_APLICADA_CASILLA] > Decimal("0")
    assert (
        q4_compensated.casilla_values[_M303_RESULTADO_CASILLA]
        < q4_compensated.casilla_values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    )


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_conflicting_binding_input(
    secure_objects: SecureObjectRepository,
) -> None:
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)
    tx_repo.save(
        TransactionCatalogue.from_transactions(
            (
                _transaction(
                    "sale-general",
                    direction=TransactionDirection.INCOMING,
                    amount=Decimal("121.00"),
                    taxable_base=Decimal("100.00"),
                    iva_amount=Decimal("21.00"),
                ),
            ),
        ),
    )

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            filing_instance_evidence=_m303_filing_evidence(work_unit.period),
            binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("99.00")},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )
    assert excinfo.value.translated_message == "errors.error.error_modelo_aggregation_binding"

    assert cr_repo.load().revisions == {}
    assert all(
        event.event_type != BucketEventType.MODELO_CALCULATION_CREATED for event in event_repo.load().events.values()
    )


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_empty_bucket_ledger_binding_injection(
    secure_objects: SecureObjectRepository,
) -> None:
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            filing_instance_evidence=_m303_filing_evidence(work_unit.period),
            binding_values={"modelo-303-iva-repercutido-general-cuota": Decimal("99.00")},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )
    assert excinfo.value.translated_message == "errors.error.error_modelo_aggregation_binding"

    assert cr_repo.load().revisions == {}
    assert all(
        event.event_type != BucketEventType.MODELO_CALCULATION_CREATED for event in event_repo.load().events.values()
    )


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_ledger_bound_casilla_injection(
    secure_objects: SecureObjectRepository,
) -> None:
    _store_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            filing_instance_evidence=_m303_filing_evidence(work_unit.period),
            casilla_inputs={_M303_REPERCUTIDO_GENERAL_CASILLA: Decimal("99.00")},
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.caller_casilla_source_binding_conflict"

    assert cr_repo.load().revisions == {}
    assert all(
        event.event_type != BucketEventType.MODELO_CALCULATION_CREATED for event in event_repo.load().events.values()
    )


def test_first_period_empty_ledger_m303_calculates_zero_sin_actividad(
    secure_objects: SecureObjectRepository,
) -> None:
    """A first-period filer with an empty ledger files a valid zero (sin actividad) Modelo 303.

    Art. 164.Uno.6.º LIVA (Ley 37/1992) obliges every sujeto pasivo to present the
    periodic ``declaración-liquidación`` regardless of activity, so a period with no
    operations is a legitimate zero-result filing, not an error. When the taxpayer's
    ``censo.activity_start_date`` falls inside the target period there is no in-scope
    prior compensation dependency, so the IVA wallet gate grounds a ``first_period_zero``
    decision and the calculate produces a zero result with NO ledger import, NO seed,
    and NO manual override — the path a new filer needs.
    """
    _store_first_period_profile(secure_objects)
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)

    # Empty ledger: no transactions saved at all, no overrides, no seed.
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        filing_instance_evidence=_m303_filing_evidence(work_unit.period),
        clock=_T1,
    )

    prior_compensacion_casilla = validated_casilla_id("iva.compensacion-pendiente-periodos-anteriores")
    assert revision.source_transaction_ids == ()
    assert revision.casilla_values[_M303_REPERCUTIDO_GENERAL_CASILLA] == Decimal("0")
    assert revision.casilla_values[_M303_SOPORTADO_INTERIORES_CASILLA] == Decimal("0")
    assert revision.casilla_values[_M303_RESULTADO_CASILLA] == Decimal("0.00")
    assert revision.casilla_values[prior_compensacion_casilla] == Decimal("0")

    # The revision is persisted and the calculation lifecycle event fired.
    assert len(cr_repo.load().revisions) == 1
    calculation_events = [
        event
        for event in event_repo.load().for_bucket(_BUCKET_ID)
        if event.event_type == BucketEventType.MODELO_CALCULATION_CREATED
    ]
    assert len(calculation_events) == 1

    # The IVA wallet authority recorded a non-blocking first-period zero decision,
    # so prior compensation was grounded rather than silently assumed.
    decision = IvaWalletDecisionRepository(objects=secure_objects).load_decision(
        "12345678Z",
        Period.from_year_and_code(2026, "1T"),
    )
    assert decision is not None
    assert decision.blocked is False
    assert decision.selected_amount == Decimal("0")
    assert str(decision.divergence) == "first_period_zero"
    assert decision.reason_identity is IvaCompensationDecisionReason.FIRST_PERIOD_ZERO_ACTIVITY_START_UNCONTRASTED
