"""Shared fixtures for the Renta imputation tests that run to exported bytes.

The ledger rows, the refund account and the verify-and-export step the Modelo 130 and
Modelo 100 imputation tests share. Expected figures live in the tests that assert them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from cadrumo.adapters.persistence.profile.inventory import InventoryLedgerRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.own_accounts import OwnAccountRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.aggregation.tests.inventory_source_support import closed_no_stock_ledger
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.contribuyente.inventory.records import InventoryLedgerDocument
from cadrumo.domain.invoices.catalogue import InvoiceCatalogue
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.own_accounts import (
    OwnAccountDesignation,
    OwnAccountHolding,
    OwnAccountRegister,
    OwnAccountRole,
    OwnBankAccountDetails,
)
from cadrumo.tests.env_scope import ready_clave_settings

from .m130_m100_annual_support import (
    BUCKET_ID,
    OPERATOR_SCOPE_PORTS,
    TAX_ID,
    YEAR,
    autonomaworkflow_profile,
    expense_transaction,
    export_revision_for_test,
    income_transaction,
    verify_revision_for_test,
)

NEXT_YEAR = YEAR + 1

DEVENGO = "devengo"

CASH = "cobros_y_pagos"

REFUND_IBAN = "ES9121000418450200051332"

OFFICIAL_M130_C19 = {
    "1T": Decimal("300.00"),
    "2T": Decimal("360.00"),
    "3T": Decimal("400.00"),
    "4T": Decimal("460.00"),
}


def _income(row_id: str, banked: date, accrues: date, amount: str) -> Transaction:
    template = income_transaction("1T")
    value = Decimal(amount)
    raw = template.raw.model_copy(
        update={
            "provider_transaction_id": row_id,
            "booked_date": banked,
            "value_date": banked,
            "amount": value,
            "description": row_id,
        }
    )
    stored = template.model_dump(mode="python", exclude={"transaction_id"})
    return Transaction.model_validate({**stored, "raw": raw, "taxable_base": value, "accrual_date": accrues})


def _expense(row_id: str, banked: date, accrues: date, category: str, amount: str) -> Transaction:
    row = expense_transaction(
        row_id, value_date=banked, category=SpendingCategory.from_registry(category), taxable_base=Decimal(amount)
    )
    return row.model_copy(update={"accrual_date": accrues})


def persist_ledger(objects: SecureObjectRepository) -> None:
    rows = (
        _income("income-c", date(YEAR, 2, 15), date(YEAR, 2, 15), "4000.00"),
        _income("income-b", date(YEAR, 5, 20), date(YEAR, 2, 15), "3500.00"),
        _income("income-a", date(NEXT_YEAR, 1, 20), date(YEAR, 11, 5), "2500.00"),
        _expense("expense-e1", date(YEAR, 7, 10), date(YEAR, 4, 1), "software_suscripcion", "700.00"),
        _expense("expense-e2", date(NEXT_YEAR, 2, 1), date(YEAR, 12, 1), "asesoria_fiscal", "900.00"),
    )
    TransactionCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(
        TransactionCatalogue.from_transactions(rows)
    )
    InvoiceCatalogueRepository(bucket_id=BUCKET_ID, objects=objects).save(InvoiceCatalogue())
    InventoryLedgerRepository(objects=objects).save(InventoryLedgerDocument(ledgers=(closed_no_stock_ledger(YEAR),)))


def verify_and_export(revision: CalculationRevision, objects: SecureObjectRepository, output: Path) -> bytes:
    report = verify_revision_for_test(
        revision.calculation_revision_id,
        actor="imputation-e2e",
        workflow_profile=autonomaworkflow_profile(),
        settings=ready_clave_settings(TAX_ID),
        operator_scope_ports=OPERATOR_SCOPE_PORTS,
    )
    assert report.granted_verificado_completo is True, report.findings
    receipt = export_revision_for_test(
        ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id, output_path=output, actor="imputation-e2e"
        ),
        workflow_profile=autonomaworkflow_profile(),
        export_ports=modelo_export_ports_for_test(bucket_id=BUCKET_ID, taxpayer_tax_id=TAX_ID, secure_objects=objects),
    )
    payload = output.read_bytes()
    assert receipt.byte_size == len(payload)
    return payload


def register_refund_account(objects: SecureObjectRepository) -> None:
    """Designate a Spanish own account to receive the refund, as the export's account page needs."""

    def change(register: OwnAccountRegister) -> OwnAccountRegister:
        account_id = register.next_account_id()
        return register.with_new_account(
            OwnBankAccountDetails(label="Devolución", holding=OwnAccountHolding.TITULAR, iban=REFUND_IBAN)
        ).with_designation(OwnAccountDesignation(role=OwnAccountRole.REFUND, own_account_id=account_id))

    OwnAccountRepository(objects=objects).mutate(change)
