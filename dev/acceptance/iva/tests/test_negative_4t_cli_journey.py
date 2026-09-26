"""Public installed-CLI acceptance for the negative 2025/4T IVA journey."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ..negative_4t_cli_journey import run_iva_negative_4t_cli_journey

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_installed_cli_negative_2025_4t_compensar_generates_wallet_history(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """One deductible purchase becomes a local pending filing and available IVA credit."""
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root

    receipt = run_iva_negative_4t_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
        year=2025,
    )

    assert receipt.acceptance_ids == ("IVA-01-NEGATIVE-2025-4T-COMPENSAR",)
    assert receipt.filing_year == 2025
    assert Decimal(receipt.iva_resultado) == Decimal("-10.50")
    assert receipt.filing_origin == "local"
    assert receipt.filing_confirmation == "pendiente"
    assert receipt.filing_aeat_accepted is False
    assert receipt.filing_live_submission is False
    assert receipt.wallet_row_count == 2
    assert Decimal(receipt.wallet_generated_amount) == Decimal("10.50")
    assert Decimal(receipt.wallet_available_end_amount) == Decimal("10.50")
    assert receipt.wallet_carry_forward_lot_count == 1
    assert receipt.wallet_remaining_lot_amount is not None
    assert Decimal(receipt.wallet_remaining_lot_amount) == Decimal("10.50")
    assert receipt.authority_generation
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert any(
        command.argv[2:6] == ("app", "modelo", "work", "file")
        and "--refund-election" in command.argv
        and "compensar" in command.argv
        for command in receipt.commands
    )
    assert any(
        command.argv[2:6] == ("app", "live", "iva-wallet", "history") and command.argv[-2:] == ("--as-of-year", "2025")
        for command in receipt.commands
    )
    assert not any(command.argv[2:5] == ("app", "modelo", "export") for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-negative-4t-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)


def test_installed_cli_negative_2025_4t_devolver_leaves_no_wallet_carry(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """A local devolver election is pending only and creates no IVA carry-forward lot."""
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root

    receipt = run_iva_negative_4t_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
        year=2025,
        refund_election="devolver",
    )

    assert receipt.acceptance_ids == ("IVA-01-NEGATIVE-2025-4T-DEVOLVER",)
    assert receipt.filing_year == 2025
    assert Decimal(receipt.iva_resultado) == Decimal("-10.50")
    assert receipt.local_refund_election == "devolver"
    assert receipt.filing_origin == "local"
    assert receipt.filing_confirmation == "pendiente"
    assert receipt.filing_aeat_accepted is False
    assert receipt.filing_live_submission is False
    assert receipt.wallet_row_count == 2
    assert Decimal(receipt.wallet_generated_amount) == Decimal("0.00")
    assert Decimal(receipt.wallet_available_end_amount) == Decimal("0.00")
    assert receipt.wallet_carry_forward_lot_count == 0
    assert receipt.wallet_remaining_lot_amount is None
    assert receipt.authority_generation
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert any(
        command.argv[2:6] == ("app", "modelo", "work", "file")
        and "--refund-election" in command.argv
        and "devolver" in command.argv
        for command in receipt.commands
    )
    assert any(
        command.argv[2:6] == ("app", "live", "iva-wallet", "history") and command.argv[-2:] == ("--as-of-year", "2025")
        for command in receipt.commands
    )
    assert not any(command.argv[2:5] == ("app", "modelo", "export") for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-negative-4t-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)
