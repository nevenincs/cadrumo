"""Bounded continuation child process and sanitized receipt readback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from .continuation_contracts import InstalledContinuationError, _Direction
from .installed_tui_child import (
    reportable_child_failure_reason,
    run_installed_tui_child_process,
)


def _run_child(
    *,
    direction: _Direction,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    storage_root: Path,
    scratch: Path,
    passphrase: str,
    year: int,
) -> dict[str, object]:
    receipt = scratch / f"{direction}.json"
    evidence = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=workspace_root,
        child_module="dev.acceptance.income_tax.installed_tui_continuations",
        child_args=(
            "--child-direction",
            direction,
            "--workspace-root",
            str(workspace_root),
            "--scratch",
            str(scratch),
            "--year",
            str(year),
            "--receipt",
            str(receipt),
        ),
        storage_root=storage_root,
        authority_root=authority_root,
        receipt_path=receipt,
        passphrase=passphrase,
        timeout_seconds=2400,
    )
    if evidence.returncode != 0 or evidence.receipt_status != "proven":
        reason = reportable_child_failure_reason(receipt)
        if reason is not None:
            raise InstalledContinuationError(f"installed TUI {direction} child: {reason}")
        raise InstalledContinuationError(f"installed TUI {direction} child did not prove its public workflow")
    document = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise InstalledContinuationError("installed TUI continuation receipt is not an object")
    return cast("dict[str, object]", document)
