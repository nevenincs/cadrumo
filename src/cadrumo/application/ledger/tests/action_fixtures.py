"""Shared support for manual ledger transaction application tests."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC as _UTC
from datetime import date as _date
from datetime import datetime as _datetime
from decimal import Decimal as _Decimal
from pathlib import Path as _Path

from ....adapters.inbound.financial.providers.base import ParsedLedgerRow
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository as _BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import (
    CalculationRevisionCatalogueRepository as _CalculationRevisionCatalogueRepository,
)
from ....adapters.persistence.profile.modelos_work_units import (
    WorkUnitCatalogueRepository as _WorkUnitCatalogueRepository,
)
from ....adapters.persistence.profile.transactions import (
    TransactionCatalogueRepository as _TransactionCatalogueRepository,
)
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository as _SecureObjectRepository
from ....application.ledger.actions_manual import create_manual_transaction as _create_manual_transaction
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.tests.registry_observations import registry_grounded_observations
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.transactions.enums import (
    TransactionDirection as _TransactionDirection,
)
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction
from ....domain.transactions.raw_transaction import SourceFormat as _SourceFormat
from ....tests.filing_evidence import general_m303_filing_evidence
from ..models import ManualLedgerTransactionCommand as _ManualLedgerTransactionCommand
from ..models import ManualLedgerTransactionResult as _ManualLedgerTransactionResult

_REVISION_CASILLA: CasillaId = validated_casilla_id("01")
_BUCKET_ID = "26262626-2626-4626-8626-262626262626"
_OTHER_BUCKET_ID = "27272727-2727-4727-8727-272727272727"

__all__ = [
    "_BUCKET_ID",
    "_OTHER_BUCKET_ID",
    "_create_manual_row",
    "_repositories",
    "parsed_import_transaction",
    "persist_verified_revision_citing_transaction",
    "purchase_invoice",
]


def _repositories(
    objects: _SecureObjectRepository,
    *,
    bucket_id: str = _BUCKET_ID,
) -> tuple[_TransactionCatalogueRepository, _BucketEventHistoryRepository]:
    return (
        _TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        _BucketEventHistoryRepository(objects=objects),
    )


def _create_manual_row(
    secure_objects: _SecureObjectRepository,
    *,
    description: str,
    idempotency_key: str,
    amount: _Decimal | None = None,
    booked_date: _date | None = None,
    occurred_at: _datetime | None = None,
) -> tuple[_TransactionCatalogueRepository, _BucketEventHistoryRepository, _ManualLedgerTransactionResult]:
    transaction_repository, event_repository = _repositories(secure_objects)
    resolved_booked_date = booked_date if booked_date is not None else _date(2026, 5, 2)
    resolved_amount = amount if amount is not None else _Decimal("25.00")
    resolved_occurred_at = occurred_at if occurred_at is not None else _datetime(2026, 5, 4, 9, 30, tzinfo=_UTC)
    created = _create_manual_transaction(
        _ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=resolved_booked_date,
            amount=resolved_amount,
            direction=_TransactionDirection.OUTGOING,
            description=description,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=resolved_occurred_at,
    )
    return transaction_repository, event_repository, created


def _purchase_invoice() -> Invoice:
    line = InvoiceLine(
        description="Material oficina",
        quantity=_Decimal("1"),
        unit_price=_Decimal("100.00"),
        subtotal=_Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=_Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": _BUCKET_ID,
            "invoice_number": "P-2026-001",
            "issued_at": _date(2026, 5, 2),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": _Decimal("100.00"),
            "iva_total": _Decimal("21.00"),
            "grand_total": _Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )


def _raw_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: _Decimal = _Decimal("80.00"),
    description: str = "provider import row",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=transaction_id,
        booked_date=_date(2026, 5, 1),
        value_date=_date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description=description,
        provenance=RawProvenance(
            source_path=_Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=_SourceFormat.CSV,
            ingested_at=_datetime(2026, 5, 1, 12, 0, tzinfo=_UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _parsed_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: _Decimal = _Decimal("80.00"),
    description: str = "provider import row",
    direction: _TransactionDirection = _TransactionDirection.OUTGOING,
) -> ParsedLedgerRow:
    """Wrap a magnitude import row with an explicit direction (parse-boundary pair)."""
    return ParsedLedgerRow(
        raw=_raw_import_transaction(transaction_id=transaction_id, amount=amount, description=description),
        direction=direction,
    )


def parsed_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: _Decimal = _Decimal("80.00"),
    description: str = "provider import row",
    direction: _TransactionDirection = _TransactionDirection.OUTGOING,
) -> ParsedLedgerRow:
    return _parsed_import_transaction(
        transaction_id=transaction_id,
        amount=amount,
        description=description,
        direction=direction,
    )


def _persist_verified_revision_citing_transaction(
    objects: _SecureObjectRepository,
    *,
    transaction_id: str,
    additional_transaction_ids: Iterable[str] = (),
    bucket_id: str = _BUCKET_ID,
) -> None:
    source_transaction_ids = (transaction_id, *tuple(additional_transaction_ids))
    period = Period.from_year_and_code(2026, "1T")
    registry_snapshot_ref = (
        bundled_authority()
        .snapshot(
            "303",
            filing_year=period.filing_year,
            period=period.registry_token,
        )
        .snapshot_ref
    )
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id=registry_snapshot_ref.revision_id,
    )
    filing_instance_evidence = general_m303_filing_evidence(period, reference="test:ledger-action-support")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: _Decimal("1")},
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id=registry_snapshot_ref.revision_id,
        name="303-2026-1T",
        created_at=_datetime(2026, 5, 1, 8, 0, tzinfo=_UTC),
        updated_at=_datetime(2026, 5, 2, 8, 0, tzinfo=_UTC),
        current_calculation_revision_id=revision_id,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=registry_snapshot_ref,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        source_transaction_ids=source_transaction_ids,
        casilla_values={_REVISION_CASILLA: _Decimal("1")},
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=2026,
            period=period.registry_token,
            casilla_values={_REVISION_CASILLA: _Decimal("1")},
        ),
        created_at=_datetime(2026, 5, 2, 8, 0, tzinfo=_UTC),
        updated_at=_datetime(2026, 5, 2, 9, 0, tzinfo=_UTC),
        verified_at=_datetime(2026, 5, 2, 9, 0, tzinfo=_UTC),
        verified_by="operator-A",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    _WorkUnitCatalogueRepository(objects=objects).save(WorkUnitCatalogue.from_work_units((work_unit,)))
    _CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions={revision_id: revision}),
    )


def purchase_invoice() -> Invoice:
    return _purchase_invoice()


def persist_verified_revision_citing_transaction(
    objects: _SecureObjectRepository,
    *,
    transaction_id: str,
    additional_transaction_ids: Iterable[str] = (),
    bucket_id: str = _BUCKET_ID,
) -> None:
    _persist_verified_revision_citing_transaction(
        objects,
        transaction_id=transaction_id,
        additional_transaction_ids=additional_transaction_ids,
        bucket_id=bucket_id,
    )
