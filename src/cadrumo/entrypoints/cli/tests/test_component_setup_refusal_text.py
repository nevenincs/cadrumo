"""A refusal for a component that is not set up reads as its sentence plus what the item's row allows.

The verdicts come from the real setup probes: the browser probe reading an
empty browsers root, and the local reader probe asking a closed runtime port.
The refusals pass through the real CLI error boundary and the live action
resolver, both in-process and rebuilt from a worker's recorded error detail.
The item's quick-status row comes from the real row derivation: absent, so its
action sets it up, or blocked as not in this build, as every item reads while
this build sets nothing up. Text output shows the error's sentence and then
the exact command for an offerable row, the row's own sentence for a blocked
row, and nothing more when the status cannot be read; JSON keeps the typed
action record unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
import typer

from cadrumo.tests.english_locale_fixture import english_locale_fixture
from cadrumo_client.commands.registered_operation_errors import detailed_registered_operation_error

from ....adapters.outbound.aeat.browser.errors import BrowserError
from ....adapters.outbound.aeat.browser.session import require_browser_ready
from ....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyStatusRow,
)
from ....application.dependency_registry import dependency_item_declarations, derive_dependency_row
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ....application.ledger.preconditions import LedgerPreconditionCondition
from ....application.local_reader import probe_local_reader
from ....application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from ....application.provisioning_browser import probe_playwright_browser
from ....application.provisioning_contracts import ProvisioningPreconditionCondition, provisioning_no_recovery_verdict
from ....core.config import Settings
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.model_catalogue import ModelRole
from .._component_setup_rendering import setup_status_source
from ..common import resolve_cli_precondition_action
from ..config.check_cli import dependency_payload, dependency_text_lines
from ..config.status_rendering import precondition_action_lines
from ..errors import command_error_boundary
from .cli_runner import invoke_typer_app, semantic_cli_output

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"
_BROWSER_FIX = "To fix it, run: aeat config provision browser"
_LOCAL_AI_FIX = "To fix it, run: aeat config provision pull"
_LOCAL_AI_HELD = "Local AI: This version of Cadrumo does not include this."
_BROWSER_HELD = "Browser for the tax agency website: This version of Cadrumo does not include this."


def _rows(outcome: DependencyProbeOutcome) -> tuple[DependencyStatusRow, ...]:
    """Every item's quick-status row, derived by the real registry from one probe reading each."""
    blocked = DependencyBlockedReason.NOT_IN_THIS_BUILD if outcome is DependencyProbeOutcome.BLOCKED else None
    return tuple(
        derive_dependency_row(
            declaration,
            DependencyProbeReading(
                item_id=declaration.item_id, mode=DependencyCheckMode.QUICK, outcome=outcome, blocked_reason=blocked
            ),
        )
        for declaration in dependency_item_declarations()
    )


@contextmanager
def _status(outcome: DependencyProbeOutcome) -> Generator[None]:
    """Bind the invocation's quick setup status to rows of ``outcome``."""
    with setup_status_source(lambda: _rows(outcome)):
        yield


def _unreadable_status() -> tuple[DependencyStatusRow, ...]:
    raise ConnectionError("the runtime did not answer")


def _browser_refusal(tmp_path: Path) -> BrowserError:
    with pytest.raises(BrowserError) as raised:
        require_browser_ready(
            Settings(cadrumo_playwright_browsers_dir=tmp_path / "empty-browsers"), profile_name="setup-text"
        )
    return raised.value


def _reader_refusal() -> PurchaseInvoiceEvidenceReaderError:
    status = probe_local_reader(ModelRole.VISION_TRANSCRIPTION, Settings(cadrumo_llm_ollama_chat_url=_CLOSED_ENDPOINT))
    assert status.available is False
    assert status.precondition_verdict is not None
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


def _assert_sentence_and_command(output: str, *, sentence: str, fix: str) -> None:
    lines = output.splitlines()
    assert sentence in lines[0]
    assert f"  {fix}" in lines
    assert lines[-1] == f"  {fix}"
    _assert_no_action_record(output)


def _assert_no_action_record(output: str) -> None:
    assert "action." not in output
    assert "failed_condition_id" not in output
    assert "provisioning." not in output
    assert "  command:" not in output


def test_a_missing_browser_prints_the_sentence_and_the_setup_command(tmp_path: Path) -> None:
    error = _browser_refusal(tmp_path)

    with _status(DependencyProbeOutcome.ABSENT):
        result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)

    assert result.exit_code != 0
    _assert_sentence_and_command(semantic_cli_output(result), sentence=resolve_error_message(error), fix=_BROWSER_FIX)


def test_a_browser_this_build_cannot_set_up_prints_its_sentence_and_no_command(tmp_path: Path) -> None:
    error = _browser_refusal(tmp_path)

    with _status(DependencyProbeOutcome.BLOCKED):
        result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)

    assert result.exit_code != 0
    output = semantic_cli_output(result)
    lines = output.splitlines()
    assert resolve_error_message(error) in lines[0]
    assert lines[-1] == f"  {_BROWSER_HELD}"
    assert "To fix it" not in output
    _assert_no_action_record(output)


def test_json_keeps_the_typed_browser_action_and_prints_no_command_line(tmp_path: Path) -> None:
    error = _browser_refusal(tmp_path)

    result = invoke_typer_app(_refusing_app(lambda: error), ["--json"], catch_exceptions=False)

    assert result.exit_code != 0
    assert "To fix it" not in result.stderr
    action = json.loads(result.stderr)["error"]["action"]
    assert action["failed_condition_id"] == ProvisioningPreconditionCondition.PLAYWRIGHT_BROWSER_INSTALLED.value
    assert action["evidence"][0]["values"]["browser_cache_root"] == str(tmp_path / "empty-browsers")
    assert action["action"] == {
        "action_id": "operator.provision.browser",
        "target_command_key": "config.provision.browser",
        "cli_path": ["aeat", "config", "provision", "browser"],
    }
    assert action["argument_bindings"] == []
    assert action["conditionality"] == "immediate"


def test_a_worker_recorded_browser_refusal_prints_the_same_command(tmp_path: Path) -> None:
    """An operation refused in the profile worker reaches the CLI as its recorded detail."""
    detail = build_operation_error_detail(_browser_refusal(tmp_path))
    assert detail is not None
    recorded = detailed_registered_operation_error(
        OperationErrorDetailV1.model_validate_json(detail.model_dump_json()), {}
    )

    with _status(DependencyProbeOutcome.ABSENT):
        result = invoke_typer_app(_refusing_app(lambda: recorded), [], catch_exceptions=False)

    assert result.exit_code != 0
    _assert_sentence_and_command(
        semantic_cli_output(result), sentence=resolve_error_message(recorded), fix=_BROWSER_FIX
    )


def test_an_unreachable_local_ai_prints_the_sentence_and_the_setup_command() -> None:
    error = _reader_refusal()

    with _status(DependencyProbeOutcome.ABSENT):
        result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)

    assert result.exit_code != 0
    _assert_sentence_and_command(semantic_cli_output(result), sentence=resolve_error_message(error), fix=_LOCAL_AI_FIX)


def test_a_local_ai_this_build_cannot_set_up_prints_its_sentence_and_no_command() -> None:
    error = _reader_refusal()

    with _status(DependencyProbeOutcome.BLOCKED):
        result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)

    assert result.exit_code != 0
    output = semantic_cli_output(result)
    assert output.splitlines()[-1] == f"  {_LOCAL_AI_HELD}"
    assert "To fix it" not in output
    _assert_no_action_record(output)


def test_an_unreadable_setup_status_prints_the_sentence_alone() -> None:
    error = _reader_refusal()

    with setup_status_source(_unreadable_status):
        result = invoke_typer_app(_refusing_app(lambda: error), [], catch_exceptions=False)

    assert result.exit_code != 0
    output = semantic_cli_output(result)
    lines = output.splitlines()
    assert len(lines) == 1, output
    assert resolve_error_message(error) in lines[0]
    _assert_no_action_record(output)


def test_a_command_without_a_profile_connection_reads_no_status_and_offers_nothing() -> None:
    """The boundary reads the status through the command's own connection; without one it offers nothing."""
    error = _reader_refusal()
    app = typer.Typer()

    @app.command()
    @command_error_boundary
    def refused(ctx: typer.Context) -> None:
        del ctx
        raise error

    result = invoke_typer_app(app, [], catch_exceptions=False)

    assert result.exit_code != 0
    output = semantic_cli_output(result)
    lines = output.splitlines()
    assert len(lines) == 1, output
    assert resolve_error_message(error) in lines[0]
    _assert_no_action_record(output)


def test_status_rows_show_the_setup_command_for_a_missing_browser(tmp_path: Path) -> None:
    status = probe_playwright_browser(tmp_path / "empty-browsers")
    assert status.precondition_verdict is not None

    action = resolve_cli_precondition_action(status.precondition_verdict)

    with _status(DependencyProbeOutcome.ABSENT):
        assert precondition_action_lines(action) == (f"precondition_action\t{_BROWSER_FIX}",)
        lines = dependency_text_lines(dependency_payload(status))
    assert f"{status.service}.precondition_action\t{_BROWSER_FIX}" in lines
    assert not any(".precondition_action." in line for line in lines)
    with _status(DependencyProbeOutcome.BLOCKED):
        assert precondition_action_lines(action) == (f"precondition_action\t{_BROWSER_HELD}",)
    with setup_status_source(_unreadable_status):
        assert precondition_action_lines(action) == ()


def test_a_verdict_setup_cannot_repair_keeps_its_typed_rows() -> None:
    """A role the hardware cannot serve names no setup action, so no command is printed."""
    verdict = provisioning_no_recovery_verdict(
        ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
        facts={"role": ModelRole.VISION_TRANSCRIPTION.value, "role_model_selected": False},
    )

    lines = precondition_action_lines(resolve_cli_precondition_action(verdict))

    assert lines[0] == (
        f'precondition_action.failed_condition_id\t"{ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE.value}"'
    )
    assert "precondition_action.action\tnull" in lines
    assert not any("To fix it" in line for line in lines)
