"""Installed-wheel CLI/TUI calendar parity over independent and continued synthetic stores.

Four isolated secure stores prove that the installed CLI and installed TUI state
the same calendar meaning for one evaluation date:

* ``cli_only`` and ``tui_only`` are independent stores read by one frontend each;
* ``cli_to_tui`` creates local work through the CLI, then reads it in the TUI;
* ``tui_to_cli`` creates local work through the TUI calendar, then reads it
  through the CLI, which resumes the session the TUI login admitted.

Each store's profile is admitted through the public CLI ``config profile
create`` flow; the calendar reads and the continuation writes are the frontend
under test.  The profile secret crosses every process boundary on stdin only.
The final receipt keeps row identities, field-level match results and package
identity; rendered text and envelopes stay in the run directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    admit_existing_profile_for_headless_launcher,
    assert_installed_product_origin,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    run_admitted_installed_launcher,
    run_installed_tui_child_process,
    select_public_data_table_row,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)
from dev.acceptance.installed_cli import (
    InstalledCli,
    InstalledCliError,
    authority_generation,
)

_SCHEMA = "calendar-01-installed-parity-v1"
_PATTERN_REVISION = "1.7"
_BRIEF_REVISION = "0.1"
_ACTOR = "calendar-acceptance"
# The TUI must reach one continuation row before its evaluation date, so the
# rows are chosen from the prior filing year's quarterly obligations.
_CLI_WRITE_PERIOD = "1T"
_TUI_WRITE_PERIOD = "2T"
_WRITE_MODELO = "303"
# The CLI states "AEAT history never captured" once per envelope; the TUI states
# it on every row as an unobservable source.
_NO_AEAT_HISTORY_NOTICE = "overview.no_aeat_history"

type ChildMode = Literal["inspect", "create_then_inspect"]
type Outcome = Literal["proven", "failed", "blocked", "not_exercised"]

# Fields compared between the CLI envelope and the rendered TUI detail.
COMPARED_FIELDS = (
    "evaluated",
    "original_close",
    "effective_close",
    "payment_cutoff",
    "days_overdue",
    "shift",
    "holidays",
    "local",
    "aeat",
    "receipt",
)


class CalendarParityError(RuntimeError):
    """The installed calendar journey could not prove one stated meaning."""


@dataclass(frozen=True, slots=True)
class CalendarWindow:
    """The evaluation date and the date range both frontends are asked for."""

    as_of: date
    from_date: date
    to_date: date

    @classmethod
    def for_evaluation(cls, as_of: date) -> CalendarWindow:
        """Cover the prior and current calendar years, as the workbench calendar does."""
        return cls(as_of=as_of, from_date=date(as_of.year - 1, 1, 1), to_date=date(as_of.year, 12, 31))


@dataclass(frozen=True, slots=True)
class CliCalendarRow:
    """One calendar row as the installed CLI states it in JSON and text."""

    row_key: str
    modelo: str
    filing_year: int
    period: str
    evaluated_on: str
    closes_on: str
    adjusted_closes_on: str
    payment_cutoff_on: str | None
    days_overdue: int | None
    shift_text: str
    holidays_text: str
    local_filing_state: str
    aeat_submission_state: str
    justificante_verified: bool
    aeat_observable: bool
    work_unit_id: str | None


def tui_row_key(modelo: str, filing_year: int, period: str) -> str:
    """Return the public DataTable row key of one calendar natural address."""
    return f"{modelo}|{filing_year}|{period}"


def parse_cli_calendar(document: Mapping[str, Any], text: str) -> dict[str, CliCalendarRow]:
    """Join the JSON rows with their localized text statements by natural address."""
    result = document.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("entries"), list):
        raise CalendarParityError("installed CLI calendar omitted its entries")
    notices = document.get("notices") or []
    aeat_observable = not any(
        isinstance(notice, dict) and notice.get("code") == _NO_AEAT_HISTORY_NOTICE for notice in notices
    )
    statements: dict[tuple[str, str], dict[str, str]] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4 or not parts[3].startswith("opens="):
            continue
        fields = dict(part.split("=", 1) for part in parts[3:] if "=" in part)
        statements[(parts[0], parts[1])] = fields
    rows: dict[str, CliCalendarRow] = {}
    for entry in result["entries"]:
        if not isinstance(entry, dict):
            raise CalendarParityError("installed CLI calendar entry is not an object")
        year_text, _, period = str(entry["period"]).partition(" ")
        statement = statements.get((str(entry["modelo"]), str(entry["period"])))
        if statement is None:
            raise CalendarParityError("installed CLI calendar text omitted a JSON row")
        key = tui_row_key(str(entry["modelo"]), int(year_text), period)
        if key in rows:
            raise CalendarParityError("installed CLI calendar repeated a natural address")
        rows[key] = CliCalendarRow(
            row_key=key,
            modelo=str(entry["modelo"]),
            filing_year=int(year_text),
            period=period,
            evaluated_on=str(entry["evaluated_on"]),
            closes_on=str(entry["closes_on"]),
            adjusted_closes_on=str(entry["adjusted_closes_on"]),
            payment_cutoff_on=entry.get("payment_cutoff_on"),
            days_overdue=entry.get("days_overdue"),
            shift_text=statement.get("shift", ""),
            holidays_text=statement.get("holidays", ""),
            local_filing_state=str(entry["local_filing_state"]),
            aeat_submission_state=str(entry["aeat_submission_state"]),
            justificante_verified=bool(entry["justificante_verified"]),
            aeat_observable=aeat_observable,
            work_unit_id=statement.get("work_unit"),
        )
    return rows


def parse_tui_detail(rendered: str) -> dict[str, str]:
    """Split the rendered English calendar detail into its labelled values."""
    labels = {
        "Evaluated": "evaluated",
        "Original close": "original_close",
        "Effective close": "effective_close",
        "Payment": "payment_cutoff",
        "Days overdue": "days_overdue",
        "Shift": "shift",
        "Holidays": "holidays",
        "Local": "local",
        "AEAT": "aeat",
        "Receipt": "receipt",
    }
    fields: dict[str, str] = {}
    for line in rendered.splitlines():
        for part in line.split(" · "):
            label, separator, value = part.partition(": ")
            name = labels.get(label.strip())
            if separator and name is not None:
                fields[name] = value.strip()
    return fields


def expected_tui_fields(row: CliCalendarRow, labels: Mapping[str, str]) -> dict[str, str]:
    """State what the TUI must render for one CLI row, using the product's own labels."""

    def day(value: str | None) -> str:
        return labels["none"] if value is None else date.fromisoformat(value).strftime("%d/%m/%Y")

    if not row.aeat_observable:
        aeat = labels["aeat.unknown"]
        receipt = labels["receipt.unknown"]
    else:
        aeat = labels[f"aeat.{row.aeat_submission_state}"]
        receipt = labels["receipt.verified"] if row.justificante_verified else labels["receipt.not_verified"]
    return {
        "evaluated": day(row.evaluated_on),
        "original_close": day(row.closes_on),
        "effective_close": day(row.adjusted_closes_on),
        "payment_cutoff": day(row.payment_cutoff_on),
        "days_overdue": labels["none"] if row.days_overdue is None else str(row.days_overdue),
        "shift": row.shift_text,
        "holidays": row.holidays_text,
        "local": labels[f"local.{row.local_filing_state}"],
        "aeat": aeat,
        "receipt": receipt,
    }


def compare_rows(
    cli_rows: Mapping[str, CliCalendarRow],
    tui_rows: Mapping[str, Mapping[str, str]],
    labels: Mapping[str, str],
) -> list[dict[str, object]]:
    """Compare every CLI row with its rendered TUI detail field by field."""
    if set(cli_rows) != set(tui_rows):
        raise CalendarParityError("installed CLI and TUI calendars list different natural addresses")
    comparisons: list[dict[str, object]] = []
    for key in sorted(cli_rows):
        expected = expected_tui_fields(cli_rows[key], labels)
        rendered = tui_rows[key]
        mismatched = sorted(name for name in COMPARED_FIELDS if rendered.get(name) != expected[name])
        comparisons.append({"row": key, "fields": len(COMPARED_FIELDS), "mismatched": mismatched})
    return comparisons


# ---------------------------------------------------------------------------
# Installed TUI child
# ---------------------------------------------------------------------------


def _product_labels() -> dict[str, str]:
    """Translate every state token the calendar detail can render, through the installed catalogue."""
    from cadrumo.application.overview.calendar_models import OverviewAeatSubmissionState, OverviewLocalFilingState
    from cadrumo.entrypoints.tui.declarations.controller import declarations_copy

    labels = {
        "none": declarations_copy("tui.declarations.calendar.none"),
        "receipt.verified": declarations_copy("tui.declarations.calendar.justificante.verified"),
        "receipt.not_verified": declarations_copy("tui.declarations.calendar.justificante.not_verified"),
        "receipt.unknown": declarations_copy("tui.declarations.calendar.justificante.unknown"),
        "aeat.unknown": declarations_copy("tui.declarations.calendar.aeat.unknown"),
        "local.unknown": declarations_copy("tui.declarations.calendar.local.unknown"),
    }
    for local in OverviewLocalFilingState:
        labels[f"local.{local.value}"] = declarations_copy(f"tui.declarations.calendar.local.{local.value}")
    for aeat in OverviewAeatSubmissionState:
        labels[f"aeat.{aeat.value}"] = declarations_copy(f"tui.declarations.calendar.aeat.{aeat.value}")
    return labels


async def _open_declarations(pilot: Any) -> tuple[str, ...]:
    """Open Declarations through the command palette and return its visible work-unit row keys."""
    from textual.css.query import NoMatches
    from textual.widgets import Input, OptionList

    from cadrumo.core.i18n.render import tr

    label = tr("tui.search.destination.declarations")
    await pilot.press("ctrl+p")
    for _ in range(180):
        await pilot.pause()
        try:
            search = pilot.app.screen.query_one(Input)
            options = pilot.app.screen.query_one(OptionList)
        except NoMatches:
            continue
        search.value = "declarations"
        for index in range(options.option_count):
            if getattr(getattr(options.get_option_at_index(index), "hit", None), "text", None) == label:
                options.highlighted = index
                await pilot.press("enter")
                break
        else:
            continue
        break
    else:
        raise CalendarParityError("installed command palette did not offer Declarations")
    from textual.widgets import DataTable

    await wait_for_public_selector(pilot, "#declarations-list", polls=240)
    await pilot.pause()
    table = query_public_selector(pilot, "#declarations-list", DataTable)
    return tuple(str(row_key.value) for row_key in table.rows)


async def _open_calendar(pilot: Any) -> tuple[str, ...]:
    """Open the Declarations calendar showing every row; return the work-unit keys seen on the way."""
    from textual.widgets import Select

    work_units = await _open_declarations(pilot)
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-navigation",
        row_key="declarations.calendar",
    )
    await wait_for_public_selector(pilot, "#declarations-calendar-agenda", polls=240)
    query_public_selector(pilot, "#declarations-calendar-scope", Select).value = "all"
    await pilot.pause()
    return work_units


async def _read_visible_rows(pilot: Any) -> dict[str, dict[str, str]]:
    """Highlight each visible calendar row and read its rendered detail."""
    from textual.widgets import DataTable, Static

    table = query_public_selector(pilot, "#declarations-calendar-agenda", DataTable)
    rows: dict[str, dict[str, str]] = {}
    for row_key in list(table.rows):
        table.focus()
        table.move_cursor(row=table.get_row_index(row_key))
        await pilot.pause()
        rendered = str(query_public_selector(pilot, "#declarations-calendar-detail", Static).render())
        rows[str(row_key.value)] = {"rendered": rendered, **parse_tui_detail(rendered)}
    if not rows:
        raise CalendarParityError("installed TUI calendar showed no rows under the all scope")
    return rows


async def _create_work_from_calendar(pilot: Any, row_key: str) -> None:
    """Create one filing-period work unit through the calendar's visible confirmation."""
    from textual.widgets import Static

    await select_public_data_table_row(pilot=pilot, table_selector="#declarations-calendar-agenda", row_key=row_key)
    await wait_for_public_selector(pilot, "#btn-confirm-accept", polls=180)
    await pilot.click("#btn-confirm-accept")
    await pilot.app.workers.wait_for_complete()
    notice = str(query_public_selector(pilot, "#declarations-calendar-notice", Static).render()).strip()
    if not notice.startswith("Created "):
        raise CalendarParityError("installed TUI calendar did not report the created work")
    await pilot.press("escape")


async def _wait_for_refreshed_workbench(pilot: Any, *, polls: int = 6000) -> None:
    """Wait until the public Home is mounted and no workbench refresh is in progress."""
    from textual.css.query import NoMatches
    from textual.widgets import Static

    for _ in range(polls):
        try:
            updating = query_public_selector(pilot, "#root-updating", Static)
            pilot.app.screen.query_one("#home-agenda")
        except NoMatches:
            pass
        else:
            if not updating.display:
                return
        await pilot.pause()
    raise CalendarParityError("installed TUI did not finish refreshing the workbench after the calendar write")


def _run_child(*, workspace_root: Path, mode: ChildMode, write_row: str | None, passphrase: str) -> dict[str, object]:
    """Read, or create then read, the calendar through one fresh installed TUI process."""
    admit_existing_profile_for_headless_launcher(passphrase=passphrase)
    observed: dict[str, dict[str, str]] = {}
    work_units: list[str] = []

    async def drive(pilot: Any) -> None:
        if mode == "create_then_inspect":
            if write_row is None:
                raise CalendarParityError("installed TUI create child has no calendar row")
            await _open_calendar(pilot)
            await _create_work_from_calendar(pilot, write_row)
            # Leave the calendar and let the workbench rebuild from the store
            # before the second read, or it would show the pre-write generation.
            await pilot.press("escape")
            await _wait_for_refreshed_workbench(pilot)
        work_units.extend(await _open_calendar(pilot))
        observed.update(await _read_visible_rows(pilot))
        pilot.app.exit()

    run_admitted_installed_launcher(passphrase=passphrase, drive_after_home=drive, admission_polls=6000)
    if not observed:
        raise CalendarParityError("installed TUI calendar child did not finish")
    product = installed_product_evidence(workspace_root=workspace_root)
    return {
        "schema_version": _SCHEMA,
        "status": "proven",
        "mode": mode,
        "product_origin": product.product_origin,
        "product_init_sha256": product.product_init_sha256,
        "product_init_path": str(assert_installed_product_origin(workspace_root=workspace_root)),
        "rows": observed,
        "work_units": work_units,
        "labels": _product_labels(),
    }


# ---------------------------------------------------------------------------
# Outer installed run
# ---------------------------------------------------------------------------


def _require_empty_directory(path: Path, *, label: str) -> Path:
    """Create one caller-owned directory only when it is fresh."""
    if path.exists() and any(path.iterdir()):
        raise CalendarParityError(f"{label} must be fresh and empty")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _resumed_cli_calendar(cli: InstalledCli, window: CalendarWindow) -> tuple[dict[str, CliCalendarRow], str]:
    """Read the calendar after a TUI login, resuming its session where the OS keychain allows.

    The product keeps a resumable session only in the OS keychain; without one it
    refuses to resume and accepts the stdin credential instead.  Either way the
    read is a fresh installed process over the same store the TUI wrote.
    """
    probe = cli.run(
        ("app", "overview", "calendar", "--from", window.from_date.isoformat(), "--to", window.from_date.isoformat()),
        command="overview.calendar.resume_probe",
        authenticated=False,
        allow_error=True,
    )
    error = probe.get("error")
    if probe.get("status") != "error":
        return _cli_calendar(cli, window, authenticated=False), "resumed_tui_session"
    if isinstance(error, dict) and error.get("code") == "AUTH_STORAGE_KEYRING_UNAVAILABLE":
        return _cli_calendar(cli, window, authenticated=True), "stdin_secret_os_keychain_unavailable"
    raise CalendarParityError("installed CLI could neither resume the TUI session nor report the keychain refusal")


def _cli_calendar(cli: InstalledCli, window: CalendarWindow, *, authenticated: bool) -> dict[str, CliCalendarRow]:
    """Read the calendar once as JSON and once as text through fresh installed processes."""
    arguments = (
        "app",
        "overview",
        "calendar",
        "--from",
        window.from_date.isoformat(),
        "--to",
        window.to_date.isoformat(),
        "--allow-incomplete",
    )
    try:
        document = cli.run(arguments, command="overview.calendar", authenticated=authenticated)
    except InstalledCliError as error:
        raise CalendarParityError(f"installed CLI calendar JSON failed: {error}") from error
    try:
        text = cli.run_text(arguments, authenticated=authenticated, command="overview.calendar")
    except InstalledCliError as error:
        raise CalendarParityError(f"installed CLI calendar text failed: {error}") from error
    return parse_cli_calendar(document, text)


def _cli_create_work(cli: InstalledCli, *, modelo: str, year: int, period: str) -> None:
    """Create one filing-period work unit through the public CLI verb."""
    try:
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                modelo,
                "--year",
                str(year),
                "--period",
                period,
                "--by",
                _ACTOR,
            ),
            command="modelo.work.create",
        )
    except InstalledCliError as error:
        raise CalendarParityError(f"installed CLI work create failed: {error}") from error


def _run_tui_child(
    args: argparse.Namespace,
    *,
    python_executable: Path,
    authority_root: Path,
    store: Path,
    receipt: Path,
    passphrase: str,
    mode: ChildMode,
    write_row: str | None = None,
) -> dict[str, Any]:
    """Run one stdin-credentialed installed TUI child and return its receipt."""
    child_args = ["--child", mode, "--workspace-root", str(args.workspace_root), "--receipt", str(receipt)]
    if write_row is not None:
        child_args += ["--write-row", write_row]
    child = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=args.workspace_root,
        child_module="dev.acceptance.calendar.installed_parity",
        child_args=tuple(child_args),
        storage_root=store,
        receipt_path=receipt,
        passphrase=passphrase,
        authority_root=authority_root,
        timeout_seconds=1800,
    )
    document = json.loads(receipt.read_text(encoding="utf-8"))
    if child.returncode != 0 or document.get("status") != "proven":
        cause = document.get("error") or document.get("diagnostic") or "no sanitized cause"
        raise CalendarParityError(f"installed TUI calendar {mode} child failed: {cause}")
    if document.get("product_origin") != "site-packages":
        raise CalendarParityError("installed TUI calendar child did not import the installed product")
    return document


def _tui_fields(document: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    return {
        key: {name: value for name, value in row.items() if name != "rendered"} for key, row in document["rows"].items()
    }


def _scenario(name: str, comparisons: list[dict[str, object]], **extra: object) -> dict[str, object]:
    failed = [item for item in comparisons if item["mismatched"]]
    continuation_lost = extra.get("written_work_visible_in_other_frontend") is False
    return {
        "scenario": name,
        "outcome": "failed" if failed or continuation_lost else "proven",
        "rows_compared": len(comparisons),
        "fields_per_row": len(COMPARED_FIELDS),
        "mismatches": failed,
        **extra,
    }


def _run_outer(args: argparse.Namespace, progress: dict[str, object]) -> dict[str, object]:
    """Run the four store scenarios and compare every calendar row the two frontends state."""
    cli_executable = args.cli.resolve(strict=True)
    python_executable = args.python.resolve(strict=True)
    if cli_executable.parent != python_executable.parent:
        raise CalendarParityError("installed CLI and TUI child Python do not belong to one environment")
    authority_root = args.authority_root.resolve(strict=True)
    root = _require_empty_directory(args.output_root, label="calendar parity output root")
    window = CalendarWindow.for_evaluation(datetime.now(ZoneInfo("Europe/Madrid")).date())
    profile_year = window.from_date.year
    cli_row = tui_row_key(_WRITE_MODELO, profile_year, _CLI_WRITE_PERIOD)
    tui_row = tui_row_key(_WRITE_MODELO, profile_year, _TUI_WRITE_PERIOD)

    def store(name: str) -> tuple[Path, InstalledCli, str]:
        path = _require_empty_directory(root / name, label=f"{name} secure store")
        passphrase = secrets.token_urlsafe(32)
        cli = InstalledCli(cli_executable, storage_root=path, authority_root=authority_root, passphrase=passphrase)
        try:
            cli.create_profile(year=profile_year)
        except InstalledCliError as error:
            raise CalendarParityError(f"{name}: installed CLI profile admission failed: {error}") from error
        return path, cli, passphrase

    def child(path: Path, passphrase: str, name: str, mode: ChildMode, write_row: str | None = None) -> dict[str, Any]:
        return _run_tui_child(
            args,
            python_executable=python_executable,
            authority_root=authority_root,
            store=path,
            receipt=root / f"{name}-tui.json",
            passphrase=passphrase,
            mode=mode,
            write_row=write_row,
        )

    completed: list[dict[str, object]] = []
    progress["completed_scenarios"] = completed
    progress["source_commit"] = args.source_commit
    progress["wheel_sha256"] = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    progress["authority_generation"] = authority_generation(authority_root)
    progress["calendar_window"] = {"from": window.from_date.isoformat(), "to": window.to_date.isoformat()}

    # Independent stores: one frontend reads each.
    _, cli_only, _ = store("cli_only")
    cli_rows = _cli_calendar(cli_only, window, authenticated=True)
    tui_only_path, _, tui_only_secret = store("tui_only")
    tui_only = child(tui_only_path, tui_only_secret, "tui_only", "inspect")
    labels = tui_only["labels"]
    independent = _scenario("independent_stores", compare_rows(cli_rows, _tui_fields(tui_only), labels))
    completed.append(independent)

    # CLI -> TUI: the CLI writes local work, the TUI must state it.
    c2t_path, c2t_cli, c2t_secret = store("cli_to_tui")
    if cli_rows[cli_row].work_unit_id is not None:
        raise CalendarParityError("a fresh store already carried local work for the continuation row")
    _cli_create_work(c2t_cli, modelo=_WRITE_MODELO, year=profile_year, period=_CLI_WRITE_PERIOD)
    c2t_rows = _cli_calendar(c2t_cli, window, authenticated=True)
    cli_work = c2t_rows[cli_row].work_unit_id
    if cli_work is None:
        raise CalendarParityError("installed CLI calendar did not attach the CLI-created work to its row")
    c2t_tui = child(c2t_path, c2t_secret, "cli_to_tui", "inspect")
    cli_to_tui = _scenario(
        "cli_to_tui",
        compare_rows(c2t_rows, _tui_fields(c2t_tui), labels),
        written_row=cli_row,
        written_work_visible_in_other_frontend=cli_work in c2t_tui["work_units"],
    )
    completed.append(cli_to_tui)

    # TUI -> CLI: the TUI calendar writes local work, the resumed CLI must state it.
    t2c_path, t2c_cli, t2c_secret = store("tui_to_cli")
    t2c_tui = child(t2c_path, t2c_secret, "tui_to_cli", "create_then_inspect", write_row=tui_row)
    t2c_rows, t2c_authentication = _resumed_cli_calendar(t2c_cli, window)
    tui_work = t2c_rows[tui_row].work_unit_id
    tui_to_cli = _scenario(
        "tui_to_cli",
        compare_rows(t2c_rows, _tui_fields(t2c_tui), labels),
        written_row=tui_row,
        written_work_visible_in_other_frontend=tui_work is not None and tui_work in t2c_tui["work_units"],
        cli_authentication=t2c_authentication,
    )

    product_hashes = {document["product_init_sha256"] for document in (tui_only, c2t_tui, t2c_tui)}
    if len(product_hashes) != 1:
        raise CalendarParityError("installed TUI children imported different products")
    scenarios = [independent, cli_to_tui, tui_to_cli]
    evaluation_dates = {row.evaluated_on for rows in (cli_rows, c2t_rows, t2c_rows) for row in rows.values()}
    coverage_states = sorted({row.holidays_text for row in cli_rows.values()})
    return {
        "schema_version": _SCHEMA,
        "status": "proven" if all(item["outcome"] == "proven" for item in scenarios) else "failed",
        "pattern_revision": _PATTERN_REVISION,
        "brief_revision": _BRIEF_REVISION,
        "source_commit": args.source_commit,
        "wheel_filename": args.wheel.name,
        "wheel_sha256": hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
        "authority_generation": authority_generation(authority_root),
        "product_origin": "site-packages",
        "product_init_path": t2c_tui["product_init_path"],
        "product_init_sha256": product_hashes.pop(),
        "evaluation_date": sorted(evaluation_dates),
        "calendar_window": {"from": window.from_date.isoformat(), "to": window.to_date.isoformat()},
        "profile_admission": "public_cli_profile_create",
        "compared_fields": list(COMPARED_FIELDS),
        "holiday_coverage_statements_seen": len(coverage_states),
        "scenarios": scenarios,
        "not_exercised": {
            "live_aeat": "live AEAT access is blocked by the operator",
            "unlinked_notification": (
                "notifications enter a store only through the live pull; no offline public ingestion"
            ),
        },
        "cli_json_command_count": sum(len(cli.commands) for cli in (cli_only, c2t_cli, t2c_cli)),
        "tui_child_process_count": 3,
        "synthetic_stores_retained": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=("inspect", "create_then_inspect"))
    parser.add_argument("--write-row")
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def _failure_document(error: Exception, progress: Mapping[str, object] | None = None) -> dict[str, object]:
    """Reduce a failure to its type, the value-free stage message and the progress already proven."""
    if isinstance(error, CalendarParityError):
        diagnostic = str(error)
    elif isinstance(error, (InstalledTuiChildError, InstalledCliError)):
        diagnostic = "installed frontend or command failed"
    else:
        diagnostic = "unexpected installed calendar parity failure"
    return {
        "schema_version": _SCHEMA,
        "status": "failed",
        "error_type": type(error).__name__,
        "diagnostic": diagnostic,
        **(progress or {}),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed outer calendar parity or one stdin-credentialed TUI child."""
    args = _parser().parse_args(argv)
    progress: dict[str, object] = {}
    try:
        if args.child is not None:
            document = _run_child(
                workspace_root=args.workspace_root,
                mode=args.child,
                write_row=args.write_row,
                passphrase=read_passphrase_from_stdin(),
            )
        else:
            required = (args.cli, args.python, args.wheel, args.authority_root, args.output_root, args.source_commit)
            if None in required:
                raise CalendarParityError("installed calendar outer run lacks its wheel and source inputs")
            document = _run_outer(args, progress)
    except InstalledTuiChildError as error:
        if args.child is None:
            document = _failure_document(error, progress)
        else:
            write_installed_tui_failure_receipt(path=args.receipt, schema_version=_SCHEMA, error=error)
            return 2
    except Exception as error:
        document = _failure_document(error, progress)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if document["status"] == "proven" else 2


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
