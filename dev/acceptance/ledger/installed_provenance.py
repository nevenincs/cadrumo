"""Installed-wheel check of public Ledger import provenance across every supported path.

Every supported (record kind, file format, importing frontend) combination in
:mod:`.provenance_fixtures` writes its own synthetic source into a fresh store.
CLI cases import through ``ledger import`` or ``ledger invoice import``; TUI
cases import through the installed Ledger import form in one fresh child
process.  Every record, whichever frontend imported it, is then read back
through public CLI (``ledger track`` JSON and text for transactions,
``ledger invoice view`` JSON for invoices) and through the installed TUI
invoice or transaction detail in a second fresh child process.  The profile
secret crosses every process boundary on stdin only and never reaches the
receipt.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, Protocol

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    assert_installed_product_origin,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    run_installed_tui_child_process,
    select_public_data_table_row,
    wait_for_any_public_selector,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)
from dev.acceptance.installed_cli import (
    InstalledCli,
    InstalledCliError,
    authority_generation,
    build_installed_cli_environment,
)

from .installed_tui_journey import (
    LedgerInstalledTuiError,
    _activate_button,
    _admit_existing_profile_for_headless_launcher,
    _open_invoice_detail,
    _open_ledger_destination,
    _open_transaction_detail,
    _require_empty_directory,
    _result,
    _text,
)
from .provenance_fixtures import ProvenanceCase, provenance_cases

_SCHEMA = "ledger-01-installed-provenance-v2"
_PATTERN_REVISION = "1.7"
_BRIEF_REVISION = "0.1"
_YEAR = 2025
_KEYCHAIN_UNAVAILABLE = "AUTH_STORAGE_KEYRING_UNAVAILABLE"
_TUI_IMPORT_KINDS = {"received": "invoices_received", "issued": "invoices_issued"}

type ChildMode = Literal["import", "inspect"]

# The installed root is built on a worker thread before Login or Home mounts;
# on a loaded host that outlasts a fixed count of event-loop pauses.
_ADMISSION_SURFACE_SECONDS = 300.0


def assert_json_provenance(payload: Mapping[str, Any], *, filename: str, row: int, stage: str) -> None:
    """Require the public JSON filename and row projection of one imported record."""
    if (payload.get("source_filename"), payload.get("source_row_index")) != (filename, row):
        raise LedgerInstalledTuiError(f"{stage} did not expose the imported filename and row")


def assert_track_text_provenance(text: str, *, filename: str, row: int) -> None:
    """Require the tab-separated import source and row lines of ``ledger track`` text."""
    lines = set(text.splitlines())
    if f"import_source\t{filename}" not in lines or f"import_source_row\t{row}" not in lines:
        raise LedgerInstalledTuiError("installed ledger track text did not expose the imported filename and row")


def assert_detail_provenance(rendered: str, *, filename: str, row: int, stage: str) -> None:
    """Require the ``filename:row`` provenance token in one rendered TUI detail."""
    if f"{filename}:{row}" not in rendered:
        raise LedgerInstalledTuiError(f"{stage} did not display the imported filename and row")


def _cli_track_text(cli: InstalledCli, transaction_id: str, *, authenticated: bool) -> str:
    """Read ``ledger track`` in its default text format with the shared installed environment."""
    secret_flag = ("--profile-secrets-stdin",) if authenticated else ()
    completed = subprocess.run(  # noqa: S603 - executable comes from explicit installed-wheel input
        [str(cli.executable), *secret_flag, "app", "ledger", "track", transaction_id],
        check=False,
        capture_output=True,
        cwd=cli.storage_root,
        env=build_installed_cli_environment(storage_root=cli.storage_root, authority_root=cli.authority_root),
        input=json.dumps({"profile_passphrase": cli.passphrase}, separators=(",", ":")) if authenticated else "",
        text=True,
        timeout=180,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise LedgerInstalledTuiError(f"installed CLI ledger.track text failed (exit_code={completed.returncode})")
    return completed.stdout


def _cli(
    cli: InstalledCli, arguments: Sequence[str], *, command: str, stage: str, authenticated: bool = True
) -> dict[str, Any]:
    """Run one public JSON command and name the failed stage without retaining payloads.

    ``authenticated=False`` resumes the session a TUI login admitted.  The
    product refuses a stdin secret while such a session is resumable, because
    the secret would go unused.
    """
    try:
        return _result(cli.run(arguments, command=command, authenticated=authenticated), stage=stage)
    except InstalledCliError as error:
        # The shared runner's message names the static command and the public
        # error code only; identifiers and payloads never reach it.
        raise LedgerInstalledTuiError(f"{stage}: installed CLI {error}") from error


def _import_through_cli(cli: InstalledCli, case: ProvenanceCase, path: Path) -> None:
    """Import one CLI case and require every row of its source to be accepted."""
    stage = f"{case.case_id} CLI import"
    if case.record == "transaction":
        if case.provider is None:
            raise LedgerInstalledTuiError(f"{stage} has no statement provider")
        imported = _cli(
            cli,
            ("app", "ledger", "import", "--file", str(path), "--provider", case.provider),
            command="ledger.import",
            stage=stage,
        )
        accepted = imported.get("imported")
    else:
        if case.invoice_kind is None:
            raise LedgerInstalledTuiError(f"{stage} has no invoice kind")
        imported = _cli(
            cli,
            ("app", "ledger", "invoice", "import", "--file", str(path), "--kind", case.invoice_kind),
            command="ledger.invoice.import",
            stage=stage,
        )
        accepted = imported.get("created")
    if accepted != case.row_count:
        raise LedgerInstalledTuiError(f"{stage} did not accept every synthetic row")


def _public_rows(
    cli: InstalledCli, arguments: Sequence[str], *, command: str, key: str, authenticated: bool
) -> dict[str, dict[str, Any]]:
    """Index one public list envelope by its unique public key."""
    listed = _cli(cli, arguments, command=command, stage=f"{command} discovery", authenticated=authenticated)
    rows = listed.get("rows")
    if not isinstance(rows, list):
        raise LedgerInstalledTuiError(f"{command} omitted public rows")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get(key), str):
            if row[key] in indexed:
                raise LedgerInstalledTuiError(f"{command} exposed a duplicate public {key}")
            indexed[row[key]] = row
    return indexed


class _PublicCommandRunner(Protocol):
    """The one installed-CLI call the session probe makes."""

    def run(
        self, arguments: Sequence[str], /, *, command: str, authenticated: bool, allow_error: bool
    ) -> dict[str, Any]: ...


def _tui_login_session_mode(cli: _PublicCommandRunner) -> Literal["resumed_tui_session", "stdin_secret"]:
    """Ask the product whether the TUI login left a session the CLI can resume.

    A TUI login persists its session only through a usable OS keychain; without
    one the product keeps the login process-scoped and a later CLI call must
    authenticate itself. Both are supported product states, so the readback
    observes which one this host produced instead of assuming it.
    """
    try:
        document = cli.run(("app", "ledger", "list"), command="ledger.list", authenticated=False, allow_error=True)
    except InstalledCliError as error:
        raise LedgerInstalledTuiError(f"TUI session probe: installed CLI {error}") from error
    if document.get("status") != "error":
        return "resumed_tui_session"
    error = document.get("error")
    code = error.get("code") if isinstance(error, dict) else None
    if code == _KEYCHAIN_UNAVAILABLE:
        return "stdin_secret"
    raise LedgerInstalledTuiError(f"TUI session probe refused with an unexpected code: {code}")


def _host_free_memory_gb() -> float | None:
    """Report free physical memory, which bounds whether a run failed for the host's reasons."""
    if sys.platform != "win32":
        return None
    import ctypes

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.length = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(status.available_physical / 2**30, 1)


def _cli_readback(cli: InstalledCli, cases: Sequence[ProvenanceCase], *, authenticated: bool) -> dict[str, list[str]]:
    """Read every imported target through public CLI and return per-case surfaces."""
    transactions = _public_rows(
        cli, ("app", "ledger", "list"), command="ledger.list", key="description", authenticated=authenticated
    )
    invoices = _public_rows(
        cli,
        ("app", "ledger", "invoice", "list"),
        command="ledger.invoice.list",
        key="invoice_number",
        authenticated=authenticated,
    )
    surfaces: dict[str, list[str]] = {}
    for case in cases:
        stage = f"{case.case_id} CLI readback"
        if case.record == "transaction":
            row = transactions.get(case.target_key)
            if row is None:
                raise LedgerInstalledTuiError(f"{stage} did not find the imported transaction")
            transaction_id = _text(row.get("transaction_id"), stage=stage)
            tracked = _cli(
                cli,
                ("app", "ledger", "track", transaction_id),
                command="ledger.track",
                stage=stage,
                authenticated=authenticated,
            )
            assert_json_provenance(tracked, filename=case.filename, row=case.locator, stage=f"{stage} track JSON")
            assert_track_text_provenance(
                _cli_track_text(cli, transaction_id, authenticated=authenticated),
                filename=case.filename,
                row=case.locator,
            )
            surfaces[case.case_id] = ["cli_track_json", "cli_track_text"]
        else:
            row = invoices.get(case.target_key)
            if row is None:
                raise LedgerInstalledTuiError(f"{stage} did not find the imported invoice")
            invoice_id = _text(row.get("invoice_id"), stage=stage)
            viewed = _cli(
                cli,
                ("app", "ledger", "invoice", "view", invoice_id),
                command="ledger.invoice.view",
                stage=stage,
                authenticated=authenticated,
            )
            assert_json_provenance(viewed, filename=case.filename, row=case.locator, stage=f"{stage} view JSON")
            if viewed.get("kind") != case.invoice_kind:
                raise LedgerInstalledTuiError(f"{stage} stored a different invoice kind")
            surfaces[case.case_id] = ["cli_invoice_view_json"]
    return surfaces


async def _import_through_tui(pilot: Any, entry: Mapping[str, Any]) -> None:
    """Import one source through the installed Ledger import form's preview and confirmation."""
    from textual.widgets import Button, Input, Select, Static

    case_id = entry["case_id"]
    await _open_ledger_destination(pilot)
    await select_public_data_table_row(pilot=pilot, table_selector="#ledger-navigation", row_key="import")
    await wait_for_public_selector(pilot, "#ledger-import-path", polls=180)
    if entry["record"] == "transaction":
        query_public_selector(pilot, "#ledger-import-kind", Select).value = "bank_statement"
        await pilot.pause()
        query_public_selector(pilot, "#ledger-import-provider", Select).value = entry["provider"]
    else:
        query_public_selector(pilot, "#ledger-import-kind", Select).value = _TUI_IMPORT_KINDS[entry["invoice_kind"]]
        await pilot.pause()
        query_public_selector(pilot, "#ledger-import-country", Input).value = "ES"
    query_public_selector(pilot, "#ledger-import-path", Input).value = entry["path"]
    await _activate_button(pilot, "#ledger-import-preview-button")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-confirm", polls=180)
    refusal = str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip()
    if refusal or query_public_selector(pilot, "#ledger-import-confirm", Button).disabled:
        raise LedgerInstalledTuiError(f"{case_id} TUI import did not reach public confirmation")
    await _activate_button(pilot, "#ledger-import-confirm")
    await pilot.app.workers.wait_for_complete()
    if str(query_public_selector(pilot, "#ledger-refusal", Static).render()).strip():
        raise LedgerInstalledTuiError(f"{case_id} TUI import visibly refused persistence")
    await _activate_button(pilot, "#ledger-import-again")
    await pilot.app.workers.wait_for_complete()
    await wait_for_public_selector(pilot, "#ledger-import-preview-button", polls=180)


async def _inspect_through_tui(pilot: Any, entry: Mapping[str, Any]) -> None:
    """Open one record's installed TUI detail and require its provenance token."""
    from textual.widgets import Static

    if entry["record"] == "invoice":
        await _open_invoice_detail(pilot, invoice_number=entry["target_key"])
        stage = f"{entry['case_id']} installed TUI invoice detail"
    else:
        await _open_transaction_detail(pilot, description=entry["target_key"])
        stage = f"{entry['case_id']} installed TUI transaction detail"
    assert_detail_provenance(
        str(query_public_selector(pilot, "#ledger-record-detail", Static).render()),
        filename=entry["filename"],
        row=entry["locator"],
        stage=stage,
    )


async def _wait_with_deadline(
    pilot: Any, selectors: tuple[str, ...], *, seconds: float = _ADMISSION_SURFACE_SECONDS
) -> str:
    """Wait for one public admission surface for up to ``seconds``."""
    from textual.css.query import NoMatches

    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    while True:
        for selector in selectors:
            try:
                query_public_selector(pilot, selector)
            except NoMatches:
                continue
            return selector
        if loop.time() >= deadline:
            # The shared helper raises with the sanitized public-surface diagnostic.
            return await wait_for_any_public_selector(pilot, selectors, polls=1)
        await pilot.pause(0.5)


async def _admit_installed_session(pilot: Any, *, passphrase: str) -> None:
    """Unlock through the visible Login screen, or accept an already admitted Home."""
    from textual.widgets import Input

    if await _wait_with_deadline(pilot, ("#field-passphrase", "#home-agenda")) == "#field-passphrase":
        query_public_selector(pilot, "#field-passphrase", Input).value = passphrase
        await pilot.click("#btn-unlock")
    await _wait_with_deadline(pilot, ("#home-agenda",))


def _run_installed_launcher(*, passphrase: str, drive_after_home: Any) -> None:
    """Run one ordinary headless installed launch and require a clean exit."""
    from cadrumo.entrypoints.tui.launcher import main as launch

    async def drive(pilot: Any) -> None:
        await _admit_installed_session(pilot, passphrase=passphrase)
        await drive_after_home(pilot)

    if launch(headless=True, auto_pilot=drive) != 0:
        raise LedgerInstalledTuiError("installed Ledger launcher did not exit cleanly")


def _read_manifest(path: Path) -> list[dict[str, Any]]:
    """Read the outer run's value-free case coordinates."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, list) or not all(isinstance(entry, dict) for entry in document):
        raise LedgerInstalledTuiError("installed provenance manifest is malformed")
    return document


def _optional_extra_version(distribution: str) -> str | None:
    """Report an installed optional dependency's version from the product environment."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def _run_child(*, workspace_root: Path, mode: ChildMode, manifest: Path, passphrase: str) -> dict[str, object]:
    """Import the TUI cases, or inspect every case, through one fresh installed TUI process."""
    entries = _read_manifest(manifest)
    selected = [entry for entry in entries if entry["import_frontend"] == "tui"] if mode == "import" else entries
    _admit_existing_profile_for_headless_launcher(passphrase=passphrase)
    observations: list[str] = []

    async def drive(pilot: Any) -> None:
        for entry in selected:
            try:
                if mode == "import":
                    await _import_through_tui(pilot, entry)
                    observations.append(f"tui_import:{entry['case_id']}")
                else:
                    await _inspect_through_tui(pilot, entry)
                    observations.append(f"tui_detail:{entry['case_id']}")
            except InstalledTuiChildError as error:
                raise InstalledTuiChildError(f"{entry['case_id']}: {error}", diagnostic=error.diagnostic) from error
        pilot.app.exit()

    _run_installed_launcher(passphrase=passphrase, drive_after_home=drive)
    if len(observations) != len(selected) or not selected:
        raise LedgerInstalledTuiError(f"installed TUI provenance {mode} callback did not finish")
    product = installed_product_evidence(workspace_root=workspace_root)
    return {
        "schema_version": _SCHEMA,
        "status": "proven",
        "mode": mode,
        "product_origin": product.product_origin,
        "product_init_path": str(assert_installed_product_origin(workspace_root=workspace_root)),
        "product_init_sha256": product.product_init_sha256,
        "ofxtools_version": _optional_extra_version("ofxtools"),
        "observations": observations,
    }


def _parse_child_receipt(path: Path, *, mode: ChildMode, expected: Sequence[str]) -> dict[str, Any]:
    """Read one child's value-free receipt and require installed origin plus every expected observation."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LedgerInstalledTuiError(f"installed TUI provenance {mode} child receipt is unreadable") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != _SCHEMA
        or document.get("status") != "proven"
        or document.get("mode") != mode
        or document.get("product_origin") != "site-packages"
        or not isinstance(document.get("product_init_sha256"), str)
        or len(document["product_init_sha256"]) != 64
        or not isinstance(document.get("product_init_path"), str)
        or list(document.get("observations") or ()) != list(expected)
    ):
        raise LedgerInstalledTuiError(f"installed TUI provenance {mode} child did not prove every case")
    return document


def _run_tui_child(
    args: argparse.Namespace,
    *,
    mode: ChildMode,
    python_executable: Path,
    authority_root: Path,
    store: Path,
    root: Path,
    manifest: Path,
    passphrase: str,
    expected: Sequence[str],
) -> dict[str, Any]:
    """Run one fresh installed TUI child with its credential on stdin."""
    receipt = root / f"installed-tui-{mode}.json"
    child = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=args.workspace_root,
        child_module="dev.acceptance.ledger.installed_provenance",
        child_args=(
            "--child",
            mode,
            "--workspace-root",
            str(args.workspace_root),
            "--receipt",
            str(receipt),
            "--manifest",
            str(manifest),
        ),
        storage_root=store,
        receipt_path=receipt,
        passphrase=passphrase,
        authority_root=authority_root,
        timeout_seconds=1800,
    )
    if child.returncode != 0:
        try:
            failure = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failure = {}
        # The child writes only sanitized, value-free failure text: a case id,
        # a stage and the public selector that was missing.
        cause = (failure.get("error") or failure.get("diagnostic")) if isinstance(failure, dict) else None
        cause = cause or "no sanitized cause"
        raise LedgerInstalledTuiError(f"installed TUI provenance {mode} child exited unsuccessfully: {cause}")
    return _parse_child_receipt(receipt, mode=mode, expected=expected)


def _run_outer(args: argparse.Namespace) -> dict[str, object]:
    """Import every case into a fresh synthetic store and read each back through both frontends."""
    cli_executable = args.cli.resolve(strict=True)
    python_executable = args.python.resolve(strict=True)
    if cli_executable.parent != python_executable.parent:
        raise LedgerInstalledTuiError("installed CLI and TUI child Python do not belong to one environment")
    wheel_sha256 = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    authority_root = args.authority_root.resolve(strict=True)
    root = _require_empty_directory(args.output_root, label="Ledger provenance output root")
    store = _require_empty_directory(root / "secure-store", label="Ledger provenance secure store")
    sources = _require_empty_directory(root / "sources", label="Ledger provenance synthetic sources")
    cases = provenance_cases()
    paths = {case.case_id: case.write(sources) for case in cases}
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps([case.manifest_entry(paths[case.case_id]) for case in cases], indent=2) + "\n", encoding="utf-8"
    )

    host_free_memory_gb = _host_free_memory_gb()
    passphrase = secrets.token_urlsafe(32)
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    try:
        cli.create_profile(year=_YEAR)
    except InstalledCliError as error:
        raise LedgerInstalledTuiError("installed CLI profile creation failed") from error
    cli_cases = [case for case in cases if case.import_frontend == "cli"]
    tui_cases = [case for case in cases if case.import_frontend == "tui"]
    for case in cli_cases:
        _import_through_cli(cli, case, paths[case.case_id])
    # Before any TUI login the CLI authenticates with the stdin secret.
    cli_surfaces = _cli_readback(cli, cli_cases, authenticated=True)

    imported = _run_tui_child(
        args,
        mode="import",
        python_executable=python_executable,
        authority_root=authority_root,
        store=store,
        root=root,
        manifest=manifest,
        passphrase=passphrase,
        expected=[f"tui_import:{case.case_id}" for case in tui_cases],
    )
    tui_readback_authentication = _tui_login_session_mode(cli)
    cli_surfaces.update(_cli_readback(cli, tui_cases, authenticated=tui_readback_authentication == "stdin_secret"))
    inspected = _run_tui_child(
        args,
        mode="inspect",
        python_executable=python_executable,
        authority_root=authority_root,
        store=store,
        root=root,
        manifest=manifest,
        passphrase=passphrase,
        expected=[f"tui_detail:{case.case_id}" for case in cases],
    )
    if imported["product_init_sha256"] != inspected["product_init_sha256"]:
        raise LedgerInstalledTuiError("installed TUI children imported different products")
    transaction_count = sum(1 for case in cases if case.record == "transaction")
    return {
        "schema_version": _SCHEMA,
        "status": "proven",
        "pattern_revision": _PATTERN_REVISION,
        "brief_revision": _BRIEF_REVISION,
        "source_commit": args.source_commit,
        "wheel_filename": args.wheel.name,
        "wheel_sha256": wheel_sha256,
        "installed_extras": {"ofxtools": inspected.get("ofxtools_version")},
        "authority_generation": authority_generation(authority_root),
        "year": _YEAR,
        "product_origin": inspected["product_origin"],
        "product_init_path": inspected["product_init_path"],
        "product_init_sha256": inspected["product_init_sha256"],
        "cases": [
            {
                **case.receipt_entry(),
                "surfaces": [*cli_surfaces[case.case_id], "tui_detail"],
                "cli_authentication": tui_readback_authentication if case.import_frontend == "tui" else "stdin_secret",
            }
            for case in cases
        ],
        "cli_json_command_count": len(cli.commands),
        "cli_text_command_count": transaction_count,
        "tui_child_process_count": 2,
        "host_free_memory_gb_at_start": host_free_memory_gb,
        "synthetic_store_retained": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=("import", "inspect"))
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def _failure_document(error: Exception) -> dict[str, object]:
    """Reduce a failure to its type and, for driver-owned refusals, the value-free stage message."""
    if isinstance(error, LedgerInstalledTuiError):
        diagnostic = str(error)
    elif isinstance(error, (InstalledTuiChildError, InstalledCliError)):
        diagnostic = "installed frontend or command failed"
    else:
        diagnostic = "unexpected installed Ledger provenance failure"
    return {"schema_version": _SCHEMA, "status": "failed", "error_type": type(error).__name__, "diagnostic": diagnostic}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed outer provenance matrix or one stdin-credentialed TUI child."""
    args = _parser().parse_args(argv)
    try:
        if args.child is not None:
            if args.manifest is None:
                raise LedgerInstalledTuiError("installed TUI provenance child has no case manifest")
            document = _run_child(
                workspace_root=args.workspace_root,
                mode=args.child,
                manifest=args.manifest,
                passphrase=read_passphrase_from_stdin(),
            )
        else:
            if None in (args.cli, args.python, args.wheel, args.authority_root, args.output_root, args.source_commit):
                raise LedgerInstalledTuiError("installed provenance outer run lacks its wheel and source inputs")
            document = _run_outer(args)
    except InstalledTuiChildError as error:
        if args.child is None:
            document = _failure_document(error)
        else:
            write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA, error=error)
            return 2
    except Exception as error:
        document = _failure_document(error)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if document["status"] == "proven" else 2


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
