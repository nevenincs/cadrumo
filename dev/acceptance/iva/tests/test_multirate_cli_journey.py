"""Public installed-CLI acceptance for a two-rate issued Modelo 303 invoice."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ..multirate_cli_journey import run_iva_multirate_cli_journey

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_installed_multirate_cli_journey(tmp_path: Path) -> None:
    """One issued invoice preserves 21% and 10% IVA through verification."""
    repository_root = Path(__file__).resolve().parents[4]
    executable = Path(sys.executable).with_name("aeat.exe")
    authority_root = repository_root / ".authority"
    assert executable.is_file(), executable
    assert (authority_root / "authority.current.json").is_file(), authority_root

    receipt = run_iva_multirate_cli_journey(
        executable=executable,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
    )

    assert receipt.acceptance_ids == ("IVA-CLI-MULTIRATE-2025-1T",)
    assert Decimal(receipt.iva_resultado) == Decimal("21.00") + Decimal("5.00") - Decimal("10.50")
    assert len(receipt.transaction_ids) == 3
    assert receipt.issued_invoice_line_rates == ("RATE_21", "RATE_10")
    assert set(receipt.issued_invoice_linked_transaction_ids) == set(receipt.transaction_ids[:2])
    assert [(row.casilla_id, Decimal(row.value)) for row in receipt.rate_observations] == [
        ("iva.repercutido.general", Decimal("21.00")),
        ("iva.repercutido.reducido", Decimal("5.00")),
        ("iva.soportado.interiores", Decimal("10.50")),
    ]
    assert all(row.legal_ref_count > 0 and row.source_ref_count > 0 for row in receipt.rate_observations)
    assert receipt.calculation_revision_id
    assert receipt.verification_report_id
    assert receipt.verification_granted is True
    assert receipt.verification_status
    assert receipt.export_status == "not_attempted_product_software_identity_pending"
    assert receipt.authority_generation
    assert receipt.executable_sha256
    assert receipt.source_identity
    assert receipt.package_identity.startswith("cadrumo==")
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    assert not any(command.argv[1:4] == ("app", "modelo", "export") for command in receipt.commands)
    rendered = str(receipt.to_dict())
    assert "synthetic-multirate-purchase.pdf" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert all(command.returncode == 0 for command in receipt.commands)
