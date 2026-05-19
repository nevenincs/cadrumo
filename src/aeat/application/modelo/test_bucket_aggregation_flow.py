"""Modelo calculation from bucket-local ledger aggregation."""

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
from ...domain.buckets import BucketEventHistoryRepository, BucketEventType
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from . import (
    ModeloAggregationBindingError,
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
        )
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


def _repositories(engine: Engine):
    objects = SecureObjectRepository(engine=engine)
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
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, amount=amount),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def _seed_303_work_unit(work_unit_repository: WorkUnitCatalogueRepository):
    return create_work_unit(
        bucket_id="bucket-a",
        modelo="303",
        filing_year=2026,
        period="1T",
        revision_id="2009-y-siguientes",
        repository=work_unit_repository,
        clock=_T0,
    )


def test_calculate_modelo_revision_from_bucket_aggregation_uses_bucket_transaction_catalogue(
    secure_engine: Engine,
) -> None:
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_engine)
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
        amount=Decimal("-60.50"),
        taxable_base=Decimal("50.00"),
        iva_amount=Decimal("10.50"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((incoming, outgoing)))

    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        actor="operator-A",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id="bucket-a",
            objects=SecureObjectRepository(engine=secure_engine),
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

    events = event_repo.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [BucketEventType.MODELO_CALCULATION_CREATED]
    assert events[0].payload["casilla_count"] == str(len(revision.casilla_values))
    assert events[0].payload["source_transaction_count"] == "2"


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_conflicting_binding_input(
    secure_engine: Engine,
) -> None:
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_engine)
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

    with pytest.raises(ModeloAggregationBindingError, match="cannot override"):
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

    assert cr_repo.load().revisions == {}
    assert event_repo.load().events == {}


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_empty_bucket_ledger_binding_injection(
    secure_engine: Engine,
) -> None:
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_engine)
    work_unit = _seed_303_work_unit(wu_repo)

    with pytest.raises(ModeloAggregationBindingError, match="cannot override"):
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

    assert cr_repo.load().revisions == {}
    assert event_repo.load().events == {}


def test_calculate_modelo_revision_from_bucket_aggregation_rejects_ledger_bound_casilla_injection(
    secure_engine: Engine,
) -> None:
    wu_repo, cr_repo, event_repo, tx_repo = _repositories(secure_engine)
    work_unit = _seed_303_work_unit(wu_repo)

    with pytest.raises(ModeloAggregationBindingError, match="cannot override"):
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

    assert cr_repo.load().revisions == {}
    assert event_repo.load().events == {}
