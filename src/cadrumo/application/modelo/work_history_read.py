"""One declaration's history in words: each recorded event, newest first, with its meaning and when it happened.

The meaning of every declaration event lives here, once. An event with a
lifecycle meaning (created, calculated, checked, filed, corrected …) carries
that meaning as its kind and is said in the words the filing history uses for
it; every other recorded event carries the closed kind ``other`` and words of
its own, so nothing that happened to the declaration is dropped or reworded by
a frontend. A rename names the old and the new name as its detail.

The history is read from the declaration's own event log; it never contacts
the AEAT and says nothing about what the AEAT holds. Recording a filing here
is the filer's local record, not a submission.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Final, Literal, Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import validate_utc_aware
from ...domain.buckets.event import BucketEvent, BucketEventId, BucketEventType, bucket_event_order_key
from .declarations_workspace_contracts import DeclarationsLifecycleKind
from .history import WorkUnitHistory

OTHER_HISTORY_KIND: Final = "other"
"""The kind of an event with no lifecycle meaning of its own."""

LIFECYCLE_KIND_BY_EVENT: Final[Mapping[BucketEventType, DeclarationsLifecycleKind]] = MappingProxyType(
    {
        BucketEventType.MODELO_WORK_UNIT_CREATED: DeclarationsLifecycleKind.CREATED,
        BucketEventType.MODELO_WORK_UNIT_RENAMED: DeclarationsLifecycleKind.RENAMED,
        BucketEventType.MODELO_WORK_UNIT_DISCARDED: DeclarationsLifecycleKind.DISCARDED,
        BucketEventType.MODELO_CALCULATION_CREATED: DeclarationsLifecycleKind.CALCULATED,
        BucketEventType.MODELO_VERIFICATION_PASSED: DeclarationsLifecycleKind.VERIFIED,
        BucketEventType.MODELO_VERIFICATION_REFUSED: DeclarationsLifecycleKind.VERIFICATION_REFUSED,
        BucketEventType.MODELO_FILED: DeclarationsLifecycleKind.FILED,
        BucketEventType.MODELO_FILED_SUPERSEDED: DeclarationsLifecycleKind.SUPERSEDED,
        BucketEventType.MODELO_AMENDED: DeclarationsLifecycleKind.AMENDED,
        BucketEventType.MODELO_FILING_IMPORTED: DeclarationsLifecycleKind.EXTERNAL_EVIDENCE_IMPORTED,
        BucketEventType.MODELO_EXPORTED: DeclarationsLifecycleKind.EXPORTED,
        BucketEventType.MODELO_FILING_RECONCILED: DeclarationsLifecycleKind.RECONCILED,
        BucketEventType.MODELO_OBSERVATION_OVERRIDDEN: DeclarationsLifecycleKind.OBSERVATION_OVERRIDDEN,
        BucketEventType.MODELO_OBSERVATION_OVERRIDE_CLEARED: DeclarationsLifecycleKind.OBSERVATION_OVERRIDE_CLEARED,
    }
)
"""The lifecycle meaning each declaration event carries; an event absent here has none."""

_LIFECYCLE_LOCALE_ROOT: Final[str] = "workspace.declarations.lifecycle"

_OTHER_EVENT_LOCALE_KEYS: Final[Mapping[BucketEventType, str]] = MappingProxyType(
    {
        BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED: "workspace.modelo.history.event.live_evidence_stamped",
        BucketEventType.MODELO_LEDGER_EVIDENCE_RECAPTURED: "workspace.modelo.history.event.ledger_evidence_recaptured",
        BucketEventType.MODELO_RECONCILED: "workspace.modelo.history.event.revision_reconciled",
        BucketEventType.MODELO_IVA_WALLET_CORRECTED: "workspace.modelo.history.event.iva_wallet_corrected",
        BucketEventType.MODELO_IVA_WALLET_OVERRIDE_RECORDED: (
            "workspace.modelo.history.event.iva_wallet_override_recorded"
        ),
        BucketEventType.MODELO_AUDIT_VERIFIED: "workspace.modelo.history.event.audit_verified",
        BucketEventType.MODELO_AUDIT_EXPORTED: "workspace.modelo.history.event.audit_exported",
    }
)
"""Words for the recorded events with no lifecycle meaning that a declaration's history shows."""

_OTHER_LOCALE_KEY: Final[str] = "workspace.modelo.history.other"
_RENAMED_DETAIL_LOCALE_KEY: Final[str] = "workspace.modelo.history.detail.renamed"


class ModeloWorkHistoryEntryV1(BaseModel):
    """One recorded event of a declaration, said in the language asked for.

    ``kind`` is the event's lifecycle meaning, or ``other`` for an event that
    has none; ``detail`` adds what the words alone do not say, when there is
    something to add.
    """

    model_config = STRICT_FROZEN_CONFIG

    event_id: BucketEventId
    kind: DeclarationsLifecycleKind | Literal["other"]
    words: str = Field(min_length=1)
    detail: str | None = None
    occurred_at: datetime

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _occurred_at_is_utc(self) -> Self:
        validate_utc_aware(self.occurred_at)
        return self


def history_kind(event_type: BucketEventType) -> DeclarationsLifecycleKind | Literal["other"]:
    """The lifecycle meaning of one event, or ``other`` when it carries none."""
    return LIFECYCLE_KIND_BY_EVENT.get(event_type, OTHER_HISTORY_KIND)


def _words(event: BucketEvent, language: OutputLanguage) -> str:
    kind = LIFECYCLE_KIND_BY_EVENT.get(event.event_type)
    if kind is not None:
        return tr(f"{_LIFECYCLE_LOCALE_ROOT}.{kind.value}", locale=language.value)
    return tr(_OTHER_EVENT_LOCALE_KEYS.get(event.event_type, _OTHER_LOCALE_KEY), locale=language.value)


def _detail(event: BucketEvent, language: OutputLanguage) -> str | None:
    if event.event_type is not BucketEventType.MODELO_WORK_UNIT_RENAMED:
        return None
    previous = event.payload.get("previous_name")
    new = event.payload.get("new_name")
    if previous is None or previous == "" or new is None or new == "":
        return None
    return tr(_RENAMED_DETAIL_LOCALE_KEY, locale=language.value, previous=previous, new=new)


def worded_history(history: WorkUnitHistory, language: OutputLanguage) -> tuple[ModeloWorkHistoryEntryV1, ...]:
    """The declaration's events, newest first, each with its kind, words and any detail in ``language``."""
    ordered = sorted(history.events, key=bucket_event_order_key, reverse=True)
    return tuple(
        ModeloWorkHistoryEntryV1(
            event_id=event.event_id,
            kind=history_kind(event.event_type),
            words=_words(event, language),
            detail=_detail(event, language),
            occurred_at=event.occurred_at,
        )
        for event in ordered
    )


def _require_disjoint_tables() -> None:
    if set(LIFECYCLE_KIND_BY_EVENT) & set(_OTHER_EVENT_LOCALE_KEYS):
        raise ValueError("an event with a lifecycle meaning is worded by that meaning")


_require_disjoint_tables()

__all__ = [
    "LIFECYCLE_KIND_BY_EVENT",
    "OTHER_HISTORY_KIND",
    "ModeloWorkHistoryEntryV1",
    "history_kind",
    "worded_history",
]
