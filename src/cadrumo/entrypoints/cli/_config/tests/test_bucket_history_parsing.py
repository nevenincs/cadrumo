"""Tests for bucket-history CLI filter parsing."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import typer
from pydantic import ValidationError

from .....domain.buckets import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ..._config_bucket_history_payloads import BucketHistoryEventPayload
from .._bucket_history import (
    _bucket_history_event_matches,
    _bucket_history_event_payload,
    _parse_bucket_event_types,
    _parse_bucket_history_instant,
    _resolve_profile_history_target,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _event_at(occurred_at: datetime) -> BucketEvent:
    """Build a real, content-addressed bucket event stamped at ``occurred_at``."""
    fields = {
        "bucket_id": "p",
        "event_type": BucketEventType.PROFILE_SELECTED,
        "occurred_at": occurred_at,
        "actor": "cadrumo.config.profile.history",
        "object_type": BucketEventObjectType.PROFILE,
        "object_id": "profile-1",
        "payload": {},
    }
    event_id = derive_bucket_event_id(**fields)
    return BucketEvent(event_id=event_id, payload_version=1, **fields)


def test_parse_bucket_event_types_returns_typed_filters() -> None:
    parsed = _parse_bucket_event_types(
        [
            BucketEventType.LEDGER_TRANSACTION_CREATED.value,
            BucketEventType.MODELO_FILED.value,
        ],
    )

    assert parsed == (
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.MODELO_FILED,
    )


def test_parse_bucket_event_types_rejects_unknown_value_with_localized_message() -> None:
    with pytest.raises(typer.BadParameter) as exc_info:
        _parse_bucket_event_types(["not-a-bucket-event"])

    message = str(exc_info.value)
    assert "not-a-bucket-event" in message
    assert BucketEventType.LEDGER_TRANSACTION_CREATED.value in message
    assert "BucketEventType" not in message


def test_parse_bucket_history_instant_normalises_naive_date_to_utc() -> None:
    parsed = _parse_bucket_history_instant("2026-01-01", flag="--since")

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(None)


def test_bucket_history_filter_compares_naive_since_against_aware_events() -> None:
    # Regression: a bare ``--since 2026-02-01`` parsed naive while events stamp
    # ``occurred_at`` as aware UTC, raising ``TypeError`` on the ``<`` comparison.
    since_dt = _parse_bucket_history_instant("2026-02-01", flag="--since")
    before = _event_at(datetime(2026, 1, 15, tzinfo=UTC))
    after = _event_at(datetime(2026, 3, 15, tzinfo=UTC))

    assert (
        _bucket_history_event_matches(
            before,
            since_dt=since_dt,
            until_dt=None,
            object_id_token=None,
            actor_token=None,
        )
        is False
    )
    assert (
        _bucket_history_event_matches(
            after,
            since_dt=since_dt,
            until_dt=None,
            object_id_token=None,
            actor_token=None,
        )
        is True
    )


def test_bucket_history_event_payload_carries_payload_version() -> None:
    """The profile-history projection carries the same discriminator LedgerHistoryEventPayload does.

    A consumer cannot select the correct interpretation of the free-form
    ``payload`` mapping without ``payload_version``; dropping it from the
    projection while the canonical BucketEvent carries it is the defect this
    regression pins.
    """
    event = _event_at(datetime(2026, 1, 15, tzinfo=UTC))

    payload = _bucket_history_event_payload(event)

    assert payload.payload_version == event.payload_version == 1


def test_bucket_history_event_payload_requires_payload_version() -> None:
    """A row missing the discriminator is refused, not silently defaulted."""
    with pytest.raises(ValidationError):
        BucketHistoryEventPayload.model_validate(
            {
                "event_id": "e" * 64,
                "event_type": BucketEventType.PROFILE_SELECTED,
                "occurred_at": datetime(2026, 1, 15, tzinfo=UTC),
                "actor": "cadrumo.config.profile.history",
                "object_type": BucketEventObjectType.PROFILE,
                "object_id": "profile-1",
            },
        )


def test_profile_history_without_name_resolves_the_active_profile(tmp_path) -> None:
    """The omitted subject is the real active profile, not a copied default."""
    from .....application.user_profile.registration import register_profile_with_credentials
    from .....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
    from .....domain.user_profile.values import UserProfileFact
    from .....tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label="History Subject",
            passphrase="history-subject-operator-secret",  # noqa: S106 - synthetic fixture
            facts=(UserProfileFact(path=PROFILE_OUTPUT_LANGUAGE_PATH, value="en"),),
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )

        assert _resolve_profile_history_target(None) == (
            "History Subject",
            outcome.bucket_id,
        )
