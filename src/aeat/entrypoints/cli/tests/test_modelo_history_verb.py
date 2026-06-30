"""CLI surface tests for ``aeat app modelo history``.

Closes the contract history-test gap: every verb in the
link/check/preflight/reconcile/history five-verb backend-wired set now
carries a dedicated CLI surface test exercising the real backend
(:class:`BucketEventHistoryRepository`).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....domain.buckets import (
    BucketEventHistoryCatalogue,
    BucketEventHistoryRepository,
    BucketEventType,
)
from ....domain.buckets._event import (
    BucketEvent,
    BucketEventObjectType,
    derive_bucket_event_id,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("11111111-1111-4111-8111-111111111111"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="11111111-1111-4111-8111-111111111111")
        )
        yield


def _seed_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    modelo: str,
    year: str,
    period: str,
    year_payload_key: str = "year",
    offset_seconds: int = 0,
) -> str:
    """Persist one modelo-lifecycle event through the real repository."""

    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    occurred_at = datetime.now(UTC).replace(microsecond=0)
    if offset_seconds:
        occurred_at = occurred_at.replace(second=(occurred_at.second + offset_seconds) % 60)
    object_id = "wu" + "0" * (64 - 2)
    actor = "cli/aeat"
    payload = {"modelo": modelo, year_payload_key: year, "period": period}
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=object_id,
        payload=payload,
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=object_id,
        payload_version=1,
        payload=payload,
    )
    updated = BucketEventHistoryCatalogue(events={**catalogue.events, event_id: event})
    repo.save(updated)
    return event_id


def _active_bucket_id() -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def test_history_returns_empty_envelope_for_modelo_with_no_events() -> None:
    """`aeat app modelo history --modelo 303` against an empty bucket
    surfaces a typed envelope with ``count=0`` and no events."""

    result = invoke_cached_cli(["app", "modelo", "history", "--modelo", "303"])
    assert result.exit_code == 0, result.output
    assert "modelo\t303" in result.output
    assert "count\t0" in result.output


def test_history_filters_events_to_requested_modelo() -> None:
    """Only events whose payload's ``modelo`` matches the ``--modelo``
    flag appear in the history output."""

    bucket_id = _active_bucket_id()
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        modelo="303",
        year="2026",
        period="1T",
    )
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        modelo="130",
        year="2026",
        period="1T",
        offset_seconds=1,
    )

    result = invoke_cached_cli(["app", "modelo", "history", "--modelo", "303"])
    assert result.exit_code == 0, result.output
    assert "count\t1" in result.output, result.output
    # The line-emitted history rows carry "<iso>\t<event_type>\t<object_id>\t<actor>";
    # the modelo filter retained the M303 row and dropped the M130 row.
    assert "modelo.calculation.created" in result.output
    assert result.output.count("modelo.calculation.created") == 1


def test_history_year_and_period_filters_narrow_results() -> None:
    """Adding ``--year`` and ``--period`` filters narrows the result set."""

    bucket_id = _active_bucket_id()
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_FILED,
        modelo="303",
        year="2026",
        period="1T",
    )
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_FILED,
        modelo="303",
        year="2026",
        period="2T",
        offset_seconds=1,
    )
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_FILED,
        modelo="303",
        year="2025",
        period="1T",
        offset_seconds=2,
    )

    result = invoke_cached_cli(
        ["app", "modelo", "history", "--modelo", "303", "--year", "2026", "--period", "1T"],
    )
    assert result.exit_code == 0, result.output
    assert "count\t1" in result.output, result.output
    # Year+period filters narrow to exactly one event row.
    assert result.output.count("modelo.filed") == 1


def test_history_year_filter_includes_real_lifecycle_filing_year_payloads() -> None:
    """Real lifecycle services stamp ``filing_year``; model history must include them."""

    bucket_id = _active_bucket_id()
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        modelo="303",
        year="2026",
        period="1T",
        year_payload_key="filing_year",
    )
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_EXPORTED,
        modelo="303",
        year="2026",
        period="1T",
        year_payload_key="filing_year",
        offset_seconds=1,
    )
    _seed_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.MODELO_EXPORTED,
        modelo="303",
        year="2025",
        period="1T",
        year_payload_key="filing_year",
        offset_seconds=2,
    )

    result = invoke_cached_cli(
        ["app", "modelo", "history", "--modelo", "303", "--year", "2026", "--period", "1T"],
    )

    assert result.exit_code == 0, result.output
    assert "count\t2" in result.output, result.output
    assert result.output.count("modelo.calculation.created") == 1
    assert result.output.count("modelo.exported") == 1
