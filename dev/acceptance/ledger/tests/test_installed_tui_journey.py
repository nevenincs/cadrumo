"""Focused checks for the installed LEDGER-01 TUI acceptance driver."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ..installed_tui_journey import (
    LedgerInstalledTuiError,
    _invoice_observation,
    _parse_child_receipt,
    _require_empty_directory,
    _transaction_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_public_invoice_observation_carries_the_canonical_linked_metadata() -> None:
    observation = _invoice_observation(
        {
            "bucket_id": "bucket-1",
            "invoice_id": "invoice-1",
            "notes": "after",
            "grand_total": "121.00",
            "linked_transaction_ids": ["transaction-b", "transaction-a"],
        },
        stage="test",
    )

    assert observation.bucket_id == "bucket-1"
    assert observation.invoice_id == "invoice-1"
    assert observation.notes == "after"
    assert observation.grand_total == Decimal("121.00")
    assert observation.linked_transaction_ids == ("transaction-a", "transaction-b")


def test_public_transaction_observation_keeps_edit_lineage_for_replacement_identity() -> None:
    observation = _transaction_observation(
        {
            "bucket_id": "bucket-1",
            "transaction": {
                "transaction_id": "replacement",
                "description": "after",
                "amount": "10.00",
                "invoice_id": None,
            },
            "tracking": {"edit_lineage": [{"previous_transaction_id": "original"}]},
        },
        stage="test",
    )

    assert observation.transaction_id == "replacement"
    assert observation.predecessor_ids == ("original",)


def test_child_receipt_requires_installed_origin_and_nonempty_public_observation(tmp_path: Path) -> None:
    receipt = tmp_path / "child.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": "ledger-01-installed-tui-v1",
                "status": "proven",
                "mode": "tui_only_reopen",
                "product_origin": "site-packages",
                "product_init_sha256": "a" * 64,
                "observations": ["fresh_process"],
            }
        ),
        encoding="utf-8",
    )

    parsed = _parse_child_receipt(receipt, expected_mode="tui_only_reopen")

    assert parsed.product_origin == "site-packages"
    assert parsed.observations == ("fresh_process",)


def test_nonempty_acceptance_output_root_refuses_without_touching_prior_evidence(tmp_path: Path) -> None:
    root = tmp_path / "existing-run"
    root.mkdir()
    marker = root / "prior-receipt.json"
    marker.write_text("synthetic", encoding="utf-8")

    with pytest.raises(LedgerInstalledTuiError, match="fresh and empty"):
        _require_empty_directory(root, label="Ledger test output")

    assert marker.read_text(encoding="utf-8") == "synthetic"
