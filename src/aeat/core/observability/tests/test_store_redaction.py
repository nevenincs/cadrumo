"""Regression tests for run-trace and event-log on-disk redaction.

Locks the contract that :func:`aeat.core.observability.save_trace` and
:func:`aeat.core.observability.save_events_append` must redact every
in-scope sensitive value (NIF, bearer token, sensitive URL path) before
the structured payload reaches the on-disk store. Tracks the original
TRACE-001 regression: plaintext NIF and OAuth tokens were observed in
``runs/<run-id>/trace.json`` because the audit-class redaction policy
was not applied to argument records and navigation events.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.aeat_literal_fixtures import (
    AEAT_HOST_SUFFIX_EXPECTED,
    REDACTION_INTERNAL_PATH_CANARY,
    aeat_url,
)
from ...config import override_settings
from .. import (
    ArgumentRecord,
    ArgumentSource,
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    save_events_append,
    save_trace,
)
from .._store import _EVENTS_FILENAME, _TRACE_FILENAME, runs_dir

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_NIF_CANARY = "12345678Z"
_BEARER_CANARY = (
    "eyJhbGciOiJIUzI1NiJ9XYZ012345PADDING."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0PADDING."
    "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJ"
)
_URL_CANARY = aeat_url("aeat_gob", REDACTION_INTERNAL_PATH_CANARY)


def test_save_trace_redacts_nif_canary_in_arguments(
    tmp_path: Path,
) -> None:
    """A NIF in arguments must be SHA-256-prefixed on disk, never plaintext."""
    with override_settings(aeat_runs_dir=str(tmp_path)):
        trace = RunTrace(
            run_id="0123456789abcdef",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat hello",
            arguments=(ArgumentRecord(name="taxpayer", value=_NIF_CANARY, source=ArgumentSource.FLAG),),
            corpus_sha256="b" * 64,
            db_sha256="c" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        save_trace(trace)
        on_disk = (runs_dir() / trace.run_id / _TRACE_FILENAME).read_text(encoding="utf-8")
        assert _NIF_CANARY not in on_disk
        assert "sha256:" in on_disk


def test_save_trace_redacts_bearer_token_canary(
    tmp_path: Path,
) -> None:
    """A bearer-token-shaped string must be fingerprinted on disk."""
    with override_settings(aeat_runs_dir=str(tmp_path)):
        trace = RunTrace(
            run_id="fedcba9876543210",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat hello",
            arguments=(ArgumentRecord(name="auth", value=_BEARER_CANARY, source=ArgumentSource.FLAG),),
            corpus_sha256="b" * 64,
            db_sha256="c" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        save_trace(trace)
        on_disk = (runs_dir() / trace.run_id / _TRACE_FILENAME).read_text(encoding="utf-8")
        assert _BEARER_CANARY not in on_disk
        assert "token:sha256:" in on_disk


def test_save_trace_redacts_url_path_to_host_only(
    tmp_path: Path,
) -> None:
    """A URL with sensitive path/query must collapse to host-only on disk."""
    with override_settings(aeat_runs_dir=str(tmp_path)):
        trace = RunTrace(
            run_id="abcdef0123456789",
            started_at=datetime(2026, 4, 14, tzinfo=UTC),
            finished_at=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            entrypoint="aeat hello",
            arguments=(ArgumentRecord(name="endpoint", value=_URL_CANARY, source=ArgumentSource.FLAG),),
            corpus_sha256="b" * 64,
            db_sha256="c" * 64,
            cert_fingerprint="",
            outcome=RunOutcome.OK,
        )
        save_trace(trace)
        on_disk = (runs_dir() / trace.run_id / _TRACE_FILENAME).read_text(encoding="utf-8")
        assert "/internal/path" not in on_disk
        assert "token=12345" not in on_disk
        # Host stays.
        assert AEAT_HOST_SUFFIX_EXPECTED in on_disk


def test_save_events_append_redacts_url_path(
    tmp_path: Path,
) -> None:
    """A URL with sensitive path on a NavigationPayload event must be host-only on disk."""
    with override_settings(aeat_runs_dir=str(tmp_path)):
        event = RunEvent(
            run_id="0123456789abcdef",
            step_id="step-0",
            kind=RunEventKind.NAVIGATION,
            payload=RunEventPayload(navigation=NavigationPayload(url=_URL_CANARY)),
            timestamp=datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC),
            module="aeat.core.observability.test_store_redaction",
        )
        save_events_append(event.run_id, event)
        on_disk = (runs_dir() / event.run_id / _EVENTS_FILENAME).read_text(encoding="utf-8")
        assert "/internal/path" not in on_disk
        assert "token=12345" not in on_disk
        assert AEAT_HOST_SUFFIX_EXPECTED in on_disk
