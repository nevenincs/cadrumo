"""Failure chains name each cause by identifiers and share one correlation id."""

from __future__ import annotations

import io
import json
import logging

import pytest

from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS

from ....tests.log_records import delivered_records
from ..error_codes import render_error_json, render_error_text
from ..failure_report import failure_chain, failure_trace_id, log_boundary_failure, root_cause_context
from ..hierarchy import CadrumoError, InternalInvariantError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRIVATE = "12345678Z"


def _lookup(table: dict[str, int], key: str) -> int:
    return table[key]


def _resolve_port() -> None:
    try:
        _lookup({}, f"secret-{_PRIVATE}")
    except KeyError as error:
        raise InternalInvariantError(f"port for taxpayer {_PRIVATE} has not been composed") from error


def _raised_invariant() -> InternalInvariantError:
    try:
        _resolve_port()
    except InternalInvariantError as error:
        return error
    raise AssertionError("the invariant was not raised")


def test_chain_names_every_link_with_its_raising_frame_root_last() -> None:
    chain = failure_chain(_raised_invariant())

    assert [link.exception_type for link in chain] == [
        "cadrumo.core.errors.hierarchy.InternalInvariantError",
        "KeyError",
    ]
    assert chain[0].code == "INTERNAL_INVARIANT"
    assert chain[0].raised_at is not None and chain[0].raised_at.endswith(
        f":_resolve_port:{_line_of('raise Internal')}"
    )
    assert chain[1].raised_at is not None and chain[1].raised_at.endswith(f":_lookup:{_line_of('return table[key]')}")
    assert all(_PRIVATE not in link.render() for link in chain)


def test_suppressed_context_ends_the_chain() -> None:
    try:
        try:
            raise ValueError("first")
        except ValueError:
            raise InternalInvariantError("second") from None
    except InternalInvariantError as error:
        assert [link.exception_type for link in failure_chain(error)] == [
            "cadrumo.core.errors.hierarchy.InternalInvariantError"
        ]


def test_internal_envelope_shows_the_root_cause_and_the_logged_trace_id(caplog: pytest.LogCaptureFixture) -> None:
    error = _raised_invariant()
    with caplog.at_level(logging.DEBUG):
        trace_id = log_boundary_failure(logging.getLogger("cadrumo.tests.failure_report"), "unit_boundary", error)

    (record,) = [
        record for record in delivered_records(caplog) if getattr(record, "failure_boundary", None) == "unit_boundary"
    ]
    assert record.levelno == logging.ERROR
    assert record.__dict__["trace_id"] == trace_id
    assert record.__dict__["error_type"] == "cadrumo.core.errors.hierarchy.InternalInvariantError"
    assert str(record.__dict__["error_origin"]).endswith(":_resolve_port:" + str(_line_of("raise Internal")))
    assert str(record.__dict__["root_cause"]).endswith(":_lookup:" + str(_line_of("return table[key]")))
    assert record.__dict__["error_code"] == "INTERNAL_INVARIANT"
    assert "has not been composed" in str(record.__dict__["invariant"])
    assert _PRIVATE not in str(record.__dict__["invariant"])
    assert _PRIVATE not in record.getMessage()

    document = json.loads(render_error_json(error))["error"]
    assert document["code"] == "INTERNAL_INVARIANT"
    assert document["trace_id"] == trace_id
    assert document["context"]["trace_id"] == trace_id
    assert document["context"]["exception_type"] == "KeyError"
    assert document["context"]["cause_chain"] == "InternalInvariantError <- KeyError"
    assert _PRIVATE not in json.dumps(document)
    text = render_error_text(error)
    assert trace_id in text and "KeyError" in text and _PRIVATE not in text


def test_a_wrapper_reports_the_id_its_cause_was_logged_under() -> None:
    cause = _raised_invariant()
    first = failure_trace_id(cause)
    try:
        raise RuntimeError("wrapper") from cause
    except RuntimeError as wrapper:
        assert failure_trace_id(wrapper) == first
        assert root_cause_context(wrapper)["trace_id"] == first


def test_expected_refusal_envelopes_are_unchanged() -> None:
    from ...locks_errors import LockAcquisitionError

    document = json.loads(render_error_json(LockAcquisitionError(context={"reason": "held"})))["error"]
    assert document["trace_id"] is None
    assert document["context"] == {"reason": "held"}


def test_an_identifier_shaped_private_reason_is_scrubbed_from_the_written_boundary_line() -> None:
    # An identifier-shaped context reason enters the chain verbatim; the project
    # logger's scrubbing filter is what keeps it out of the written line.
    from ...diagnostic_log import DiagnosticFormatter
    from ...logging import LOG_FILE_FORMAT, flush_logging, get_logger

    logger = get_logger("cadrumo.tests.failure_report_sink")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(DiagnosticFormatter(LOG_FILE_FORMAT))
    logger.addHandler(handler)
    previous_level, previous_propagate = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        log_boundary_failure(
            logger, "unit_boundary", CadrumoError("synthetic boundary failure", context={"reason": _PRIVATE})
        )
        # Delivery runs on the dispatch thread and reaches the handler only while it is attached.
        assert flush_logging(timeout=HANG_GUARD_SECONDS)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    line = stream.getvalue()
    assert "boundary failure at unit_boundary" in line
    assert "chain: cadrumo.core.errors.hierarchy.CadrumoError[" in line
    assert _PRIVATE not in line


def _line_of(fragment: str) -> int:
    import inspect

    lines, start = inspect.getsourcelines(_lookup if "table" in fragment else _resolve_port)
    return start + next(index for index, line in enumerate(lines) if fragment in line)
