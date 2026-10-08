"""Installed ledger launcher admission and visible child journey stages."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from dev.acceptance.income_tax.installed_tui_child import (
    admitted_session_autopilot,
    installed_product_evidence,
    register_profile_through_installed_tui,
)

from .installed_tui_contracts import _SCHEMA_VERSION, ChildMode, LedgerInstalledTuiError, LedgerTuiChildReceipt
from .installed_tui_controls import (
    _capture_invoice_via_tui,
    _capture_transaction_via_tui,
    _edit_unlinked_transaction,
    _inspect_invoice,
    _inspect_transaction,
    _refuse_linked_transaction_edit,
    _tui_only_transaction_descriptions,
    _update_invoice_notes,
    _write_tui_only_statement,
)


def _run_launcher(*, passphrase: str, drive_after_home: Any) -> None:
    """Run one ordinary installed launch and require a truthful normal exit."""
    from cadrumo.entrypoints.tui.launcher import main

    exit_code = main(
        headless=True,
        auto_pilot=admitted_session_autopilot(passphrase=passphrase, drive_after_home=drive_after_home),
    )
    if exit_code != 0:
        raise LedgerInstalledTuiError("installed Ledger launcher did not exit cleanly")


def _child_receipt(*, workspace_root: Path, mode: ChildMode, observations: tuple[str, ...]) -> LedgerTuiChildReceipt:
    """Build a value-free receipt after public controls have completed."""
    product = installed_product_evidence(workspace_root=workspace_root)
    return LedgerTuiChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        mode=mode,
        product_origin=product.product_origin,
        product_init_sha256=product.product_init_sha256,
        observations=observations,
    )


def _run_tui_only_capture_update_child(
    *,
    workspace_root: Path,
    scratch: Path,
    passphrase: str,
    invoice_number: str,
    initial_notes: str,
    updated_notes: str,
    year: int,
) -> LedgerTuiChildReceipt:
    """Register, capture, inspect, and update through one installed TUI child."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(register_profile_through_installed_tui(profile_label="ledger-tui-only", passphrase=passphrase))

    observations: list[str] = []
    initial_description, updated_description = _tui_only_transaction_descriptions(year)
    statement = _write_tui_only_statement(scratch=scratch, year=year, description=initial_description)

    async def drive(pilot: Any) -> None:
        await _capture_invoice_via_tui(
            pilot,
            invoice_number=invoice_number,
            notes=initial_notes,
            year=year,
        )
        observations.append("invoice_capture")
        await _capture_transaction_via_tui(pilot, statement=statement)
        observations.append("transaction_capture")
        await _update_invoice_notes(
            pilot,
            invoice_number=invoice_number,
            initial_notes=initial_notes,
            updated_notes=updated_notes,
        )
        observations.extend(("invoice_catalogue", "invoice_detail", "invoice_metadata_update"))
        await _edit_unlinked_transaction(
            pilot,
            description=initial_description,
            updated_description=updated_description,
        )
        observations.extend(("transaction_detail", "transaction_edit"))
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    expected_observations = (
        "invoice_capture",
        "transaction_capture",
        "invoice_catalogue",
        "invoice_detail",
        "invoice_metadata_update",
        "transaction_detail",
        "transaction_edit",
    )
    if tuple(observations) != expected_observations:
        raise LedgerInstalledTuiError("installed Ledger capture callback did not complete its public route")
    return _child_receipt(
        workspace_root=workspace_root,
        mode="tui_only_capture_update",
        observations=tuple(observations),
    )


def _run_existing_profile_child(
    *,
    workspace_root: Path,
    passphrase: str,
    mode: ChildMode,
    invoice_number: str,
    initial_notes: str,
    updated_notes: str | None,
    transaction_description: str | None,
    updated_description: str | None,
) -> LedgerTuiChildReceipt:
    """Run one public readback or continuation action against an existing profile."""
    observations: list[str] = []

    async def drive(pilot: Any) -> None:
        if mode == "tui_only_reopen":
            if transaction_description is None:
                raise LedgerInstalledTuiError("TUI-only reopen child is missing its captured transaction description")
            await _inspect_invoice(pilot, invoice_number=invoice_number, expected_notes=initial_notes)
            await _inspect_transaction(pilot, description=transaction_description)
            observations.extend(("fresh_process", "invoice_catalogue", "invoice_detail", "transaction_detail"))
        elif mode == "cli_to_tui":
            if updated_notes is None or transaction_description is None or updated_description is None:
                raise LedgerInstalledTuiError("CLI-to-TUI child is missing its public continuation input")
            await _update_invoice_notes(
                pilot,
                invoice_number=invoice_number,
                initial_notes=initial_notes,
                updated_notes=updated_notes,
            )
            await _edit_unlinked_transaction(
                pilot,
                description=transaction_description,
                updated_description=updated_description,
            )
            observations.extend(("invoice_detail", "invoice_metadata_update", "transaction_detail", "transaction_edit"))
        elif mode == "linked_refusal_readback":
            if transaction_description is None:
                raise LedgerInstalledTuiError("linked refusal child is missing its public transaction description")
            await _inspect_invoice(pilot, invoice_number=invoice_number, expected_notes=initial_notes)
            await _refuse_linked_transaction_edit(pilot, description=transaction_description)
            observations.extend(
                ("invoice_detail", "linked_transaction_detail", "linked_transaction_edit_refusal", "refusal_readback")
            )
        elif mode == "tui_to_cli_reopen":
            await _inspect_invoice(pilot, invoice_number=invoice_number, expected_notes=initial_notes)
            observations.extend(("fresh_process", "invoice_catalogue", "cli_updated_invoice_detail"))
        else:  # pragma: no cover - parser and outer runner constrain this closed mode set
            raise LedgerInstalledTuiError("installed Ledger TUI child received an unsupported existing-profile mode")
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    return _child_receipt(workspace_root=workspace_root, mode=mode, observations=tuple(observations))


def run_installed_tui_child(
    *,
    workspace_root: Path,
    scratch: Path,
    passphrase: str,
    mode: ChildMode,
    invoice_number: str,
    initial_notes: str,
    updated_notes: str | None,
    transaction_description: str | None,
    updated_description: str | None,
    year: int,
) -> LedgerTuiChildReceipt:
    """Dispatch the closed installed-child modes after validating their public inputs."""
    if not all(isinstance(value, str) and value for value in (invoice_number, initial_notes)):
        raise LedgerInstalledTuiError("installed Ledger TUI child requires non-empty public invoice coordinates")
    if mode == "tui_only_capture_update":
        if not isinstance(updated_notes, str) or not updated_notes:
            raise LedgerInstalledTuiError("TUI-only capture child requires updated invoice notes")
        return _run_tui_only_capture_update_child(
            workspace_root=workspace_root,
            scratch=scratch,
            passphrase=passphrase,
            invoice_number=invoice_number,
            initial_notes=initial_notes,
            updated_notes=updated_notes,
            year=year,
        )
    return _run_existing_profile_child(
        workspace_root=workspace_root,
        passphrase=passphrase,
        mode=mode,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=updated_notes,
        transaction_description=transaction_description,
        updated_description=updated_description,
    )
