"""Seed the ledger payment an activity-asset acceptance journey registers its machine against."""

from __future__ import annotations

from decimal import Decimal

from dev.acceptance.income_tax.cli_journey import command_result
from dev.acceptance.installed_cli import InstalledCli

_IVA_RATE = Decimal("0.21")


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def seed_machine_acquisition(cli: InstalledCli, *, basis: str, booked: str, label: str) -> str:
    """Record the payment for a machine through the registered ``ledger add`` route.

    The register refuses an acquisition the ledger does not bear out, so the
    payment is recorded first, in the category the register owns, and its
    identity is what the asset revision names.

    Args:
        cli: Installed command runner bound to the journey's profile.
        basis: Price of the machine before IVA, in euros.
        booked: ISO date the payment was made.
        label: Stable name that keeps the idempotency key unique to the journey.

    Returns:
        The ledger transaction identity of the payment.
    """
    price = Decimal(basis)
    iva = (price * _IVA_RATE).quantize(Decimal("0.01"))
    added = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "add",
                "--date",
                booked,
                "--amount",
                _money(price + iva),
                "--direction",
                "OUTGOING",
                "--description",
                f"Synthetic {label} acquisition",
                "--classification",
                "BUSINESS",
                "--category-id",
                "hardware_amortizable",
                "--taxable-base",
                _money(price),
                "--iva-rate",
                str(_IVA_RATE),
                "--iva-amount",
                _money(iva),
                "--idempotency-key",
                f"acquisition-{label}",
            )
        )
    )
    return str(added["transaction_id"])
