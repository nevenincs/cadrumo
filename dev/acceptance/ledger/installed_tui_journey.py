"""Installed LEDGER-01 TUI acceptance through the public Ledger workbench.

The driver keeps the product outside the checkout: each Textual child imports
``cadrumo`` from the installed wheel, admits a profile through the ordinary
screens, and uses visible controls, table rows, and command envelopes only.
It deliberately has no persistence or application-service shortcut.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    register_profile_through_installed_tui,
    run_installed_tui_child_process,
    wait_for_public_selector,
)
from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .frontend_contract import (
    InvoiceObservation,
    TransactionObservation,
    assert_invoice_metadata_continuation,
    assert_linked_identity_refusal,
    assert_unlinked_detail_continuation,
)

_SCHEMA_VERSION = "ledger-01-installed-tui-v1"
_YEAR = 2025
_COUNTERPARTY_NIF = "A58818501"
_INVOICE_BASE = Decimal("100.00")
_INVOICE_IVA = Decimal("21.00")
_INVOICE_TOTAL = _INVOICE_BASE + _INVOICE_IVA
_TUI_IMPORTED_TRANSACTION_AMOUNT = Decimal("10.00")
_TUI_IMPORTED_TRANSACTION_DIRECTION = "INCOMING"
_LINKED_IDENTITY_REFUSAL = "linked transaction identity cannot change without updating its invoice link"
_N26_HEADER = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"

type ChildMode = Literal[
    "tui_only_capture_update",
    "tui_only_reopen",
    "cli_to_tui",
    "linked_refusal_readback",
    "tui_to_cli_reopen",
]


class LedgerInstalledTuiError(RuntimeError):
    """Raised when an installed public Ledger journey cannot prove its claim."""


@dataclass(frozen=True, slots=True)
class LedgerTuiChildReceipt:
    """Value-free result from one fresh installed Textual child."""

    schema_version: str
    status: Literal["proven"]
    mode: ChildMode
    product_origin: str
    product_init_sha256: str
    observations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only public route and package evidence."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class LedgerContinuationReceipt:
    """Sanitized evidence for one sequential public-frontend continuation."""

    direction: Literal["cli_to_tui", "tui_to_cli"]
    status: Literal["proven"]
    tui_observations: tuple[str, ...]
    cli_command_count: int
    export_rows: int
    export_sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return an artifact-safe continuation receipt."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class InstalledLedgerTuiReceipt:
    """Value-free result for the installed TUI-only and continuation journeys."""

    schema_version: str
    status: Literal["proven"]
    package_identity: str
    year: int
    product_origin: str
    product_init_sha256: str
    tui_only_observations: tuple[str, ...]
    cli_to_tui: LedgerContinuationReceipt
    tui_to_cli: LedgerContinuationReceipt

    def to_dict(self) -> dict[str, object]:
        """Return the durable acceptance receipt without financial payloads."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class TuiOnlyCliOracleReceipt:
    """Sanitized installed-CLI readback for the independently TUI-written fixture."""

    schema_version: str
    status: Literal["proven"]
    journey: Literal["tui_only_cli_oracle"]
    package_identity: str
    year: int
    product_origin: str
    product_init_sha256: str
    tui_only_observations: tuple[str, ...]
    cli_oracle_observations: tuple[str, ...]
    cli_command_count: int

    def to_dict(self) -> dict[str, object]:
        """Return value-free evidence for the supplemental installed journey."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class _TuiOnlyRun:
    """Private coordinates retained only while an outer journey reads back its own store."""

    receipt: LedgerTuiChildReceipt
    cli_oracle_observations: tuple[str, ...]
    cli_command_count: int


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Create one caller-owned acceptance directory only when it is fresh."""
    if path.exists() and any(path.iterdir()):
        raise LedgerInstalledTuiError(f"{label} must be fresh and empty")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _result(document: dict[str, Any], *, stage: str) -> dict[str, Any]:
    """Return one public CLI result object or name the failed observation stage."""
    result = document.get("result")
    if not isinstance(result, dict):
        raise LedgerInstalledTuiError(f"{stage} did not return a public result object")
    return result


def _cli_command(
    cli: InstalledCli,
    arguments: Sequence[str],
    *,
    stage: str,
    command: str,
    allow_error: bool = False,
) -> dict[str, Any]:
    """Run one public command and retain a value-free failure identity.

    The shared runner deliberately keeps envelopes out of its evidence.  The
    acceptance layer adds the scenario stage plus a static command name and
    its public exit/status so a failed installed journey can be diagnosed
    without retaining identifiers, financial values, or credentials.
    """
    command_count = len(cli.commands)
    try:
        return cli.run(arguments, command=command, allow_error=allow_error)
    except InstalledCliError as error:
        evidence = cli.commands[-1] if len(cli.commands) > command_count else None
        if evidence is None:
            outcome = "no accepted envelope"
        else:
            outcome = f"status={evidence.status}, exit_code={evidence.returncode}"
        raise LedgerInstalledTuiError(f"{stage}: installed CLI {command} failed ({outcome})") from error


def _create_profile(cli: InstalledCli, *, year: int, stage: str) -> None:
    """Create the shared synthetic profile while preserving a safe failure stage."""
    command_count = len(cli.commands)
    try:
        cli.create_profile(year=year)
    except InstalledCliError as error:
        evidence = cli.commands[-1] if len(cli.commands) > command_count else None
        command = evidence.command if evidence is not None else "config.profile"
        outcome = (
            "no accepted envelope" if evidence is None else f"status={evidence.status}, exit_code={evidence.returncode}"
        )
        raise LedgerInstalledTuiError(f"{stage}: installed CLI {command} failed ({outcome})") from error


def _decimal(value: object, *, stage: str) -> Decimal:
    """Parse an observed public monetary value without accepting malformed data."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise LedgerInstalledTuiError(f"{stage} exposed an invalid public monetary value") from error
    if not amount.is_finite():
        raise LedgerInstalledTuiError(f"{stage} exposed a non-finite public monetary value")
    return amount


def _text(value: object, *, stage: str) -> str:
    """Require one non-empty public transport string."""
    if not isinstance(value, str) or not value:
        raise LedgerInstalledTuiError(f"{stage} omitted a required public identifier")
    return value


def _invoice_observation(payload: dict[str, Any], *, stage: str) -> InvoiceObservation:
    """Project a public invoice envelope into the shared continuation contract."""
    links = payload.get("linked_transaction_ids")
    if not isinstance(links, list) or not all(isinstance(link, str) and link for link in links):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid reciprocal invoice links")
    notes = payload.get("notes")
    if not isinstance(notes, str):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid invoice notes")
    return InvoiceObservation(
        bucket_id=_text(payload.get("bucket_id"), stage=stage),
        invoice_id=_text(payload.get("invoice_id"), stage=stage),
        notes=notes,
        grand_total=_decimal(payload.get("grand_total"), stage=stage),
        linked_transaction_ids=tuple(sorted(links)),
    )


def _transaction_observation(payload: dict[str, Any], *, stage: str) -> TransactionObservation:
    """Project a public tracking envelope into the shared continuation contract."""
    transaction = payload.get("transaction")
    tracking = payload.get("tracking")
    if not isinstance(transaction, dict) or not isinstance(tracking, dict):
        raise LedgerInstalledTuiError(f"{stage} did not expose a public transaction tracking result")
    lineage = tracking.get("edit_lineage")
    if not isinstance(lineage, list):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction edit lineage")
    predecessors: list[str] = []
    for entry in lineage:
        if not isinstance(entry, dict):
            raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction edit lineage")
        predecessor = entry.get("previous_transaction_id")
        if not isinstance(predecessor, str) or not predecessor:
            raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction predecessor identity")
        predecessors.append(predecessor)
    invoice_id = transaction.get("invoice_id")
    if invoice_id is not None and (not isinstance(invoice_id, str) or not invoice_id):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction invoice association")
    return TransactionObservation(
        bucket_id=_text(payload.get("bucket_id"), stage=stage),
        transaction_id=_text(transaction.get("transaction_id"), stage=stage),
        description=_text(transaction.get("description"), stage=stage),
        amount=_decimal(transaction.get("amount"), stage=stage),
        invoice_id=invoice_id,
        predecessor_ids=tuple(predecessors),
    )


def _read_invoice(cli: InstalledCli, invoice_id: str, *, stage: str) -> InvoiceObservation:
    """Read one canonical invoice through the installed public CLI."""
    return _invoice_observation(
        _result(
            _cli_command(
                cli,
                ("app", "ledger", "invoice", "view", invoice_id),
                stage=stage,
                command="ledger.invoice.view",
            ),
            stage=stage,
        ),
        stage=stage,
    )


def _read_transaction(cli: InstalledCli, transaction_id: str, *, stage: str) -> TransactionObservation:
    """Read one transaction and its public edit lineage through ``ledger track``."""
    return _transaction_observation(
        _result(
            _cli_command(
                cli,
                ("app", "ledger", "track", transaction_id),
                stage=stage,
                command="ledger.track",
            ),
            stage=stage,
        ),
        stage=stage,
    )


def _find_invoice_by_number(cli: InstalledCli, invoice_number: str, *, stage: str) -> InvoiceObservation:
    """Resolve a public invoice identity only from the canonical list surface."""
    listing = _result(
        _cli_command(
            cli,
            ("app", "ledger", "invoice", "list"),
            stage=stage,
            command="ledger.invoice.list",
        ),
        stage=stage,
    )
    rows = listing.get("rows")
    if not isinstance(rows, list):
        raise LedgerInstalledTuiError(f"{stage} did not expose public invoice rows")
    matches = [row for row in rows if isinstance(row, dict) and row.get("invoice_number") == invoice_number]
    if len(matches) != 1:
        raise LedgerInstalledTuiError(f"{stage} did not expose exactly one matching public invoice")
    return _invoice_observation(cast("dict[str, Any]", matches[0]), stage=stage)


def _assert_tui_only_cli_oracle(
    cli: InstalledCli,
    *,
    invoice_number: str,
    updated_notes: str,
    updated_description: str,
) -> tuple[str, ...]:
    """Read back a TUI-only write through canonical installed JSON commands.

    The child already proves the public import picker, preview, and confirmation.
    The JSON CLI intentionally has no source filename or source-row projection
    for ``ledger track``, so this oracle confines itself to the values and
    lineage the typed JSON surfaces actually expose.
    """
    invoice = _find_invoice_by_number(
        cli,
        invoice_number,
        stage="TUI-only CLI oracle invoice discovery",
    )
    invoice_payload = _result(
        _cli_command(
            cli,
            ("app", "ledger", "invoice", "view", invoice.invoice_id),
            stage="TUI-only CLI oracle invoice readback",
            command="ledger.invoice.view",
        ),
        stage="TUI-only CLI oracle invoice readback",
    )
    if (
        _text(invoice_payload.get("invoice_id"), stage="TUI-only CLI oracle invoice readback") != invoice.invoice_id
        or invoice_payload.get("invoice_number") != invoice_number
        or invoice_payload.get("notes") != updated_notes
    ):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not preserve canonical invoice identity or metadata")
    if (
        _decimal(invoice_payload.get("base_total"), stage="TUI-only CLI oracle invoice readback"),
        _decimal(invoice_payload.get("iva_total"), stage="TUI-only CLI oracle invoice readback"),
        _decimal(invoice_payload.get("grand_total"), stage="TUI-only CLI oracle invoice readback"),
    ) != (_INVOICE_BASE, _INVOICE_IVA, _INVOICE_TOTAL):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not preserve canonical invoice totals")
    if invoice_payload.get("linked_transaction_ids") != []:
        raise LedgerInstalledTuiError("TUI-only CLI oracle invoice unexpectedly acquired a transaction link")

    listing = _result(
        _cli_command(
            cli,
            ("app", "ledger", "list"),
            stage="TUI-only CLI oracle transaction discovery",
            command="ledger.list",
        ),
        stage="TUI-only CLI oracle transaction discovery",
    )
    rows = listing.get("rows")
    if not isinstance(rows, list):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not expose public transaction rows")
    matches = [row for row in rows if isinstance(row, dict) and row.get("description") == updated_description]
    if len(matches) != 1:
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not expose exactly one imported transaction")
    transaction_row = cast("dict[str, Any]", matches[0])
    transaction_id = _text(transaction_row.get("transaction_id"), stage="TUI-only CLI oracle transaction readback")
    if (
        _decimal(transaction_row.get("amount"), stage="TUI-only CLI oracle transaction readback")
        != _TUI_IMPORTED_TRANSACTION_AMOUNT
        or transaction_row.get("direction") != _TUI_IMPORTED_TRANSACTION_DIRECTION
        or transaction_row.get("invoice_id") is not None
    ):
        raise LedgerInstalledTuiError(
            "TUI-only CLI oracle did not preserve imported transaction value, direction, or link"
        )

    tracking_payload = _result(
        _cli_command(
            cli,
            ("app", "ledger", "track", transaction_id),
            stage="TUI-only CLI oracle transaction lineage",
            command="ledger.track",
        ),
        stage="TUI-only CLI oracle transaction lineage",
    )
    tracked = _transaction_observation(tracking_payload, stage="TUI-only CLI oracle transaction lineage")
    transaction = tracking_payload.get("transaction")
    if (
        not isinstance(transaction, dict)
        or tracked.transaction_id != transaction_id
        or tracked.description != updated_description
        or tracked.amount != _TUI_IMPORTED_TRANSACTION_AMOUNT
        or tracked.invoice_id is not None
        or transaction.get("direction") != _TUI_IMPORTED_TRANSACTION_DIRECTION
    ):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not preserve tracked transaction state")
    if not tracked.predecessor_ids or transaction_id in tracked.predecessor_ids:
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not expose supported edit lineage")
    return (
        "cli_invoice_identity_and_totals",
        "cli_invoice_absent_link",
        "cli_imported_transaction_value_and_direction",
        "cli_imported_transaction_absent_link",
        "cli_post_edit_lineage",
    )


def _add_invoice(
    cli: InstalledCli,
    *,
    invoice_number: str,
    notes: str,
    year: int,
    stage: str,
) -> InvoiceObservation:
    """Capture one small issued invoice through the installed public CLI."""
    document = _cli_command(
        cli,
        (
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "issued",
            "--counterparty-name",
            "Ledger acceptance customer",
            "--counterparty-nif",
            _COUNTERPARTY_NIF,
            "--invoice-number",
            invoice_number,
            "--invoice-date",
            f"{year}-03-15",
            "--taxable-base",
            format(_INVOICE_BASE, "f"),
            "--iva-rate",
            "21",
            "--country-code",
            "ES",
            "--iva-category",
            "domestic_general",
            "--notes",
            notes,
        ),
        stage=stage,
        command="ledger.invoice.add",
    )
    return _invoice_observation(_result(document, stage=stage), stage=stage)


def _add_transaction(
    cli: InstalledCli,
    *,
    description: str,
    amount: Decimal,
    idempotency_key: str,
    year: int,
    stage: str,
) -> TransactionObservation:
    """Capture a public unlinked transaction with explicit IVA facts."""
    document = _cli_command(
        cli,
        (
            "app",
            "ledger",
            "add",
            "--date",
            f"{year}-03-18",
            "--amount",
            format(amount, "f"),
            "--direction",
            "INCOMING",
            "--description",
            description,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            format(_INVOICE_BASE, "f"),
            "--iva-rate",
            "0.21",
            "--iva-amount",
            format(_INVOICE_IVA, "f"),
            "--iva-category",
            "domestic_general",
            "--source-jurisdiction",
            "ES",
            "--idempotency-key",
            idempotency_key,
        ),
        stage=stage,
        command="ledger.add",
    )
    result = _result(document, stage=stage)
    return _read_transaction(cli, _text(result.get("transaction_id"), stage=stage), stage=stage)


def _link_transaction(cli: InstalledCli, transaction_id: str, invoice_id: str, *, stage: str) -> None:
    """Link through the public command and require the normal successful envelope."""
    _result(
        _cli_command(
            cli,
            ("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id),
            stage=stage,
            command="ledger.link",
        ),
        stage=stage,
    )


def _assert_linked_identity_refused(cli: InstalledCli, transaction_id: str) -> None:
    """Exercise the public guarded rejection before a TUI readback verifies stability."""
    document = _cli_command(
        cli,
        ("app", "ledger", "update", transaction_id, "--description", "ledger-linked-refusal-attempt"),
        stage="linked identity refusal",
        command="ledger.update",
        allow_error=True,
    )
    error = document.get("error")
    if (
        not cli.commands
        or cli.commands[-1].returncode == 0
        or document.get("status") != "error"
        or not isinstance(error, dict)
        or error.get("code") != "ERROR_TRANSACTION_VALIDATION"
        or error.get("message") != _LINKED_IDENTITY_REFUSAL
    ):
        raise LedgerInstalledTuiError("public linked identity edit did not refuse")


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
    if not output_path.is_file():
        raise LedgerInstalledTuiError(f"{stage} did not create the public export artifact")
    try:
        export_bytes = output_path.read_bytes()
        export_rows = [json.loads(line) for line in export_bytes.decode("utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LedgerInstalledTuiError(f"{stage} produced an unreadable public export") from error
    if not all(isinstance(row, dict) for row in export_rows):
        raise LedgerInstalledTuiError(f"{stage} produced a non-object public export row")
    if exported.get("row_count") != len(rows) or len(export_rows) != len(rows):
        raise LedgerInstalledTuiError(f"{stage} export row count differs from public persisted state")
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
    digest = hashlib.sha256(export_bytes).hexdigest()
    if exported.get("sha256") != digest:
        raise LedgerInstalledTuiError(f"{stage} export digest differs from the emitted artifact")
    return len(export_rows), digest


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
        document.get("schema_version") != _SCHEMA_VERSION
        or document.get("status") != "proven"
        or document.get("mode") != expected_mode
        or document.get("product_origin") != "site-packages"
        or not isinstance(document.get("product_init_sha256"), str)
        or len(cast("str", document["product_init_sha256"])) != 64
        or not isinstance(observations, list)
        or not observations
        or not all(isinstance(value, str) and value for value in observations)
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


async def _activate_button(pilot: Any, selector: str) -> None:
    """Use a focused public button, which also works in the compact test terminal."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    if button.disabled:
        raise LedgerInstalledTuiError(f"installed Ledger TUI exposed disabled action {selector}")
    button.focus()
    await pilot.press("enter")
    await pilot.pause()


async def _open_ledger_destination(pilot: Any) -> None:
    """Enter Ledger through the installed command palette and public destination label."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    label = tr("tui.search.destination.ledger")
    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            options = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = "ledger"
        for index in range(options.option_count):
            hit = getattr(options.get_option_at_index(index), "hit", None)
            if getattr(hit, "text", None) == label:
                options.highlighted = index
                await pilot.press("enter")
                await wait_for_public_selector(pilot, "#ledger-navigation", polls=180)
                return
    raise LedgerInstalledTuiError("installed command palette did not offer Ledger")


async def _select_table_row_by_text(pilot: Any, *, selector: str, expected: str) -> None:
    """Open exactly one visible DataTable row identified by public rendered text."""
    from textual.widgets import DataTable

    await wait_for_public_selector(pilot, selector, polls=180)
    for _ in range(180):
        table = query_public_selector(pilot, selector, DataTable)
        matches = [
            row_key for row_key in table.rows if expected in " ".join(str(cell) for cell in table.get_row(row_key))
        ]
        if len(matches) == 1:
            table.focus()
            table.move_cursor(row=table.get_row_index(matches[0]))
            await pilot.press("enter")
            return
        if len(matches) > 1:
            raise LedgerInstalledTuiError(f"installed Ledger TUI exposed multiple public rows for {selector}")
        await pilot.pause()
    raise LedgerInstalledTuiError(f"installed Ledger TUI did not expose the required public row in {selector}")


async def _open_ledger_overview(pilot: Any) -> None:
    """Route to the public Ledger overview from the root palette."""
    from dev.acceptance.income_tax.installed_tui_child import select_public_data_table_row

    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="overview")
    await wait_for_public_selector(pilot, "#ledger-add-invoice", polls=180)


async def _capture_invoice_via_tui(
    pilot: Any,
    *,
    invoice_number: str,
    notes: str,
    year: int,
) -> None:
    """Persist one invoice through the normal review and confirmation controls."""
    from textual.widgets import Input, Select, Static

    await _open_ledger_overview(pilot)
    await _activate_button(pilot, "#ledger-add-invoice")
    await wait_for_public_selector(pilot, "#ledger-invoice-review", polls=180)
    query_public_selector(pilot, "#ledger-invoice-kind", Select).value = "issued"
    query_public_selector(pilot, "#ledger-invoice-class", Select).value = "ordinaria"
    fields = {
        "#ledger-invoice-counterparty-name": "Ledger acceptance customer",
        "#ledger-invoice-counterparty-nif": _COUNTERPARTY_NIF,
        "#ledger-invoice-country-code": "ES",
        "#ledger-invoice-invoice-number": invoice_number,
        "#ledger-invoice-invoice-date": f"{year}-03-15",
        "#ledger-invoice-taxable-base": format(_INVOICE_BASE, "f"),
        "#ledger-invoice-iva-rate": "21",
        "#ledger-invoice-iva-category": "domestic_general",
        "#ledger-invoice-currency": "EUR",
        "#ledger-invoice-notes": notes,
    }
    for selector, value in fields.items():
        query_public_selector(pilot, selector, Input).value = value
    await _activate_button(pilot, "#ledger-invoice-review")
    await wait_for_public_selector(pilot, "#ledger-invoice-confirm", polls=180)
    await _activate_button(pilot, "#ledger-invoice-confirm")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-again", polls=180)
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal:
        raise LedgerInstalledTuiError("installed invoice form visibly refused persistence")
    await _activate_button(pilot, "#ledger-invoice-again")
    await wait_for_public_selector(pilot, "#ledger-invoice-review", polls=180)
    await pilot.press("escape")
    await wait_for_public_selector(pilot, "#ledger-add-invoice", polls=180)


def _tui_only_transaction_descriptions(year: int) -> tuple[str, str]:
    """Return the distinct visible import label and its supported edited value."""
    return (f"ledger-tui-entry-{year}-initial", f"ledger-tui-entry-{year}-updated")


def _write_tui_only_statement(*, scratch: Path, year: int, description: str) -> Path:
    """Write one transient statement for the public Ledger import form.

    The file is an operator-selected input to the UI, never a persistence
    fixture.  A fresh receipt directory prevents an earlier acceptance run
    from being overwritten.
    """
    scratch.mkdir(parents=True, exist_ok=True)
    statement = scratch / "ledger-tui-only-entry.csv"
    if statement.exists():
        raise LedgerInstalledTuiError("TUI-only transaction input path must be fresh")
    statement.write_text(
        "\n".join(
            (
                _N26_HEADER,
                f"{year}-03-16,Ledger acceptance counterparty,{description},10.00,EUR,ledger-tui-entry-{year}",
                "",
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    return statement


async def _capture_transaction_via_tui(pilot: Any, *, statement: Path) -> None:
    """Persist one transaction through Ledger's visible import review and confirmation flow."""
    from textual.widgets import Button, Input, Select, Static

    from dev.acceptance.income_tax.installed_tui_child import select_public_data_table_row

    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path", polls=180)
    query_public_selector(pilot, "#ledger-import-kind", Select).value = "bank_statement"
    query_public_selector(pilot, "#ledger-import-provider", Select).value = "csv"
    query_public_selector(pilot, "#ledger-import-path", Input).value = str(statement)
    await _activate_button(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm", polls=180)
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    confirm = query_public_selector(pilot, "#ledger-import-confirm", Button)
    if refusal or confirm.disabled:
        raise LedgerInstalledTuiError("installed Ledger transaction import did not reach public confirmation")
    await _activate_button(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError("installed Ledger transaction import visibly refused persistence")
    await _activate_button(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button", polls=180)


async def _open_invoice_detail(pilot: Any, *, invoice_number: str) -> None:
    """Reach a catalogue invoice using its visible number and stable row selection."""
    await _open_ledger_overview(pilot)
    await _activate_button(pilot, "#ledger-open-invoices")
    await _select_table_row_by_text(pilot, selector="#ledger-invoice-catalogue", expected=invoice_number)
    await wait_for_public_selector(pilot, "#ledger-invoice-notes", polls=180)


async def _inspect_invoice(pilot: Any, *, invoice_number: str, expected_notes: str) -> None:
    """Read the canonical detail and require the expected visible metadata."""
    from textual.widgets import Input, Static

    await _open_invoice_detail(pilot, invoice_number=invoice_number)
    details = str(query_public_selector(pilot, "#ledger-record-detail", Static).render())
    if invoice_number not in details:
        raise LedgerInstalledTuiError("installed invoice detail did not retain its visible identity")
    if query_public_selector(pilot, "#ledger-invoice-notes", Input).value != expected_notes:
        raise LedgerInstalledTuiError("installed invoice detail did not retain its visible notes")


async def _update_invoice_notes(
    pilot: Any,
    *,
    invoice_number: str,
    initial_notes: str,
    updated_notes: str,
) -> None:
    """Perform the supported notes-only update and refresh from committed state."""
    from textual.widgets import Button, Input, Static

    await _inspect_invoice(pilot, invoice_number=invoice_number, expected_notes=initial_notes)
    notes = query_public_selector(pilot, "#ledger-invoice-notes", Input)
    notes.value = updated_notes
    await _activate_button(pilot, "#ledger-invoice-edit-review")
    save = query_public_selector(pilot, "#ledger-invoice-edit-save", Button)
    if save.disabled:
        raise LedgerInstalledTuiError("installed invoice detail did not enable its reviewed save action")
    await _activate_button(pilot, "#ledger-invoice-edit-save")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-invoice-notes", polls=180)
    if query_public_selector(pilot, "#ledger-invoice-notes", Input).value != updated_notes:
        raise LedgerInstalledTuiError("installed invoice detail did not refresh the committed notes")
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError("installed invoice detail visibly refused the supported notes update")


async def _open_transaction_detail(pilot: Any, *, description: str) -> None:
    """Reach a transaction through visible Entries selection and its public action button."""
    from dev.acceptance.income_tax.installed_tui_child import select_public_data_table_row

    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await _select_table_row_by_text(pilot, selector="#ledger-entries", expected=description)
    await _activate_button(pilot, "#ledger-open-transaction")
    await wait_for_public_selector(pilot, "#ledger-transaction-description", polls=180)


async def _inspect_transaction(pilot: Any, *, description: str) -> None:
    """Require a public detail readback before testing continuation or refusal stability."""
    from textual.widgets import Input

    await _open_transaction_detail(pilot, description=description)
    if query_public_selector(pilot, "#ledger-transaction-description", Input).value != description:
        raise LedgerInstalledTuiError("installed transaction detail did not retain its visible description")


async def _edit_unlinked_transaction(
    pilot: Any,
    *,
    description: str,
    updated_description: str,
) -> None:
    """Edit one unlinked transaction only through review, save, and refreshed detail."""
    from textual.widgets import Button, Input, Static

    await _inspect_transaction(pilot, description=description)
    query_public_selector(pilot, "#ledger-transaction-description", Input).value = updated_description
    await _activate_button(pilot, "#ledger-transaction-edit-review")
    save = query_public_selector(pilot, "#ledger-transaction-edit-save", Button)
    if save.disabled:
        raise LedgerInstalledTuiError("installed transaction detail did not enable its reviewed save action")
    await _activate_button(pilot, "#ledger-transaction-edit-save")
    await pilot.app.workers.wait_for_complete()
    if query_public_selector(pilot, "#ledger-transaction-description", Input).value != updated_description:
        raise LedgerInstalledTuiError("installed transaction detail did not refresh the committed description")
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError("installed transaction detail visibly refused the supported edit")


async def _refuse_linked_transaction_edit(pilot: Any, *, description: str) -> None:
    """Exercise the public review/save refusal before rereading committed detail."""
    from textual.widgets import Button, Input, Static

    await _inspect_transaction(pilot, description=description)
    query_public_selector(pilot, "#ledger-transaction-description", Input).value = f"{description}-attempted-edit"
    await _activate_button(pilot, "#ledger-transaction-edit-review")
    save = query_public_selector(pilot, "#ledger-transaction-edit-save", Button)
    if save.disabled:
        raise LedgerInstalledTuiError("installed linked transaction detail did not enable its reviewed save action")
    await _activate_button(pilot, "#ledger-transaction-edit-save")
    await pilot.app.workers.wait_for_complete()
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip().casefold()
    if not all(marker in refusal for marker in ("linked transaction identity", "invoice link")):
        raise LedgerInstalledTuiError("installed linked transaction detail did not show the linked-identity refusal")
    await _inspect_transaction(pilot, description=description)


async def _login_existing_profile_through_installed_tui(*, passphrase: str) -> None:
    """Admit an existing profile through its installed public Login screen.

    A fresh child has no active bucket session.  The production launcher keeps
    credential screens out of a headless run, so this generic prelude drives
    the same visible Login controls before the actual launcher owns the Ledger
    journey.  It never reads or writes the secure store directly.
    """
    from textual.widgets import Input

    from cadrumo.application.user_profile.login_interaction import (
        ProfileLoginInventoryState,
        attempt_profile_login,
        observe_profile_login_inventory,
    )
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.login import LoginScreen

    inventory = observe_profile_login_inventory()
    if inventory.state is not ProfileLoginInventoryState.RECOGNIZED:
        raise LedgerInstalledTuiError("installed Ledger Login screen did not recognize the existing profile")
    with bundled_indexed_authority().operation() as operation:
        screen = LoginScreen(
            choices=inventory.choices,
            authenticate=lambda profile_id, secret: attempt_profile_login(
                profile_id,
                secret,
                profile_decode_context=operation.profile_decode_context(),
            ),
            preselected=inventory.preselected_profile_id,
        )
        async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
            await wait_for_public_selector(pilot, "#field-passphrase")
            query_public_selector(pilot, "#field-passphrase", Input).value = passphrase
            await pilot.click("#btn-unlock")
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
    if screen.outcome is None:
        raise LedgerInstalledTuiError("installed Ledger Login screen did not admit the existing profile")


def _admit_existing_profile_for_headless_launcher(*, passphrase: str) -> None:
    """Prepare one fresh process through the generic public credential prelude."""
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(_login_existing_profile_through_installed_tui(passphrase=passphrase))


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

    _admit_existing_profile_for_headless_launcher(passphrase=passphrase)

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


def _run_tui_only(
    *,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
    cli_executable: Path | None = None,
) -> _TuiOnlyRun:
    """Prove capture, detail update, and fresh-process readback using only installed TUI controls."""
    store = _require_empty_directory(output_root / "secure-store", label="TUI-only Ledger store")
    passphrase = secrets.token_urlsafe(32)
    invoice_number = f"LEDGER-TUI-{year}-001"
    initial_notes = "ledger-tui-initial"
    updated_notes = "ledger-tui-updated"
    _initial_description, updated_description = _tui_only_transaction_descriptions(year)
    capture = _run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "capture-update.json",
        passphrase=passphrase,
        mode="tui_only_capture_update",
        year=year,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=updated_notes,
    )
    reopened = _run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "fresh-reopen.json",
        passphrase=passphrase,
        mode="tui_only_reopen",
        year=year,
        invoice_number=invoice_number,
        initial_notes=updated_notes,
        transaction_description=updated_description,
    )
    if capture.product_init_sha256 != reopened.product_init_sha256:
        raise LedgerInstalledTuiError("TUI-only fresh child imported a different installed product")
    receipt = LedgerTuiChildReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        mode="tui_only_reopen",
        product_origin="site-packages",
        product_init_sha256=capture.product_init_sha256,
        observations=(*capture.observations, *reopened.observations),
    )
    if cli_executable is None:
        return _TuiOnlyRun(receipt=receipt, cli_oracle_observations=(), cli_command_count=0)
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    return _TuiOnlyRun(
        receipt=receipt,
        cli_oracle_observations=_assert_tui_only_cli_oracle(
            cli,
            invoice_number=invoice_number,
            updated_notes=updated_notes,
            updated_description=updated_description,
        ),
        cli_command_count=len(cli.commands),
    )


def _run_cli_to_tui(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
) -> tuple[LedgerContinuationReceipt, LedgerTuiChildReceipt]:
    """Continue public CLI capture through TUI edits, refusal readback, and export parity."""
    store = _require_empty_directory(output_root / "secure-store", label="CLI-to-TUI Ledger store")
    passphrase = secrets.token_urlsafe(32)
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    _create_profile(cli, year=year, stage="CLI-to-TUI profile creation")
    invoice_number = f"LEDGER-CLI-TUI-{year}-001"
    initial_notes = "ledger-cli-initial"
    updated_notes = "ledger-tui-followup"
    invoice = _add_invoice(
        cli,
        invoice_number=invoice_number,
        notes=initial_notes,
        year=year,
        stage="CLI-to-TUI invoice capture",
    )
    linked_description = "ledger-linked-refusal-row"
    linked = _add_transaction(
        cli,
        description=linked_description,
        amount=_INVOICE_TOTAL,
        idempotency_key="ledger-cli-tui-linked",
        year=year,
        stage="CLI-to-TUI linked transaction capture",
    )
    _link_transaction(cli, linked.transaction_id, invoice.invoice_id, stage="CLI-to-TUI public link")
    unlinked_description = "ledger-unlinked-detail-row"
    unlinked = _add_transaction(
        cli,
        description=unlinked_description,
        amount=_INVOICE_TOTAL,
        idempotency_key="ledger-cli-tui-unlinked",
        year=year,
        stage="CLI-to-TUI unlinked transaction capture",
    )
    before_invoice = _read_invoice(cli, invoice.invoice_id, stage="CLI-to-TUI invoice before TUI edit")
    before_unlinked = _read_transaction(cli, unlinked.transaction_id, stage="CLI-to-TUI transaction before TUI edit")
    edited_description = "ledger-unlinked-detail-updated"
    continuation_child = _run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "tui-continuation.json",
        passphrase=passphrase,
        mode="cli_to_tui",
        year=year,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=updated_notes,
        transaction_description=unlinked_description,
        updated_description=edited_description,
    )
    after_invoice = _read_invoice(cli, invoice.invoice_id, stage="CLI-to-TUI invoice after TUI edit")
    after_unlinked = _read_transaction(cli, unlinked.transaction_id, stage="CLI-to-TUI transaction after TUI edit")
    assert_invoice_metadata_continuation(before_invoice, after_invoice, expected_notes=updated_notes)
    assert_unlinked_detail_continuation(before_unlinked, after_unlinked, expected_description=edited_description)

    before_linked_invoice = _read_invoice(cli, invoice.invoice_id, stage="linked refusal invoice before")
    before_linked_transaction = _read_transaction(cli, linked.transaction_id, stage="linked refusal transaction before")
    _assert_linked_identity_refused(cli, linked.transaction_id)
    refusal_child = _run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "linked-refusal-readback.json",
        passphrase=passphrase,
        mode="linked_refusal_readback",
        year=year,
        invoice_number=invoice_number,
        initial_notes=updated_notes,
        transaction_description=linked_description,
    )
    after_linked_invoice = _read_invoice(cli, invoice.invoice_id, stage="linked refusal invoice after")
    after_linked_transaction = _read_transaction(cli, linked.transaction_id, stage="linked refusal transaction after")
    assert_linked_identity_refusal(
        before_linked_invoice,
        after_linked_invoice,
        before_linked_transaction,
        after_linked_transaction,
    )
    export_rows, export_sha256 = _compare_export(
        cli,
        output_path=output_root / "ledger.jsonl",
        stage="CLI-to-TUI export comparison",
    )
    return (
        LedgerContinuationReceipt(
            direction="cli_to_tui",
            status="proven",
            tui_observations=(*continuation_child.observations, *refusal_child.observations),
            cli_command_count=len(cli.commands),
            export_rows=export_rows,
            export_sha256=export_sha256,
        ),
        continuation_child,
    )


def _run_tui_to_cli(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
) -> tuple[LedgerContinuationReceipt, LedgerTuiChildReceipt]:
    """Continue installed TUI capture through CLI metadata update and a new TUI readback."""
    store = _require_empty_directory(output_root / "secure-store", label="TUI-to-CLI Ledger store")
    passphrase = secrets.token_urlsafe(32)
    invoice_number = f"LEDGER-TUI-CLI-{year}-001"
    initial_notes = "ledger-tui-origin"
    tui_updated_notes = "ledger-tui-captured"
    cli_updated_notes = "ledger-cli-followup"
    capture_child = _run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "tui-capture.json",
        passphrase=passphrase,
        mode="tui_only_capture_update",
        year=year,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=tui_updated_notes,
    )
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    before_invoice = _find_invoice_by_number(cli, invoice_number, stage="TUI-to-CLI public invoice discovery")
    if before_invoice.notes != tui_updated_notes:
        raise LedgerInstalledTuiError("TUI-to-CLI capture did not commit its visible invoice metadata update")
    _result(
        _cli_command(
            cli,
            ("app", "ledger", "invoice", "update", before_invoice.invoice_id, "--notes", cli_updated_notes),
            stage="TUI-to-CLI public invoice update",
            command="ledger.invoice.update",
        ),
        stage="TUI-to-CLI public invoice update",
    )
    after_invoice = _read_invoice(cli, before_invoice.invoice_id, stage="TUI-to-CLI invoice after CLI edit")
    assert_invoice_metadata_continuation(before_invoice, after_invoice, expected_notes=cli_updated_notes)
    linked = _add_transaction(
        cli,
        description="ledger-tui-cli-linked-export-row",
        amount=_INVOICE_TOTAL,
        idempotency_key="ledger-tui-cli-linked",
        year=year,
        stage="TUI-to-CLI linked transaction capture",
    )
    _link_transaction(cli, linked.transaction_id, before_invoice.invoice_id, stage="TUI-to-CLI public link")
    export_rows, export_sha256 = _compare_export(
        cli,
        output_path=output_root / "ledger.jsonl",
        stage="TUI-to-CLI export comparison",
    )
    reopen_child = _run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "tui-reopen.json",
        passphrase=passphrase,
        mode="tui_to_cli_reopen",
        year=year,
        invoice_number=invoice_number,
        initial_notes=cli_updated_notes,
    )
    if capture_child.product_init_sha256 != reopen_child.product_init_sha256:
        raise LedgerInstalledTuiError("TUI-to-CLI children imported different installed product identities")
    return (
        LedgerContinuationReceipt(
            direction="tui_to_cli",
            status="proven",
            tui_observations=(*capture_child.observations, *reopen_child.observations),
            cli_command_count=len(cli.commands),
            export_rows=export_rows,
            export_sha256=export_sha256,
        ),
        capture_child,
    )


def run_installed_ledger_tui_journey(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    package_identity: str,
    year: int = _YEAR,
) -> InstalledLedgerTuiReceipt:
    """Run installed TUI-only and both direction continuations against fresh secure stores."""
    workspace = workspace_root.resolve(strict=True)
    authority = authority_root.resolve(strict=True)
    cli = cli_executable.resolve(strict=True)
    python = python_executable.resolve(strict=True)
    if cli.parent != python.parent:
        raise LedgerInstalledTuiError("installed CLI and TUI child Python do not belong to one environment")
    if not package_identity.startswith("wheel_sha256:") or len(package_identity.removeprefix("wheel_sha256:")) != 64:
        raise LedgerInstalledTuiError("installed Ledger journey requires the exact built wheel identity")
    root = _require_empty_directory(output_root, label="LEDGER installed-TUI output root")
    tui_only_run = _run_tui_only(
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "tui-only", label="TUI-only Ledger output root"),
        year=year,
    )
    cli_to_tui, cli_to_tui_child = _run_cli_to_tui(
        cli_executable=cli,
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "cli-to-tui", label="CLI-to-TUI Ledger output root"),
        year=year,
    )
    tui_to_cli, tui_to_cli_child = _run_tui_to_cli(
        cli_executable=cli,
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "tui-to-cli", label="TUI-to-CLI Ledger output root"),
        year=year,
    )
    product_hashes = {
        tui_only_run.receipt.product_init_sha256,
        cli_to_tui_child.product_init_sha256,
        tui_to_cli_child.product_init_sha256,
    }
    if len(product_hashes) != 1:
        raise LedgerInstalledTuiError("installed Ledger journeys used different product package identities")
    return InstalledLedgerTuiReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        package_identity=package_identity,
        year=year,
        product_origin="site-packages",
        product_init_sha256=product_hashes.pop(),
        tui_only_observations=tui_only_run.receipt.observations,
        cli_to_tui=cli_to_tui,
        tui_to_cli=tui_to_cli,
    )


def run_installed_tui_only_cli_oracle(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    package_identity: str,
    year: int = _YEAR,
) -> TuiOnlyCliOracleReceipt:
    """Run only the independent TUI path plus read-only installed CLI proof."""
    workspace = workspace_root.resolve(strict=True)
    authority = authority_root.resolve(strict=True)
    cli = cli_executable.resolve(strict=True)
    python = python_executable.resolve(strict=True)
    if cli.parent != python.parent:
        raise LedgerInstalledTuiError("installed CLI and TUI child Python do not belong to one environment")
    if not package_identity.startswith("wheel_sha256:") or len(package_identity.removeprefix("wheel_sha256:")) != 64:
        raise LedgerInstalledTuiError("installed Ledger journey requires the exact built wheel identity")
    root = _require_empty_directory(output_root, label="LEDGER supplemental installed-TUI output root")
    tui_only = _run_tui_only(
        python_executable=python,
        workspace_root=workspace,
        authority_root=authority,
        output_root=_require_empty_directory(root / "tui-only", label="supplemental TUI-only Ledger output root"),
        year=year,
        cli_executable=cli,
    )
    if not tui_only.cli_oracle_observations:
        raise LedgerInstalledTuiError("supplemental TUI-only CLI oracle recorded no public observations")
    return TuiOnlyCliOracleReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        journey="tui_only_cli_oracle",
        package_identity=package_identity,
        year=year,
        product_origin="site-packages",
        product_init_sha256=tui_only.receipt.product_init_sha256,
        tui_only_observations=tui_only.receipt.observations,
        cli_oracle_observations=tui_only.cli_oracle_observations,
        cli_command_count=tui_only.cli_command_count,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--package-identity")
    parser.add_argument("--supplemental-tui-only", action="store_true")
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--year", type=int, default=_YEAR)
    parser.add_argument(
        "--mode",
        choices=(
            "tui_only_capture_update",
            "tui_only_reopen",
            "cli_to_tui",
            "linked_refusal_readback",
            "tui_to_cli_reopen",
        ),
    )
    parser.add_argument("--invoice-number")
    parser.add_argument("--initial-notes")
    parser.add_argument("--updated-notes")
    parser.add_argument("--transaction-description")
    parser.add_argument("--updated-description")
    return parser


def _write_receipt(path: Path, document: dict[str, object]) -> None:
    """Write one JSON receipt after its caller has reduced it to safe evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run an installed outer journey or one stdin-credentialed installed TUI child."""
    args = _parser().parse_args(argv)
    try:
        if args.mode is not None:
            if args.supplemental_tui_only or any(
                value is not None for value in (args.output_root, args.cli, args.python, args.authority_root)
            ):
                raise LedgerInstalledTuiError("installed Ledger TUI child received outer-only arguments")
            receipt = run_installed_tui_child(
                workspace_root=args.workspace_root,
                scratch=args.receipt.parent,
                passphrase=read_passphrase_from_stdin(),
                mode=cast("ChildMode", args.mode),
                invoice_number=cast("str", args.invoice_number),
                initial_notes=cast("str", args.initial_notes),
                updated_notes=args.updated_notes,
                transaction_description=args.transaction_description,
                updated_description=args.updated_description,
                year=args.year,
            )
            _write_receipt(args.receipt, receipt.to_dict())
            return 0
        if None in (args.cli, args.python, args.authority_root, args.output_root, args.package_identity):
            raise LedgerInstalledTuiError(
                "installed Ledger outer journey requires CLI, Python, authority, output and wheel identity"
            )
        if args.supplemental_tui_only:
            receipt = run_installed_tui_only_cli_oracle(
                cli_executable=args.cli,
                python_executable=args.python,
                workspace_root=args.workspace_root,
                authority_root=args.authority_root,
                output_root=args.output_root,
                package_identity=args.package_identity,
                year=args.year,
            )
        else:
            receipt = run_installed_ledger_tui_journey(
                cli_executable=args.cli,
                python_executable=args.python,
                workspace_root=args.workspace_root,
                authority_root=args.authority_root,
                output_root=args.output_root,
                package_identity=args.package_identity,
                year=args.year,
            )
        _write_receipt(args.receipt, receipt.to_dict())
        return 0
    except (LedgerInstalledTuiError, InstalledTuiChildError, InstalledCliError) as error:
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA_VERSION,
                "status": "failed",
                "error_type": type(error).__name__,
                "diagnostic": (
                    str(error) if isinstance(error, LedgerInstalledTuiError) else "installed frontend or command failed"
                ),
            },
        )
        return 2
    except Exception as error:
        _write_receipt(
            args.receipt,
            {
                "schema_version": _SCHEMA_VERSION,
                "status": "failed",
                "error_type": type(error).__name__,
                "diagnostic": "unexpected installed Ledger journey failure",
            },
        )
        return 2


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())


__all__ = [
    "InstalledLedgerTuiReceipt",
    "LedgerContinuationReceipt",
    "LedgerInstalledTuiError",
    "LedgerTuiChildReceipt",
    "TuiOnlyCliOracleReceipt",
    "main",
    "run_installed_ledger_tui_journey",
    "run_installed_tui_child",
    "run_installed_tui_only_cli_oracle",
]
