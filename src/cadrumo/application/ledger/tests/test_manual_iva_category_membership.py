"""Authority membership guards for every manual ledger category writer."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any, cast

import pytest

import cadrumo.application.ledger.actions_manual as actions_manual

from ....core.classification.policies import SensitivityClass
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.iva.schema import IvaCategory
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ..action_ports import LedgerActionPorts
from ..actions_classification import bulk_classify_from_csv
from ..actions_manual import create_manual_transaction, update_manual_transaction_fields
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "21000000-0000-4000-8000-000000000001"
_BOOKED = date(2026, 5, 2)
_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


class _PreparedEventWrite(SecureObjectWrite):
    catalogue: BucketEventHistoryCatalogue


class _EventRepository:
    def __init__(self) -> None:
        self.catalogue = BucketEventHistoryCatalogue()
        self.revision_id = "0" * 64
        self.save_count = 0

    def load(self) -> BucketEventHistoryCatalogue:
        return self.catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self.catalogue = catalogue
        self.revision_id = sha256(self.revision_id.encode()).hexdigest()
        self.save_count += 1

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self.catalogue, self.revision_id

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> _PreparedEventWrite:
        return _PreparedEventWrite(
            namespace="application-test-events",
            object_key="iva-category-membership",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            written_at=_NOW,
            payload=b"event-catalogue",
            expected_revision_id=expected_revision_id,
            catalogue=catalogue,
        )

    def commit(self, write: _PreparedEventWrite) -> None:
        if write.expected_revision_id != self.revision_id:
            raise AssertionError("test event write used a stale revision")
        self.save(write.catalogue)


class _TransactionRepository:
    def __init__(self, catalogue: TransactionCatalogue, events: _EventRepository) -> None:
        self.bucket_id = _BUCKET
        self.catalogue = catalogue
        self.events = events
        self.save_count = 0

    def load(self) -> TransactionCatalogue:
        return self.catalogue

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        (event_write,) = extra_writes
        if not isinstance(event_write, _PreparedEventWrite):
            raise TypeError("test action port expected a prepared bucket-event write")
        self.events.commit(event_write)
        self.catalogue = catalogue
        self.save_count += 1


class _EmptyRepository:
    def __init__(self, catalogue: object) -> None:
        self.catalogue = catalogue

    def load(self) -> object:
        return self.catalogue


def _command(
    *,
    description: str = "category membership fixture",
    iva_category: IvaCategory | None = None,
) -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=_BUCKET,
        booked_date=_BOOKED,
        amount=Decimal("10.00"),
        direction=TransactionDirection.OUTGOING,
        description=description,
        business_classification=BusinessClassification.BUSINESS,
        actor="operator",
        source_command="aeat app ledger add",
        iva_category=iva_category,
    )


def _ports(
    *,
    operation: PinnedAuthorityOperation,
    transactions: _TransactionRepository,
    events: _EventRepository,
) -> LedgerActionPorts:
    return LedgerActionPorts(
        operation=operation,
        transaction_repository=cast(Any, transactions),
        bucket_event_repository=cast(Any, events),
        invoice_repository=cast(Any, None),
        attachment_store=cast(Any, None),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=lambda **_kwargs: UsageRatioProfile(),
        work_unit_repository=cast(Any, _EmptyRepository(WorkUnitCatalogue())),
        calculation_repository=cast(Any, _EmptyRepository(CalculationRevisionCatalogue())),
        purchase_invoice_evidence_records=(),
    )


def _repositories(catalogue: TransactionCatalogue) -> tuple[_TransactionRepository, _EventRepository]:
    events = _EventRepository()
    return _TransactionRepository(catalogue, events), events


def _stored_catalogue(*descriptions: str) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(
        actions_manual._transaction_from_command(_command(description=description), occurred_at=_NOW)
        for description in descriptions
    )


def test_create_and_update_persist_real_date_supported_categories(
    operation: PinnedAuthorityOperation,
) -> None:
    transactions, events = _repositories(TransactionCatalogue())
    ports = _ports(operation=operation, transactions=transactions, events=events)
    created = create_manual_transaction(
        _command(iva_category=IvaCategory("domestic_general")),
        ports=ports,
        occurred_at=_NOW,
    )
    assert transactions.catalogue.get(created.ref.transaction_id).iva_category == IvaCategory("domestic_general")

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(iva_category=IvaCategory("operacion_no_sujeta")),
        actor="operator",
        source_command="aeat app ledger classify",
        ports=ports,
        occurred_at=_NOW,
    )

    assert updated.transaction.iva_category == IvaCategory("operacion_no_sujeta")
    assert transactions.catalogue.get(updated.ref.transaction_id).iva_category == IvaCategory("operacion_no_sujeta")
    assert transactions.save_count == events.save_count == 2


def test_create_refuses_a_real_undeclared_category_before_catalogue_or_event_write(
    operation: PinnedAuthorityOperation,
) -> None:
    transactions, events = _repositories(TransactionCatalogue())

    with pytest.raises(RegistryValidationError, match="not declared by the facts registry"):
        create_manual_transaction(
            _command(iva_category=IvaCategory("not-a-declared-category")),
            ports=_ports(operation=operation, transactions=transactions, events=events),
            occurred_at=_NOW,
        )

    assert transactions.catalogue == TransactionCatalogue()
    assert transactions.save_count == events.save_count == 0


def test_field_patch_refuses_a_real_undeclared_category_without_a_catalogue_or_event_write(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = _stored_catalogue("field-patch membership fixture")
    transaction_id = next(iter(catalogue.transactions))
    transactions, events = _repositories(catalogue)

    with pytest.raises(RegistryValidationError, match="not declared by the facts registry"):
        update_manual_transaction_fields(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(iva_category=IvaCategory("not-a-declared-category")),
            actor="operator",
            source_command="aeat app ledger classify",
            ports=_ports(operation=operation, transactions=transactions, events=events),
            occurred_at=_NOW,
        )

    assert transactions.catalogue == catalogue
    assert transactions.save_count == events.save_count == 0


def test_bulk_classification_persists_valid_rows_and_collects_undeclared_categories(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = _stored_catalogue("valid batch row", "undeclared batch row")
    valid_id, invalid_id = tuple(catalogue.transactions)
    transactions, events = _repositories(catalogue)

    result = bulk_classify_from_csv(
        bucket_id=_BUCKET,
        csv_text=(
            "transaction_id,classification,iva_category\n"
            f"{valid_id},BUSINESS,domestic_general\n"
            f"{invalid_id},BUSINESS,not-a-declared-category\n"
        ),
        actor="operator",
        ports=_ports(operation=operation, transactions=transactions, events=events),
    )

    assert result.applied == 1
    assert result.failures[0].transaction_id == invalid_id
    assert "not declared by the facts registry" in result.failures[0].reason
    assert transactions.catalogue.get(valid_id).iva_category == IvaCategory("domestic_general")
    assert transactions.catalogue.get(invalid_id).iva_category is None
    assert transactions.save_count == events.save_count == 1


def test_none_and_declared_non_declarable_categories_are_not_remapped(
    operation: PinnedAuthorityOperation,
) -> None:
    transactions, events = _repositories(TransactionCatalogue())
    ports = _ports(operation=operation, transactions=transactions, events=events)

    actions_manual._require_declared_iva_category(_command(), ports=ports)
    actions_manual._require_declared_iva_category(_command(iva_category=IvaCategory("unknown")), ports=ports)
    actions_manual._require_declared_iva_category(
        _command(iva_category=IvaCategory("domestic_not_subject")),
        ports=ports,
    )
    actions_manual._require_declared_iva_category(
        _command(iva_category=IvaCategory("erroneous_invoice")),
        ports=ports,
    )
