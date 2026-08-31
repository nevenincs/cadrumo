"""Regression tests for run-trace and event-log on-disk redaction.

Locks the contract that :func:`cadrumo.core.observability.save_trace` and
:func:`cadrumo.core.observability.save_events_append` must redact every
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
from ....tests.storage_scope import storage_overrides
from ...storage_taxonomy import StorageCategory
from ...config import override_settings
from ..models import (
    ArgumentRecord,
    ArgumentSource,
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
)
from ..store import EVENTS_FILENAME, TRACE_FILENAME, runs_dir, save_events_append, save_trace

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_NIF_CANARY = "12345678Z"
_BEARER_CANARY = (
    "eyJhbGciOiJIUzI1NiJ9XYZ012345PADDING."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0PADDING."
    "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJ"
)
_URL_CANARY = aeat_url("aeat_gob", REDACTION_INTERNAL_PATH_CANARY)
_STARTED_AT = datetime(2026, 4, 14, tzinfo=UTC)
_FINISHED_AT = datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC)


def _trace_with_argument(*, run_id: str, argument_name: str, argument_value: str) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=_STARTED_AT,
        finished_at=_FINISHED_AT,
        entrypoint="cadrumo hello",
        arguments=(ArgumentRecord(name=argument_name, value=argument_value, source=ArgumentSource.FLAG),),
        corpus_sha256="b" * 64,
        db_sha256="c" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
    )


def test_save_trace_redacts_sensitive_arguments(tmp_path: Path) -> None:
    """Trace arguments redact NIFs, bearer tokens, and sensitive URL paths before disk."""
    cases = (
        (
            _trace_with_argument(run_id="0123456789abcdef", argument_name="taxpayer", argument_value=_NIF_CANARY),
            (_NIF_CANARY,),
            ("sha256:",),
        ),
        (
            _trace_with_argument(run_id="fedcba9876543210", argument_name="auth", argument_value=_BEARER_CANARY),
            (_BEARER_CANARY,),
            ("token:sha256:",),
        ),
        (
            _trace_with_argument(run_id="abcdef0123456789", argument_name="endpoint", argument_value=_URL_CANARY),
            ("/internal/path", "token=12345"),
            (AEAT_HOST_SUFFIX_EXPECTED,),
        ),
    )

    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        for trace, forbidden_fragments, required_fragments in cases:
            save_trace(trace)
            on_disk = (runs_dir() / trace.run_id / TRACE_FILENAME).read_text(encoding="utf-8")

            for forbidden in forbidden_fragments:
                assert forbidden not in on_disk
            for required in required_fragments:
                assert required in on_disk


def test_save_events_append_redacts_url_path(
    tmp_path: Path,
) -> None:
    """A URL with sensitive path on a NavigationPayload event must be host-only on disk."""
    with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
        event = RunEvent(
            run_id="0123456789abcdef",
            step_id="step-0",
            kind=RunEventKind.NAVIGATION,
            payload=RunEventPayload(navigation=NavigationPayload(url=_URL_CANARY)),
            timestamp=_FINISHED_AT,
            module="cadrumo.core.observability.test_store_redaction",
        )
        save_events_append(event.run_id, event)
        on_disk = (runs_dir() / event.run_id / EVENTS_FILENAME).read_text(encoding="utf-8")
        assert "/internal/path" not in on_disk
        assert "token=12345" not in on_disk
        assert AEAT_HOST_SUFFIX_EXPECTED in on_disk
