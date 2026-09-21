"""Public installed-CLI acceptance for the ordinary 2025/1T IVA path."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ..cli_journey import run_iva_m303_cli_journey

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_installed_cli_captures_reopens_and_calculates_ordinary_2025_m303(tmp_path: Path) -> None:
    """Only public installed commands may produce the saved 10.50 EUR draft."""
    repository_root = Path(__file__).resolve().parents[4]
    executable = Path(sys.executable).with_name("aeat.exe")
    authority_root = repository_root / ".authority"
    assert executable.is_file(), executable
    assert (authority_root / "authority.current.json").is_file(), authority_root

    receipt = run_iva_m303_cli_journey(
        executable=executable,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
    )

    assert Decimal(receipt.iva_resultado) == Decimal("21.00") - Decimal("10.50")
    assert len(receipt.transaction_ids) == 2
    assert len(receipt.invoice_ids) == 2
    assert receipt.attestation_attachment_id == receipt.attestation_sha256
    assert receipt.calculation_revision_id
    assert receipt.authority_generation
    assert receipt.executable_sha256
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    rendered = str(receipt.to_dict())
    assert "synthetic-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)
