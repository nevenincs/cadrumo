"""The overview calendar read serves each held-back row with the worker's words for its verdict.

A frontend that reads the overview calendar with suppressed rows shows the
sentence the worker rendered instead of wording a tax meaning of its own. A
positively excluded obligation and one the calendar could not decide read
differently, and the second never claims the obligation is excluded.
"""

from __future__ import annotations

import pytest

from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.user_profile.values import ProfileSetupState, create_user_profile_record
from ..overview.calendar import build_overview_calendar
from ..overview.calendar_models import OverviewCalendar
from ..overview.read_calendar_item_projection import OverviewSuppressedEntrySnapshot
from ..overview.read_calendar_projection import OverviewCalendarSnapshot
from ..user_profile.projections import projection_for_taxpayer
from ..user_profile.tests.persona_profile_facts import persona_profile_facts
from ..workbench_generation_calendar import calendar_query_range
from .workbench_generation_support import NOW, PROFILE_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_KEY = "workspace.declarations.calendar.suppressed.verdict."
_EXPECTED_KEYS = {
    ApplicabilityVerdict.NOT_APPLICABLE: _KEY + "not_applicable",
    ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH: _KEY + "attribution_pass_through",
    ApplicabilityVerdict.INCOMPLETE: _KEY + "incomplete",
}
_LANGUAGES = (OutputLanguage.ES, OutputLanguage.EN)


def _calendar(operation: PinnedAuthorityOperation) -> OverviewCalendar:
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=persona_profile_facts("sociedad-limitada"),
    )
    taxpayer = projection_for_taxpayer(record, tax_id_default="00000000T", schema=operation.profile_schema())
    return build_overview_calendar(
        taxpayer,
        calendar_query_range(NOW.date()),
        today=NOW.date(),
        raw_values={},
        operation=operation,
        show_suppressed=True,
    )


@pytest.mark.parametrize("language", _LANGUAGES)
def test_each_suppressed_row_of_the_read_carries_its_verdict_words_in_the_requested_language(
    authority_operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        snapshot = OverviewCalendarSnapshot.from_calendar(_calendar(authority_operation))

    verdicts = {row.verdict for row in snapshot.suppressed_entries}
    assert ApplicabilityVerdict.NOT_APPLICABLE in verdicts
    assert ApplicabilityVerdict.INCOMPLETE in verdicts, (
        "the sociedad limitada leaves modelos the calendar cannot decide"
    )
    for row in snapshot.suppressed_entries:
        assert row.verdict_words_language is language
        assert row.verdict_words == tr(_EXPECTED_KEYS[row.verdict], locale=language.value)
        assert "workspace." not in row.verdict_words
        assert "%{" not in row.verdict_words
        assert row.reason


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_undecided_words_say_neither_owed_nor_excluded(
    authority_operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        snapshot = OverviewCalendarSnapshot.from_calendar(_calendar(authority_operation))

    by_verdict = {row.verdict: row.verdict_words for row in snapshot.suppressed_entries}
    undecided = by_verdict[ApplicabilityVerdict.INCOMPLETE]
    assert undecided != by_verdict[ApplicabilityVerdict.NOT_APPLICABLE]
    expected = {
        OutputLanguage.ES: "no cuenta como obligatoria ni como excluida",
        OutputLanguage.EN: "neither owed nor excluded",
    }[language]
    assert expected in undecided.lower()


def test_the_snapshot_round_trips_the_canonical_calendar_and_the_registered_result(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = _calendar(authority_operation)
    with override_settings(cadrumo_output_language="en"):
        snapshot = OverviewCalendarSnapshot.from_calendar(calendar)

    decoded = OverviewCalendarSnapshot.model_validate_json(snapshot.model_dump_json(), strict=True)

    assert decoded == snapshot
    assert decoded.to_calendar().suppressed_entries == calendar.suppressed_entries
    row = decoded.suppressed_entries[0]
    with override_settings(cadrumo_output_language="en"):
        assert OverviewSuppressedEntrySnapshot.from_entry(row.to_entry()) == row
