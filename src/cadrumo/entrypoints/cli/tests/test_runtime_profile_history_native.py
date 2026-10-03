"""Native-worker journey for exact-profile event-history reads."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.login_session import resolve_login_target
from ....core.redaction.rules import redact_structured_for_cli_output
from ....core.type_guards import is_str_keyed_dict
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from .._config_bucket_history_payloads import BucketHistoryEventPayload, BucketHistoryResult
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]


def _invoke(
    profile: NativeCliProfileFixture,
    *command: str,
    json_output: bool = True,
) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    output_args = ("--format", "json" if json_output else "text")
    result = invoke_cached_cli(
        (*output_args, "--profile", profile.label, "--profile-secrets-stdin", *command),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def _event(
    *,
    profile_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_id: str,
    payload: dict[str, str],
) -> BucketEvent:
    fields = {
        "bucket_id": profile_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor": actor,
        "object_type": BucketEventObjectType.PROFILE,
        "object_id": object_id,
        "payload": payload,
    }
    return BucketEvent(event_id=derive_bucket_event_id(**fields), payload_version=2, **fields)


def _event_payload(event: BucketEvent) -> BucketHistoryEventPayload:
    return BucketHistoryEventPayload(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        actor=event.actor,
        object_type=event.object_type,
        object_id=event.object_id,
        payload_version=event.payload_version,
        payload=dict(event.payload),
    )


def _redacted_cli_payload(payload: object) -> dict[str, object]:
    redacted = redact_structured_for_cli_output(payload)
    assert is_str_keyed_dict(redacted)
    return redacted


def test_native_profile_history_preserves_full_events_filters_and_exact_target(tmp_path: Path) -> None:
    """Both parsed target forms return complete history; an unknown exact target refuses."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-profile-history", facts={})
        assert profile.label is not None
        profile_id = resolve_login_target(profile.label).bucket_id
        first = _event(
            profile_id=profile_id,
            event_type=BucketEventType.PROFILE_RENAMED,
            occurred_at=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
            actor="history.first",
            object_id="history-record-1",
            payload={"change": "first", "source": "native-test"},
        )
        second = _event(
            profile_id=profile_id,
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            occurred_at=datetime(2026, 2, 2, 12, 0, tzinfo=UTC),
            actor="history.second",
            object_id="history-record-2",
            payload={"change": "second", "source": "native-test"},
        )
        repository = BucketEventHistoryRepository()
        catalogue = repository.load()
        repository.save(
            BucketEventHistoryCatalogue(events={**catalogue.events, first.event_id: first, second.event_id: second})
        )
        history_before_full = repository.load()
        expected_events = history_before_full.for_bucket(profile_id)
        expected_full_result = BucketHistoryResult(
            operation="config.bucket.history",
            bucket_id=profile_id,
            events=[_event_payload(event) for event in expected_events],
        )
        expected_full_payload = _redacted_cli_payload(expected_full_result.model_dump(mode="json"))

        full = _invoke(profile, "config", "profile", "history", profile.label)
        assert full.exit_code == 0, full.output
        assert json.loads(full.output)["command"] == "config.bucket.history"
        assert profile_id not in full.output
        full_document = unwrap_cli_result(full)
        full_result = BucketHistoryResult.model_validate_json(json.dumps(full_document))
        expected_full_projection = BucketHistoryResult.model_validate_json(json.dumps(expected_full_payload))
        assert full_result == expected_full_projection
        assert full_result.operation == "config.bucket.history"
        assert full_result.event_types is None
        assert full_result.since is None and full_result.until is None
        assert full_result.object_id is None and full_result.actor is None
        assert next(event for event in full_result.events if event.event_id == second.event_id) == _event_payload(
            second
        )
        assert next(event for event in full_result.events if event.event_id == second.event_id).payload == {
            "change": "second",
            "source": "native-test",
        }
        assert next(event for event in full_result.events if event.event_id == second.event_id).payload_version == 2

        filtered = _invoke(
            profile,
            "config",
            "profile",
            "history",
            "--event-type",
            BucketEventType.PROFILE_VALUES_UPDATED.value,
            "--since",
            "2026-02-02",
            "--until",
            "2026-02-02T23:59:59+00:00",
            "--object-id",
            "history-record-2",
            "--actor",
            "history.second",
        )
        assert filtered.exit_code == 0, filtered.output
        expected_filtered_result = BucketHistoryResult(
            operation="config.bucket.history",
            bucket_id=profile_id,
            event_types=[BucketEventType.PROFILE_VALUES_UPDATED],
            since=datetime(2026, 2, 2, tzinfo=UTC),
            until=datetime(2026, 2, 2, 23, 59, 59, tzinfo=UTC),
            object_id="history-record-2",
            actor="history.second",
            events=[_event_payload(second)],
        )
        expected_filtered_payload = _redacted_cli_payload(expected_filtered_result.model_dump(mode="json"))
        filtered_document = unwrap_cli_result(filtered)
        filtered_result = BucketHistoryResult.model_validate_json(json.dumps(filtered_document))
        expected_filtered_projection = BucketHistoryResult.model_validate_json(json.dumps(expected_filtered_payload))
        assert filtered_result == expected_filtered_projection
        assert filtered_result.event_types == [BucketEventType.PROFILE_VALUES_UPDATED]
        assert filtered_result.since == datetime(2026, 2, 2, tzinfo=UTC)
        assert filtered_result.until == datetime(2026, 2, 2, 23, 59, 59, tzinfo=UTC)
        assert filtered_result.object_id == "history-record-2"
        assert filtered_result.actor == "history.second"
        assert filtered_result.events == [_event_payload(second)]

        text_history = _invoke(profile, "config", "profile", "history", json_output=False)
        assert text_history.exit_code == 0, text_history.output
        assert f"profile\t{profile.label}" in text_history.output
        assert f"event_count\t{len(expected_events)}" in text_history.output
        assert "history-record-2\thistory.second" in text_history.output

        refused = _invoke(profile, "config", "profile", "history", "unknown-history-profile")
        assert refused.exit_code != 0
        error = require_error_document(refused.output)["error"]
        assert error["code"] == "REFUSED_PROFILE_NOT_FOUND"
