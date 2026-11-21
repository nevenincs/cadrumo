"""The words the workbench generation serves with its Home projection, in each supported language."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ...core.external_constants import OutputLanguage
from ...core.period import Period
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.deadlines.festivos import DeadlineHolidayCoverage
from ...domain.deadlines.models import ObligationStatus
from ..operations.error_detail import served_words_language
from ..operations.public_mirror import project_public_mirror
from ..overview.agenda import OverviewAgenda
from ..overview.calendar_models import (
    CalendarCompleteness,
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarFilingEvidence,
    OverviewFilingStatus,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ..overview.home import (
    HOME_REASON_BLOCKED_DEPENDENCY,
    HOME_REASON_BLOCKED_EVIDENCE,
    HOME_REASON_BLOCKED_REVIEW,
    HOME_REASON_DECLARATION_NEEDS_REVIEW,
    HOME_REASON_EVIDENCE_MISSING,
    HOME_REASON_LEDGER_CLASSIFICATION_PENDING,
    HomeAccountSession,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeLedgerReadiness,
    HomeNextAction,
    HomeProjectionInput,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeZoneState,
    compose_home_projection,
)
from ..overview.next_actions import declare_next_action
from ..workbench_generation_home_words import serve_home_projection
from ..workbench_generation_public_contracts import PublicHomeProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_NOW = datetime(_YEAR, 9, 3, 10, 0, tzinfo=UTC)
_AVAILABLE = HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=_NOW)
_PERIOD = Period.from_year_and_code(_YEAR, "3T")
_UNIT = "a" * 64
_LANGUAGES = tuple(OutputLanguage)


def _entry() -> OverviewCalendarEntry:
    return OverviewCalendarEntry(
        modelo="303",
        period=_PERIOD,
        opens_on=date(_YEAR, 10, 1),
        closes_on=date(_YEAR, 10, 20),
        adjusted_closes_on=date(_YEAR, 10, 20),
        shift_reason="none",
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        evaluated_on=date(_YEAR, 9, 3),
        status=ObligationStatus.DUE_SOON,
        user_state=OverviewPeriodState.DUE,
        filing_year=_YEAR,
        filing_evidence=OverviewCalendarFilingEvidence(
            local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
            aeat_submission_state=OverviewAeatSubmissionState.ACCEPTED,
        ),
    )


def _projection(**updates: object) -> HomeProjectionV1:
    declarations = tuple(
        HomeDeclarationResume(
            work_unit_id=f"{index:x}" * 64,
            modelo="303",
            filing_year=_YEAR,
            period=_PERIOD,
            name=f"return {state.value}",
            state=state,
        )
        for index, state in enumerate(HomeDeclarationState, start=1)
    )
    actions = (
        HomeNextAction(
            rank=0,
            action=declare_next_action("operator.modelo.work.revisions", work_unit_id=_UNIT),
            reason_code="declaration_needs_review",
            modelo="303",
            filing_year=_YEAR,
            period=_PERIOD,
        ),
        HomeNextAction(rank=1, action=declare_next_action("operator.ledger.classify"), reason_code="not.a.code"),
    )
    values: dict[str, object] = {
        "generated_at": _NOW,
        "account": HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Local profile"),
        "actions_state": _AVAILABLE,
        "actions": actions,
        "declarations_state": _AVAILABLE,
        "declarations": declarations,
        "ledger_state": _AVAILABLE,
        "ledger_readiness": HomeLedgerReadiness(entries=40, requiring_review=2, unclassified=1, missing_evidence=3),
        "agenda_state": _AVAILABLE,
        "agenda_evidence_state": _AVAILABLE,
        "overview_agenda": OverviewAgenda(
            as_of=date(_YEAR, 9, 3),
            horizon_days=60,
            generated_at=_NOW,
            due_soon=(_entry(),),
            completeness=CalendarCompleteness(),
        ),
        "messages_state": _AVAILABLE,
        "messages_requiring_attention": 0,
    }
    values.update(updates)
    return compose_home_projection(HomeProjectionInput.model_validate(values))


def _said(words: str | None) -> str:
    """The sentence served, which is present and says something."""
    assert words is not None
    assert words.strip() == words and words
    return words


@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_row_and_count_is_served_worded_in_the_requested_language(language: OutputLanguage) -> None:
    served = serve_home_projection(_projection(), language)

    for item in served.actions:
        assert item.words_language is language
    action, other = served.actions
    for words in (action.action_words, action.reason_words, action.period_words):
        _said(words)
    # A reason outside the closed vocabulary is served unworded, never as its key.
    _said(other.action_words)
    assert other.reason_words is None and other.period_words is None
    assert {item.state: item.state_words for item in served.declarations}.keys() == set(HomeDeclarationState)
    for resume in served.declarations:
        _said(resume.state_words)
        _said(resume.period_words)
        assert resume.words_language is language
    assert served.ledger is not None
    assert served.ledger.words_language is language
    summary = _said(served.ledger.summary_words)
    for count in ("40", "2", "1", "3"):
        assert count in summary
    (entry,) = served.agenda
    # The agenda is worded when Home is composed, in the worker's own language.
    assert entry.words_language is served_words_language()
    _said(entry.filing_status_words)
    for words in (
        action.action_words,
        action.reason_words,
        *(resume.state_words for resume in served.declarations),
        served.ledger.summary_words,
    ):
        said = _said(words)
        assert "%{" not in said and "application.overview" not in said


def test_served_words_differ_between_the_supported_languages() -> None:
    projections = {language: serve_home_projection(_projection(), language) for language in _LANGUAGES}
    for field in (
        lambda p: p.actions[0].reason_words,
        lambda p: p.actions[0].action_words,
        lambda p: p.declarations[0].state_words,
        lambda p: p.ledger.summary_words if p.ledger else None,
    ):
        assert len({field(projection) for projection in projections.values()}) == len(_LANGUAGES)


def test_the_closed_reason_codes_all_have_words_in_every_language() -> None:
    for language in _LANGUAGES:
        for code in (
            HOME_REASON_BLOCKED_DEPENDENCY,
            HOME_REASON_BLOCKED_EVIDENCE,
            HOME_REASON_BLOCKED_REVIEW,
            HOME_REASON_DECLARATION_NEEDS_REVIEW,
            HOME_REASON_EVIDENCE_MISSING,
            HOME_REASON_LEDGER_CLASSIFICATION_PENDING,
        ):
            action = HomeNextAction(rank=0, action=declare_next_action("operator.ledger.classify"), reason_code=code)
            served = serve_home_projection(_projection(actions=(action,)), language)
            _said(served.actions[0].reason_words)


def test_a_zone_that_is_not_showing_its_data_says_why_and_never_gains_rows() -> None:
    zones = {
        "actions_state": HomeZoneState(
            availability=HomeAvailability.UNAVAILABLE, reason_code="workbench.home.actions_projector_unavailable"
        ),
        "declarations_state": HomeZoneState(
            availability=HomeAvailability.UNAVAILABLE, reason_code="a.reason.without.words"
        ),
        "ledger_state": HomeZoneState(
            availability=HomeAvailability.UNAVAILABLE, reason_code="workbench.ledger.snapshot_projector_unavailable"
        ),
        "agenda_state": HomeZoneState(
            availability=HomeAvailability.STALE,
            observed_at=_NOW,
            reason_code="workbench.home.agenda_projector_unavailable",
        ),
        "messages_state": HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED, reason_code="workbench.home.messages_never_pulled"
        ),
    }
    served = serve_home_projection(
        _projection(
            **zones,
            actions=(),
            declarations=(),
            ledger_readiness=None,
            overview_agenda=None,
            messages_requiring_attention=None,
        ),
        OutputLanguage.ES,
    )

    _said(served.actions_state.reason_words)
    assert served.actions_state.reason_words_language is OutputLanguage.ES
    _said(served.ledger_state.reason_words)
    _said(served.messages_state.reason_words)
    # An unworded reason and a stale zone are left to the frontend's own generic line.
    assert served.declarations_state.reason_words is None
    assert served.declarations_state.reason_words_language is None
    assert served.agenda_state.reason_words is None
    assert served.agenda_evidence_state.reason_words is None
    assert (served.actions, served.declarations, served.ledger, served.agenda) == ((), (), None, ())
    assert served.messages_requiring_attention is None


def test_the_public_projection_carries_the_served_words_unchanged() -> None:
    served = serve_home_projection(_projection(), OutputLanguage.CA)

    public = project_public_mirror(served, HomeProjectionV1, PublicHomeProjectionV1)

    assert isinstance(public, PublicHomeProjectionV1)
    assert public.actions[0].reason_words == served.actions[0].reason_words
    assert public.actions[0].action_words == served.actions[0].action_words
    assert public.declarations[0].state_words == served.declarations[0].state_words
    assert public.ledger is not None and served.ledger is not None
    assert public.ledger.summary_words == served.ledger.summary_words
    assert public.agenda[0].filing_status is OverviewFilingStatus.ACCEPTED
    assert public.agenda[0].filing_status_words == served.agenda[0].filing_status_words


def test_words_and_their_language_travel_together() -> None:
    with pytest.raises(ValueError, match="travel together"):
        HomeZoneState(
            availability=HomeAvailability.UNAVAILABLE, reason_code="x", reason_words="words", reason_words_language=None
        )
    with pytest.raises(ValueError, match="travel together"):
        HomeLedgerReadiness(entries=1, requiring_review=0, unclassified=0, missing_evidence=0, summary_words="words")
