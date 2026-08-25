"""Boundary test: SQLAlchemy-wrapped CadrumoError is forwarded as a clean refusal.

When an :class:`cadrumo.core.errors.CadrumoError` is raised inside SQLAlchemy
bind-param processing (an encrypted-column codec that needs an unlocked
session), SQLAlchemy catches it and re-raises it wrapped in a
:class:`sqlalchemy.exc.StatementError`, with the original on ``orig``.

The CLI error boundary must unwrap that and emit the typed refusal
verbatim. Otherwise the no-session refusal is mis-classified as an
unexpected internal error and a full traceback is written to the log
file, where ``aeat config repair logs`` later echoes it back at the
operator as if it were a live crash.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import pytest
import sqlalchemy.exc as sa_exc
import typer
from pydantic import TypeAdapter

from ....adapters.persistence.storage.master_key import NoActiveBucketSessionError
from ....core.errors import CadrumoError, build_error_envelope, render_error_text
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ....llm import LLMRequest, PromptDefinition
from ..errors import (
    CliUnexpectedBoundaryError,
    _unwrap_cadrumo_error,
    command_error_boundary,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The real typed refusal raised by an encrypted-column codec when no
# bucket session is unlocked — the exact error the boundary must
# forward verbatim instead of mis-reporting as an internal defect.
_ProbeRefusal = NoActiveBucketSessionError


def test_terminal_nested_llm_validation_preserves_typed_refusal_in_every_locale(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The standalone terminal uses the callback projector for Pydantic errors."""
    from .._terminal_errors import run_standalone_with_error_contract

    for locale in SUPPORTED_OUTPUT_LANGUAGES:
        with pytest.raises(SystemExit) as exited:
            run_standalone_with_error_contract(
                lambda: LLMRequest(prompt=" \t"),
                argv=["--language", locale, "--format", "json"],
            )
        captured = capsys.readouterr()
        document = json.loads(captured.err)
        error = document["error"]
        assert error["code"] == "REFUSED_CLI_VALIDATION_BOUNDARY"
        assert error["category"] == "REFUSED"
        assert error["action"]["failed_condition_id"] == "llm.request.prompt_nonempty"
        assert error["action"]["evidence"][0]["values"] == {"request_prompt_nonempty": False}
        assert error["action"]["action"] is None
        assert error["action"]["conditionality"] == "not_applicable"
        assert error["action"]["no_recovery_outcome"] == "operator_decision"
        assert exited.value.code == 2

        with pytest.raises(SystemExit):
            run_standalone_with_error_contract(
                lambda: LLMRequest(prompt=" \t"),
                argv=["--language", locale],
            )
        text = capsys.readouterr().err
        assert 'action.failed_condition_id: "llm.request.prompt_nonempty"' in text
        assert "action.action: null" in text


@pytest.mark.parametrize(
    "dispatch",
    [
        lambda: LLMRequest(prompt="valid", max_tokens=0),
        lambda: TypeAdapter(tuple[LLMRequest, PromptDefinition]).validate_python(
            (
                {"prompt": " \t"},
                {"id": "Not canonical", "version": 1, "template": "{{ value }}", "description": "x"},
            ),
        ),
    ],
)
def test_terminal_validation_fails_closed_without_one_typed_candidate(
    dispatch: Callable[[], object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-typed and ambiguous nested validation retain the generic outcome."""
    from .._terminal_errors import run_standalone_with_error_contract

    with pytest.raises(SystemExit):
        run_standalone_with_error_contract(dispatch, argv=["--format", "json"])
    action = json.loads(capsys.readouterr().err)["error"]["action"]
    assert action["failed_condition_id"] == "cli.validation.boundary_clean"
    assert action["action"] is None
    assert action["no_recovery_outcome"] == "operator_decision"


def test_unwrap_finds_cadrumo_error_through_sqlalchemy_orig() -> None:
    """A StatementError carrying an CadrumoError on ``orig`` unwraps to it."""

    refusal = _ProbeRefusal("no active bucket session")
    statement_error = sa_exc.StatementError(
        message="bind-param processing failed",
        statement="SELECT 1",
        params={},
        orig=refusal,
    )

    assert _unwrap_cadrumo_error(statement_error) is refusal


def test_unwrap_finds_cadrumo_error_through_cause_chain() -> None:
    """An exception chained via ``__cause__`` unwraps to the CadrumoError."""

    refusal = _ProbeRefusal("no active bucket session")
    try:
        try:
            raise refusal
        except _ProbeRefusal as exc:
            raise RuntimeError("library wrapper") from exc
    except RuntimeError as wrapper:
        assert _unwrap_cadrumo_error(wrapper) is refusal


def test_unwrap_returns_none_for_plain_exception() -> None:
    """A genuine non-CadrumoError exception unwraps to None."""

    assert _unwrap_cadrumo_error(RuntimeError("genuine bug")) is None


def test_boundary_forwards_wrapped_refusal_without_logging_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The boundary emits the wrapped refusal and logs no exc_info traceback.

    A traceback in the log is exactly what feeds the
    ``aeat config repair logs`` mis-render. The boundary must classify
    the wrapped refusal as the typed CadrumoError, not as
    CliUnexpectedBoundaryError.
    """

    refusal = _ProbeRefusal("no active bucket session; run switch")

    def _callback() -> None:
        raise sa_exc.StatementError(
            message="bind-param processing failed",
            statement="SELECT secure_objects.payload FROM secure_objects",
            params={},
            orig=refusal,
        )

    wrapped = command_error_boundary(_callback)

    with (
        caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.cli.errors"),
        pytest.raises(typer.Exit) as exit_info,
    ):
        wrapped()

    # Exit code is the typed refusal's category code, never the
    # unexpected-error code.
    assert exit_info.value.exit_code != 0
    # No "unexpected exception" traceback was logged: that log line is
    # what lands in cadrumo.log and is later echoed by `repair logs`.
    assert not any("unexpected exception" in record.message for record in caplog.records), [
        record.message for record in caplog.records
    ]


def test_boundary_still_reports_genuine_bug_as_unexpected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A genuine non-CadrumoError bug is still classified as unexpected.

    The unwrap must not swallow real defects: an exception with no
    CadrumoError in its chain keeps the CliUnexpectedBoundaryError path
    and its diagnostic log line.
    """

    def _callback() -> None:
        raise RuntimeError("a genuine internal defect")

    wrapped = command_error_boundary(_callback)

    with (
        caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.cli.errors"),
        pytest.raises(typer.Exit),
    ):
        wrapped()

    assert any("unexpected exception" in record.message for record in caplog.records), [
        record.message for record in caplog.records
    ]


def test_cli_unexpected_boundary_error_is_cadrumo_error() -> None:
    """Sanity: the unexpected-boundary wrapper is itself an CadrumoError."""

    assert issubclass(CliUnexpectedBoundaryError, CadrumoError)


def test_unexpected_boundary_does_not_smuggle_a_recovery_command() -> None:
    """An internal fault reports diagnostics without claiming a CLI remedy."""
    boundary = CliUnexpectedBoundaryError(RuntimeError("an import error, say"))

    rendered = render_error_text(boundary)
    assert "aeat config repair logs" not in rendered, rendered
    assert "repair integrity" not in rendered, rendered

    envelope = build_error_envelope(boundary)
    assert "suggestion" not in envelope.model_dump(mode="json")


def test_terminal_boundary_logs_the_traceback_for_a_genuine_crash(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The terminal boundary writes the traceback it tells the operator to read.

    ``_emit_crash`` renders an INTERNAL envelope whose message directs the
    operator to the diagnostic logs. Before this line existed it logged
    nothing, so an isolated run left two DEBUG lines and no traceback, and
    triage had to patch the emitter in-process to see the failure at all.
    """
    from .._terminal_errors import _emit_crash

    with (
        caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.cli._terminal_errors"),
        pytest.raises(SystemExit),
    ):
        _emit_crash(RuntimeError("a genuine internal defect"))
    capsys.readouterr()

    crashes = [record for record in caplog.records if "unexpected exception" in record.message]
    assert crashes, [record.message for record in caplog.records]
    assert crashes[0].exc_info is not None
    assert crashes[0].exc_info[0] is RuntimeError


def test_terminal_boundary_logs_no_traceback_for_a_typed_refusal(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A typed refusal reaching the terminal boundary must not log a traceback.

    Command resolution raises already-classified refusals outside any callback
    boundary. Logging their tracebacks would make ``aeat config repair logs``
    echo an operator-actionable condition back as if it were a live crash --
    the same mis-render the command boundary avoids.
    """
    from .._terminal_errors import _emit_crash

    with (
        caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.cli._terminal_errors"),
        pytest.raises(SystemExit),
    ):
        _emit_crash(_ProbeRefusal("no active bucket session; run switch"))
    capsys.readouterr()

    assert not any("unexpected exception" in record.message for record in caplog.records), [
        record.message for record in caplog.records
    ]
