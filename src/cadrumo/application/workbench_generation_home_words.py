"""The words the workbench generation serves with its Home projection.

Home names its rows by closed codes: a reason, a declaration state, an action
identity, a zone's unavailability reason. A frontend that holds no tax
vocabulary cannot word them, so the projection that carries Home across a
process boundary serves each code's sentence in the worker's language beside
the code. A code the catalogue has no sentence for is served as absent, never
as a key or an invented label, and a zone that is not showing its data says so
in the frontend's own generic words.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from ..core.external_constants import OutputLanguage
from ..core.i18n.render import lookup_translation, tr
from .modelo.work_form_wording import period_words
from .operator_actions.served_actions import served_action_fields
from .overview.home import (
    HOME_REASON_BLOCKED_DEPENDENCY,
    HOME_REASON_BLOCKED_EVIDENCE,
    HOME_REASON_BLOCKED_REVIEW,
    HOME_REASON_DECLARATION_NEEDS_REVIEW,
    HOME_REASON_EVIDENCE_MISSING,
    HOME_REASON_LEDGER_CLASSIFICATION_PENDING,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeNextAction,
    HomeProjectionV1,
    HomeZoneState,
)

_ZONE_REASON_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "workbench.calendar.aeat_reader_unavailable": (
            "application.overview.served.home.zone.calendar_aeat_reader_unavailable"
        ),
        "workbench.calendar.taxpayer_model_undeclared": (
            "application.overview.served.home.zone.calendar_taxpayer_model_undeclared"
        ),
        "workbench.home.actions_projector_unavailable": (
            "application.overview.served.home.zone.home_actions_projector_unavailable"
        ),
        "workbench.home.agenda_projector_unavailable": (
            "application.overview.served.home.zone.home_agenda_projector_unavailable"
        ),
        "workbench.home.declarations_resume_projector_unavailable": (
            "application.overview.served.home.zone.home_declarations_resume_projector_unavailable"
        ),
        "workbench.home.messages_never_pulled": "application.overview.served.home.zone.home_messages_never_pulled",
        "workbench.home.taxpayer_profile_incomplete": (
            "application.overview.served.home.zone.home_taxpayer_profile_incomplete"
        ),
        "workbench.ledger.snapshot_projector_unavailable": (
            "application.overview.served.home.zone.ledger_snapshot_projector_unavailable"
        ),
    }
)
"""One catalogue key per unavailability reason Home words; any other reason is served unworded."""

_REASON_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        HOME_REASON_BLOCKED_DEPENDENCY: "application.overview.served.home.reason.blocked_dependency",
        HOME_REASON_BLOCKED_EVIDENCE: "application.overview.served.home.reason.blocked_evidence",
        HOME_REASON_BLOCKED_REVIEW: "application.overview.served.home.reason.blocked_review",
        HOME_REASON_DECLARATION_NEEDS_REVIEW: "application.overview.served.home.reason.declaration_needs_review",
        HOME_REASON_EVIDENCE_MISSING: "application.overview.served.home.reason.evidence_missing",
        HOME_REASON_LEDGER_CLASSIFICATION_PENDING: (
            "application.overview.served.home.reason.ledger_classification_pending"
        ),
    }
)
"""One catalogue key per closed next-action reason code."""

_DECLARATION_STATE_LOCALE_KEYS: Final[Mapping[HomeDeclarationState, str]] = MappingProxyType(
    {
        HomeDeclarationState.DRAFT: "application.overview.served.home.declaration_state.draft",
        HomeDeclarationState.NEEDS_REVIEW: "application.overview.served.home.declaration_state.needs_review",
        HomeDeclarationState.READY: "application.overview.served.home.declaration_state.ready",
        HomeDeclarationState.FILED: "application.overview.served.home.declaration_state.filed",
        HomeDeclarationState.DISCARDED: "application.overview.served.home.declaration_state.discarded",
    }
)
"""One catalogue key per closed resumable-declaration state."""

_LEDGER_SUMMARY_LOCALE_KEY: Final = "application.overview.served.home.ledger_summary"


def _words(key: str | None, language: OutputLanguage, **context: object) -> str | None:
    """``key``'s words in ``language``, or ``None`` when the catalogue has none."""
    if key is None or lookup_translation(key, locale=language.value) is None:
        return None
    words = tr(key, locale=language.value, **context).strip()
    return words or None


def _serve_zone_state(state: HomeZoneState, language: OutputLanguage) -> HomeZoneState:
    """``state`` with its unavailability reason said, for a zone that is not showing current data.

    A stale zone keeps its last observation and is worded by the frontend's
    generic line: the reason sentences say the zone was never read, which a
    stale one was.
    """
    words = None
    if state.reason_code is not None and state.availability is not HomeAvailability.STALE:
        words = _words(_ZONE_REASON_LOCALE_KEYS.get(state.reason_code), language)
    return state.model_copy(
        update={"reason_words": words, "reason_words_language": None if words is None else language}
    )


def _serve_next_action(item: HomeNextAction, language: OutputLanguage) -> HomeNextAction:
    """``item`` with its action, reason and period said in ``language``."""
    served_action = served_action_fields(str(item.action.action.action_id), language)["action_words"]
    action_words = served_action if isinstance(served_action, str) else None
    reason = _words(_REASON_LOCALE_KEYS.get(item.reason_code), language)
    period = None if item.period is None else period_words(item.period, language)
    served = any(words is not None for words in (action_words, reason, period))
    return item.model_copy(
        update={
            "action_words": action_words,
            "reason_words": reason,
            "period_words": period,
            "words_language": language if served else None,
        }
    )


def _serve_declaration_resume(item: HomeDeclarationResume, language: OutputLanguage) -> HomeDeclarationResume:
    """``item`` with its state and period said in ``language``."""
    return item.model_copy(
        update={
            "state_words": _words(_DECLARATION_STATE_LOCALE_KEYS[item.state], language),
            "period_words": period_words(item.period, language),
            "words_language": language,
        }
    )


def _serve_ledger_readiness(ledger: HomeLedgerReadiness, language: OutputLanguage) -> HomeLedgerReadiness:
    """``ledger`` with its counts said in ``language``."""
    words = _words(
        _LEDGER_SUMMARY_LOCALE_KEY,
        language,
        entries=ledger.entries,
        requiring_review=ledger.requiring_review,
        unclassified=ledger.unclassified,
        missing_evidence=ledger.missing_evidence,
    )
    return ledger.model_copy(update={"summary_words": words, "words_language": None if words is None else language})


def serve_home_projection(projection: HomeProjectionV1, language: OutputLanguage) -> HomeProjectionV1:
    """``projection`` with the words of every code it carries served in ``language``.

    Unavailable zones keep carrying no rows and no counts: serving adds words
    to what a zone holds and never fills a zone.
    """

    def zone(state: HomeZoneState) -> HomeZoneState:
        return _serve_zone_state(state, language)

    return projection.model_copy(
        update={
            "actions_state": zone(projection.actions_state),
            "actions": tuple(_serve_next_action(item, language) for item in projection.actions),
            "declarations_state": zone(projection.declarations_state),
            "declarations": tuple(_serve_declaration_resume(item, language) for item in projection.declarations),
            "ledger_state": zone(projection.ledger_state),
            "ledger": None if projection.ledger is None else _serve_ledger_readiness(projection.ledger, language),
            "agenda_state": zone(projection.agenda_state),
            "agenda_evidence_state": zone(projection.agenda_evidence_state),
            "messages_state": zone(projection.messages_state),
        }
    )


__all__ = ["serve_home_projection"]
