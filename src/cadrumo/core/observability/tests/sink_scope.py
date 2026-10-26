"""Attach recording-test handlers with the actual diagnostic redaction filters."""

from __future__ import annotations

import logging

from ...logging import SecretScrubbingFilter, _ThirdPartyDebugFilter


def attach_run_sink(sink: logging.Handler) -> None:
    """Install ``SecretScrubbingFilter`` on ``sink`` then attach it to root.

    Ensures every record flowing through the JSONL run sink is scrubbed
    before it reaches the serialiser, even when the root-logger filter
    has already scrubbed the shared record in-place.  The filter is
    idempotent: a second call with the same sink is a no-op because the
    guard checks ``root_logger.handlers`` for an existing instance.

    Args:
        sink: The :class:`logging.Handler` to attach to the root logger.

    The sink is a diagnostic observability target. It receives redacted log
    records, not CLI result payloads or secure-storage records.
    """
    if not any(isinstance(f, SecretScrubbingFilter) for f in sink.filters):
        sink.addFilter(SecretScrubbingFilter())
    logging.getLogger().addHandler(sink)


def detach_run_sink(sink: logging.Handler) -> None:
    """Remove ``sink`` from the root logger and perform symmetric teardown.

    Reverses every side-effect of :func:`attach_run_sink`: the handler is
    removed from the root logger, the :class:`SecretScrubbingFilter`
    instances that :func:`attach_run_sink` installed on the sink are
    removed, and the sink is flushed so in-flight records reach their
    destination before the handle is released.

    The caller is responsible for closing the sink after detach; this
    function deliberately does not call :meth:`~logging.Handler.close` so
    a caller can flush output and inspect state before teardown.

    Args:
        sink: The :class:`logging.Handler` previously attached by
            :func:`attach_run_sink`.
    """
    logging.getLogger().removeHandler(sink)
    sink.filters = [f for f in sink.filters if not isinstance(f, SecretScrubbingFilter | _ThirdPartyDebugFilter)]
    sink.flush()
