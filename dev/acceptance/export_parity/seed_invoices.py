"""Canonical invoices stage for installed export-parity seeding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .scenario import (
    CLIENT,
    IssuedInvoice,
    ReceivedInvoice,
    WithholdingDuty,
)
from .seed_contracts import (
    _UNCHANGED_UPDATE,
    SeedRefusalError,
)
from .seed_inputs import (
    _investment_asset_args,
    _is_investment_good,
    _money,
    _rate,
)
from .seed_state import SeedState


def _received_invoice_identity(self: InvoiceSeedStage, item: ReceivedInvoice, stage: str) -> Any:
    """Received invoice identity."""
    withholding_args: tuple[str, ...] = (
        ("--retention-rate", _rate(item.withholding / item.base), "--retention-amount", _money(item.withholding))
        if item.withholding
        else ()
    )
    invoice_id = self.receipt.identifiers.get(f"invoice:{item.key}") or self._stored_invoice(
        "received", item.key.upper()
    )
    if invoice_id is None:
        invoice_id = self._result(
            (
                "app",
                "ledger",
                "invoice",
                "add",
                "--kind",
                "received",
                "--counterparty-name",
                item.counterparty.name,
                "--counterparty-nif",
                item.counterparty.tax_id,
                "--invoice-number",
                item.key.upper(),
                "--invoice-date",
                item.invoice_date.isoformat(),
                "--taxable-base",
                _money(item.base),
                "--iva-rate",
                _rate(item.iva_rate * 100),
                "--country-code",
                "ES",
                *withholding_args,
                "--iva-category",
                "domestic_general" if item.iva_rate else "domestic_exempt",
            ),
            stage=f"{stage}.invoice",
        )["invoice_id"]
    self._remember(f"invoice:{item.key}", invoice_id)
    self.receipt.save(self.receipt_path)
    return invoice_id


def _classify_received_transaction(
    self: InvoiceSeedStage, item: ReceivedInvoice, stage: str, transaction_id: str
) -> None:
    """Classify received transaction."""
    if item.iva_rate and self._pending(f"classify:{item.key}"):
        try:
            self._result(
                (
                    "app",
                    "ledger",
                    "classify",
                    transaction_id,
                    "--classification",
                    "BUSINESS",
                    "--deduction-kind",
                    "domestic_investment" if _is_investment_good(item) else "domestic_current",
                    *_investment_asset_args(item),
                    "--counterparty-country",
                    "ES",
                    "--reaffirm",
                ),
                stage=f"{stage}.classify",
            )
        except SeedRefusalError:
            # An interrupted run already applied this classification; the product
            # refuses a no-op update, which on resume is the expected answer.
            if _UNCHANGED_UPDATE not in self.receipt.blocked.get(f"{stage}.classify", ""):
                raise
            self.receipt.blocked.pop(f"{stage}.classify")
        self._complete(f"classify:{item.key}")


class InvoiceSeedStage(SeedState):
    """Own the installed seed invoices behavior."""

    def _issued(self, item: IssuedInvoice) -> None:
        stage = f"ledger.issued.{item.key}"
        description = f"Synthetic fees {item.key}"
        transaction_id = self.receipt.identifiers.get(f"tx:{item.key}") or self._stored_transaction(description)
        if transaction_id is None:
            added = self._result(
                (
                    "app",
                    "ledger",
                    "add",
                    "--date",
                    item.payment_date.isoformat(),
                    "--amount",
                    _money(item.receipt),
                    "--direction",
                    "INCOMING",
                    "--description",
                    description,
                    "--classification",
                    "BUSINESS",
                    "--taxable-base",
                    _money(item.base),
                    "--iva-rate",
                    "0.21",
                    "--iva-amount",
                    _money(item.iva),
                    "--iva-category",
                    "domestic_general",
                    "--irpf-category",
                    "actividad_economica",
                    "--source-jurisdiction",
                    "ES",
                    "--idempotency-key",
                    item.key,
                ),
                stage=stage,
            )
            transaction_id = str(added["transaction_id"])
        self._remember(f"tx:{item.key}", transaction_id)
        self.receipt.save(self.receipt_path)
        invoice_id = self.receipt.identifiers.get(f"invoice:{item.key}") or self._stored_invoice(
            "issued", item.key.upper()
        )
        if invoice_id is None:
            added = self._result(
                (
                    "app",
                    "ledger",
                    "invoice",
                    "add",
                    "--kind",
                    "issued",
                    "--counterparty-name",
                    CLIENT.name,
                    "--counterparty-nif",
                    CLIENT.tax_id,
                    "--invoice-number",
                    item.key.upper(),
                    "--invoice-date",
                    item.invoice_date.isoformat(),
                    "--taxable-base",
                    _money(item.base),
                    "--iva-rate",
                    "21",
                    "--country-code",
                    "ES",
                    "--retention-rate",
                    _rate(item.withholding_rate),
                    "--retention-amount",
                    _money(item.withholding),
                    "--iva-category",
                    "domestic_general",
                ),
                stage=f"{stage}.invoice",
            )
            invoice_id = str(added["invoice_id"])
        self._remember(f"invoice:{item.key}", invoice_id)
        self.receipt.save(self.receipt_path)
        if self._pending(f"link:{item.key}"):
            self._result(("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id), stage=f"{stage}.link")
            self._complete(f"link:{item.key}")

    def _evidence_pdf(self, item: ReceivedInvoice) -> Path:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"{item.key}.pdf"
        path.write_bytes(f"%PDF-1.4\n% synthetic export-parity purchase evidence {item.key}\n".encode("ascii"))
        return path

    def _received(self, item: ReceivedInvoice) -> None:
        stage = f"ledger.received.{item.key}"
        evidence_id = self.receipt.identifiers.get(f"evidence:{item.key}")
        if evidence_id is None:
            evidence = self._result(
                (
                    "app",
                    "ledger",
                    "evidence",
                    "add",
                    str(self._evidence_pdf(item)),
                    "--supplier",
                    item.counterparty.name,
                ),
                stage=f"{stage}.evidence",
            )
            evidence_id = self._remember(f"evidence:{item.key}", evidence["evidence_id"])
            self.receipt.save(self.receipt_path)
        iva_args: tuple[str, ...] = (
            (
                "--taxable-base",
                _money(item.base),
                "--iva-rate",
                _rate(item.iva_rate),
                "--iva-amount",
                _money(item.iva),
                "--iva-category",
                "domestic_general",
            )
            if item.iva_rate
            else (
                "--taxable-base",
                _money(item.base),
                "--iva-rate",
                "0",
                "--iva-amount",
                "0.00",
                "--iva-category",
                "domestic_exempt",
            )
        )
        # A payment settled net of the declarant's withholding names the IRPF
        # category that makes the cash gap a withholding rather than a mismatch.
        irpf_args: tuple[str, ...] = {
            WithholdingDuty.NONE: (),
            WithholdingDuty.PROFESSIONAL: ("--irpf-category", "actividad_economica"),
            WithholdingDuty.URBAN_RENT: ("--irpf-category", "arrendamiento_local"),
        }[item.duty]
        description = f"Synthetic purchase {item.key}"
        transaction_id = self.receipt.identifiers.get(f"tx:{item.key}") or self._stored_transaction(description)
        if transaction_id is None:
            transaction_id = self._remember(
                f"tx:{item.key}",
                self._result(
                    (
                        "app",
                        "ledger",
                        "add",
                        "--date",
                        item.payment_date.isoformat(),
                        "--amount",
                        _money(item.payment),
                        "--direction",
                        "OUTGOING",
                        "--description",
                        description,
                        "--classification",
                        "BUSINESS",
                        "--category-id",
                        item.category,
                        *iva_args,
                        *irpf_args,
                        "--purchase-invoice-evidence-id",
                        evidence_id,
                        "--source-jurisdiction",
                        "ES",
                        "--idempotency-key",
                        item.key,
                    ),
                    stage=stage,
                )["transaction_id"],
            )
            self.receipt.save(self.receipt_path)
        self._remember(f"tx:{item.key}", transaction_id)
        invoice_id = _received_invoice_identity(self, item, stage)
        if self._pending(f"link:{item.key}"):
            self._result(("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id), stage=f"{stage}.link")
            self._complete(f"link:{item.key}")
        _classify_received_transaction(self, item, stage, transaction_id)
