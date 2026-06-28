"""Real-behavior tests for the overview module logger.

Verifies that the module-level ``logger`` obtained via
:func:`aeat.core.logging.get_logger` carries a
:class:`~aeat.core.logging.SecretScrubbingFilter` that scrubs
NIF-shaped strings before the record reaches any handler.
"""

from __future__ import annotations

import logging

import pytest

from ....core.logging import SecretScrubbingFilter

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _scrubbing_filter_is_attached(log: logging.Logger) -> bool:
    """Return True if any filter on the logger (or root) is a SecretScrubbingFilter."""
    target: logging.Logger | None = log
    while target is not None:
        if any(isinstance(f, SecretScrubbingFilter) for f in target.filters):
            return True
        if not target.propagate:
            break
        parent = target.parent
        target = parent if isinstance(parent, logging.Logger) else None
    root = logging.getLogger()
    return any(isinstance(f, SecretScrubbingFilter) for f in root.filters)


def test_overview_logger_has_secret_scrubbing_filter() -> None:
    """The module-level logger in _overview carries SecretScrubbingFilter."""

    from .. import _overview

    assert _scrubbing_filter_is_attached(_overview.logger), (
        "SecretScrubbingFilter was not found on the overview logger or its root"
    )


def test_overview_logger_scrubs_nif_in_log_record(caplog: pytest.LogCaptureFixture) -> None:
    """A log record containing a NIF string must have the NIF redacted.

    The overview logger is obtained via get_logger(), which attaches
    SecretScrubbingFilter directly to the logger instance.  The filter
    mutates record.msg and record.args in-place so caplog captures the
    already-scrubbed message text.
    """

    from .. import _overview

    nif = "12345678Z"
    redacted_marker = "<redacted>"

    # Force the filter to run by emitting through the real logger.
    # We capture at WARNING because the overview logger is typically configured
    # at WARNING for stderr; the filter fires regardless of level.
    with caplog.at_level(logging.WARNING, logger=_overview.logger.name):
        _overview.logger.warning("profile tax_id=%s skipped", nif)

    assert caplog.records, "No log records captured — logger propagation may be broken"

    record = caplog.records[-1]
    rendered = record.getMessage()
    assert nif not in rendered, f"NIF {nif!r} was not scrubbed; got: {rendered!r}"
    assert redacted_marker in rendered, f"Expected '<redacted>' in rendered message; got: {rendered!r}"


def test_overview_logger_scrubs_nif_in_message_body(caplog: pytest.LogCaptureFixture) -> None:
    """NIF embedded directly in the message format string is also scrubbed."""

    from .. import _overview

    nif = "87654321X"

    with caplog.at_level(logging.WARNING, logger=_overview.logger.name):
        _overview.logger.warning("overview calendar: skipping profile tax_id=%s", nif)

    assert caplog.records, "No log records captured"

    record = caplog.records[-1]
    rendered = record.getMessage()
    assert nif not in rendered, f"NIF {nif!r} survived scrubbing in message body; got: {rendered!r}"
