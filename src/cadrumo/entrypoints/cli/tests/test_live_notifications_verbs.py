"""CLI surface tests for `aeat app live notifications {list, show}`."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import Result
from pydantic import ValidationError

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

# INTENTIONAL: integration because it exercises the notifications CLI surface against
# isolated local storage without contacting AEAT.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        override_settings(cadrumo_audit_dir=tmp_path / "audit"),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
        )
        yield


def _invoke_notifications(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "notifications", *args])


def test_notifications_list_is_empty_on_fresh_bucket() -> None:
    result = _invoke_notifications(["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_notifications_show_refuses_unknown_snapshot() -> None:
    result = _invoke_notifications(["view", "no-such-snapshot"])
    assert result.exit_code != 0


def test_notification_snapshot_payloads_refuse_malformed_identity_time_url_and_count() -> None:
    """Notification transport preserves the persisted snapshot's strict fields."""

    from .._app_live_payloads import NotificationsCaptureResult, NotificationSnapshotListingPayload

    instant = datetime(2026, 8, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        NotificationSnapshotListingPayload(snapshot_id="bad", captured_at=instant, row_count=0)
    with pytest.raises(ValidationError):
        NotificationSnapshotListingPayload(snapshot_id="a" * 64, captured_at="not-a-timestamp", row_count=0)
    with pytest.raises(ValidationError):
        NotificationSnapshotListingPayload(snapshot_id="a" * 64, captured_at=instant, row_count=-1)
    with pytest.raises(ValidationError):
        NotificationsCaptureResult(
            bucket_id="00000000-0000-4000-8000-000000000000",
            snapshot_id="a" * 64,
            captured_at=instant,
            persisted_at=instant,
            row_count=0,
            source_url="",
        )
