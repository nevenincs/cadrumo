"""Appending proves only the newcomer's id; tampered events are still refused."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from .. import event as event_module
from ..errors import BucketEventValidationError
from ..event import BucketEvent, BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ..event_repository import append_bucket_event, build_bucket_event

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET = "5612ee74-f4e5-47c2-9df9-2afa04286b2a"
_T0 = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)


def _event(index: int) -> BucketEvent:
    return build_bucket_event(
        bucket_id=_BUCKET,
        event_type=BucketEventType.LEDGER_TRANSACTION_CORRECTION_APPLIED,
        occurred_at=_T0 + timedelta(seconds=index),
        actor="operator",
        object_type=BucketEventObjectType.LEDGER_TRANSACTION,
        object_id=f"transaction-{index}",
        payload={"sequence": str(index)},
        payload_version=1,
    )


def _history(size: int) -> BucketEventHistoryCatalogue:
    catalogue = BucketEventHistoryCatalogue()
    for index in range(size):
        catalogue = append_bucket_event(catalogue, _event(index))
    return catalogue


def test_appending_to_a_long_history_derives_one_id_per_append(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [_event(index) for index in range(60)]
    derivations: list[str] = []
    derive = event_module.derive_bucket_event_id

    def counting(**fields: Any) -> str:
        derivations.append(str(fields["object_id"]))
        return derive(**fields)

    monkeypatch.setattr(event_module, "derive_bucket_event_id", counting)
    catalogue = BucketEventHistoryCatalogue()
    for event in events:
        catalogue = append_bucket_event(catalogue, event)

    assert len(derivations) == len(events)
    assert list(catalogue.events) == [event.event_id for event in events]


def test_an_appended_history_equals_a_validated_one() -> None:
    appended = _history(5)

    assert appended == BucketEventHistoryCatalogue(events=dict(appended.events))


def test_a_tampered_event_is_refused_at_append() -> None:
    """TEETH: an instance that skipped validation cannot enter the history unproven."""
    history = _history(3)
    forged = _event(7).model_copy(update={"payload": {"sequence": "tampered"}})
    assert forged.event_id not in history.events, "a colliding id would be refused for another reason"

    with pytest.raises(BucketEventValidationError) as refused:
        append_bucket_event(history, forged)

    context = refused.value.context
    assert context is not None
    assert context["event_id_matches_derivation"] is False


def test_a_tampered_persisted_payload_is_refused_on_load() -> None:
    """TEETH: events read back from storage are still derived and compared."""
    stored = _history(3).model_dump_json()
    tampered = stored.replace('"sequence":"2"', '"sequence":"9"')
    assert tampered != stored

    with pytest.raises((BucketEventValidationError, ValidationError)):
        BucketEventHistoryCatalogue.model_validate_json(tampered)
