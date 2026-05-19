"""Tests for bucket-local IVA ledger observation projection."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...core.config import Settings
from ...core.resources import resources
from ...domain.calculations.registry import resolve_ledger_iva_aggregation_binding_values
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...domain.vat import IvaFlowDirection, ProrrataKind, ProrrataRegime, VATCategory, VATRateKind
from . import (
    AggregationValidationError,
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations,
    aggregate_iva_ledger_observations_from_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    amount: Decimal = Decimal("-121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="b" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    amount: Decimal = Decimal("-121.00"),
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    booked_date: date = date(2026, 4, 5),
    value_date: date | None = date(2026, 4, 5),
    currency: str = "EUR",
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    prorrata_reference: str | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "business_classification": business_classification,
            "business_pct": business_pct,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "prorrata_reference": prorrata_reference,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def test_outgoing_business_transaction_projects_to_soportado_iva_observation() -> None:
    transaction = _transaction("row-expense")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.issues == ()
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.ledger_id == transaction.transaction_id
    assert observation.transaction_date == date(2026, 4, 5)
    assert observation.category is VATCategory.DOMESTIC_GENERAL_21
    assert observation.rate_kind is VATRateKind.GENERAL
    assert observation.flow_direction is IvaFlowDirection.SOPORTADO
    assert observation.base_amount == transaction.taxable_base
    assert observation.iva_amount == transaction.iva_amount


def test_archived_and_stashed_transactions_do_not_feed_iva_projection() -> None:
    active = _transaction("row-active")
    archived = _transaction(
        "row-archived",
        taxable_base=Decimal("900.00"),
        iva_amount=Decimal("189.00"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed = _transaction(
        "row-stashed",
        taxable_base=Decimal("700.00"),
        iva_amount=Decimal("147.00"),
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((active, archived, stashed)),
        period="2026Q2",
    )

    assert result.issues == ()
    assert [observation.ledger_id for observation in result.observations] == [active.transaction_id]
    assert result.observations[0].base_amount == active.taxable_base
    assert result.observations[0].iva_amount == active.iva_amount


def test_incoming_business_transaction_projects_to_repercutido_iva_observation() -> None:
    transaction = _transaction(
        "row-income",
        amount=Decimal("110.00"),
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.10"),
        iva_amount=Decimal("10.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.issues == ()
    observation = result.observations[0]
    assert observation.category is VATCategory.DOMESTIC_REDUCED_10
    assert observation.rate_kind is VATRateKind.REDUCED
    assert observation.flow_direction is IvaFlowDirection.REPERCUTIDO
    assert observation.iva_amount == Decimal("10.00")


def test_mixed_business_transaction_applies_business_percentage_to_base_and_iva() -> None:
    transaction = _transaction(
        "row-mixed",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.issues == ()
    assert result.observations[0].base_amount == Decimal("50.0000")
    assert result.observations[0].iva_amount == Decimal("10.5000")


def test_outgoing_input_row_carries_legal_prorrata_reference_separately_from_observation() -> None:
    transaction = _transaction(
        "row-prorrata",
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        prorrata_reference="prorrata:2026:provisional:general",
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.issues == ()
    assert len(result.observations) == 1
    assert len(result.prorrata_references) == 1
    reference = result.prorrata_references[0]
    assert reference.transaction_id == transaction.transaction_id
    assert reference.transaction_date == date(2026, 4, 5)
    assert reference.reference.year == 2026
    assert reference.reference.kind is ProrrataKind.PROVISIONAL
    assert reference.reference.regime is ProrrataRegime.GENERAL
    assert reference.base_amount == Decimal("200.00")
    assert reference.input_vat_amount == Decimal("42.00")
    assert result.observations[0].iva_amount == Decimal("42.00")


def test_mixed_input_row_applies_business_percentage_before_carrying_prorrata_reference() -> None:
    transaction = _transaction(
        "row-mixed-prorrata",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        taxable_base=Decimal("200.00"),
        iva_amount=Decimal("42.00"),
        prorrata_reference="prorrata:2026:provisional:especial:sector-retail",
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.issues == ()
    assert result.prorrata_references[0].reference.sector_id == "sector-retail"
    assert result.prorrata_references[0].base_amount == Decimal("50.0000")
    assert result.prorrata_references[0].input_vat_amount == Decimal("10.5000")


def test_invalid_prorrata_reference_is_reported_without_dropping_iva_observation() -> None:
    transaction = _transaction("row-bad-prorrata", prorrata_reference="telefonia_movil")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert len(result.observations) == 1
    assert result.prorrata_references == ()
    assert result.issues[0].transaction_id == transaction.transaction_id
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE


def test_prorrata_reference_on_output_vat_row_is_reported_but_output_observation_survives() -> None:
    transaction = _transaction(
        "row-output-prorrata",
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
        prorrata_reference="prorrata:2026:provisional:general",
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.observations[0].flow_direction is IvaFlowDirection.REPERCUTIDO
    assert result.prorrata_references == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE


def test_personal_transaction_is_reported_without_iva_observation() -> None:
    transaction = _transaction("row-personal", business_classification=BusinessClassification.PERSONAL)

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION


def test_missing_tax_fact_is_reported_before_projection() -> None:
    transaction = _transaction("row-missing-rate", iva_rate=None)

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.MISSING_IVA_RATE


def test_non_canonical_iva_rate_is_reported() -> None:
    transaction = _transaction("row-bad-rate", iva_rate=Decimal("0.07"), iva_amount=Decimal("7.00"))

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE


def test_out_of_period_and_foreign_currency_rows_do_not_project() -> None:
    old_row = _transaction("row-old", booked_date=date(2026, 1, 5), value_date=date(2026, 1, 5))
    usd_row = _transaction("row-usd", currency="USD")

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((old_row, usd_row)),
        period="2026Q2",
    )

    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
    ]


def test_repository_backed_projection_rejects_bucket_mismatch_before_loading() -> None:
    with pytest.raises(AggregationValidationError, match="bucket_mismatch"):
        aggregate_iva_ledger_observations_from_repositories(
            bucket_id="bucket-a",
            period="2026Q2",
            transaction_repository=TransactionCatalogueRepository(bucket_id="bucket-b"),
        )


def test_repository_backed_projection_loads_persisted_bucket_catalogue(secure_engine: Engine) -> None:
    transaction = _transaction("row-repository")
    repository = TransactionCatalogueRepository(
        bucket_id="bucket-a",
        objects=SecureObjectRepository(engine=secure_engine),
    )
    repository.save(TransactionCatalogue.from_transactions((transaction,)))

    result = aggregate_iva_ledger_observations_from_repositories(
        bucket_id="bucket-a",
        period="2026Q2",
        transaction_repository=TransactionCatalogueRepository(
            bucket_id="bucket-a",
            objects=SecureObjectRepository(engine=secure_engine),
        ),
    )

    assert result.issues == ()
    assert result.observations[0].ledger_id == transaction.transaction_id


def test_internal_transfer_is_reported_as_unsupported_direction() -> None:
    transaction = _transaction(
        "row-transfer",
        amount=Decimal("-10.00"),
        direction=TransactionDirection.INTERNAL_TRANSFER,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2026Q2",
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION


def test_missing_base_and_amount_are_reported_as_distinct_tax_fact_issues() -> None:
    missing_base = _transaction("row-missing-base", taxable_base=None)
    missing_amount = _transaction("row-missing-amount", iva_amount=None)

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((missing_base, missing_amount)),
        period="2026Q2",
    )

    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT,
    ]


def test_dated_vat_registry_gap_is_reported_as_unsupported_rate() -> None:
    transaction = _transaction(
        "row-pre-registry",
        booked_date=date(2023, 4, 5),
        value_date=date(2023, 4, 5),
        iva_rate=Decimal("0.21"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((transaction,)),
        period="2023Q2",
    )

    assert result.observations == ()
    assert result.issues[0].reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE


def test_zero_and_super_reduced_rates_project_to_canonical_vat_categories() -> None:
    zero = _transaction("row-zero", taxable_base=Decimal("100.00"), iva_rate=Decimal("0"), iva_amount=Decimal("0"))
    super_reduced = _transaction(
        "row-super",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.04"),
        iva_amount=Decimal("4.00"),
    )

    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((zero, super_reduced)),
        period="2026Q2",
    )

    assert [observation.category for observation in result.observations] == [
        VATCategory.DOMESTIC_ZERO,
        VATCategory.DOMESTIC_SUPER_REDUCED_4,
    ]


def test_projected_observations_feed_modelo_303_binding_resolver() -> None:
    incoming = _transaction(
        "row-output",
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )
    outgoing = _transaction(
        "row-input",
        taxable_base=Decimal("50.00"),
        iva_rate=Decimal("0.10"),
        iva_amount=Decimal("5.00"),
    )
    projection = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((incoming, outgoing)),
        period="2026Q2",
    )
    modelos = resources().modelos.all()
    revision = next(item for item in modelos if item.id == "303").revisions["2009-y-siguientes"]

    binding_values = resolve_ledger_iva_aggregation_binding_values(revision, projection.observations)

    assert binding_values["modelo-303-iva-repercutido-general-cuota"] == incoming.iva_amount
    assert binding_values["modelo-303-iva-soportado-interiores-cuota"] == outgoing.iva_amount
