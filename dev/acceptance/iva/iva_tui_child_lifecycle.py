"""Admitted installed IVA capture and fresh-session reopen child stages."""

from __future__ import annotations

import asyncio
import os
from importlib import metadata
from pathlib import Path
from typing import Any, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    public_surface_diagnostic,
    query_public_selector,
    register_profile_through_installed_tui,
    select_public_data_table_row,
    wait_for_public_selector,
)

from .iva_tui_contracts import (
    _CLASSIFICATION_FIELDS,
    _SCHEMA_VERSION,
    _UNEXERCISED,
    AuthorityIdentity,
    IvaInstalledTuiError,
    _CaptureChildReceipt,
    _ReopenChildReceipt,
)
from .iva_tui_controls import _open_ledger
from .iva_tui_identity import _assert_bundled_authority, _assert_installed_source_modules, _authority_identity
from .iva_tui_import import _classify_transaction, _import_statement, _resolve_imported_transaction_ids
from .iva_tui_scenario import _synthetic_rows, _write_synthetic_statement


def _child_authority() -> AuthorityIdentity:
    """Read the isolated authority root installed by the shared child runner."""
    raw = os.environ.get("CADRUMO_AUTHORITY_ROOT")
    if not raw:
        raise InstalledTuiChildError("installed TUI child has no isolated authority root")
    try:
        return _authority_identity(Path(raw))
    except IvaInstalledTuiError as exc:
        raise InstalledTuiChildError(str(exc)) from exc


def _capture_child(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    scratch: Path,
    year: int,
    expected_manifest_sha256: str,
    expected_modules: tuple[tuple[str, str], ...],
) -> _CaptureChildReceipt:
    """Run all product writes through the installed TUI and no CLI command."""
    product = installed_product_evidence(workspace_root=workspace_root)
    _assert_installed_source_modules(
        expected_manifest_sha256=expected_manifest_sha256,
        expected_modules=expected_modules,
    )
    authority = _child_authority()
    _assert_bundled_authority(authority)
    synthetic_rows = _synthetic_rows(year)
    statement = _write_synthetic_statement(scratch, synthetic_rows)
    transaction_ids: tuple[str, str] | None = None
    classifications = 0

    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition
    from cadrumo.entrypoints.tui.launcher import main

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))

    async def drive(pilot: Any) -> None:
        nonlocal classifications, transaction_ids
        await _import_statement(pilot, statement=statement)
        transaction_ids = await _resolve_imported_transaction_ids(pilot, synthetic_rows)
        for transaction_id, scenario_row in zip(transaction_ids, synthetic_rows, strict=True):
            await _classify_transaction(pilot, transaction_id=transaction_id, scenario_row=scenario_row)
            classifications += 1
        pilot.app.exit()

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive),
    )
    if exit_code != 0 or transaction_ids is None or classifications != 2:
        raise InstalledTuiChildError("installed IVA TUI capture did not complete both public classifications")
    return _CaptureChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        mode="capture",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        package_version=metadata.version("cadrumo"),
        source_manifest_sha256=expected_manifest_sha256,
        source_module_count=len(expected_modules),
        authority_generation=authority.logical_generation,
        authority_descriptor_sha256=authority.descriptor_sha256,
        authority_database_sha256=authority.database_sha256,
        transaction_ids=transaction_ids,
        classification_fields_submitted=_CLASSIFICATION_FIELDS,
        public_control_handles=(
            "#ledger-import-preview-button",
            "#ledger-import-confirm",
            "#ledger-classification-confirm",
        ),
        unexercised=_UNEXERCISED,
    )


def _reopen_child(
    *,
    workspace_root: Path,
    passphrase: str,
    expected_transaction_ids: tuple[str, str],
    expected_manifest_sha256: str,
    expected_modules: tuple[tuple[str, str], ...],
) -> _ReopenChildReceipt:
    """Use a separate installed launcher process to reopen the persisted entries."""
    product = installed_product_evidence(workspace_root=workspace_root)
    _assert_installed_source_modules(
        expected_manifest_sha256=expected_manifest_sha256,
        expected_modules=expected_modules,
    )
    authority = _child_authority()
    _assert_bundled_authority(authority)
    observed: tuple[str, str] | None = None
    reopen_error: InstalledTuiChildError | None = None
    reopen_stage = "launcher_not_entered"

    from textual.widgets import DataTable

    from cadrumo.entrypoints.tui.launcher import main

    async def drive(pilot: Any) -> None:
        nonlocal observed, reopen_error, reopen_stage
        try:
            reopen_stage = "opening_ledger"
            await _open_ledger(pilot)
            reopen_stage = "selecting_entries"
            await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
            reopen_stage = "waiting_for_entries"
            await wait_for_public_selector(pilot, "#ledger-entries", polls=180)
            table = cast(DataTable[str], query_public_selector(pilot, "#ledger-entries", DataTable))
            if table.row_count == 0:
                raise InstalledTuiChildError(
                    "fresh installed TUI Ledger Entries projection was empty after capture",
                    diagnostic=public_surface_diagnostic(pilot),
                )
            found = tuple(
                str(row_key.value) for row_key in table.rows if str(row_key.value) in expected_transaction_ids
            )
            if set(found) != set(expected_transaction_ids):
                raise InstalledTuiChildError(
                    "fresh installed TUI Ledger Entries did not expose both captured identities",
                    diagnostic=public_surface_diagnostic(pilot),
                )
            observed = expected_transaction_ids
            reopen_stage = "entries_reopened"
        except InstalledTuiChildError as error:
            reopen_error = error
        finally:
            pilot.app.exit()

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive),
    )
    if reopen_error is not None:
        raise reopen_error
    if exit_code != 0 or observed != expected_transaction_ids:
        raise InstalledTuiChildError(f"fresh installed TUI reopen ended before completion (stage={reopen_stage})")
    return _ReopenChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        mode="reopen",
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        package_version=metadata.version("cadrumo"),
        source_manifest_sha256=expected_manifest_sha256,
        source_module_count=len(expected_modules),
        authority_generation=authority.logical_generation,
        authority_descriptor_sha256=authority.descriptor_sha256,
        authority_database_sha256=authority.database_sha256,
        observed_transaction_ids=observed,
        public_control_handles=("#ledger-navigation", "#ledger-entries"),
    )
