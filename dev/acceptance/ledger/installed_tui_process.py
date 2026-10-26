"""Bounded installed ledger child launching and receipt admission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from dev.acceptance.income_tax.installed_tui_child import (
    run_installed_tui_child_process,
)

from .installed_tui_contracts import _SCHEMA_VERSION, ChildMode, LedgerInstalledTuiError, LedgerTuiChildReceipt


def _child_receipt_identity_matches(document: dict[str, Any], expected_mode: ChildMode) -> bool:
    """Require the installed public route named by the child launch."""
    return bool(
        document.get("schema_version") == _SCHEMA_VERSION
        and document.get("status") == "proven"
        and document.get("mode") == expected_mode
        and document.get("product_origin") == "site-packages"
    )


def _child_product_digest_matches(document: dict[str, Any]) -> bool:
    """Require the admitted product digest shape without accepting absent identity."""
    return isinstance(document.get("product_init_sha256"), str) and len(document["product_init_sha256"]) == 64


def _child_observations_match(observations: object) -> bool:
    """Require at least one nonempty public observation."""
    return (
        isinstance(observations, list)
        and bool(observations)
        and all(isinstance(value, str) and value for value in observations)
    )


def _parse_child_receipt(path: Path, *, expected_mode: ChildMode) -> LedgerTuiChildReceipt:
    """Read and validate the deliberately value-free child result."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LedgerInstalledTuiError("installed Ledger TUI child receipt is unreadable") from error
    if not isinstance(document, dict):
        raise LedgerInstalledTuiError("installed Ledger TUI child receipt is not an object")
    observations = document.get("observations")
    if (
        not _child_receipt_identity_matches(document, expected_mode)
        or not _child_product_digest_matches(document)
        or not _child_observations_match(observations)
    ):
        raise LedgerInstalledTuiError("installed Ledger TUI child did not prove the expected public route")
    return LedgerTuiChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        mode=expected_mode,
        product_origin="site-packages",
        product_init_sha256=cast("str", document["product_init_sha256"]),
        observations=tuple(cast("list[str]", observations)),
    )


def _run_child(
    *,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    storage_root: Path,
    receipt_path: Path,
    passphrase: str,
    mode: ChildMode,
    year: int,
    invoice_number: str,
    initial_notes: str,
    updated_notes: str | None = None,
    transaction_description: str | None = None,
    updated_description: str | None = None,
    timeout_seconds: int = 900,
) -> LedgerTuiChildReceipt:
    """Run one fresh installed child with secrets delivered only on stdin."""
    arguments = [
        "--workspace-root",
        str(workspace_root),
        "--receipt",
        str(receipt_path),
        "--mode",
        mode,
        "--year",
        str(year),
        "--invoice-number",
        invoice_number,
        "--initial-notes",
        initial_notes,
    ]
    if updated_notes is not None:
        arguments.extend(("--updated-notes", updated_notes))
    if transaction_description is not None:
        arguments.extend(("--transaction-description", transaction_description))
    if updated_description is not None:
        arguments.extend(("--updated-description", updated_description))
    evidence = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=workspace_root,
        child_module="dev.acceptance.ledger.installed_tui_journey",
        child_args=arguments,
        storage_root=storage_root,
        receipt_path=receipt_path,
        passphrase=passphrase,
        authority_root=authority_root,
        timeout_seconds=timeout_seconds,
    )
    if evidence.returncode != 0 or evidence.receipt_status != "proven":
        raise LedgerInstalledTuiError(f"installed Ledger TUI {mode} child did not exit successfully")
    return _parse_child_receipt(receipt_path, expected_mode=mode)
