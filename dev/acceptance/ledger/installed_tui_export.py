"""Independent installed export parity with public persisted ledger state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from dev.acceptance.installed_cli import InstalledCli

from .installed_tui_cli_transport import _cli_command, _decimal, _result, _text
from .installed_tui_contracts import LedgerInstalledTuiError


def _read_public_export_artifact(output_path: Path, *, stage: str) -> tuple[list[dict[str, Any]], bytes]:
    """Read public export artifact."""
    if not output_path.is_file():
        raise LedgerInstalledTuiError(f"{stage} did not create the public export artifact")
    try:
        export_bytes = output_path.read_bytes()
        export_rows = [json.loads(line) for line in export_bytes.decode("utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LedgerInstalledTuiError(f"{stage} produced an unreadable public export") from error
    if not all(isinstance(row, dict) for row in export_rows):
        raise LedgerInstalledTuiError(f"{stage} produced a non-object public export row")
    return export_rows, export_bytes


def _assert_public_export_rows(rows: list[dict[str, Any]], export_rows: list[dict[str, Any]], *, stage: str) -> None:
    """Public export rows."""
    persisted_by_id = {str(row.get("transaction_id")): row for row in rows}
    exported_by_id = {str(row.get("transaction_id")): row for row in export_rows}
    if set(exported_by_id) != set(persisted_by_id):
        raise LedgerInstalledTuiError(f"{stage} export identities differ from public persisted state")
    for transaction_id, persisted_row in persisted_by_id.items():
        exported_row = exported_by_id[transaction_id]
        # JSONL exports deliberately render an absent optional text link as an
        # empty cell, whereas the public list envelope projects it as null.
        # Normalize only that documented absent-link representation; a linked
        # identifier continues through the exact-string comparison below.
        exported_link = _optional_link_id(
            None if exported_row.get("invoice_id") == "" else exported_row.get("invoice_id"),
            stage=stage,
        )
        persisted_link = _optional_link_id(persisted_row.get("invoice_id"), stage=stage)
        if (
            _decimal(exported_row.get("amount"), stage=stage),
            exported_link,
            exported_row.get("direction"),
        ) != (
            _decimal(persisted_row.get("amount"), stage=stage),
            persisted_link,
            persisted_row.get("direction"),
        ):
            raise LedgerInstalledTuiError(f"{stage} export values or links differ from public persisted state")


def _optional_link_id(value: object, *, stage: str) -> str | None:
    """Project a canonical optional invoice link without accepting other blank identifiers."""
    return None if value is None else _text(value, stage=stage)


def _compare_export(cli: InstalledCli, *, output_path: Path, stage: str) -> tuple[int, str]:
    """Compare the installed JSONL export with public persisted rows and links."""
    persisted = _result(
        _cli_command(cli, ("app", "ledger", "list"), stage=stage, command="ledger.list"),
        stage=stage,
    )
    rows = persisted.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise LedgerInstalledTuiError(f"{stage} did not expose public persisted transaction rows")
    exported = _result(
        _cli_command(
            cli,
            ("app", "ledger", "export", "--output", str(output_path), "--export-format", "jsonl"),
            stage=stage,
            command="ledger.export",
        ),
        stage=stage,
    )
    export_rows, export_bytes = _read_public_export_artifact(output_path, stage=stage)
    if exported.get("row_count") != len(rows) or len(export_rows) != len(rows):
        raise LedgerInstalledTuiError(f"{stage} export row count differs from public persisted state")
    _assert_public_export_rows(rows, export_rows, stage=stage)
    digest = hashlib.sha256(export_bytes).hexdigest()
    if exported.get("sha256") != digest:
        raise LedgerInstalledTuiError(f"{stage} export digest differs from the emitted artifact")
    return len(export_rows), digest
