"""Documented synthetic IVA capture through installed public CLI commands."""

from __future__ import annotations

from pathlib import Path

from dev.acceptance.installed_cli import InstalledCli

from .cli_journey import (
    SanitizedCommandReceipt,
    _invoice_add_args,
    _invoice_line,
    _required_id,
    _result,
    _run,
)
from .filing_year import IvaJourneyYear


def _add_issued_invoice(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, journey_year: IvaJourneyYear
) -> str:
    invoice = _result(
        _run(
            cli,
            receipts,
            artifact,
            _invoice_add_args(
                kind="issued",
                counterparty_name="Synthetic annual-foundation client SL",
                counterparty_nif="A58818501",
                invoice_number=f"IVA-ISS-ANNUAL-FOUNDATION-{journey_year.year}-1T",
                invoice_date=journey_year.iso_date(2, 15),
                iva_category="domestic_general",
                line=_invoice_line(
                    description="Synthetic annual-foundation sale",
                    subtotal="100.00",
                    iva_amount="21.00",
                ),
            ),
            result_keys=("invoice_id",),
        )
    )
    return _required_id(invoice, "invoice_id")


def _add_documented_ledger_facts(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    purchase_evidence_id: str,
    journey_year: IvaJourneyYear,
) -> tuple[str, ...]:
    year = journey_year.year
    sales = (
        ("1T", journey_year.iso_date(2, 10), "2420.00", "2000.00", "420.00"),
        ("2T", journey_year.iso_date(5, 12), "1815.00", "1500.00", "315.00"),
        ("3T", journey_year.iso_date(8, 15), "1210.00", "1000.00", "210.00"),
        ("4T", journey_year.iso_date(11, 20), "3025.00", "2500.00", "525.00"),
    )
    rows = tuple(
        _add_documented_transaction(
            cli=cli,
            receipts=receipts,
            artifact=artifact,
            date=date,
            amount=amount,
            direction="INCOMING",
            description=f"Synthetic documented annual IVA sale {period}",
            taxable_base=base,
            iva_amount=iva,
            idempotency_key=f"iva-01-annual-m390-sale-{year}-{period.lower()}",
        )
        for period, date, amount, base, iva in sales
    )
    purchase = _add_documented_transaction(
        cli=cli,
        receipts=receipts,
        artifact=artifact,
        date=journey_year.iso_date(3, 5),
        amount="605.00",
        direction="OUTGOING",
        description="Synthetic documented annual IVA purchase 1T",
        taxable_base="500.00",
        iva_amount="105.00",
        idempotency_key=f"iva-01-annual-m390-purchase-{year}-1t",
        purchase_evidence_id=purchase_evidence_id,
    )
    _classify_purchase(cli=cli, receipts=receipts, artifact=artifact, transaction_id=purchase)
    return (*rows, purchase)


def _add_documented_transaction(
    *,
    cli: InstalledCli,
    receipts: list[SanitizedCommandReceipt],
    artifact: Path,
    date: str,
    amount: str,
    direction: str,
    description: str,
    taxable_base: str,
    iva_amount: str,
    idempotency_key: str,
    purchase_evidence_id: str | None = None,
) -> str:
    args = [
        "app",
        "ledger",
        "add",
        "--date",
        date,
        "--amount",
        amount,
        "--direction",
        direction,
        "--description",
        description,
        "--classification",
        "BUSINESS",
    ]
    if purchase_evidence_id is not None:
        args.extend(("--category-id", "material_oficina"))
    args.extend(
        (
            "--taxable-base",
            taxable_base,
            "--iva-rate",
            "0.21",
            "--iva-amount",
            iva_amount,
            "--iva-category",
            "domestic_general",
        )
    )
    if purchase_evidence_id is not None:
        args.extend(("--purchase-invoice-evidence-id", purchase_evidence_id))
    args.extend(("--source-jurisdiction", "ES", "--idempotency-key", idempotency_key))
    return _required_id(
        _result(_run(cli, receipts, artifact, tuple(args), result_keys=("transaction_id",))), "transaction_id"
    )


def _classify_purchase(
    *, cli: InstalledCli, receipts: list[SanitizedCommandReceipt], artifact: Path, transaction_id: str
) -> None:
    _run(
        cli,
        receipts,
        artifact,
        (
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--deduction-kind",
            "domestic_current",
            "--counterparty-country",
            "ES",
            "--reaffirm",
        ),
        result_keys=(),
    )
