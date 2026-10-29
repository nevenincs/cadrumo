"""Encrypted SQL repository with atomic per-bucket transaction reads and writes.

Core types:
:class:`~cadrumo.adapters.persistence.storage.envelope.contract.Envelope`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    InvestmentAssetAcquisitionLink,
    validate_investment_asset_reciprocity,
)
from ....domain.calculations.registry.iva_deduction_catalogue import is_iva_deduction_kind
from ....domain.iva.deduction_facts import validate_iva_deduction_fact
from ....domain.iva.flow import derive_flow_for_classification
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.errors import LedgerStorageError
from ....domain.transactions.models import (
    Transaction,
)
from ....domain.transactions.repository import transaction_index_object_key, transaction_object_key
from ..storage.errors import (
    SecureObjectRowIdentityError,
)
from ..storage.secure_object_namespaces import (
    TRANSACTION_CATALOGUE_NAMESPACE,
)
from .transaction_iva_migration import migrated_iva_deduction_fact, migrated_iva_rate_kind
from .transaction_row_contracts import (
    TransactionMembershipIndex,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.secure_object_namespaces import SecureObjectNamespaceDefinition


def validated_migrated_transactions(bucket_id: str, payloads: Mapping[str, bytes]) -> tuple[Transaction, ...]:
    """Return the complete semantically validated upgraded transaction set."""
    from ..storage.envelope.contract import Envelope

    index_key = transaction_index_object_key(bucket_id)
    index_payload = payloads.get(index_key)
    if index_payload is None:
        raise LedgerStorageError("transaction index is absent during schema migration")
    index = Envelope[TransactionMembershipIndex].model_validate_json(index_payload).payload
    missing = [
        transaction_id
        for transaction_id in index.transaction_ids
        if transaction_object_key(bucket_id, transaction_id) not in payloads
    ]
    if missing:
        raise LedgerStorageError(
            "transaction rows absent for index ids during schema migration: " + ", ".join(sorted(missing)),
        )
    transactions: list[Transaction] = []
    for transaction_id in index.transaction_ids:
        payload = payloads[transaction_object_key(bucket_id, transaction_id)]
        envelope = Envelope[Transaction].model_validate_json(payload)
        assert_transaction_row_identity(envelope.payload, bucket_id=bucket_id, expected_transaction_id=transaction_id)
        validate_migrated_deduction_fact(envelope.payload)
        transactions.append(envelope.payload)
    return tuple(transactions)


def validate_migrated_deduction_fact(transaction: Transaction) -> None:
    """Validate persisted v1 tax evidence without defaulting any semantic axis."""
    fact = migrated_iva_deduction_fact(transaction)
    if fact is None:
        return
    rate_kind = migrated_iva_rate_kind(transaction, fact)
    invoice_kind = (
        InvoiceKind.RECEIVED if transaction.direction is TransactionDirection.OUTGOING else InvoiceKind.ISSUED
    )
    flow_direction = derive_flow_for_classification(
        category=fact.category,
        invoice_direction=invoice_kind,
    )
    validate_iva_deduction_fact(
        kind=fact.kind,
        provenance=fact.provenance,
        category=fact.category,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        base_amount=fact.taxable_base,
        iva_amount=fact.iva_amount,
        investment_asset_id=transaction.investment_asset_id,
        rectifies_ledger_id=transaction.rectifies_ledger_id,
    )


def migration_investment_links(
    transactions: Iterable[Transaction],
) -> dict[int, list[InvestmentAssetAcquisitionLink]]:
    """Group migrated investment deductions by filing year."""
    links_by_year: dict[int, list[InvestmentAssetAcquisitionLink]] = {}
    for transaction in transactions:
        if not (
            transaction.deduction_fact_kind is not None
            and is_iva_deduction_kind(transaction.deduction_fact_kind, "kind.investment_acquisition")
        ):
            continue
        investment_asset_id = transaction.investment_asset_id
        if investment_asset_id is None:
            raise LedgerStorageError(
                f"transaction {transaction.transaction_id!r} has an investment deduction kind without an asset link",
            )
        transaction_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
        links_by_year.setdefault(transaction_date.year, []).append(
            InvestmentAssetAcquisitionLink(
                ledger_id=transaction.transaction_id,
                transaction_date=transaction_date,
                deduction_fact_kind=transaction.deduction_fact_kind,
                investment_asset_id=investment_asset_id,
                prorrata_sector_id=transaction.prorrata_sector_id,
            ),
        )
    return links_by_year


def validate_iva_authority_migration(
    bucket_id: str,
    payloads: Mapping[tuple[str, str], bytes],
    *,
    bienes_definition: SecureObjectNamespaceDefinition,
    bienes_key: str,
    asset_profile_id: str,
) -> None:
    """Validate upgraded transaction rows against reciprocal bienes authority."""
    transaction_payloads = {
        key: payload
        for (namespace, key), payload in payloads.items()
        if namespace == TRANSACTION_CATALOGUE_NAMESPACE.namespace
    }
    transactions = validated_migrated_transactions(bucket_id, transaction_payloads)
    register_payload = payloads.get((bienes_definition.namespace, bienes_key))
    if register_payload is None:
        raise LedgerStorageError("bienes-inversion register is absent during IVA authority migration")
    register = BienesInversionIvaRegister.model_validate_json(register_payload)
    links_by_year = migration_investment_links(transactions)
    years = sorted(set(links_by_year) | {record.acquisition_year for record in register.records})
    for filing_year in years:
        validate_investment_asset_reciprocity(
            observations=tuple(links_by_year.get(filing_year, [])),
            register=register,
            ledger_profile_id=bucket_id,
            asset_profile_id=asset_profile_id,
            filing_year=filing_year,
        )


def assert_transaction_row_identity(transaction: Transaction, *, bucket_id: str, expected_transaction_id: str) -> None:
    """Refuse a row addressed by a different transaction identity."""
    if transaction.transaction_id != expected_transaction_id:
        raise SecureObjectRowIdentityError(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            expected_identifier=transaction_object_key(bucket_id, expected_transaction_id),
        )
