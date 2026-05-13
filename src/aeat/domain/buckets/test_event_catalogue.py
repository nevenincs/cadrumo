"""Direct domain tests for ``BucketEventHistoryCatalogue`` invariants.

The catalogue is a frozen, strict pydantic record keyed by event id.
These tests exercise the strict-invariant boundary directly: payload
keys must equal each event's content-addressed id, ``for_bucket`` and
``for_object`` return chronologically-ordered slices, the catalogue is
immutable, and re-construction with a mismatched key raises a typed
error.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from aeat.domain.buckets._event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


_BUCKET_A = "operator-a"
_BUCKET_B = "operator-b"
_T0 = datetime(2026, 4, 1, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 4, 1, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


def _build_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    object_type: BucketEventObjectType,
    object_id: str,
    actor: str = "operator",
    payload: dict[str, str] | None = None,
) -> BucketEvent:
    canonical_payload = payload or {}
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=canonical_payload,
    )
    return BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload_version=1,
        payload=canonical_payload,
    )


def test_empty_catalogue_is_constructible_and_iterates_to_nothing() -> None:
    catalogue = BucketEventHistoryCatalogue()
    assert len(catalogue) == 0
    assert tuple(catalogue) == ()
    assert catalogue.for_bucket(_BUCKET_A) == ()
    assert (
        catalogue.for_object(
            object_type=BucketEventObjectType.WORK_UNIT, object_id="anything"
        )
        == ()
    )


def test_catalogue_rejects_key_that_does_not_match_event_id() -> None:
    event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    bogus_key = "0" * 64
    with pytest.raises(ValidationError, match=r"does not match event_id"):
        BucketEventHistoryCatalogue(events={bogus_key: event})


def test_catalogue_for_bucket_returns_chronological_order() -> None:
    later = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T2,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-2",
    )
    earlier = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    middle = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_VERIFICATION_PASSED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.VERIFICATION_REPORT,
        object_id="vr-1",
    )

    catalogue = BucketEventHistoryCatalogue(
        events={
            later.event_id: later,
            earlier.event_id: earlier,
            middle.event_id: middle,
        }
    )
    rows = catalogue.for_bucket(_BUCKET_A)
    assert tuple(e.occurred_at for e in rows) == (_T0, _T1, _T2)


def test_catalogue_for_bucket_isolates_buckets() -> None:
    a_event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-a",
    )
    b_event = _build_event(
        bucket_id=_BUCKET_B,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-b",
    )
    catalogue = BucketEventHistoryCatalogue(
        events={a_event.event_id: a_event, b_event.event_id: b_event}
    )
    assert tuple(e.event_id for e in catalogue.for_bucket(_BUCKET_A)) == (a_event.event_id,)
    assert tuple(e.event_id for e in catalogue.for_bucket(_BUCKET_B)) == (b_event.event_id,)


def test_catalogue_for_bucket_filters_by_event_types() -> None:
    calc = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    filed = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-1",
    )
    catalogue = BucketEventHistoryCatalogue(
        events={calc.event_id: calc, filed.event_id: filed}
    )
    rows = catalogue.for_bucket(_BUCKET_A, event_types=(BucketEventType.MODELO_FILED,))
    assert tuple(e.event_id for e in rows) == (filed.event_id,)


def test_catalogue_for_object_returns_events_for_one_object() -> None:
    fr_created = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-1",
    )
    other_fr = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_FILED,
        occurred_at=_T1,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-2",
    )
    fr_amended = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_AMENDED,
        occurred_at=_T2,
        object_type=BucketEventObjectType.FILING_RECORD,
        object_id="fr-1",
        payload={"amends": "true"},
    )
    catalogue = BucketEventHistoryCatalogue(
        events={
            fr_created.event_id: fr_created,
            other_fr.event_id: other_fr,
            fr_amended.event_id: fr_amended,
        }
    )
    rows = catalogue.for_object(
        object_type=BucketEventObjectType.FILING_RECORD, object_id="fr-1"
    )
    assert tuple(e.event_id for e in rows) == (fr_created.event_id, fr_amended.event_id)


def test_catalogue_get_returns_event_by_id_or_none() -> None:
    event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    catalogue = BucketEventHistoryCatalogue(events={event.event_id: event})
    assert catalogue.get(event.event_id) is event
    assert catalogue.get("0" * 64) is None


def test_catalogue_is_frozen_and_extra_forbid() -> None:
    catalogue = BucketEventHistoryCatalogue()
    with pytest.raises(ValidationError, match="frozen"):
        catalogue.events = MappingProxyType({})  # type: ignore[misc]

    event = _build_event(
        bucket_id=_BUCKET_A,
        event_type=BucketEventType.MODELO_CALCULATION_CREATED,
        occurred_at=_T0,
        object_type=BucketEventObjectType.CALCULATION_REVISION,
        object_id="rev-1",
    )
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        BucketEventHistoryCatalogue(events={event.event_id: event}, extra="no")  # type: ignore[call-arg]
