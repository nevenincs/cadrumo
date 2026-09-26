"""Focused checks for the installed LEDGER-01 TUI acceptance driver."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from dev.acceptance.installed_cli import InstalledCli

from ..installed_tui_journey import (
    LedgerInstalledTuiError,
    _assert_linked_identity_refused,
    _assert_tui_only_cli_oracle,
    _invoice_observation,
    _optional_link_id,
    _parse_child_receipt,
    _require_empty_directory,
    _transaction_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _RefusalCli:
    """Minimal public-command double for the guard-specific refusal assertion."""

    def __init__(self, document: dict[str, object]) -> None:
        self.document = document
        self.commands: list[SimpleNamespace] = []

    def run(self, *_: object, **__: object) -> dict[str, object]:
        self.commands.append(SimpleNamespace(returncode=2))
        return self.document


class _OracleCli:
    """Minimal installed-CLI double that exposes only public JSON envelopes."""

    def __init__(self, documents: list[dict[str, object]]) -> None:
        self.documents = documents
        self.commands: list[SimpleNamespace] = []

    def run(self, *_: object, **kwargs: object) -> dict[str, object]:
        self.commands.append(SimpleNamespace(returncode=0, command=kwargs.get("command")))
        return self.documents.pop(0)


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


def test_linked_identity_refusal_requires_the_public_guard_code_and_message() -> None:
    accepted = _RefusalCli(
        {
            "status": "error",
            "error": {
                "code": "ERROR_TRANSACTION_VALIDATION",
                "message": "linked transaction identity cannot change without updating its invoice link",
            },
        }
    )
    _assert_linked_identity_refused(cast("InstalledCli", accepted), "transaction-1")

    generic = _RefusalCli(
        {
            "status": "error",
            "error": {"code": "ERROR_TRANSACTION_VALIDATION", "message": "a different validation error"},
        }
    )
    with pytest.raises(LedgerInstalledTuiError, match="did not refuse"):
        _assert_linked_identity_refused(cast("InstalledCli", generic), "transaction-1")


def test_optional_link_normalization_does_not_treat_a_blank_identifier_as_a_link() -> None:
    assert _optional_link_id(None, stage="test") is None
    assert _optional_link_id("invoice-1", stage="test") == "invoice-1"
    with pytest.raises(LedgerInstalledTuiError, match="required public identifier"):
        _optional_link_id("", stage="test")


def test_tui_only_cli_oracle_reads_canonical_totals_unlinked_import_and_edit_lineage() -> None:
    cli = _OracleCli(
        [
            {
                "status": "ok",
                "result": {
                    "rows": [
                        {
                            "bucket_id": "bucket-1",
                            "invoice_id": "invoice-1",
                            "invoice_number": "LEDGER-TUI-2025-001",
                            "notes": "ledger-tui-updated",
                            "grand_total": "121.00",
                            "linked_transaction_ids": [],
                        }
                    ]
                },
            },
            {
                "status": "ok",
                "result": {
                    "invoice_id": "invoice-1",
                    "invoice_number": "LEDGER-TUI-2025-001",
                    "notes": "ledger-tui-updated",
                    "base_total": "100.00",
                    "iva_total": "21.00",
                    "grand_total": "121.00",
                    "linked_transaction_ids": [],
                },
            },
            {
                "status": "ok",
                "result": {
                    "rows": [
                        {
                            "transaction_id": "replacement-1",
                            "description": "ledger-tui-import-2025-updated",
                            "amount": "10.00",
                            "direction": "INCOMING",
                            "invoice_id": None,
                        }
                    ]
                },
            },
            {
                "status": "ok",
                "result": {
                    "bucket_id": "bucket-1",
                    "transaction": {
                        "transaction_id": "replacement-1",
                        "description": "ledger-tui-import-2025-updated",
                        "amount": "10.00",
                        "direction": "INCOMING",
                        "invoice_id": None,
                    },
                    "tracking": {"edit_lineage": [{"previous_transaction_id": "original-1"}]},
                },
            },
        ]
    )

    observations = _assert_tui_only_cli_oracle(
        cast("InstalledCli", cli),
        invoice_number="LEDGER-TUI-2025-001",
        updated_notes="ledger-tui-updated",
        updated_description="ledger-tui-import-2025-updated",
    )

    assert observations == (
        "cli_invoice_identity_and_totals",
        "cli_invoice_absent_link",
        "cli_imported_transaction_value_and_direction",
        "cli_imported_transaction_absent_link",
        "cli_post_edit_lineage",
    )
    assert len(cli.commands) == 4
