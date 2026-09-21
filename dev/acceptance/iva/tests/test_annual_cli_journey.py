"""Public installed-CLI acceptance for the first IVA annual-foundation slice."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ..annual_cli_journey import run_iva_annual_foundation_cli_journey

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_installed_cli_2025_1t_local_filing_establishes_annual_foundation(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """A verified ordinary 303 persists its local filing identity for later annual work."""
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root

    receipt = run_iva_annual_foundation_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
    )

    assert receipt.acceptance_ids == ("IVA-01-ANNUAL-FOUNDATION-2025-1T",)
    assert Decimal(receipt.iva_resultado) == Decimal("21.00") - Decimal("10.50")
    assert receipt.calculation_revision_id
    assert receipt.verification_report_id
    assert receipt.verification_status
    assert receipt.filing_record_id
    assert receipt.filing_origin == "local"
    assert receipt.filing_confirmation == "pendiente"
    assert receipt.filing_aeat_accepted is False
    assert receipt.filing_live_submission is False
    assert receipt.authority_generation
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert any(command.argv[2:6] == ("app", "modelo", "work", "file") for command in receipt.commands)
    assert any(command.argv[2:6] == ("app", "modelo", "work", "list") for command in receipt.commands)
    assert any(command.argv[2:6] == ("app", "modelo", "filing-record", "list") for command in receipt.commands)
    assert not any(command.argv[2:5] == ("app", "modelo", "export") for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-annual-foundation-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)
