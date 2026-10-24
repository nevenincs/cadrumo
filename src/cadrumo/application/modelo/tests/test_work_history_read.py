"""A declaration's history says each recorded event once, newest first, with its meaning, words and when.

The events are real bucket events with content-derived ids: the declaration
was created, renamed, its calculation reconciled, and an event of another
family was recorded against it. Lifecycle events read as their lifecycle
meaning in the filing history's words, a rename names the old and new name,
and an event with no lifecycle meaning reads as ``other`` with words of its
own.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType, derive_bucket_event_id
from ..declarations_workspace_contracts import DeclarationsLifecycleKind
from ..history import WorkUnitHistory
from ..work_history_read import LIFECYCLE_KIND_BY_EVENT, OTHER_HISTORY_KIND, worded_history

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "5aa00000-0000-4000-8000-0000000000aa"
_UNIT = "e" * 64
_START = datetime(2026, 4, 2, 9, tzinfo=UTC)


def _event(event_type: BucketEventType, minutes: int, payload: dict[str, str] | None = None) -> BucketEvent:
    values = payload or {}
    occurred_at = _START + timedelta(minutes=minutes)
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=_BUCKET,
            event_type=event_type,
            occurred_at=occurred_at,
            actor="operator",
            object_type=BucketEventObjectType.WORK_UNIT,
            object_id=_UNIT,
            payload=values,
        ),
        bucket_id=_BUCKET,
        event_type=event_type,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.WORK_UNIT,
        object_id=_UNIT,
        payload_version=1,
        payload=values,
    )


@pytest.mark.parametrize("language", [OutputLanguage.EN, OutputLanguage.ES])
def test_each_event_reads_newest_first_with_its_meaning_and_words(language: OutputLanguage) -> None:
    created = _event(BucketEventType.MODELO_WORK_UNIT_CREATED, 0)
    renamed = _event(
        BucketEventType.MODELO_WORK_UNIT_RENAMED, 5, {"previous_name": "Primer trimestre", "new_name": "T1 2026"}
    )
    reconciled = _event(BucketEventType.MODELO_RECONCILED, 10)
    unrelated = _event(BucketEventType.LEDGER_RATIOS_SET, 15)
    history = WorkUnitHistory(bucket_id=_BUCKET, work_unit_id=_UNIT, events=(created, renamed, reconciled, unrelated))

    entries = worded_history(history, language)

    def say(key: str, **values: object) -> str:
        return tr(key, locale=language.value, **values)

    assert [entry.event_id for entry in entries] == [
        unrelated.event_id,
        reconciled.event_id,
        renamed.event_id,
        created.event_id,
    ]
    assert [entry.kind for entry in entries] == [
        OTHER_HISTORY_KIND,
        OTHER_HISTORY_KIND,
        DeclarationsLifecycleKind.RENAMED,
        DeclarationsLifecycleKind.CREATED,
    ]
    assert [entry.words for entry in entries] == [
        say("workspace.modelo.history.other"),
        say("workspace.modelo.history.event.revision_reconciled"),
        say("workspace.declarations.lifecycle.renamed"),
        say("workspace.declarations.lifecycle.created"),
    ]
    assert entries[2].detail == say(
        "workspace.modelo.history.detail.renamed", previous="Primer trimestre", new="T1 2026"
    )
    assert "T1 2026" in entries[2].detail
    assert all(entry.detail is None for entry in (entries[0], entries[1], entries[3]))
    assert [entry.occurred_at for entry in entries] == sorted(
        (event.occurred_at for event in history.events), reverse=True
    )


def test_every_lifecycle_meaning_is_carried_by_some_declaration_event() -> None:
    assert set(LIFECYCLE_KIND_BY_EVENT.values()) == set(DeclarationsLifecycleKind)
    assert all(event.name.startswith("MODELO_") for event in LIFECYCLE_KIND_BY_EVENT)
