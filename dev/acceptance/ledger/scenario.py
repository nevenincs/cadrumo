"""Versioned synthetic inputs for the future LEDGER-01 installed CLI journey.

The scenario names stable fixture coordinates rather than product-generated
invoice or transaction IDs.  A runner must capture those public IDs from the
installed CLI response and retain them in its shared receipt implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

BRIEF_ID = "LEDGER-01"
BRIEF_REVISION = "0.1"
SCENARIO_VERSION = "ledger-cli-lifecycle-v1"

type InvoiceKind = Literal["issued", "received"]
type TransactionDirection = Literal["INCOMING", "OUTGOING"]


@dataclass(frozen=True, slots=True)
class InvoiceFixture:
    """One manual invoice whose generated catalogue ID is read from the CLI."""

    fixture_id: str
    kind: InvoiceKind
    counterparty_name: str
    counterparty_tax_id: str
    counterparty_country: str
    invoice_number: str
    invoice_date: date
    currency: str
    taxable_base: Decimal
    iva_rate_fraction: Decimal
    iva_category: str
    notes: str

    @property
    def iva_amount(self) -> Decimal:
        """Return the independent one-line IVA amount used for readback."""
        return (self.taxable_base * self.iva_rate_fraction).quantize(Decimal("0.01"))

    @property
    def cli_iva_rate_percent(self) -> str:
        """Render the CLI invoice input unit from the independent fraction."""
        return str(self.iva_rate_fraction * Decimal("100"))

    @property
    def grand_total(self) -> Decimal:
        """Return the independently expected invoice total."""
        return self.taxable_base + self.iva_amount


@dataclass(frozen=True, slots=True)
class TransactionFixture:
    """One manual transaction to capture and link through public CLI verbs."""

    fixture_id: str
    transaction_date: date
    direction: TransactionDirection
    amount: Decimal
    description: str
    classification: str
    taxable_base: Decimal
    iva_rate_fraction: Decimal
    iva_amount: Decimal
    iva_category: str
    linked_invoice_fixture_id: str


@dataclass(frozen=True, slots=True)
class InvoiceMetadataUpdateFixture:
    """A supported non-identity invoice update for the installed CLI path."""

    invoice_fixture_id: str
    notes: str


@dataclass(frozen=True, slots=True)
class StructuredImportRow:
    """One CSV row, retaining its source-row coordinate for provenance checks."""

    source_row: int
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuredInvoiceImportFixture:
    """One supported invoice-import input and its exact replay expectation."""

    fixture_id: str
    filename: str
    kind: InvoiceKind
    columns: tuple[str, ...]
    rows: tuple[StructuredImportRow, ...]
    expected_created: int
    expected_refused: int
    expected_replay_skipped_duplicate: int

    def row_values(self, row: StructuredImportRow) -> dict[str, str]:
        """Return one renderer-ready row without defining a second importer."""
        return dict(zip(self.columns, row.values, strict=True))


@dataclass(frozen=True, slots=True)
class PurchaseEvidenceFixture:
    """Synthetic document bytes to attach to the received-invoice settlement."""

    fixture_id: str
    linked_transaction_fixture_id: str
    filename: str
    supplier: str
    text_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LedgerCliScenario:
    """Source facts consumed by the future CLI-only lifecycle acceptance driver."""

    year: int
    manual_invoices: tuple[InvoiceFixture, ...]
    transactions: tuple[TransactionFixture, ...]
    invoice_update: InvoiceMetadataUpdateFixture
    structured_import: StructuredInvoiceImportFixture
    purchase_evidence: PurchaseEvidenceFixture
    fresh_process_invoice_fixture_ids: tuple[str, ...]
    fresh_process_transaction_fixture_ids: tuple[str, ...]


def build_ledger_cli_scenario(year: int) -> LedgerCliScenario:
    """Build the small, synthetic common-regime lifecycle fixture for ``year``."""
    issued = InvoiceFixture(
        fixture_id="issued-manual",
        kind="issued",
        counterparty_name="Synthetic customer SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number=f"LEDGER-ISS-{year}-001",
        invoice_date=date(year, 3, 15),
        currency="EUR",
        taxable_base=Decimal("100.00"),
        iva_rate_fraction=Decimal("0.21"),
        iva_category="domestic_general",
        notes="ledger-cli-initial",
    )
    transaction = TransactionFixture(
        fixture_id="issued-settlement",
        transaction_date=date(year, 3, 18),
        direction="INCOMING",
        amount=issued.grand_total,
        description="Synthetic issued-invoice settlement",
        classification="BUSINESS",
        taxable_base=issued.taxable_base,
        iva_rate_fraction=issued.iva_rate_fraction,
        iva_amount=issued.iva_amount,
        iva_category=issued.iva_category,
        linked_invoice_fixture_id=issued.fixture_id,
    )
    received_transaction = TransactionFixture(
        fixture_id="received-settlement",
        transaction_date=date(year, 3, 25),
        direction="OUTGOING",
        amount=Decimal("60.50"),
        description="Synthetic received-invoice settlement",
        classification="BUSINESS",
        taxable_base=Decimal("50.00"),
        iva_rate_fraction=Decimal("0.21"),
        iva_amount=Decimal("10.50"),
        iva_category="domestic_general",
        linked_invoice_fixture_id="received-import",
    )
    import_row = StructuredImportRow(
        source_row=2,
        values=(
            "B12345674",
            "Synthetic supplier SL",
            f"LEDGER-REC-{year}-001",
            f"{year}-03-20",
            "50.00",
            "21",
            "ES",
            "ledger-cli-import",
        ),
    )
    structured_import = StructuredInvoiceImportFixture(
        fixture_id="received-import",
        filename="ledger-received.csv",
        kind="received",
        columns=(
            "counterparty_nif",
            "counterparty_name",
            "invoice_number",
            "invoice_date",
            "taxable_base",
            "iva_rate",
            "country_code",
            "notes",
        ),
        rows=(
            import_row,
            StructuredImportRow(
                source_row=3,
                values=(
                    "B12345674",
                    "Synthetic supplier SL",
                    "",
                    f"{year}-03-21",
                    "75.00",
                    "21",
                    "ES",
                    "ledger-cli-refused-row",
                ),
            ),
        ),
        expected_created=1,
        expected_refused=1,
        expected_replay_skipped_duplicate=1,
    )
    return LedgerCliScenario(
        year=year,
        manual_invoices=(issued,),
        transactions=(transaction, received_transaction),
        invoice_update=InvoiceMetadataUpdateFixture(
            invoice_fixture_id=issued.fixture_id,
            notes="ledger-cli-updated",
        ),
        structured_import=structured_import,
        purchase_evidence=PurchaseEvidenceFixture(
            fixture_id="received-document",
            linked_transaction_fixture_id=received_transaction.fixture_id,
            filename="synthetic-received.pdf",
            supplier="Synthetic supplier SL",
            text_lines=(f"LEDGER-REC-{year}-001", "Synthetic supplier SL", "Total 60.50 EUR"),
        ),
        fresh_process_invoice_fixture_ids=(issued.fixture_id, structured_import.fixture_id),
        fresh_process_transaction_fixture_ids=(transaction.fixture_id, received_transaction.fixture_id),
    )


__all__ = [
    "BRIEF_ID",
    "BRIEF_REVISION",
    "SCENARIO_VERSION",
    "InvoiceFixture",
    "InvoiceKind",
    "InvoiceMetadataUpdateFixture",
    "LedgerCliScenario",
    "PurchaseEvidenceFixture",
    "StructuredImportRow",
    "StructuredInvoiceImportFixture",
    "TransactionDirection",
    "TransactionFixture",
    "build_ledger_cli_scenario",
]
