"""Component-related CLI refusals render their supplied facts without another status read."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import typer

from cadrumo.tests.english_locale_fixture import english_locale_fixture
from cadrumo_client.commands.registered_operation_errors import detailed_registered_operation_error

from ....adapters.outbound.aeat.browser.errors import BrowserError
from ....adapters.outbound.aeat.browser.session import require_browser_ready
from ....adapters.outbound.components.tests.recorded_rows import not_in_this_build_row, recorded_absent_row
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ....application.ledger.import_operation import LedgerImportFileRefusal
from ....application.ledger.preconditions import LedgerPreconditionCondition
from ....application.local_reader import probe_local_ai_program
from ....application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from ....application.operator_actions.projection import PreconditionVerdictSnapshot
from ....application.preflight import dependency_preflight_checks
from ....application.provisioning_browser import probe_playwright_browser
from ....application.provisioning_contracts import ProvisioningPreconditionCondition, provisioning_no_recovery_verdict
from ....core.config import Settings
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.json_contract import ResolvedNoticeAction
from ....core.model_roles import ModelRole
from ..common import resolve_cli_precondition_action
from ..config import provision_cli
from ..config.check_cli import dependency_payload, dependency_text_lines
from ..config.status_rendering import precondition_action_lines
from ..errors import command_error_boundary
from ..ledger_import_commands import _refused_file_report
from .cli_runner import invoke_cached_cli, invoke_typer_app, semantic_cli_output

__all__ = ["english_locale_fixture"]
pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _browser_refusal(tmp_path: Path) -> BrowserError:
    with pytest.raises(BrowserError) as raised:
        require_browser_ready(
            Settings(cadrumo_playwright_browsers_dir=tmp_path / "empty-browsers"), profile_name="setup-text"
        )
    return raised.value


def _reader_refusal() -> PurchaseInvoiceEvidenceReaderError:
    status = probe_local_ai_program(recorded_absent_row("local_ai"))
    assert status.available is False and status.precondition_verdict is not None
    return PurchaseInvoiceEvidenceReaderError(
        LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value,
        translated_message="errors.refused.refused_ledger_evidence_reader_unavailable",
        precondition_verdict=status.precondition_verdict,
    )


def _refusing_app(refusal: Callable[[], CadrumoError]) -> typer.Typer:
    app = typer.Typer()

    @app.command()
    @command_error_boundary
    def refused(json_out: bool = typer.Option(False, "--json")) -> None:
        del json_out
        raise refusal()

    return app


def test_browser_refusal_without_status_points_to_the_status_report(tmp_path: Path) -> None:
    error = _browser_refusal(tmp_path)
    result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)
    assert result.exit_code != 0
    output = semantic_cli_output(result)
    assert resolve_error_message(error) in output.splitlines()[0]
    assert "Check component status: aeat config provision status" in output
    assert "aeat config provision browser" not in output


def test_json_keeps_the_typed_browser_action_and_no_private_path(tmp_path: Path) -> None:
    result = invoke_typer_app(_refusing_app(lambda: _browser_refusal(tmp_path)), ["--json"], catch_exceptions=False)
    assert result.exit_code != 0
    action = json.loads(result.stderr)["error"]["action"]
    assert action["failed_condition_id"] == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert action["evidence"][0]["values"]["chromium_installed"] is False
    assert not any(str(tmp_path) in str(value) for value in action["evidence"][0]["values"].values())
    assert action["action"]["action_id"] == "operator.provision.browser"
    assert action["action"]["cli_path"] == ["aeat", "config", "provision", "browser"]
    notice = json.loads(result.stderr)["notices"][-1]
    assert "Show whether each component is ready" in notice["message"]
    assert notice["action"]["action"]["cli_path"] == ["config", "provision", "status"]


def test_worker_recorded_browser_refusal_preserves_the_same_action(tmp_path: Path) -> None:
    detail = build_operation_error_detail(_browser_refusal(tmp_path))
    assert detail is not None
    recorded = detailed_registered_operation_error(
        OperationErrorDetailV1.model_validate_json(detail.model_dump_json()), {}
    )
    result = invoke_typer_app(_refusing_app(lambda: recorded), [], catch_exceptions=False)
    output = semantic_cli_output(result)
    assert result.exit_code != 0 and resolve_error_message(recorded) in output.splitlines()[0]
    assert "Check component status: aeat config provision status" in output
    assert "aeat config provision browser" not in output


def test_local_ai_refusal_retains_its_typed_action_without_inventing_component_status() -> None:
    error = _reader_refusal()
    result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)
    output = semantic_cli_output(result)
    assert result.exit_code != 0 and resolve_error_message(error) in output.splitlines()[0]
    assert "Set it up in the Cadrumo desktop app." in output
    assert "aeat config provision status" not in output


def test_local_ai_json_preserves_verdict_and_adds_desktop_guidance() -> None:
    result = invoke_typer_app(_refusing_app(_reader_refusal), ["--json"], catch_exceptions=False)
    document = json.loads(result.stderr)
    assert document["error"]["action"]["action"]["action_id"] == "operator.provision.local_ai"
    assert document["notices"][-1]["message"] == "Set it up in the Cadrumo desktop app."


@pytest.mark.parametrize("signed_in", [False, True])
def test_refusal_rendering_does_not_submit_a_component_status_operation(
    monkeypatch: pytest.MonkeyPatch, signed_in: bool
) -> None:
    from .. import _profile_authentication_gate

    reads: list[object] = []
    error = _reader_refusal()
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: object() if signed_in else None)
    monkeypatch.setattr(_profile_authentication_gate, "preflight_parsed_leaf", lambda *args, **kwargs: None)

    def refuse_read(*args: object, **kwargs: object) -> None:
        reads.append(args)
        raise error

    monkeypatch.setattr(provision_cli, "_read", refuse_read)
    result = invoke_cached_cli(["config", "provision", "status"])
    assert result.exit_code != 0
    assert resolve_error_message(error) in semantic_cli_output(result)
    assert len(reads) == 1


def test_status_precondition_renders_supplied_typed_action(tmp_path: Path) -> None:
    status = probe_playwright_browser(tmp_path / "empty-browsers")
    assert status.precondition_verdict is not None
    action = resolve_cli_precondition_action(status.precondition_verdict)
    lines = precondition_action_lines(action)
    assert any("Check component status: aeat config provision status" in line for line in lines)
    assert not any("To fix it" in line for line in lines)
    assert any(
        "Check component status: aeat config provision status" in line
        for line in dependency_text_lines(dependency_payload(status))
    )


@pytest.mark.parametrize("blocked", [False, True])
def test_current_browser_row_controls_error_and_ledger_recovery(blocked: bool) -> None:
    row = not_in_this_build_row("browser") if blocked else recorded_absent_row("browser")
    (check,) = dependency_preflight_checks((row,))
    verdict = check.precondition_verdict
    assert verdict is not None
    error = BrowserError("Browser unavailable", precondition_verdict=verdict)
    result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)
    output = semantic_cli_output(result)
    refusal = LedgerImportFileRefusal(
        file_name="statement.pdf",
        reason_code="reader_unavailable",
        precondition_verdict=PreconditionVerdictSnapshot.from_verdict(verdict),
    )
    report = _refused_file_report((refusal,))
    ledger_text = "\n".join(report.lines)
    if blocked:
        assert "This version of Cadrumo does not include this." in output
        assert "This version of Cadrumo does not include this." in ledger_text
        assert "aeat config provision browser" not in output + ledger_text
        assert report.notices[-1].action is None
    else:
        assert "To fix it, run: aeat config provision browser" in output
        assert "To fix it, run: aeat config provision browser" in ledger_text
        action = report.notices[-1].action
        assert isinstance(action, ResolvedNoticeAction)
        assert action.action.target_command_key == "config.provision.browser"
    structured = invoke_typer_app(_refusing_app(lambda: error), ["--json"], catch_exceptions=False)
    notice = json.loads(structured.stderr)["notices"][-1]
    if blocked:
        assert notice["action"] is None
    else:
        assert notice["action"]["action"]["target_command_key"] == "config.provision.browser"


def test_ledger_without_browser_status_points_only_to_status(tmp_path: Path) -> None:
    verdict = probe_playwright_browser(tmp_path / "empty-browsers").precondition_verdict
    assert verdict is not None
    refusal = LedgerImportFileRefusal(
        file_name="statement.pdf",
        reason_code="reader_unavailable",
        precondition_verdict=PreconditionVerdictSnapshot.from_verdict(verdict),
    )
    report = _refused_file_report((refusal,))
    text = "\n".join(report.lines)
    assert "Check component status: aeat config provision status" in text
    assert "aeat config provision browser" not in text
    action = report.notices[-1].action
    assert isinstance(action, ResolvedNoticeAction)
    assert action.action.target_command_key == "config.provision.status"
    assert "aeat" not in report.notices[-1].message


def test_ledger_local_ai_recovery_exposes_desktop_guidance() -> None:
    verdict = probe_local_ai_program(recorded_absent_row("local_ai")).precondition_verdict
    assert verdict is not None
    refusal = LedgerImportFileRefusal(
        file_name="statement.pdf",
        reason_code="reader_unavailable",
        precondition_verdict=PreconditionVerdictSnapshot.from_verdict(verdict),
    )
    report = _refused_file_report((refusal,))
    assert "  Set it up in the Cadrumo desktop app." in report.lines
    assert report.notices[-1].message == "Set it up in the Cadrumo desktop app."
    assert report.notices[-1].action is None


def test_a_verdict_with_no_recovery_keeps_its_typed_rows() -> None:
    verdict = provisioning_no_recovery_verdict(
        ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
        facts={"role": ModelRole.VISION_TRANSCRIPTION.value, "role_model_selected": False},
    )
    lines = precondition_action_lines(resolve_cli_precondition_action(verdict))
    assert lines[0] == (
        f'precondition_action.failed_condition_id\t"{ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value}"'
    )
    assert "precondition_action.action\tnull" in lines
