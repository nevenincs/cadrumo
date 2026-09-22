"""Installed TUI IVA capture, classification, and fresh-session reopen proof.

The bounded journey deliberately stops at persisted Ledger facts.  It does not
create a Modelo 303 work unit, attest, calculate, verify, or export.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from importlib import metadata, resources
from pathlib import Path
from typing import Any, Final, Literal, cast

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admitted_session_autopilot,
    installed_product_evidence,
    public_surface_diagnostic,
    query_public_selector,
    read_passphrase_from_stdin,
    register_profile_through_installed_tui,
    run_installed_tui_child_process,
    select_public_data_table_row,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)

_SCHEMA_VERSION: Final = "iva-01-installed-tui-capture-reopen-v1"
_N26_HEADER: Final = "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID"
_SOURCE_MODULES: Final[tuple[tuple[str, str], ...]] = (
    ("cadrumo.application.ledger.actions_manual", "src/cadrumo/application/ledger/actions_manual.py"),
    ("cadrumo.entrypoints.tui.launcher", "src/cadrumo/entrypoints/tui/launcher.py"),
    ("cadrumo.entrypoints.tui.ledger.classification", "src/cadrumo/entrypoints/tui/ledger/classification.py"),
    ("cadrumo.entrypoints.tui.ledger.entries", "src/cadrumo/entrypoints/tui/ledger/entries.py"),
    ("cadrumo.entrypoints.tui.ledger.import_flow", "src/cadrumo/entrypoints/tui/ledger/import_flow.py"),
    ("cadrumo.entrypoints.tui.ledger_doors", "src/cadrumo/entrypoints/tui/ledger_doors.py"),
)
_CLASSIFICATION_FIELDS: Final[tuple[str, ...]] = (
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "deduction_fact_kind",
)
_UNEXERCISED: Final[tuple[str, ...]] = (
    "invoice_capture_or_link",
    "m303_secure_attestation",
    "m303_work_creation",
    "m303_calculation",
    "m303_verification",
    "m303_export",
)


class IvaInstalledTuiError(RuntimeError):
    """Raised when the bounded installed IVA evidence cannot be proven."""


@dataclass(frozen=True, slots=True)
class _SyntheticIvaRow:
    """One transient ordinary IVA input row, used by every journey assertion."""

    entry_date: str
    counterparty: str
    payment_reference: str
    signed_amount: str
    taxable_base: str
    iva_amount: str
    deduction_fact_kind: str


_SYNTHETIC_ROWS: Final[tuple[_SyntheticIvaRow, _SyntheticIvaRow]] = (
    _SyntheticIvaRow(
        entry_date="2025-02-15",
        counterparty="IVA TUI sale",
        payment_reference="iva-tui-sale",
        signed_amount="121.00",
        taxable_base="100.00",
        iva_amount="21.00",
        deduction_fact_kind="",
    ),
    _SyntheticIvaRow(
        entry_date="2025-02-18",
        counterparty="IVA TUI purchase",
        payment_reference="iva-tui-purchase",
        signed_amount="-60.50",
        taxable_base="50.00",
        iva_amount="10.50",
        deduction_fact_kind="domestic_current",
    ),
)


@dataclass(frozen=True, slots=True)
class AuthorityIdentity:
    """The published authority pair selected for this isolated run."""

    logical_generation: str
    descriptor_sha256: str
    database_sha256: str


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """A digest of the TUI source members that must be in the built wheel."""

    manifest_sha256: str
    module_sha256s: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ChildHandle:
    """Value-free handle for one fresh installed TUI child process."""

    mode: Literal["capture", "reopen"]
    returncode: int
    receipt_status: str
    receipt_sha256: str
    stdout_sha256: str
    stderr_sha256: str


@dataclass(frozen=True, slots=True)
class InstalledIvaTuiReceipt:
    """Sanitized evidence for the deliberately limited IVA acceptance slice."""

    schema_version: str
    status: Literal["proven"]
    partial_acceptance_ids: tuple[str, ...]
    acceptance_scope: Literal["partial_ledger_capture_classification_reopen"]
    tui_only_path: str
    continuation_path: str
    product_origin: str
    product_init_sha256: str
    package_version: str
    package_payload_sha256: str
    source_manifest_sha256: str
    source_module_count: int
    authority_generation: str
    authority_descriptor_sha256: str
    authority_database_sha256: str
    child_handles: tuple[ChildHandle, ChildHandle]
    transaction_count: int
    classification_fields_submitted: tuple[str, ...]
    canonical_fields_read_back: tuple[str, ...]
    canonical_classification_fingerprint: str
    continuation_command_handles: tuple[str, ...]
    deduction_kind_readback: str
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return only identity, control, and digest evidence."""
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class _CaptureChildReceipt:
    """Value-free capture-child receipt passed to the outer driver."""

    schema_version: str
    status: Literal["proven"]
    mode: Literal["capture"]
    product_origin: str
    product_init_sha256: str
    package_version: str
    source_manifest_sha256: str
    source_module_count: int
    authority_generation: str
    authority_descriptor_sha256: str
    authority_database_sha256: str
    transaction_ids: tuple[str, str]
    classification_fields_submitted: tuple[str, ...]
    public_control_handles: tuple[str, ...]
    unexercised: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


@dataclass(frozen=True, slots=True)
class _ReopenChildReceipt:
    """Value-free fresh-TUI-session receipt passed to the outer driver."""

    schema_version: str
    status: Literal["proven"]
    mode: Literal["reopen"]
    product_origin: str
    product_init_sha256: str
    package_version: str
    source_manifest_sha256: str
    source_module_count: int
    authority_generation: str
    authority_descriptor_sha256: str
    authority_database_sha256: str
    observed_transaction_ids: tuple[str, str]
    public_control_handles: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


def _sha256(data: bytes) -> str:
    """Return a stable SHA-256 digest without retaining the source bytes."""
    return hashlib.sha256(data).hexdigest()


def _canonical_ledger_decimal_text(value: str) -> str:
    """Render independent expected fixed-point text for the public Ledger view."""
    return format(Decimal(value).normalize(), "f")


def _source_identity(workspace_root: Path) -> SourceIdentity:
    """Hash the exact critical source members before the supported wheel build."""
    root = workspace_root.resolve(strict=True)
    rows: list[tuple[str, str]] = []
    for module_name, relative_path in _SOURCE_MODULES:
        source = root / relative_path
        if not source.is_file():
            raise IvaInstalledTuiError("critical installed-TUI source member is absent")
        rows.append((module_name, _sha256(source.read_bytes())))
    payload = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return SourceIdentity(manifest_sha256=_sha256(payload), module_sha256s=tuple(rows))


def _authority_identity(authority_root: Path) -> AuthorityIdentity:
    """Read and verify the one published authority pair supplied to the run."""
    root = authority_root.resolve(strict=True)
    descriptor_path = root / "authority.current.json"
    if not descriptor_path.is_file():
        raise IvaInstalledTuiError("authority root has no published current descriptor")
    descriptor_bytes = descriptor_path.read_bytes()
    try:
        descriptor = json.loads(descriptor_bytes)
    except json.JSONDecodeError as exc:
        raise IvaInstalledTuiError("authority descriptor is not valid JSON") from exc
    if not isinstance(descriptor, dict):
        raise IvaInstalledTuiError("authority descriptor is not an object")
    generation = descriptor.get("logical_generation")
    database = descriptor.get("database")
    database_sha256 = descriptor.get("database_sha256")
    if not all(isinstance(value, str) and value for value in (generation, database, database_sha256)):
        raise IvaInstalledTuiError("authority descriptor is missing its published identity values")
    database_path = (root / database).resolve()
    if database_path.parent != root or not database_path.is_file():
        raise IvaInstalledTuiError("authority descriptor names an invalid database member")
    if _sha256(database_path.read_bytes()) != database_sha256:
        raise IvaInstalledTuiError("authority database bytes do not match the descriptor digest")
    return AuthorityIdentity(
        logical_generation=generation,
        descriptor_sha256=_sha256(descriptor_bytes),
        database_sha256=database_sha256,
    )


def _assert_bundled_authority(expected: AuthorityIdentity) -> None:
    """Require the installed wheel to carry the same descriptor and database."""
    authority = resources.files("cadrumo").joinpath("_data", "registry", "authority")
    descriptor_resource = authority.joinpath("authority.current.json")
    try:
        descriptor_bytes = descriptor_resource.read_bytes()
        descriptor = json.loads(descriptor_bytes)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise InstalledTuiChildError("installed wheel has no readable bundled authority descriptor") from exc
    if not isinstance(descriptor, dict):
        raise InstalledTuiChildError("installed wheel authority descriptor is not an object")
    database = descriptor.get("database")
    if not isinstance(database, str) or not database:
        raise InstalledTuiChildError("installed wheel authority descriptor has no database member")
    if _sha256(descriptor_bytes) != expected.descriptor_sha256:
        raise InstalledTuiChildError("installed wheel authority descriptor differs from the supplied authority")
    try:
        database_bytes = authority.joinpath(database).read_bytes()
    except FileNotFoundError as exc:
        raise InstalledTuiChildError("installed wheel omits the descriptor-selected authority database") from exc
    if _sha256(database_bytes) != expected.database_sha256:
        raise InstalledTuiChildError("installed wheel authority database differs from the supplied authority")


def _module_hash_arguments(source: SourceIdentity) -> tuple[str, ...]:
    """Render only module names and digests for the isolated child process."""
    arguments: list[str] = []
    for module_name, digest in source.module_sha256s:
        arguments.extend(("--source-module", f"{module_name}={digest}"))
    return tuple(arguments)


def _parse_module_hashes(items: Sequence[str]) -> tuple[tuple[str, str], ...]:
    """Validate source-module attestations passed by the parent driver."""
    parsed: list[tuple[str, str]] = []
    for item in items:
        module_name, separator, digest = item.partition("=")
        if not separator or not module_name or len(digest) != 64:
            raise InstalledTuiChildError("installed TUI child received an invalid source-module attestation")
        parsed.append((module_name, digest))
    if not parsed or len({module for module, _ in parsed}) != len(parsed):
        raise InstalledTuiChildError("installed TUI child received duplicate or empty source-module attestations")
    return tuple(sorted(parsed))


def _assert_installed_source_modules(
    *, expected_manifest_sha256: str, expected_modules: tuple[tuple[str, str], ...]
) -> None:
    """Prove critical imports came from the installed distribution bytes."""
    distribution_root = Path(str(metadata.distribution("cadrumo").locate_file(""))).resolve(strict=True)
    actual: list[tuple[str, str]] = []
    for module_name, expected_digest in expected_modules:
        module = importlib.import_module(module_name)
        module_file = getattr(module, "__file__", None)
        if not isinstance(module_file, str):
            raise InstalledTuiChildError("critical installed-TUI module has no file origin")
        origin = Path(module_file).resolve(strict=True)
        if not origin.is_relative_to(distribution_root):
            raise InstalledTuiChildError("critical installed-TUI module escaped the installed distribution")
        actual_digest = _sha256(origin.read_bytes())
        if actual_digest != expected_digest:
            raise InstalledTuiChildError("installed wheel source member differs from the source selected for this run")
        actual.append((module_name, actual_digest))
    payload = json.dumps(actual, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if _sha256(payload) != expected_manifest_sha256:
        raise InstalledTuiChildError("installed critical-source manifest differs from the parent attestation")


async def _open_ledger(pilot: Any) -> None:
    """Reach Ledger through the normal installed command-palette interaction."""
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    destination_label = tr("tui.search.destination.ledger")
    await pilot.press("ctrl+p")
    await pilot.pause()
    pilot.app.screen.query_one(Input).value = "ledger"
    for _ in range(180):
        options = pilot.app.screen.query_one(OptionList)
        for index in range(options.option_count):
            option = options.get_option_at_index(index)
            if getattr(getattr(option, "hit", None), "text", None) == destination_label:
                options.highlighted = index
                await pilot.press("enter")
                await wait_for_public_selector(pilot, "#ledger-navigation", polls=180)
                return
        await pilot.pause()
    raise InstalledTuiChildError(
        "installed command palette did not offer the Ledger destination",
        diagnostic=public_surface_diagnostic(pilot),
    )


async def _activate(pilot: Any, selector: str) -> None:
    """Activate a visible public button without a coordinate-dependent click."""
    from textual.widgets import Button

    button = query_public_selector(pilot, selector, Button)
    button.focus()
    await pilot.press("enter")


def _visible_text(widget: Any) -> str:
    """Read an already-rendered public status line, never a persistence object."""
    return str(widget.render()).strip()


def _write_synthetic_statement(scratch: Path) -> Path:
    """Create the private, transient two-row synthetic bank statement."""
    scratch.mkdir(parents=True, exist_ok=True)
    statement = scratch / "iva-installed-tui.csv"
    rows = [_N26_HEADER]
    for item in _SYNTHETIC_ROWS:
        rows.append(
            ",".join(
                (
                    item.entry_date,
                    item.counterparty,
                    item.payment_reference,
                    item.signed_amount,
                    "EUR",
                    item.payment_reference,
                )
            )
        )
    statement.write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return statement


async def _import_statement(pilot: Any, *, statement: Path) -> None:
    """Persist the transient statement through visible import preview/confirm controls."""
    from textual.widgets import Button, Input, Select, Static

    await _open_ledger(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path", polls=180)
    cast(Select[str], query_public_selector(pilot, "#ledger-import-kind", Select)).value = "bank_statement"
    cast(Select[str], query_public_selector(pilot, "#ledger-import-provider", Select)).value = "csv"
    query_public_selector(pilot, "#ledger-import-path", Input).value = str(statement)
    await _activate(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm", polls=180)
    refusal = _visible_text(query_public_selector(pilot, "#ledger-refusal", Static))
    confirm = query_public_selector(pilot, "#ledger-import-confirm", Button)
    if refusal or confirm.disabled:
        raise InstalledTuiChildError("installed Ledger import preview did not reach its visible confirmation state")
    await _activate(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    refusal = _visible_text(query_public_selector(pilot, "#ledger-refusal", Static))
    if refusal:
        raise InstalledTuiChildError("installed Ledger import exposed a persistence refusal")
    await _activate(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button", polls=180)


async def _resolve_imported_transaction_ids(pilot: Any) -> tuple[str, str]:
    """Resolve both opaque row identities from their unique visible synthetic labels."""
    from textual.widgets import DataTable

    await _open_ledger(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries", polls=180)
    table = cast(DataTable[str], query_public_selector(pilot, "#ledger-entries", DataTable))
    if table.row_count == 0:
        raise InstalledTuiChildError(
            "installed Ledger Entries projection was empty after confirmed import",
            diagnostic=public_surface_diagnostic(pilot),
        )
    if table.row_count != len(_SYNTHETIC_ROWS):
        raise InstalledTuiChildError(
            "installed Ledger Entries projection count differs from the confirmed import",
            diagnostic=public_surface_diagnostic(pilot),
        )
    resolved: list[str] = []
    for item in _SYNTHETIC_ROWS:
        matches = [
            row_key
            for row_key in table.rows
            if item.entry_date in " ".join(str(cell) for cell in table.get_row(row_key))
        ]
        if len(matches) != 1:
            raise InstalledTuiChildError(
                "installed Ledger Entries did not expose one unambiguous imported scenario date",
                diagnostic=public_surface_diagnostic(pilot),
            )
        resolved.append(str(matches[0].value))
    if len(resolved) != 2:
        raise InstalledTuiChildError("installed Ledger Entries did not retain two imported row identities")
    return resolved[0], resolved[1]


async def _classify_transaction(
    pilot: Any,
    *,
    transaction_id: str,
    scenario_row: _SyntheticIvaRow,
) -> None:
    """Submit one combined IVA classification through the public TUI form."""
    from textual.widgets import DataTable, Input, Static

    from cadrumo.core.i18n.render import tr

    await _open_ledger(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="entries")
    await wait_for_public_selector(pilot, "#ledger-entries", polls=180)
    table = cast(DataTable[str], query_public_selector(pilot, "#ledger-entries", DataTable))
    row_key = next((candidate for candidate in table.rows if str(candidate.value) == transaction_id), None)
    if row_key is None:
        raise InstalledTuiChildError("installed Ledger Entries lost an imported transaction before classification")
    table.focus()
    table.move_cursor(row=table.get_row_index(row_key))
    await pilot.press("enter")
    await pilot.pause()
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-navigation",
        row_key="classification",
    )
    await wait_for_public_selector(pilot, "#ledger-classifications", polls=180)
    values = {
        "#ledger-classification-taxable-base": scenario_row.taxable_base,
        "#ledger-classification-iva-rate": "0.21",
        "#ledger-classification-iva-amount": scenario_row.iva_amount,
        "#ledger-classification-iva-category": "domestic_general",
        "#ledger-classification-deduction-fact-kind": scenario_row.deduction_fact_kind,
    }
    for selector, value in values.items():
        query_public_selector(pilot, selector, Input).value = value
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-classifications",
        row_key="BUSINESS",
    )
    await _activate(pilot, "#ledger-classification-confirm")
    await pilot.app.workers.wait_for_complete()
    refusal = _visible_text(query_public_selector(pilot, "#ledger-refusal", Static))
    terminal = _visible_text(query_public_selector(pilot, "#ledger-flow-status", Static))
    if refusal or terminal != tr("tui.ledger.classification.success"):
        raise InstalledTuiChildError(
            "installed combined IVA classification did not reach its succeeded public terminal"
        )
    await pilot.press("escape")
    await pilot.app.workers.wait_for_complete()


def _child_authority() -> AuthorityIdentity:
    """Read the isolated authority root installed by the shared child runner."""
    raw = os.environ.get("CADRUMO_AUTHORITY_ROOT")
    if not raw:
        raise InstalledTuiChildError("installed TUI child has no isolated authority root")
    try:
        return _authority_identity(Path(raw))
    except IvaInstalledTuiError as exc:
        raise InstalledTuiChildError(str(exc)) from exc


async def _login_existing_profile_through_tui(*, passphrase: str) -> None:
    """Unlock the capture profile through the installed production Login screen."""
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
        raise InstalledTuiChildError("installed IVA TUI login did not recognize the captured profile")
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
        raise InstalledTuiChildError("installed IVA TUI Login screen did not admit the captured profile")


def _capture_child(
    *,
    workspace_root: Path,
    profile_label: str,
    passphrase: str,
    scratch: Path,
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
    statement = _write_synthetic_statement(scratch)
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
        transaction_ids = await _resolve_imported_transaction_ids(pilot)
        for transaction_id, scenario_row in zip(transaction_ids, _SYNTHETIC_ROWS, strict=True):
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

    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition
    from cadrumo.entrypoints.tui.launcher import main

    # A fresh headless launcher truthfully declines to display credential
    # screens. Admit this already-captured profile through that screen first;
    # its canonical session is then what the production launcher reuses.
    with live_exchange_rate_composition(), profile_adapter_composition():
        asyncio.run(_login_existing_profile_through_tui(passphrase=passphrase))

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


def _write_success_receipt(path: Path, receipt: _CaptureChildReceipt | _ReopenChildReceipt) -> None:
    """Persist a receipt whose schema contains no source facts or credentials."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _child_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child-mode", required=True, choices=("capture", "reopen"))
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--profile-label", default="iva-installed-tui")
    parser.add_argument("--source-manifest-sha256", required=True)
    parser.add_argument("--source-module", action="append", default=[])
    parser.add_argument("--expected-transaction-id", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one credentialed installed-TUI child and persist its sanitized receipt."""
    args = _child_parser().parse_args(argv)
    try:
        modules = _parse_module_hashes(args.source_module)
        if args.child_mode == "capture":
            if args.scratch is None:
                raise InstalledTuiChildError("capture child requires a transient scratch directory")
            receipt: _CaptureChildReceipt | _ReopenChildReceipt = _capture_child(
                workspace_root=args.workspace_root,
                profile_label=args.profile_label,
                passphrase=read_passphrase_from_stdin(),
                scratch=args.scratch,
                expected_manifest_sha256=args.source_manifest_sha256,
                expected_modules=modules,
            )
        else:
            ids = tuple(args.expected_transaction_id)
            if len(ids) != 2 or len(set(ids)) != 2:
                raise InstalledTuiChildError("reopen child requires exactly two distinct captured Ledger identities")
            receipt = _reopen_child(
                workspace_root=args.workspace_root,
                passphrase=read_passphrase_from_stdin(),
                expected_transaction_ids=(ids[0], ids[1]),
                expected_manifest_sha256=args.source_manifest_sha256,
                expected_modules=modules,
            )
    except (IvaInstalledTuiError, InstalledTuiChildError) as exc:
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=exc if isinstance(exc, InstalledTuiChildError) else InstalledTuiChildError(str(exc)),
        )
        return 2
    _write_success_receipt(args.receipt, receipt)
    return 0


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Use caller-owned temporary output only when it has no previous evidence."""
    if path.exists() and any(path.iterdir()):
        raise IvaInstalledTuiError(f"{label} must be empty before an installed acceptance run")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _object(value: object, *, label: str) -> dict[str, object]:
    """Require one public JSON object without retaining the whole command output."""
    if not isinstance(value, dict):
        raise IvaInstalledTuiError(f"{label} returned no object")
    return cast(dict[str, object], value)


def _readback_canonical_fields(
    *,
    executable: Path,
    storage_root: Path,
    authority_root: Path,
    passphrase: str,
    transaction_ids: tuple[str, str],
) -> tuple[str, tuple[str, ...]]:
    """Read public persisted fields in fresh installed CLI processes, without writes.

    This is intentionally a ``tui_to_cli`` continuation.  It is not claimed as
    part of the TUI-only capture/reopen path.
    """
    from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

    expected = tuple(
        (
            transaction_id,
            {
                "business_classification": "BUSINESS",
                "taxable_base": _canonical_ledger_decimal_text(scenario_row.taxable_base),
                "iva_rate": "0.21",
                "iva_amount": _canonical_ledger_decimal_text(scenario_row.iva_amount),
                "iva_category": "domestic_general",
            },
        )
        for transaction_id, scenario_row in zip(transaction_ids, _SYNTHETIC_ROWS, strict=True)
    )
    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=passphrase,
    )
    observed: list[tuple[str, str, str, str, str, str]] = []
    try:
        for transaction_id, expected_fields in expected:
            document = cli.run(("app", "ledger", "view", transaction_id))
            result = _object(document.get("result"), label="installed public ledger view result")
            transaction = _object(result.get("transaction"), label="installed public ledger transaction")
            if result.get("transaction_id") != transaction_id:
                raise IvaInstalledTuiError("installed public ledger view returned a different transaction identity")
            for field_name, expected_value in expected_fields.items():
                if transaction.get(field_name) != expected_value:
                    raise IvaInstalledTuiError(
                        f"installed public Ledger view did not preserve submitted canonical field {field_name!r}"
                    )
            observed.append(
                (
                    transaction_id,
                    expected_fields["business_classification"],
                    expected_fields["taxable_base"],
                    expected_fields["iva_rate"],
                    expected_fields["iva_amount"],
                    expected_fields["iva_category"],
                )
            )
    except InstalledCliError as exc:
        raise IvaInstalledTuiError("installed read-only CLI continuation refused Ledger readback") from exc
    if len(cli.commands) != 2 or any(command.returncode != 0 for command in cli.commands):
        raise IvaInstalledTuiError(
            "installed read-only CLI continuation did not produce two successful fresh-process reads"
        )
    fingerprint = _sha256(json.dumps(observed, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    return fingerprint, tuple("app.ledger.view" for _ in cli.commands)


def _child_document(path: Path, *, mode: str) -> dict[str, object]:
    """Load a child receipt only after the shared runner has verified its presence."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IvaInstalledTuiError("installed TUI child receipt cannot be decoded") from exc
    result = _object(document, label="installed TUI child receipt")
    if result.get("status") != "proven" or result.get("mode") != mode:
        raise IvaInstalledTuiError("installed TUI child did not prove its requested bounded mode")
    return result


def _required_text(document: Mapping[str, object], key: str) -> str:
    """Read a nonempty value-free identity string from a validated child receipt."""
    value = document.get(key)
    if not isinstance(value, str) or not value:
        raise IvaInstalledTuiError("installed TUI receipt is missing a required identity value")
    return value


def _assert_child_identity(
    document: Mapping[str, object],
    *,
    source: SourceIdentity,
    authority: AuthorityIdentity,
    product_origin: str | None = None,
    product_init_sha256: str | None = None,
    package_version: str | None = None,
) -> tuple[str, str, str]:
    """Require both child processes to attest one installed source/package/authority."""
    observed_origin = _required_text(document, "product_origin")
    observed_init = _required_text(document, "product_init_sha256")
    observed_version = _required_text(document, "package_version")
    if observed_origin != "site-packages":
        raise IvaInstalledTuiError("installed TUI child did not attest a site-packages product origin")
    if document.get("source_manifest_sha256") != source.manifest_sha256:
        raise IvaInstalledTuiError("installed TUI child source manifest differs from the supported wheel build input")
    if document.get("source_module_count") != len(source.module_sha256s):
        raise IvaInstalledTuiError("installed TUI child source-module count differs from the attestation")
    expected_authority = {
        "authority_generation": authority.logical_generation,
        "authority_descriptor_sha256": authority.descriptor_sha256,
        "authority_database_sha256": authority.database_sha256,
    }
    if any(document.get(key) != value for key, value in expected_authority.items()):
        raise IvaInstalledTuiError(
            "installed TUI child authority identity differs from the selected published authority"
        )
    if product_origin is not None and observed_origin != product_origin:
        raise IvaInstalledTuiError("fresh installed TUI child product origins differ")
    if product_init_sha256 is not None and observed_init != product_init_sha256:
        raise IvaInstalledTuiError("fresh installed TUI child product initializers differ")
    if package_version is not None and observed_version != package_version:
        raise IvaInstalledTuiError("fresh installed TUI child package versions differ")
    return observed_origin, observed_init, observed_version


def _capture_transaction_ids(document: Mapping[str, object]) -> tuple[str, str]:
    """Take the two opaque transaction handles from a sanitized capture receipt."""
    values = document.get("transaction_ids")
    if not isinstance(values, list) or len(values) != 2:
        raise IvaInstalledTuiError("capture receipt did not retain two transaction handles")
    first, second = values
    if not isinstance(first, str) or not first or not isinstance(second, str) or not second:
        raise IvaInstalledTuiError("capture receipt did not retain two transaction handles")
    if first == second:
        raise IvaInstalledTuiError("capture receipt retained duplicate transaction handles")
    return first, second


def run_installed_tui_capture_reopen(
    *,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
) -> InstalledIvaTuiReceipt:
    """Build/install the current source, then run capture, fresh TUI reopen, and read-only continuation."""
    root = _require_empty_directory(output_root, label="IVA installed-TUI output root")
    workspace = workspace_root.resolve(strict=True)
    authority = _authority_identity(authority_root)
    source = _source_identity(workspace)

    # This is the shared supported build/install path.  The source-member
    # attestation below fails closed if its cached wheel predates this source.
    from dev.packaging._acquire_common import venv_executable
    from dev.packaging._installed_wheel_binding import (
        assert_installed_console_entry_point,
        installed_python_for_cli,
        installed_wheel_payload_sha256,
    )
    from dev.packaging.release_cohort_support import client_venv_template

    template = client_venv_template()
    executable = venv_executable(template, "aeat").resolve(strict=True)
    python_executable = installed_python_for_cli(executable)
    assert_installed_console_entry_point(
        executable,
        distribution="cadrumo",
        entry_point="aeat",
        expected_value="cadrumo.entrypoints.cli.bootstrap:main",
    )
    package_payload_sha256 = installed_wheel_payload_sha256(executable)
    storage_root = _require_empty_directory(root / "secure-store", label="IVA installed-TUI secure store")
    scratch = _require_empty_directory(root / "transient", label="IVA installed-TUI transient directory")
    passphrase = secrets.token_urlsafe(32)
    source_arguments = _module_hash_arguments(source)

    capture_path = root / "capture.json"
    capture_process = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=workspace,
        child_module="dev.acceptance.iva.installed_tui_capture_reopen",
        child_args=(
            "--child-mode",
            "capture",
            "--workspace-root",
            str(workspace),
            "--scratch",
            str(scratch),
            "--receipt",
            str(capture_path),
            "--source-manifest-sha256",
            source.manifest_sha256,
            *source_arguments,
        ),
        storage_root=storage_root,
        authority_root=authority_root,
        receipt_path=capture_path,
        passphrase=passphrase,
        timeout_seconds=900,
    )
    if capture_process.returncode != 0 or capture_process.receipt_status != "proven":
        raise IvaInstalledTuiError("installed IVA TUI capture child did not prove its bounded journey")
    capture = _child_document(capture_path, mode="capture")
    product_origin, product_init_sha256, package_version = _assert_child_identity(
        capture,
        source=source,
        authority=authority,
    )
    transaction_ids = _capture_transaction_ids(capture)
    submitted_fields = capture.get("classification_fields_submitted")
    if (
        not isinstance(submitted_fields, list)
        or len(submitted_fields) != len(_CLASSIFICATION_FIELDS)
        or any(not isinstance(field, str) for field in submitted_fields)
        or tuple(submitted_fields) != _CLASSIFICATION_FIELDS
    ):
        raise IvaInstalledTuiError("capture receipt did not attest all combined IVA classification fields")

    reopen_path = root / "reopen.json"
    reopen_process = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=workspace,
        child_module="dev.acceptance.iva.installed_tui_capture_reopen",
        child_args=(
            "--child-mode",
            "reopen",
            "--workspace-root",
            str(workspace),
            "--receipt",
            str(reopen_path),
            "--source-manifest-sha256",
            source.manifest_sha256,
            *source_arguments,
            "--expected-transaction-id",
            transaction_ids[0],
            "--expected-transaction-id",
            transaction_ids[1],
        ),
        storage_root=storage_root,
        authority_root=authority_root,
        receipt_path=reopen_path,
        passphrase=passphrase,
        timeout_seconds=900,
    )
    if reopen_process.returncode != 0 or reopen_process.receipt_status != "proven":
        raise IvaInstalledTuiError("fresh installed IVA TUI reopen child did not prove its bounded journey")
    reopen = _child_document(reopen_path, mode="reopen")
    _assert_child_identity(
        reopen,
        source=source,
        authority=authority,
        product_origin=product_origin,
        product_init_sha256=product_init_sha256,
        package_version=package_version,
    )
    observed_ids = _capture_transaction_ids({"transaction_ids": reopen.get("observed_transaction_ids")})
    if observed_ids != transaction_ids:
        raise IvaInstalledTuiError("fresh installed TUI reopen returned a different captured identity order")

    fingerprint, command_handles = _readback_canonical_fields(
        executable=executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=passphrase,
        transaction_ids=transaction_ids,
    )
    return InstalledIvaTuiReceipt(
        schema_version=_SCHEMA_VERSION,
        status="proven",
        partial_acceptance_ids=("V1", "V2", "V10"),
        acceptance_scope="partial_ledger_capture_classification_reopen",
        tui_only_path="installed_tui_capture_classify_then_fresh_tui_entries_reopen",
        continuation_path="read_only_installed_cli_ledger_view_after_tui_capture",
        product_origin=product_origin,
        product_init_sha256=product_init_sha256,
        package_version=package_version,
        package_payload_sha256=package_payload_sha256,
        source_manifest_sha256=source.manifest_sha256,
        source_module_count=len(source.module_sha256s),
        authority_generation=authority.logical_generation,
        authority_descriptor_sha256=authority.descriptor_sha256,
        authority_database_sha256=authority.database_sha256,
        child_handles=(
            ChildHandle(
                mode="capture",
                returncode=capture_process.returncode,
                receipt_status=capture_process.receipt_status,
                receipt_sha256=capture_process.receipt_sha256,
                stdout_sha256=capture_process.stdout_sha256,
                stderr_sha256=capture_process.stderr_sha256,
            ),
            ChildHandle(
                mode="reopen",
                returncode=reopen_process.returncode,
                receipt_status=reopen_process.receipt_status,
                receipt_sha256=reopen_process.receipt_sha256,
                stdout_sha256=reopen_process.stdout_sha256,
                stderr_sha256=reopen_process.stderr_sha256,
            ),
        ),
        transaction_count=2,
        classification_fields_submitted=_CLASSIFICATION_FIELDS,
        canonical_fields_read_back=(
            "business_classification",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "iva_category",
        ),
        canonical_classification_fingerprint=fingerprint,
        continuation_command_handles=command_handles,
        deduction_kind_readback="not_proven_public_ledger_view_does_not_expose_deduction_fact_kind",
        unexercised=_UNEXERCISED,
    )


if __name__ == "__main__":  # pragma: no cover - child execution is integration-owned
    raise SystemExit(main())
