"""Public installed-CLI acceptance for the ordinary 2025/1T IVA path."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ..cli_journey import run_iva_m303_cli_journey

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


# Measured on a quiet host on 2026-09-23: 195 s wheel build and install, then 402 s of fresh-process
# authenticated CLI calls. The budget is about twice that; revisit it when CLI start-up gets faster.
@pytest.mark.timeout(900)
def test_installed_cli_records_product_identity_block_after_verifying_ordinary_2025_m303(
    tmp_path: Path, installed_wheel_aeat: Path
) -> None:
    """The public path records its known export-authority blocker without claiming an export."""
    repository_root = Path(__file__).resolve().parents[4]
    authority_root = repository_root / ".authority"
    assert (authority_root / "authority.current.json").is_file(), authority_root

    receipt = run_iva_m303_cli_journey(
        executable=installed_wheel_aeat,
        authority_root=authority_root,
        storage_root=tmp_path / "secure-store",
        artifact_root=tmp_path / "private-source-artifacts",
        year=2025,
    )

    assert Decimal(receipt.iva_resultado) == Decimal("21.00") - Decimal("10.50")
    assert receipt.filing_year == 2025
    assert len(receipt.transaction_ids) == 2
    assert len(receipt.invoice_ids) == 2
    assert not any("attest-m303-exonerado-390" in command.argv for command in receipt.commands)
    assert not any("--m303-exonerado-390-attachment-id" in command.argv for command in receipt.commands)
    assert receipt.calculation_revision_id
    assert receipt.verification_report_id
    assert receipt.verification_granted is True
    assert receipt.verification_status
    assert receipt.export_status == "verified_export_blocked"
    assert receipt.export_failure_code == "REFUSED_MODELO_EXPORT_PRODUCT_IDENTITY_UNAVAILABLE"
    assert receipt.export_failure_diagnostic is not None
    # The journey itself refuses unless the typed refusal context locates these fields at DP30300 93-96 and 101-109.
    assert '"Versión del Programa"' in receipt.export_failure_diagnostic
    assert '"NIF del desarrollador"' in receipt.export_failure_diagnostic
    assert receipt.export_artifact is None
    assert receipt.export_size is None
    assert receipt.export_sha256 is None
    assert receipt.export_layout_id is None
    assert receipt.export_parser_verdict == "not_run_product_software_identity_pending"
    assert receipt.exported_iva_resultado is None
    assert receipt.local_export_only is None
    assert receipt.authority_generation
    assert receipt.executable_sha256
    assert receipt.purchase_artifact == "<synthetic-purchase-artifact>"
    rendered = str(receipt.to_dict())
    assert "synthetic-purchase.pdf" not in rendered
    assert "m303-2025-1t.fichero-boe" not in rendered
    assert "profile_passphrase" not in rendered
    assert "attachment:" not in rendered
    assert receipt.commands[-1].returncode != 0
    assert all(command.returncode == 0 for command in receipt.commands[:-1])
