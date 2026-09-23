"""Focused receipt and local-XSD checks for the INCOME-01 TUI driver."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

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
    _observe_operation_terminal,
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


class _Operation:
    generation = SimpleNamespace(logical_generation="a" * 64)

    def supported_filing_years(self) -> SimpleNamespace:
        return SimpleNamespace(floor=2022)

    def snapshot(self, modelo: str, *, filing_year: int, period: str) -> SimpleNamespace:
        revision = SimpleNamespace(id=f"{modelo}-{filing_year}", export_layouts=())
        return SimpleNamespace(revision=revision)


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
    assert contract.calculate.activation_id == "#modelo-lifecycle-calculate"
    assert contract.verify.activation_id == "#modelo-lifecycle-verify"
    assert contract.local_file.confirmation_id == "#btn-confirm-accept"
    assert contract.export.activation_id == "#modelo-lifecycle-export"
    assert "profile_selection" in contract.missing_controls()
    assert "calculate.activation" not in contract.missing_controls()


def test_refresh_destination_must_be_the_current_installed_screen() -> None:
    class Screen:
        def query_one(self, selector: str) -> object:
            assert selector == "#declarations-list"
            return object()

    class App:
        screen = Screen()

    class Pilot:
        app = App()

        async def pause(self) -> None:
            raise AssertionError("current-screen refresh target should already be visible")

    asyncio.run(
        wait_for_tui_refresh(
            Pilot(),
            binding=TuiOperationBinding("modelo.work.calculate", refresh_result_id="#declarations-list"),
            maximum_polls=1,
        )
    )


@pytest.mark.parametrize(
    ("notice", "expected"),
    [
        ("Refused", "refused"),
        ("Refused: the attestation belongs to another quarter", "refused"),
        ("Succeeded", "succeeded"),
        ("Partly succeeded: one row was skipped", "partial"),
        ("Refusedly", None),
        ("Refused - no separator", None),
        ("", None),
    ],
)
def test_a_settled_notice_is_a_terminal_copy_alone_or_followed_by_its_explanation(
    notice: str, expected: str | None
) -> None:
    copies = {"Succeeded": "succeeded", "Partly succeeded": "partial", "Refused": "refused"}

    assert settled_notice_terminal(notice, copies) == expected


@pytest.mark.parametrize(
    ("copy_key", "explanation", "condition"),
    [
        ("operation.modal.terminal.refused", "the attestation belongs to another quarter", "refused"),
        ("operation.modal.terminal.succeeded", None, "succeeded"),
    ],
)
def test_a_modal_that_dismissed_itself_settles_from_the_workspace_notice(
    copy_key: str, explanation: str | None, condition: str
) -> None:
    """The modal closes the moment its operation is terminal; the lasting notice carries the result."""
    from textual.css.query import NoMatches

    from cadrumo.core.i18n.render import tr

    copy = tr(copy_key)
    notice = copy if explanation is None else f"{copy}: {explanation}"

    class Notice:
        def render(self) -> str:
            return notice

    class DismissedModal:
        is_mounted = False

        def query_one(self, selector: str) -> object:
            raise NoMatches(selector)

    class App:
        def query_one(self, selector: str) -> object:
            assert selector == "#modelo-lifecycle-notice"
            return Notice()

    class Pilot:
        app = App()

        async def pause(self) -> None:
            raise AssertionError("a settled notice must classify on the first poll")

    terminal = asyncio.run(
        _observe_operation_terminal(
            cast("Any", Pilot()),
            modal=cast("Any", DismissedModal()),
            binding=TuiOperationBinding(
                "modelo.work.calculate",
                terminal_result_id="#operation-modal-status",
                refusal_notice_id="#modelo-lifecycle-notice",
            ),
            maximum_polls=1,
        )
    )

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
