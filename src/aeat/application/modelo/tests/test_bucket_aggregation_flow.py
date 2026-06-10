"""Modelo calculation from bucket-local ledger aggregation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import CalculationRevision
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    ModeloAggregationBindingError,
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile.repository


def _repositories(objects: SecureObjectRepository):
    return (
        WorkUnitCatalogueRepository(objects=objects),
        CalculationRevisionCatalogueRepository(objects=objects),
        BucketEventHistoryRepository(objects=objects),
        TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects),
    )


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 2, 10),
    amount: Decimal,
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
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
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def _seed_303_work_unit(
    work_unit_repository: WorkUnitCatalogueRepository,
    *,
    period: str = "1T",
):
    return create_work_unit(
        bucket_id="bucket-a",
        modelo="303",
        filing_year=2026,
        period=period,
        # The law-determined M303 revision for filing_year 2026 is
        # ``2023-y-siguientes`` (``2009-y-siguientes`` covers only 2009-2022).
        # The calc-time assertion (snapshot.revision.id ==
        # work_unit.revision_id) refuses the stale pin.
        revision_id="2023-y-siguientes",
        repository=work_unit_repository,
        clock=_T0,
    )


def _store_profile(objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id="bucket-a", objects=objects).save(
        UserProfileRecord(
            profile_id="bucket-a",
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_T0,
            updated_at=_T0,
        )
    )


def _wallet_decision(*, period: str, selected_amount: Decimal) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=period,
        selected_authority="aeat_wallet",
        selected_amount=selected_amount,
        wallet_amount=selected_amount,
        local_recurrence_amount=selected_amount,
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="bucket aggregation trace fixture",
        wallet_captured_at=_T1,
        decided_at=_T1,
    )


def _assert_modelo_303_trace(revision: CalculationRevision) -> None:
    observations = {observation.casilla_id: observation for observation in revision.observations}
    for casilla_id in ("iva.repercutido.general", "iva.soportado.interiores"):
        observation = observations[casilla_id]
        assert observation.formula_id is None
        assert observation.legal_refs
        assert observation.source_refs

    computed_result = observations["iva.resultado-regimen-general"]
    assert computed_result.formula_id == "modelo-303-iva-resultado-regimen-general"
    # See note in test_calculate_modelo_revision_from_bucket_aggregation_uses_bucket_transaction_catalogue.
    assert set(computed_result.operand_refs) >= {"27", "45"} or set(computed_result.operand_refs) >= {
        "iva.cuota-devengada-total",
        "iva.cuota-deducible-total",
    }
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
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=wallet_decision,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id="bucket-a",
            objects=secure_objects,
        ),
        clock=_T1,
    )

    assert Decimal(revision.inputs_snapshot["iva.repercutido.general"]) == incoming.iva_amount
    assert Decimal(revision.inputs_snapshot["iva.soportado.interiores"]) == outgoing.iva_amount
    assert Decimal(revision.binding_overrides["modelo-303-iva-repercutido-general-cuota"]) == incoming.iva_amount
    assert Decimal(revision.binding_overrides["modelo-303-iva-soportado-interiores-cuota"]) == outgoing.iva_amount
    assert revision.casilla_values["iva.repercutido.general"] == incoming.iva_amount
    assert revision.casilla_values["iva.soportado.interiores"] == outgoing.iva_amount
    assert revision.source_transaction_ids == tuple(sorted((incoming.transaction_id, outgoing.transaction_id)))

    observations = {observation.casilla_id: observation for observation in revision.observations}
    bound_output = observations["iva.repercutido.general"]
    bound_input = observations["iva.soportado.interiores"]
    assert bound_output.formula_id is None
    assert bound_input.formula_id is None
    assert bound_output.legal_refs
    assert bound_output.source_refs
    assert bound_input.legal_refs
    assert bound_input.source_refs

    computed_result = observations["iva.resultado-regimen-general"]
    assert computed_result.formula_id == "modelo-303-iva-resultado-regimen-general"
    # 2009 revision references its operands by casilla number ("27" - "45");
    # 2023 revision uses the typed ids. Accept either to keep this assertion
    # tied to the formula wiring, not the registry revision generation.
    assert set(computed_result.operand_refs) >= {"27", "45"} or set(computed_result.operand_refs) >= {
        "iva.cuota-devengada-total",
        "iva.cuota-deducible-total",
    }
    assert computed_result.legal_refs
    assert computed_result.source_refs

    events = event_repo.load().for_bucket("bucket-a")
    calculation_events = [event for event in events if event.event_type == BucketEventType.MODELO_CALCULATION_CREATED]
    assert len(calculation_events) == 1
    assert calculation_events[0].payload["casilla_count"] == str(len(revision.casilla_values))
    assert calculation_events[0].payload["source_transaction_count"] == "2"


def test_calculate_modelo_revision_from_bucket_aggregation_refuses_when_ledger_preflight_blocks(
    secure_objects: SecureObjectRepository,
) -> None:
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
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=event_repo,
            transaction_repository=tx_repo,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.ledger_preflight_blocked"

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

    assert q1_positive.casilla_values["iva.resultado-regimen-general"] > Decimal("0")
    assert q1_positive.casilla_values["iva.resultado"] > Decimal("0")
    assert q1_positive.casilla_values["iva.compensacion-generada-periodo"] == Decimal("0")

    assert q2_negative.casilla_values["iva.resultado-regimen-general"] < Decimal("0")
    assert q2_negative.casilla_values["iva.resultado"] < Decimal("0")
    assert q2_negative.casilla_values["iva.compensacion-generada-periodo"] > Decimal("0")

    assert q3_zero.casilla_values["iva.resultado-regimen-general"] == Decimal("0")
    assert q3_zero.casilla_values["iva.resultado"] == Decimal("0")
    assert q3_zero.casilla_values["iva.compensacion-generada-periodo"] == Decimal("0")

    assert q4_compensated.casilla_values["iva.compensacion-aplicada-periodo"] > Decimal("0")
    assert (
        q4_compensated.casilla_values["iva.resultado"] < q4_compensated.casilla_values["iva.resultado-regimen-general"]
    )


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_conflicting_binding_input(
    secure_objects: SecureObjectRepository,
) -> None:
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
            )
        )
    )

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
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
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
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
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_objects)
    work_unit = _seed_303_work_unit(wu_repo)

    with pytest.raises(ModeloAggregationBindingError) as exc_info:
        calculate_modelo_revision_from_bucket_aggregation(
            work_unit.work_unit_id,
            actor="operator-A",
            casilla_inputs={"iva.repercutido.general": Decimal("99.00")},
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
