"""Explicit-year synthetic installed IVA statement inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .iva_tui_contracts import _N26_HEADER


@dataclass(frozen=True, slots=True)
class _SyntheticIvaRow:
    """One transient ordinary IVA input row, used by every journey assertion."""

    entry_date: str
    counterparty: str
    payment_reference: str
    signed_amount: str
    taxable_base: str
    iva_amount: str
    deduction_fact_kind: str


def _synthetic_rows(year: int) -> tuple[_SyntheticIvaRow, _SyntheticIvaRow]:
    """Return the two transient rows, dated inside the first quarter of ``year``."""
    return (
        _SyntheticIvaRow(
            entry_date=date(year, 2, 15).isoformat(),
            counterparty="IVA TUI sale",
            payment_reference="iva-tui-sale",
            signed_amount="121.00",
            taxable_base="100.00",
            iva_amount="21.00",
            deduction_fact_kind="",
        ),
        _SyntheticIvaRow(
            entry_date=date(year, 2, 18).isoformat(),
            counterparty="IVA TUI purchase",
            payment_reference="iva-tui-purchase",
            signed_amount="-60.50",
            taxable_base="50.00",
            iva_amount="10.50",
            deduction_fact_kind="domestic_current",
        ),
    )


def _write_synthetic_statement(scratch: Path, synthetic_rows: tuple[_SyntheticIvaRow, ...]) -> Path:
    """Create the private, transient two-row synthetic bank statement."""
    scratch.mkdir(parents=True, exist_ok=True)
    statement = scratch / "iva-installed-tui.csv"
    rows = [_N26_HEADER]
    for item in synthetic_rows:
        rows.append(
            ",".join(
                (
                    item.entry_date,
                    item.counterparty,
                    item.payment_reference,
                    item.signed_amount,
                    "EUR",
                    item.payment_reference,
                )
            )
        )
    statement.write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return statement
