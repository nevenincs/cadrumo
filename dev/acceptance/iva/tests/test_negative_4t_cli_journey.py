"""Public installed-CLI acceptance for the negative fourth-quarter IVA journey."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from dev.acceptance.installed_cli import build_installed_cli_environment
from dev.packaging.installed_runtime import installed_cli_runtime

from ..negative_4t_cli_journey import IvaNegative4TCliJourneyReceipt, RefundElection, run_iva_negative_4t_cli_journey
from .journey_year_support import newest_fully_authored_journey_year

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _run_negative_4t_journey(
    tmp_path: Path, installed_wheel_aeat: Path, *, refund_election: RefundElection = "compensar"
) -> tuple[IvaNegative4TCliJourneyReceipt, int]:
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root
    year = newest_fully_authored_journey_year(authority_root)

    receipt = run_iva_negative_4t_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
        year=year,
        refund_election=refund_election,
        runtime_scope=installed_cli_runtime(
            installed_wheel_aeat,
            build_installed_cli_environment(storage_root=tmp_path / "secure-store", authority_root=authority_root),
            tmp_path / "caller-owned-runtime.log",
        ),
    )
    return receipt, year


def _assert_local_pending_negative_4t_receipt(
    receipt: IvaNegative4TCliJourneyReceipt, year: int, *, election: str
) -> None:
    """Assertions every negative fourth-quarter outcome shares, whatever the refund election."""
    assert receipt.filing_year == year
    assert Decimal(receipt.iva_resultado) == Decimal("-10.50")
    assert receipt.filing_origin == "local"
    assert receipt.filing_confirmation == "pendiente"
    assert receipt.filing_aeat_accepted is False
    assert receipt.filing_live_submission is False
    assert receipt.wallet_row_count == 2
    assert receipt.authority_generation
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert any(
        command.argv[2:6] == ("app", "modelo", "work", "file")
        and "--refund-election" in command.argv
        and election in command.argv
        for command in receipt.commands
    )
    assert any(
        command.argv[2:6] == ("app", "live", "iva-wallet", "history")
        and command.argv[-2:] == ("--as-of-year", str(year))
        for command in receipt.commands
    )
    assert not any(command.argv[2:5] == ("app", "modelo", "export") for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-negative-4t-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)


def test_installed_cli_negative_fourth_quarter_compensar_generates_wallet_history(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """One deductible purchase becomes a local pending filing and available IVA credit."""
    receipt, year = _run_negative_4t_journey(tmp_path, installed_wheel_aeat)

    assert receipt.acceptance_ids == (f"IVA-01-NEGATIVE-{year}-4T-COMPENSAR",)
    _assert_local_pending_negative_4t_receipt(receipt, year, election="compensar")
    assert Decimal(receipt.wallet_generated_amount) == Decimal("10.50")
    assert Decimal(receipt.wallet_available_end_amount) == Decimal("10.50")
    assert receipt.wallet_carry_forward_lot_count == 1
    assert receipt.wallet_remaining_lot_amount is not None
    assert Decimal(receipt.wallet_remaining_lot_amount) == Decimal("10.50")


def test_installed_cli_negative_fourth_quarter_devolver_leaves_no_wallet_carry(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """A local devolver election is pending only and creates no IVA carry-forward lot."""
    receipt, year = _run_negative_4t_journey(tmp_path, installed_wheel_aeat, refund_election="devolver")

    assert receipt.acceptance_ids == (f"IVA-01-NEGATIVE-{year}-4T-DEVOLVER",)
    _assert_local_pending_negative_4t_receipt(receipt, year, election="devolver")
    assert receipt.local_refund_election == "devolver"
    assert Decimal(receipt.wallet_generated_amount) == Decimal("0.00")
    assert Decimal(receipt.wallet_available_end_amount) == Decimal("0.00")
    assert receipt.wallet_carry_forward_lot_count == 0
    assert receipt.wallet_remaining_lot_amount is None
