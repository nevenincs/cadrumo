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

import logging

import pytest
import sqlalchemy.exc as sa_exc
import typer

from ....adapters.persistence.storage.master_key import NoActiveBucketSessionError
from ....core.errors import CadrumoError, build_error_envelope, render_error_text
from .._errors import (
    CliUnexpectedBoundaryError,
    _unwrap_cadrumo_error,
    command_error_boundary,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

# The real typed refusal raised by an encrypted-column codec when no
# bucket session is unlocked — the exact error the boundary must
# forward verbatim instead of mis-reporting as an internal defect.
_ProbeRefusal = NoActiveBucketSessionError


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
        caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.cli._errors"),
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
        caplog.at_level(logging.ERROR, logger="cadrumo.entrypoints.cli._errors"),
        pytest.raises(typer.Exit),
    ):
        wrapped()

    assert any("unexpected exception" in record.message for record in caplog.records), [
        record.message for record in caplog.records
    ]


def test_cli_unexpected_boundary_error_is_cadrumo_error() -> None:
    """Sanity: the unexpected-boundary wrapper is itself an CadrumoError."""

    assert issubclass(CliUnexpectedBoundaryError, CadrumoError)


def test_unexpected_boundary_suggests_log_inspection_not_integrity_repair() -> None:
    """The unexpected boundary must point at the read-only log inspection.

    An unexpected exception is a code/environment fault, not corrupted stored
    state, so suggesting ``config repair integrity`` (which implies storage
    corruption and points at a mutating repair) is misleading and could send an
    operator to a pointless or mutating action. The honest recovery is the
    read-only ``config repair logs``, where the traceback is echoed back.
    """
    boundary = CliUnexpectedBoundaryError(RuntimeError("an import error, say"))

    rendered = render_error_text(boundary)
    assert "aeat config repair logs" in rendered, rendered
    assert "repair integrity" not in rendered, rendered

    envelope = build_error_envelope(boundary)
    assert envelope.suggestion == "aeat config repair logs"
    assert "integrity" not in (envelope.suggestion or "")
