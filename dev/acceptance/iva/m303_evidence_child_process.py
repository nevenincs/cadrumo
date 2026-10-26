"""Bounded installed M303 child process and sanitized receipt readback."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from dev.acceptance.income_tax.installed_tui_child import (
    run_installed_tui_child_process,
)

from .m303_evidence_contracts import (
    _CHILD_MODULE,
    ChildHandle,
    ChildMode,
    IvaInstalledM303Error,
    ReopenReadback,
    TuiOutcome,
)
from .m303_evidence_projection import _mapping

if TYPE_CHECKING:
    pass


# --------------------------------------------------------------------------- outer driver


def _child(
    *,
    args: argparse.Namespace,
    store: Path,
    passphrase: str,
    mode: ChildMode,
    work_unit_id: str,
    extra: Sequence[str] = (),
) -> tuple[ChildHandle, tuple[TuiOutcome, ...], ReopenReadback | None]:
    receipt_path = args.output_root / f"{store.name}-{mode}.json"
    process = run_installed_tui_child_process(
        python_executable=args.python,
        workspace_root=args.workspace_root,
        child_module=_CHILD_MODULE,
        child_args=(
            *("--child", mode, "--workspace-root", str(args.workspace_root), "--receipt", str(receipt_path)),
            *("--year", str(args.year), "--work-unit-id", work_unit_id, *extra),
        ),
        storage_root=store,
        authority_root=args.authority_root,
        receipt_path=receipt_path,
        passphrase=passphrase,
        timeout_seconds=900,
    )
    document = _mapping(json.loads(receipt_path.read_text(encoding="utf-8")), label=f"{mode} receipt")
    if process.returncode != 0 or process.receipt_status != "proven":
        raise IvaInstalledM303Error(f"installed TUI {mode} child failed: {document.get('error')}")
    if document.get("product_origin") != "site-packages":
        raise IvaInstalledM303Error(f"installed TUI {mode} child did not run the site-packages product")
    outcomes = tuple(
        TuiOutcome(**cast(dict[str, Any], item)) for item in cast(list[object], document.get("outcomes") or [])
    )
    handle = ChildHandle(
        mode=mode,
        returncode=process.returncode,
        receipt_status=process.receipt_status,
        receipt_sha256=process.receipt_sha256,
        stdout_sha256=process.stdout_sha256,
        stderr_sha256=process.stderr_sha256,
    )
    reopen = document.get("reopen")
    readback = ReopenReadback(**cast(dict[str, Any], reopen)) if isinstance(reopen, dict) else None
    return handle, outcomes, readback
