"""Installed CLI/TUI continuation acceptance driver for INCOME-01.

Each direction uses one isolated secure store.  The first frontend leaves a
complete profile, eight reconciled ledger facts and a locally filed 1T M130;
the second frontend reopens that state through its public surface, completes
2T--4T and Modelo 100, and validates the annual XML against the official XSD.
Receipts deliberately retain only counts, lifecycle coordinates and hashes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, cast

from dev.acceptance.installed_cli import InstalledCli, InstalledCliError

from .cli_journey import (
    JourneyError,
    _calculate_m100,
    _calculate_m130_work,
    _create_m130_work,
    _verify_and_file_m130,
    command_result,
    ingest_income_fixture,
)
from .installed_tui_child import (
    InstalledTuiChildError,
    admit_installed_session,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    register_profile_through_installed_tui,
    run_installed_tui_child_process,
    select_public_data_table_row,
    wait_for_public_selector,
    write_installed_tui_failure_receipt,
)
from .installed_tui_financial_child import (
    _apply_annual_edits,
    _capture_invoice,
    _classify_transaction,
    _configure_profile,
    _create_calendar_work,
    _import_transactions,
    _m130_expected,
    _open_destination,
    _open_work,
    _parse_m130_artifact,
    _reconcile_invoice,
    _run_lifecycle,
    _transaction_csv,
    _transaction_row_ids,
    _validate_annual_artifact,
    _work_ids_by_period,
)
from .scenario import build_scenario
from .tui_journey import (
    ContinuationStateEvidence,
    activate_tui_operation,
    canonical_financial_value_fingerprint,
    create_continuation_checkpoint,
    installed_lifecycle_contract,
    prove_continuation,
)

_SCHEMA_VERSION = "income-01-installed-continuations-v1"
_Direction = Literal["cli_to_tui", "tui_to_cli"]


class InstalledContinuationError(RuntimeError):
    """Raised when either installed frontend cannot prove its continuation."""


@dataclass(frozen=True, slots=True)
class ContinuationPathReceipt:
    """Sanitized result for one ordered installed frontend continuation."""

    direction: _Direction
    status: Literal["proven"]
    year: int
    product_origin: str
    product_init_sha256: str
    handoff_state_sha256: str
    resumed_state_sha256: str
    completion_state_sha256: str
    transactions: int
    invoices: int
    links: int
    locally_filed_periods: tuple[str, ...]
    annual_xsd_valid: bool
    annual_xsd_error_count: int
    oracle_value_fingerprint: str
    unexercised: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a receipt with no credentials or financial values."""
        return cast("dict[str, object]", asdict(self))


@dataclass(frozen=True, slots=True)
class InstalledContinuationEvidence:
    """Receipt for both independently isolated continuation directions."""

    schema_version: str
    status: Literal["proven"]
    paths: tuple[ContinuationPathReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe outer receipt."""
        return cast("dict[str, object]", asdict(self))


def _authority_generation(authority_root: Path) -> str:
    descriptor = json.loads((authority_root / "authority.current.json").read_text(encoding="utf-8"))
    generation = descriptor.get("logical_generation")
    if not isinstance(generation, str) or len(generation) != 64:
        raise InstalledContinuationError("authority descriptor has no SHA-256 logical generation")
    return generation


async def _login_existing_profile_through_tui(*, passphrase: str) -> None:
    """Use the installed Login screen to unlock the CLI-created profile."""
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
        raise InstalledTuiChildError("installed TUI login did not recognize the CLI-created profile")
    with bundled_indexed_authority().operation() as operation:
        screen = LoginScreen(
            choices=inventory.choices,
            authenticate=lambda profile_id, secret: attempt_profile_login(
                profile_id, secret, profile_decode_context=operation.profile_decode_context()
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
        raise InstalledTuiChildError("installed TUI Login screen did not admit the CLI-created profile")


def _oracle_fingerprint(year: int) -> str:
    """Fingerprint the independent scenario oracle, never a frontend readback."""
    scenario = build_scenario(year)
    values: dict[str, str] = {}
    for oracle in scenario.quarter_oracle:
        values.update({f"130.{oracle.period}.{key}": value for key, value in _m130_expected(oracle).items()})
    annual = scenario.annual_oracle
    values.update(
        {
            "100.0A.E1INGRESO": f"{annual.activity_income:.2f}",
            "100.0A.E1NGD": f"{annual.deductible_expenses:.2f}",
            "100.0A.E1RN": f"{annual.activity_net_income:.2f}",
            "100.0A.PAGOS": f"{annual.m130_payments:.2f}",
        }
    )
    return canonical_financial_value_fingerprint(values=values)


def _state(
    *, generation: str, year: int, periods: Sequence[str], filed: Sequence[str], annual_exported: bool
) -> ContinuationStateEvidence:
    quarter_periods = tuple(sorted(set(periods)))
    filed_periods = tuple(sorted(set(filed)))
    return ContinuationStateEvidence(
        authority_generation=generation,
        profile_complete=True,
        transactions=8,
        invoices=8,
        links=8,
        work_periods=quarter_periods,
        calculated_periods=filed_periods,
        verified_periods=filed_periods,
        locally_filed_periods=filed_periods,
        export_ready_modelos=("100",) if annual_exported else (),
        exported_modelos=("100",) if annual_exported else (),
        # The shared continuation contract currently carries one fingerprint.
        # This is explicitly an oracle guard; the receipt labels it as such and
        # keeps cross-frontend observed-value equality unexercised.
        canonical_value_fingerprint=_oracle_fingerprint(year),
    )


def _require_empty(path: Path, *, label: str) -> Path:
    if path.exists() and any(path.iterdir()):
        raise InstalledContinuationError(f"{label} must be fresh and empty")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _annual_schema(workspace_root: Path, year: int) -> Path:
    candidates = tuple(
        (workspace_root / "src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files").glob(
            f"*-100-esquema-xsd-ejercicio-{year}-*.xsd"
        )
    )
    if len(candidates) != 1:
        raise InstalledContinuationError("selected Modelo 100 revision has no unambiguous official XSD")
    return candidates[0]


def _parse_child_state(document: dict[str, object], key: str) -> ContinuationStateEvidence:
    raw = document.get(key)
    if not isinstance(raw, dict):
        raise InstalledContinuationError(f"TUI continuation receipt has no {key}")
    tuple_fields = (
        "work_periods",
        "calculated_periods",
        "verified_periods",
        "locally_filed_periods",
        "export_ready_modelos",
        "exported_modelos",
    )
    decoded = dict(raw)
    for name in tuple_fields:
        value = decoded.get(name)
        if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
            raise InstalledContinuationError(f"TUI continuation receipt has invalid {key}.{name}")
        decoded[name] = tuple(value)
    try:
        return ContinuationStateEvidence(**decoded)
    except TypeError as exc:
        raise InstalledContinuationError(f"TUI continuation receipt has invalid {key}") from exc


def _public_work_units(cli: InstalledCli, *, year: int) -> dict[str, dict[str, object]]:
    """Read the four partial work units from the installed CLI list surface."""
    listing = command_result(cli.run(("app", "modelo", "work", "list")))
    units = listing.get("work_units")
    if not isinstance(units, list):
        raise InstalledContinuationError("installed CLI work list returned no public work-unit collection")
    selected: dict[str, dict[str, object]] = {}
    for unit in units:
        if not isinstance(unit, dict) or unit.get("modelo") != "130" or unit.get("filing_year") != year:
            continue
        period_value = unit.get("period")
        period = (
            period_value.get("code")
            if isinstance(period_value, dict) and period_value.get("filing_year") == year
            else None
        )
        work_id = unit.get("work_unit_id")
        if not isinstance(period, str) or not isinstance(work_id, str) or not work_id or period in selected:
            raise InstalledContinuationError("installed CLI work list has ambiguous Modelo 130 public work identities")
        selected[period] = unit
    if set(selected) != {"1T", "2T", "3T", "4T"}:
        raise InstalledContinuationError("installed CLI work list did not publicly reproduce the four-unit handoff")
    return selected


def _cli_public_readback(cli: InstalledCli, *, generation: str, year: int) -> ContinuationStateEvidence:
    ledger = command_result(cli.run(("app", "ledger", "list")))
    rows = ledger.get("rows")
    if not isinstance(rows, list) or len(rows) != 8:
        raise InstalledContinuationError("installed CLI ledger list did not publicly reproduce eight transactions")
    invoices = command_result(cli.run(("app", "ledger", "invoice", "list")))
    invoice_rows = invoices.get("rows")
    if (
        invoices.get("count") != 8
        or not isinstance(invoice_rows, list)
        or any(
            not isinstance(row, dict)
            or not isinstance(row.get("linked_transaction_ids"), list)
            or len(row["linked_transaction_ids"]) != 1
            for row in invoice_rows
        )
    ):
        raise InstalledContinuationError("installed CLI invoice list did not publicly reproduce eight invoice links")
    units = _public_work_units(cli, year=year)
    q1 = units["1T"]
    if not isinstance(q1.get("filed_calculation_revision_id"), str) or not isinstance(
        q1.get("current_filing_record_id"), str
    ):
        raise InstalledContinuationError("installed CLI work list did not publicly prove the Q1 local filing")
    periods = tuple(sorted(units))
    return _state(generation=generation, year=year, periods=periods, filed=("1T",), annual_exported=False)


def _cli_complete(
    *, cli: InstalledCli, workspace_root: Path, output_dir: Path, generation: str, year: int
) -> tuple[ContinuationStateEvidence, dict[str, object]]:
    existing_units = _public_work_units(cli, year=year)
    for oracle in build_scenario(year).quarter_oracle[1:]:
        work_id = str(existing_units[oracle.period]["work_unit_id"])
        _actual, revision = _calculate_m130_work(cli, work_id=work_id, oracle=oracle)
        _verify_and_file_m130(cli, revision_id=revision, period=oracle.period)
    annual = _calculate_m100(cli, year=year, output_dir=output_dir)
    if annual.get("export_execution") != "proven":
        diagnostic = annual.get("diagnostic_code")
        raise InstalledContinuationError(
            "installed CLI did not export Modelo 100 for XSD validation"
            + (f"; diagnostic_code={diagnostic}" if isinstance(diagnostic, str) else "")
        )
    xml_path = output_dir / f"modelo-100-{year}-0A.xml"
    _values, validation = _validate_annual_artifact(
        xml_path=xml_path, xsd_path=_annual_schema(workspace_root, year), scenario=build_scenario(year)
    )
    if validation.get("xsd_valid") is not True:
        raise InstalledContinuationError("installed CLI Modelo 100 export failed official XSD validation")
    return _state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T", "0A"),
        filed=("1T", "2T", "3T", "4T"),
        annual_exported=True,
    ), validation


def _assert_cli_q1_public_artifact(*, cli: InstalledCli, output_dir: Path, year: int) -> None:
    """Export and independently compare the already-filed Q1 public artifact."""
    q1 = _public_work_units(cli, year=year)["1T"]
    work_id = q1["work_unit_id"]
    if not isinstance(work_id, str):
        raise InstalledContinuationError("installed CLI Q1 work has no public work identity")
    artifact = output_dir / f"modelo-130-{year}-1T-readback.boe"
    cli.run(("app", "modelo", "export", work_id, "--output", str(artifact), "--by", "income-acceptance"))
    _parse_m130_artifact(
        path=artifact,
        year=year,
        period="1T",
        expected=_m130_expected(build_scenario(year).quarter_oracle[0]),
    )


async def _assert_tui_partial_readback(*, pilot: Any, scenario: Any, year: int) -> dict[str, str]:
    """Require visible entries, resolved links, and a Q1 local filing history row."""
    from textual.widgets import DataTable

    rows = await _transaction_row_ids(pilot, scenario=scenario)
    works = await _work_ids_by_period(pilot, year=year)
    if len(rows) != 8 or set(works) != {"1T", "2T", "3T", "4T"}:
        raise InstalledTuiChildError("installed TUI did not publicly reproduce the four-unit partial workflow")

    await _open_destination(pilot, query="ledger", expected_selector="#ledger-navigation")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#ledger-navigation",
        row_key="reconciliation",
    )
    await wait_for_public_selector(pilot, "#ledger-suggestions")
    suggestions = query_public_selector(pilot, "#ledger-suggestions", DataTable)
    inconsistencies = query_public_selector(pilot, "#ledger-inconsistencies", DataTable)
    if suggestions.row_count or inconsistencies.row_count:
        raise InstalledTuiChildError("installed TUI reconciliation publicly reports unresolved invoice links")

    await _open_destination(pilot, query="declarations", expected_selector="#declarations-list")
    await select_public_data_table_row(
        pilot=pilot,
        table_selector="#declarations-navigation",
        row_key="declarations.filing_history",
    )
    await wait_for_public_selector(pilot, "#declarations-filings")
    filings = query_public_selector(pilot, "#declarations-filings", DataTable)
    q1_filing = any(
        str(row_key.value).startswith("filing:")
        and f"Modelo 130 · {year} · 1T" in " ".join(str(cell) for cell in filings.get_row(row_key))
        for row_key in filings.rows
    )
    if not q1_filing:
        raise InstalledTuiChildError("installed TUI filing history did not publicly prove the Q1 local filing")
    return works


async def _export_visible_m130(
    *, pilot: Any, export_path: Path, work_unit_id: str, year: int, period: str
) -> dict[str, str]:
    """Export an already-filed quarterly work through its visible TUI control."""
    from textual.widgets import Input

    await _open_work(pilot, work_unit_id=work_unit_id)
    query_public_selector(pilot, "#modelo-lifecycle-export-path", Input).value = str(export_path)
    contract = installed_lifecycle_contract(
        profile_selection_id="#manager-status",
        ledger_capture_id="#ledger-import-confirm",
        invoice_link_id="#ledger-reconciliation-confirm",
        work_create_id="#declarations-calendar-agenda",
    )
    terminal = await activate_tui_operation(pilot, binding=contract.export)
    if terminal.outcome.value != "proven":
        raise InstalledTuiChildError("installed TUI did not export the public Q1 work artifact")
    return _parse_m130_artifact(
        path=export_path,
        year=year,
        period=period,
        expected=_m130_expected(next(item for item in build_scenario(year).quarter_oracle if item.period == period)),
    )


def run_tui_continuation_child(
    *, direction: _Direction, workspace_root: Path, profile_label: str, passphrase: str, year: int, scratch: Path
) -> dict[str, object]:
    """Run the TUI side of one continuation through an installed launcher."""
    product = installed_product_evidence(workspace_root=workspace_root)
    scenario = build_scenario(year)
    authority_root = Path(os.environ["CADRUMO_AUTHORITY_ROOT"]).resolve()
    generation = _authority_generation(authority_root)
    handoff: ContinuationStateEvidence | None = None
    completion: ContinuationStateEvidence | None = None
    validation: dict[str, object] = {}
    readback_error: str | None = None
    callback_entered = False

    from cadrumo.entrypoints.tui.launcher import main

    if direction == "tui_to_cli":
        from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
        from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

        with live_exchange_rate_composition(), profile_adapter_composition():
            asyncio.run(register_profile_through_installed_tui(profile_label=profile_label, passphrase=passphrase))
    else:
        from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
        from cadrumo.entrypoints.exchange_rate_composition import live_exchange_rate_composition

        with live_exchange_rate_composition(), profile_adapter_composition():
            asyncio.run(_login_existing_profile_through_tui(passphrase=passphrase))

    async def drive(pilot: Any) -> None:
        nonlocal handoff, completion, validation, readback_error
        if direction == "cli_to_tui":
            try:
                works = await _assert_tui_partial_readback(pilot=pilot, scenario=scenario, year=year)
                await _export_visible_m130(
                    pilot=pilot,
                    export_path=scratch / f"modelo-130-{year}-1T-readback.boe",
                    work_unit_id=works["1T"],
                    year=year,
                    period="1T",
                )
            except InstalledTuiChildError as error:
                readback_error = str(error)
                pilot.app.exit()
                return
            except Exception as error:
                readback_error = f"unexpected continuation readback failure: {type(error).__name__}"
                pilot.app.exit()
                return
            handoff = _state(
                generation=generation,
                year=year,
                periods=("1T", "2T", "3T", "4T"),
                filed=("1T",),
                annual_exported=False,
            )
        else:
            await _configure_profile(pilot, scenario=scenario)
            csv_path = _transaction_csv(scenario=scenario, directory=scratch)
            await _import_transactions(pilot, csv_path=csv_path)
            rows = await _transaction_row_ids(pilot, scenario=scenario)
            if len(rows) != 8:
                raise InstalledTuiChildError("installed TUI Entries did not expose all eight transactions")
            for item in (*scenario.income, *scenario.expenses):
                await _classify_transaction(pilot, transaction_id=rows[item.transaction_id], item=item)
                await _capture_invoice(pilot, item=item)
                await _reconcile_invoice(pilot, transaction_id=item.transaction_id, invoice_id=item.invoice_id)
            for period in ("1T", "2T", "3T", "4T"):
                await _create_calendar_work(pilot, modelo="130", year=year, period=period)
            works = await _work_ids_by_period(pilot, year=year)
            q1_export = scratch / f"modelo-130-{year}-1T.boe"
            await _run_lifecycle(pilot, export_path=q1_export, work_unit_id=works["1T"])
            _parse_m130_artifact(
                path=q1_export,
                year=year,
                period="1T",
                expected=_m130_expected(scenario.quarter_oracle[0]),
            )
            handoff = _state(
                generation=generation,
                year=year,
                periods=("1T", "2T", "3T", "4T"),
                filed=("1T",),
                annual_exported=False,
            )
            pilot.app.exit()
            return

        works = await _work_ids_by_period(pilot, year=year)
        for oracle in scenario.quarter_oracle[1:]:
            artifact = scratch / f"modelo-130-{year}-{oracle.period}.boe"
            await _run_lifecycle(pilot, export_path=artifact, work_unit_id=works[oracle.period])
            _parse_m130_artifact(path=artifact, year=year, period=oracle.period, expected=_m130_expected(oracle))
        await _create_calendar_work(pilot, modelo="100", year=year, period="0A")
        works = await _work_ids_by_period(pilot, year=year)
        await _apply_annual_edits(pilot, work_unit_id=works["0A"])
        annual_export = scratch / f"modelo-100-{year}-0A.xml"
        await _run_lifecycle(pilot, export_path=annual_export, work_unit_id=works["0A"], calculate=False)
        _values, validation = _validate_annual_artifact(
            xml_path=annual_export, xsd_path=_annual_schema(workspace_root, year), scenario=scenario
        )
        if validation.get("xsd_valid") is not True:
            raise InstalledTuiChildError("installed TUI Modelo 100 export failed official XSD validation")
        completion = _state(
            generation=generation,
            year=year,
            periods=("1T", "2T", "3T", "4T", "0A"),
            filed=("1T", "2T", "3T", "4T"),
            annual_exported=True,
        )
        pilot.app.exit()

    async def launched(pilot: Any) -> None:
        nonlocal callback_entered, readback_error
        callback_entered = True
        try:
            await admit_installed_session(pilot=pilot, passphrase=passphrase)
            await drive(pilot)
        except InstalledTuiChildError as error:
            readback_error = str(error)
            pilot.app.exit()
        except Exception as error:
            readback_error = f"unexpected continuation admission/workflow failure: {type(error).__name__}"
            pilot.app.exit()

    exit_code = main(headless=True, auto_pilot=launched)
    if readback_error is not None:
        raise InstalledTuiChildError(readback_error)
    if exit_code != 0 or handoff is None:
        raise InstalledTuiChildError(
            "installed continuation launcher did not reach its partial workflow boundary "
            f"(exit_code={exit_code}, callback_entered={callback_entered})"
        )
    document: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "status": "proven",
        "direction": direction,
        "product_origin": product.product_origin,
        "product_init_sha256": product.product_init_sha256,
        "handoff_state": asdict(handoff),
        "annual_xsd_validation": validation,
    }
    if completion is not None:
        document["completion_state"] = asdict(completion)
    return document


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
        failure = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
        reason = failure.get("error") if isinstance(failure, dict) else None
        if isinstance(reason, str) and reason.startswith(("modelo.", "unexpected ", "installed ")):
            raise InstalledContinuationError(f"installed TUI {direction} child: {reason}")
        raise InstalledContinuationError(f"installed TUI {direction} child did not prove its public workflow")
    document = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise InstalledContinuationError("installed TUI continuation receipt is not an object")
    return cast("dict[str, object]", document)


def run_installed_tui_continuations(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
    only_direction: _Direction | None = None,
) -> InstalledContinuationEvidence:
    """Prove CLI→TUI and TUI→CLI continuations in two separate secure stores."""
    root = _require_empty(output_root, label="continuation output root")
    generation = _authority_generation(authority_root)
    paths: list[ContinuationPathReceipt] = []

    if only_direction == "tui_to_cli":
        paths.append(
            _run_tui_to_cli_direction(
                root=root,
                generation=generation,
                year=year,
                cli_executable=cli_executable,
                python_executable=python_executable,
                workspace_root=workspace_root,
                authority_root=authority_root,
            )
        )
        return InstalledContinuationEvidence(schema_version=_SCHEMA_VERSION, status="proven", paths=tuple(paths))

    cli_store = _require_empty(root / "cli-to-tui-store", label="CLI-to-TUI store")
    cli_scratch = _require_empty(root / "cli-to-tui-artifacts", label="CLI-to-TUI artifacts")
    cli_passphrase = secrets.token_urlsafe(32)
    cli = InstalledCli(cli_executable, storage_root=cli_store, authority_root=authority_root, passphrase=cli_passphrase)
    cli.create_profile(year=year)
    ingest_income_fixture(cli, year=year)
    work_ids = {period: _create_m130_work(cli, year=year, period=period) for period in ("1T", "2T", "3T", "4T")}
    q1 = build_scenario(year).quarter_oracle[0]
    q1_work = work_ids["1T"]
    _actual, q1_revision = _calculate_m130_work(cli, work_id=q1_work, oracle=q1)
    _verify_and_file_m130(cli, revision_id=q1_revision, period="1T")
    cli_handoff = _state(
        generation=generation,
        year=year,
        periods=("1T", "2T", "3T", "4T"),
        filed=("1T",),
        annual_exported=False,
    )
    cli_checkpoint = create_continuation_checkpoint(frontend_path="cli_to_tui", state=cli_handoff)
    child = _run_child(
        direction="cli_to_tui",
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=cli_store,
        scratch=cli_scratch,
        passphrase=cli_passphrase,
        year=year,
    )
    tui_handoff = _parse_child_state(child, "handoff_state")
    tui_completion = _parse_child_state(child, "completion_state")
    proven = prove_continuation(
        checkpoint=cli_checkpoint, frontend="tui", resumed_state=tui_handoff, completion_state=tui_completion
    )
    validation = child.get("annual_xsd_validation", {})
    paths.append(
        ContinuationPathReceipt(
            "cli_to_tui",
            "proven",
            year,
            str(child["product_origin"]),
            str(child["product_init_sha256"]),
            cli_handoff.state_sha256(),
            proven.resumed_state_sha256,
            tui_completion.state_sha256(),
            8,
            8,
            8,
            tui_completion.locally_filed_periods,
            bool(isinstance(validation, dict) and validation.get("xsd_valid")),
            len(validation.get("error_identities", ())) if isinstance(validation, dict) else 0,
            _oracle_fingerprint(year),
            ("cross_frontend_public_value_fingerprint",),
        )
    )

    if only_direction == "cli_to_tui":
        return InstalledContinuationEvidence(schema_version=_SCHEMA_VERSION, status="proven", paths=tuple(paths))

    paths.append(
        _run_tui_to_cli_direction(
            root=root,
            generation=generation,
            year=year,
            cli_executable=cli_executable,
            python_executable=python_executable,
            workspace_root=workspace_root,
            authority_root=authority_root,
        )
    )
    return InstalledContinuationEvidence(schema_version=_SCHEMA_VERSION, status="proven", paths=tuple(paths))


def _run_tui_to_cli_direction(
    *,
    root: Path,
    generation: str,
    year: int,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
) -> ContinuationPathReceipt:
    """Run the independently owned TUI-to-CLI scenario in its own secure store."""
    tui_store = _require_empty(root / "tui-to-cli-store", label="TUI-to-CLI store")
    tui_scratch = _require_empty(root / "tui-to-cli-artifacts", label="TUI-to-CLI artifacts")
    tui_passphrase = secrets.token_urlsafe(32)
    child = _run_child(
        direction="tui_to_cli",
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=tui_store,
        scratch=tui_scratch,
        passphrase=tui_passphrase,
        year=year,
    )
    tui_handoff = _parse_child_state(child, "handoff_state")
    tui_checkpoint = create_continuation_checkpoint(frontend_path="tui_to_cli", state=tui_handoff)
    readback_cli = InstalledCli(
        cli_executable, storage_root=tui_store, authority_root=authority_root, passphrase=tui_passphrase
    )
    resumed = _cli_public_readback(
        readback_cli,
        generation=generation,
        year=year,
    )
    completing_cli = InstalledCli(
        cli_executable, storage_root=tui_store, authority_root=authority_root, passphrase=tui_passphrase
    )
    _assert_cli_q1_public_artifact(cli=completing_cli, output_dir=tui_scratch, year=year)
    completion, validation = _cli_complete(
        cli=completing_cli, workspace_root=workspace_root, output_dir=tui_scratch, generation=generation, year=year
    )
    proven = prove_continuation(
        checkpoint=tui_checkpoint, frontend="cli", resumed_state=resumed, completion_state=completion
    )
    return ContinuationPathReceipt(
        "tui_to_cli",
        "proven",
        year,
        str(child["product_origin"]),
        str(child["product_init_sha256"]),
        tui_handoff.state_sha256(),
        proven.resumed_state_sha256,
        completion.state_sha256(),
        8,
        8,
        8,
        completion.locally_filed_periods,
        bool(validation.get("xsd_valid")),
        len(cast("Sequence[object]", validation.get("error_identities", ()))),
        _oracle_fingerprint(year),
        ("cross_frontend_public_value_fingerprint",),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--year", type=int)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--child-direction", choices=("cli_to_tui", "tui_to_cli"))
    parser.add_argument("--only-direction", choices=("cli_to_tui", "tui_to_cli"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a parent receipt or one stdin-credentialed installed TUI child."""
    args = _parser().parse_args(argv)
    try:
        if args.child_direction:
            if args.year is None or args.output_root is not None:
                raise InstalledContinuationError("continuation child requires --year and no --output-root")
            if args.scratch is None:
                raise InstalledContinuationError("continuation child requires --scratch")
            evidence = run_tui_continuation_child(
                direction=args.child_direction,
                workspace_root=args.workspace_root,
                profile_label="income-continuation",
                passphrase=read_passphrase_from_stdin(),
                year=args.year,
                scratch=args.scratch,
            )
        else:
            if None in (args.cli, args.python, args.authority_root, args.output_root, args.year):
                raise InstalledContinuationError(
                    "parent continuation driver requires CLI, Python, authority, output root and year"
                )
            evidence = run_installed_tui_continuations(
                cli_executable=args.cli,
                python_executable=args.python,
                workspace_root=args.workspace_root,
                authority_root=args.authority_root,
                output_root=args.output_root,
                year=args.year,
                only_direction=args.only_direction,
            )
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(
                evidence.to_dict() if isinstance(evidence, InstalledContinuationEvidence) else evidence,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0
    except (JourneyError, InstalledCliError) as exc:
        phase = str(exc).split(":", 1)[0]
        safe_phases = {"profile creation failed", "CLI invocation failed", "CLI returned no JSON"}
        reason = phase if phase in safe_phases else "installed CLI partial workflow failed"
        trace = exc.__traceback__
        while trace is not None:
            if Path(trace.tb_frame.f_code.co_filename).name in {"cli_journey.py", "installed_tui_continuations.py"}:
                reason += f" [{trace.tb_frame.f_code.co_name}]"
            trace = trace.tb_next
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(reason),
        )
        return 2
    except (InstalledContinuationError, InstalledTuiChildError) as exc:
        write_installed_tui_failure_receipt(
            path=args.receipt, schema_version=_SCHEMA_VERSION, error=InstalledTuiChildError(str(exc))
        )
        return 2
    except Exception as exc:
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(f"unexpected continuation failure: {type(exc).__name__}"),
        )
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
