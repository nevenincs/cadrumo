"""One bounded installed-TUI IVA capture/classification/reopen acceptance test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..installed_tui_capture_reopen import run_installed_tui_capture_reopen

pytestmark = [pytest.mark.integration, pytest.mark.serial, pytest.mark.hex_entrypoint]


def test_installed_tui_captures_classifies_and_reopens_ordinary_iva_rows(tmp_path: Path) -> None:
    """Exercise the real installed Ledger TUI and stop before Modelo 303 work."""
    workspace_root = Path(__file__).resolve().parents[4]
    receipt = run_installed_tui_capture_reopen(
        workspace_root=workspace_root,
        authority_root=workspace_root / ".authority",
        output_root=tmp_path,
    )

    assert receipt.status == "proven"
    assert receipt.partial_acceptance_ids == ("V1", "V2", "V10")
    assert receipt.acceptance_scope == "partial_ledger_capture_classification_reopen"
    assert receipt.product_origin == "site-packages"
    assert len(receipt.package_payload_sha256) == 64
    assert len(receipt.source_manifest_sha256) == 64
    assert len(receipt.authority_generation) == 64
    assert tuple(handle.mode for handle in receipt.child_handles) == ("capture", "reopen")
    assert all(handle.returncode == 0 and handle.receipt_status == "proven" for handle in receipt.child_handles)
    assert receipt.transaction_count == 2
    assert receipt.classification_fields_submitted[-1] == "deduction_fact_kind"
    assert receipt.canonical_fields_read_back == (
        "business_classification",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "iva_category",
    )
    assert receipt.deduction_kind_readback.startswith("not_proven_")
    assert "m303_calculation" in receipt.unexercised
    assert "m303_export" in receipt.unexercised

    rendered = json.dumps(receipt.to_dict(), sort_keys=True)
    assert "profile_passphrase" not in rendered
    assert "IVA TUI sale" not in rendered
    assert "100.00" not in rendered
    assert "10.50" not in rendered
