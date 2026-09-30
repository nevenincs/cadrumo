"""Focused receipt and local-XSD checks for the INCOME-01 TUI driver."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast, override

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Static

from cadrumo.domain.calculations.registry.authority_artifact import AuthorityGenerationPin
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from ..authority import IncomeTaxAuthorityResolution, resolve_income_tax_authority
from ..scenario import AcceptanceOutcome
from ..tui_journey import (
    AcceptanceCaseEvidence,
    ContinuationStateEvidence,
    InstalledTuiContract,
    LifecycleEvidence,
    LocalXsdValidationEvidence,
    TuiJourneyError,
    TuiOperationBinding,
    TuiTerminalEvidence,
    _observe_operation_terminal,
    activate_tui_operation,
    blocked_tui_journey_evidence,
    build_tui_journey_evidence,
    canonical_financial_value_fingerprint,
    create_continuation_checkpoint,
    installed_lifecycle_contract,
    prove_continuation,
    settled_notice_terminal,
    validate_modelo_100_xsd,
    wait_for_tui_refresh,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@dataclass(frozen=True, slots=True)
class _Support:
    floor: int


@dataclass(frozen=True, slots=True)
class _Revision:
    id: str
    export_layouts: tuple[ExportLayoutDefinition, ...]


@dataclass(frozen=True, slots=True)
class _Snapshot:
    revision: _Revision


class _Operation:
    @property
    def generation(self) -> AuthorityGenerationPin:
        return AuthorityGenerationPin(logical_generation="a" * 64, reader_incarnation="b" * 64)

    def supported_filing_years(self) -> _Support:
        return _Support(floor=2022)

    def snapshot(self, modelo: str, /, *, filing_year: int, period: str) -> _Snapshot:
        return _Snapshot(revision=_Revision(id=f"{modelo}-{filing_year}", export_layouts=()))


def _resolution() -> IncomeTaxAuthorityResolution:
    return resolve_income_tax_authority(_Operation(), as_of=date(2026, 9, 21))


def test_unavailable_tui_contract_is_blocked_without_claiming_submission() -> None:
    evidence = blocked_tui_journey_evidence(
        contract=InstalledTuiContract(),
        resolution=_resolution(),
        frontend_path="tui_to_cli",
    )

    by_id = {case.acceptance_id: case for case in evidence.cases}
    assert evidence.contract_missing_controls
    assert by_id["A1"].outcome is AcceptanceOutcome.BLOCKED
    assert by_id["A8"].outcome is AcceptanceOutcome.BLOCKED
    assert by_id["A2"].outcome is AcceptanceOutcome.NOT_EXERCISED
    assert by_id["A9"].lifecycle.export_execution is AcceptanceOutcome.BLOCKED
    assert by_id["A9"].lifecycle.local_filing is AcceptanceOutcome.BLOCKED
    assert by_id["A9"].lifecycle.submission is AcceptanceOutcome.NOT_EXERCISED


def test_installed_lifecycle_contract_uses_the_real_actions_without_claiming_entry_controls() -> None:
    contract = installed_lifecycle_contract()

    assert contract.work_open_id == "#declarations-list"
    assert contract.calculate.operation_id == "modelo.work.calculate"
    assert contract.calculate.activation_key == "c"
    assert contract.verify.activation_key == "f8"
    assert contract.verify.offered_step == "verify"
    assert contract.local_file.activation_key == "f8"
    assert contract.local_file.offered_step == "file"
    assert contract.local_file.confirmation_id == "#btn-confirm-accept"
    assert contract.export.activation_id == "#export-submit"
    assert contract.export.activation_key is None
    assert {binding.refusal_notice_id for binding in (contract.calculate, contract.verify, contract.export)} == {
        "#wb-notice"
    }
    assert "profile_selection" in contract.missing_controls()
    assert "calculate.activation" not in contract.missing_controls()


class _UnreadableDeclaration:
    """A workbench reader whose declaration cannot be read."""

    def load(self, language: object) -> object:
        raise RuntimeError("synthetic unreadable declaration")

    def help_card(self, casilla_id: object, language: object) -> object:
        raise RuntimeError("synthetic unreadable declaration")


def test_the_lifecycle_contract_drives_controls_the_real_workbench_and_its_dialogs_compose() -> None:
    """Every key is one the workbench binds and every id is on the screen that composes it."""
    from textual.widgets import Button, Input

    from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
    from cadrumo.entrypoints.tui.components.dialogs import ConfirmScreen
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.modelo.workbench.export import WorkbenchExportScreen
    from cadrumo.entrypoints.tui.modelo.workbench.ports import WorkbenchExportOffer
    from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen

    from ..tui_journey import WORKBENCH_NEXT, wait_for_workbench

    contract = installed_lifecycle_contract()
    keys = {binding.activation_key for binding in (contract.calculate, contract.verify, contract.local_file)}
    assert keys == {"c", "f8"}

    async def scenario() -> None:
        workbench = ModeloWorkbenchScreen(cast("Any", _UnreadableDeclaration()))
        app = ScreenHostApp(workbench)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            assert {"c", "f8", "e"} <= set(workbench.active_bindings)
            for selector in (
                contract.calculate.refusal_notice_id,
                contract.calculate.refresh_result_id,
                WORKBENCH_NEXT,
            ):
                assert selector is not None
                workbench.query_one(selector)
            with pytest.raises(TuiJourneyError, match="could not read its form"):
                await wait_for_workbench(pilot, seconds=10)
            app.push_screen(ConfirmScreen(title="t", message="m", confirm_label="a", cancel_label="c"))
            await pilot.pause()
            for selector in (contract.local_file.confirmation_id, contract.calculate.at_risk_proceed_id):
                assert selector is not None
                app.screen.query_one(selector, Button)
            app.pop_screen()
            offer = WorkbenchExportOffer(artefacts=(ModeloExportArtefact.FICHERO_BOE,), asks_elections=False)
            app.push_screen(WorkbenchExportScreen(offer))
            await pilot.pause()
            assert contract.export.activation_id is not None
            app.screen.query_one(contract.export.activation_id, Button)
            app.screen.query_one("#export-path", Input)

    asyncio.run(scenario())


def test_a_binding_naming_both_a_key_and_a_control_is_refused() -> None:
    binding = TuiOperationBinding(
        "modelo.work.calculate",
        activation_key="c",
        activation_id="#export-submit",
        terminal_result_id="#operation-modal-status",
        refresh_result_id="#wb-list",
        refusal_notice_id="#wb-notice",
    )

    async def scenario() -> None:
        app = _WidgetsApp(Static("", id="wb-notice"))
        async with app.run_test() as pilot:
            with pytest.raises(TuiJourneyError, match="both a key and a control"):
                await activate_tui_operation(pilot, binding=binding)

    asyncio.run(scenario())


class _NoPausePilot(Pilot[None]):
    """A real pilot that fails if the observed control is not visible on the first poll."""

    @override
    async def pause(self, delay: float | None = None) -> None:
        raise AssertionError("the observed control should be visible on the first poll")


class _WidgetsApp(App[None]):
    def __init__(self, *widgets: Static) -> None:
        super().__init__()
        self._widgets = widgets

    @override
    def compose(self) -> ComposeResult:
        yield from self._widgets


def test_refresh_destination_must_be_the_current_installed_screen() -> None:
    async def scenario() -> None:
        app = _WidgetsApp(Static(id="wb-list"))
        async with app.run_test():
            await wait_for_tui_refresh(
                _NoPausePilot(app),
                binding=TuiOperationBinding("modelo.work.calculate", refresh_result_id="#wb-list"),
                maximum_polls=1,
            )

    asyncio.run(scenario())


def test_the_refresh_wait_closes_the_statement_of_what_a_recalculation_changed() -> None:
    """The workbench is only back once the filer has closed the statement shown above it."""
    from cadrumo.entrypoints.tui.modelo.workbench.result import WorkbenchResultScreen

    async def scenario() -> None:
        app = _WidgetsApp(Static(id="wb-list"))
        async with app.run_test() as pilot:
            statement = WorkbenchResultScreen(())
            app.push_screen(statement)
            await pilot.pause()
            assert app.screen is statement
            await wait_for_tui_refresh(pilot, binding=installed_lifecycle_contract().calculate, maximum_polls=50)
            assert app.screen is not statement
            app.screen.query_one("#wb-list")

    asyncio.run(scenario())


def test_an_operation_never_starts_under_an_earlier_workbench_notice() -> None:
    """A notice left by the previous operation could otherwise be read as this one's result."""
    from cadrumo.core.i18n.render import tr

    async def scenario() -> None:
        app = _WidgetsApp(Static(tr("tui.modelo.workbench.operation.done"), id="wb-notice"))
        async with app.run_test() as pilot:
            with pytest.raises(TuiJourneyError, match="earlier workbench notice"):
                await activate_tui_operation(pilot, binding=installed_lifecycle_contract().calculate)

    asyncio.run(scenario())


def test_the_next_step_key_is_refused_while_the_workbench_offers_another_step() -> None:
    """F8 runs whatever step is offered; pressing it while filling is offered would not verify."""
    from cadrumo.core.i18n.render import tr

    fill_offered = tr("tui.modelo.workbench.next_line", action=tr("tui.modelo.workbench.next.fill", count=2), key="n")

    async def scenario() -> None:
        app = _WidgetsApp(Static("", id="wb-notice"), Static(fill_offered, id="wb-next"))
        async with app.run_test() as pilot:
            with pytest.raises(TuiJourneyError, match="does not offer verify"):
                await activate_tui_operation(pilot, binding=installed_lifecycle_contract().verify)

    asyncio.run(scenario())


def _workbench_notice(copy_key: str, explanation: str | None = None) -> str:
    from cadrumo.core.i18n.render import tr

    copy = tr(copy_key)
    return copy if explanation is None else f"{copy} {explanation}"


@pytest.mark.parametrize(
    ("copy_key", "explanation", "expected"),
    [
        ("tui.modelo.workbench.operation.done", None, ("succeeded", AcceptanceOutcome.PROVEN)),
        ("tui.modelo.workbench.result_diff.nothing_changed", None, ("succeeded", AcceptanceOutcome.PROVEN)),
        (
            "tui.modelo.workbench.operation.not_done",
            "The attestation belongs to another quarter.",
            ("refused", AcceptanceOutcome.BLOCKED),
        ),
        ("tui.modelo.workbench.operation.not_done", None, ("not_completed", AcceptanceOutcome.FAILED)),
        ("tui.modelo.workbench.operation.not_done", "   ", None),
        ("tui.modelo.workbench.operation.done", "and something else", None),
        ("tui.modelo.m303_evidence.cancelled", None, None),
    ],
)
def test_a_settled_workbench_notice_is_its_sentence_alone_or_followed_by_a_refusal_explanation(
    copy_key: str, explanation: str | None, expected: tuple[str, AcceptanceOutcome] | None
) -> None:
    assert settled_notice_terminal(_workbench_notice(copy_key, explanation)) == expected


def test_a_notice_that_only_starts_like_a_settled_sentence_is_not_a_terminal() -> None:
    from cadrumo.core.i18n.render import tr

    assert settled_notice_terminal(tr("tui.modelo.workbench.operation.not_done") + "x") is None
    assert settled_notice_terminal("") is None


@pytest.mark.parametrize(
    ("copy_key", "explanation", "condition"),
    [
        ("tui.modelo.workbench.operation.not_done", "The attestation belongs to another quarter.", "refused"),
        ("tui.modelo.workbench.operation.done", None, "succeeded"),
    ],
)
def test_a_modal_that_dismissed_itself_settles_from_the_workbench_notice(
    copy_key: str, explanation: str | None, condition: str
) -> None:
    """The modal closes the moment its operation is terminal; the lasting notice carries the result."""
    from textual.css.query import NoMatches

    notice = _workbench_notice(copy_key, explanation)

    class DismissedModal:
        is_mounted = False

        def query_one(self, selector: str) -> object:
            raise NoMatches(selector)

    async def scenario() -> TuiTerminalEvidence:
        app = _WidgetsApp(Static(notice, id="wb-notice"))
        async with app.run_test():
            return await _observe_operation_terminal(
                _NoPausePilot(app),
                modal=DismissedModal(),
                binding=TuiOperationBinding(
                    "modelo.work.calculate",
                    terminal_result_id="#operation-modal-status",
                    refusal_notice_id="#wb-notice",
                ),
                maximum_polls=1,
            )

    terminal = asyncio.run(scenario())

    assert terminal.terminal_condition == condition
    assert terminal.receipt_present is False


def test_xsd_validation_records_original_and_effective_schema_identities(tmp_path: Path) -> None:
    xsd = tmp_path / "minimal.xsd"
    xml = tmp_path / "document.xml"
    xsd.write_text(
        """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<xs:schema xmlns:xs=\"http://www.w3.org/2001/XMLSchema\">
  <xs:element name=\"Declaracion\" type=\"xs:string\"/>
</xs:schema>
""",
        encoding="utf-8",
    )
    xml.write_text("<Declaracion>synthetic</Declaracion>", encoding="utf-8")

    evidence = validate_modelo_100_xsd(xml_path=xml, xsd_path=xsd)

    assert evidence.xsd_valid is True
    assert evidence.normalization_count == 0
    assert evidence.error_identities == ()
    assert evidence.original_schema_sha256 == evidence.effective_validation_schema_sha256


def _continuation_state(*, complete: bool = False) -> ContinuationStateEvidence:
    periods = ("1T", "2T", "3T", "4T") if complete else ("1T",)
    return ContinuationStateEvidence(
        authority_generation="a" * 64,
        profile_complete=True,
        transactions=2,
        invoices=2,
        links=2,
        work_periods=periods,
        calculated_periods=periods,
        verified_periods=periods,
        locally_filed_periods=periods,
        export_ready_modelos=("100",) if complete else ("130",),
        exported_modelos=("100",) if complete else (),
        canonical_value_fingerprint="b" * 64,
    )


def test_continuation_requires_public_readback_before_the_receiving_frontend_completes() -> None:
    handoff = _continuation_state()
    checkpoint = create_continuation_checkpoint(frontend_path="cli_to_tui", state=handoff)

    evidence = prove_continuation(
        checkpoint=checkpoint,
        frontend="tui",
        resumed_state=handoff,
        completion_state=_continuation_state(complete=True),
    )

    assert checkpoint.handoff_frontend == "cli"
    assert checkpoint.resume_frontend == "tui"
    assert evidence.outcome is AcceptanceOutcome.PROVEN
    assert evidence.resumed_state_sha256 == checkpoint.state_sha256
    assert evidence.completion_state.canonical_value_fingerprint == handoff.canonical_value_fingerprint


def test_continuation_rejects_a_completed_handoff_or_the_wrong_receiving_frontend() -> None:
    with pytest.raises(TuiJourneyError, match="already complete"):
        create_continuation_checkpoint(frontend_path="tui_to_cli", state=_continuation_state(complete=True))

    checkpoint = create_continuation_checkpoint(frontend_path="tui_to_cli", state=_continuation_state())
    with pytest.raises(TuiJourneyError, match="must resume through cli"):
        prove_continuation(
            checkpoint=checkpoint,
            frontend="tui",
            resumed_state=_continuation_state(),
            completion_state=_continuation_state(complete=True),
        )


def _proven_case(acceptance_id: str) -> AcceptanceCaseEvidence:
    return AcceptanceCaseEvidence(
        acceptance_id=acceptance_id,
        outcome=AcceptanceOutcome.PROVEN,
        lifecycle=LifecycleEvidence(
            calculation=AcceptanceOutcome.PROVEN,
            verification=AcceptanceOutcome.PROVEN,
            export_readiness=AcceptanceOutcome.PROVEN,
            export_execution=AcceptanceOutcome.PROVEN,
            local_filing=AcceptanceOutcome.PROVEN,
            submission=AcceptanceOutcome.NOT_EXERCISED,
        ),
        source_state="installed_tui_public_controls",
    )


def test_final_receipt_keeps_financial_readback_hashed_and_requires_validated_export() -> None:
    contract = installed_lifecycle_contract(
        profile_selection_id="#manager-status",
        ledger_capture_id="#ledger-import-confirm",
        invoice_link_id="#ledger-reconciliation-confirm",
        work_create_id="#declarations-calendar-agenda",
    )
    fingerprint = canonical_financial_value_fingerprint(values={"130.01": "4000.00", "130.02": "500.00"})
    assert fingerprint == canonical_financial_value_fingerprint(values={"130.02": "500.00", "130.01": "4000.00"})
    xsd = LocalXsdValidationEvidence(
        xml_sha256="c" * 64,
        xml_size=1,
        original_schema_sha256="d" * 64,
        original_schema_size=1,
        normalization="test-normalization",
        normalization_count=0,
        effective_validation_schema_sha256="d" * 64,
        effective_validation_schema_size=1,
        xsd_valid=True,
        error_identities=(),
    )
    evidence = build_tui_journey_evidence(
        contract=contract,
        resolution=_resolution(),
        frontend_path="tui",
        source_state="installed_tui_public_controls",
        cases=tuple(_proven_case(f"A{number}") for number in range(1, 11)),
        xsd_validation=xsd,
    )

    assert evidence.contract_missing_controls == ()
    assert evidence.xsd_validation is xsd

    with pytest.raises(TuiJourneyError, match="requires a successful local Modelo 100 XSD validation"):
        build_tui_journey_evidence(
            contract=contract,
            resolution=_resolution(),
            frontend_path="tui",
            source_state="installed_tui_public_controls",
            cases=tuple(_proven_case(f"A{number}") for number in range(1, 11)),
        )
