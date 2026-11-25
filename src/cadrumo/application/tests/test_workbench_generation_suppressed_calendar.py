"""The workbench serves the obligations its calendar positively holds off the schedule.

A taxpayer model excludes some scheduled obligations (a sociedad limitada files no
Modelo 100). Those rows reach the frontends beside the calendar entries, with the
verdict the calendar reached and a sentence in the worker's language, and never
inside the entries, which stay the obligations that are owed.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.period import Period
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.codes import ModeloCode
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord, create_user_profile_record
from ..modelo.declarations_calendar import DeclarationsCalendarProjectionV1
from ..modelo.declarations_calendar_suppressed import (
    DeclarationsCalendarSuppressedEntryV1,
    project_suppressed_calendar_entries,
)
from ..overview.calendar import build_overview_calendar
from ..overview.calendar_models import SuppressedCalendarEntry
from ..user_profile.projections import projection_for_taxpayer
from ..user_profile.tests.persona_profile_facts import persona_profile_facts
from ..workbench_generation import InstalledWorkbenchGenerationProviderV1
from ..workbench_generation_calendar import calendar_query_range
from ..workbench_generation_projection import (
    WorkbenchGenerationOperationProjection,
    project_workbench_generation,
    restore_workbench_generation,
)
from .workbench_generation_support import NOW, PROFILE_ID, Repository, plain_generation_door

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LANGUAGES = tuple(OutputLanguage)
_VERDICT_KEYS = {
    ApplicabilityVerdict.NOT_APPLICABLE: "workspace.declarations.calendar.suppressed.verdict.not_applicable",
    ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH: (
        "workspace.declarations.calendar.suppressed.verdict.attribution_pass_through"
    ),
}


def _sociedad_limitada(operation: PinnedAuthorityOperation) -> UserProfileRecord:
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=persona_profile_facts("sociedad-limitada"),
    )


def _projection(operation: PinnedAuthorityOperation, record: UserProfileRecord) -> DeclarationsCalendarProjectionV1:
    generation = InstalledWorkbenchGenerationProviderV1(plain_generation_door(operation, profile=Repository(record)))()
    projection = generation.declarations_calendar.projection
    assert projection is not None
    return projection


def _held_back(operation: PinnedAuthorityOperation, record: UserProfileRecord) -> SuppressedCalendarEntry:
    """A suppressed row of the calendar the workbench builds, read straight from the overview builder."""
    taxpayer = projection_for_taxpayer(record, tax_id_default="00000000T", schema=operation.profile_schema())
    calendar = build_overview_calendar(
        taxpayer,
        calendar_query_range(NOW.date()),
        today=NOW.date(),
        raw_values={},
        operation=operation,
        show_suppressed=True,
    )
    return next(row for row in calendar.suppressed_entries if row.verdict is ApplicabilityVerdict.NOT_APPLICABLE)


@pytest.mark.parametrize("language", _LANGUAGES)
def test_an_excluded_obligation_is_served_beside_an_owed_one_with_its_verdict_and_words(
    authority_operation: PinnedAuthorityOperation, language: OutputLanguage
) -> None:
    record = _sociedad_limitada(authority_operation)

    with override_settings(cadrumo_output_language=language.value):
        calendar = _projection(authority_operation, record)

    owed = {entry.semantic_key() for entry in calendar.entries}
    assert ("303", NOW.year, "1T") in owed
    modelo_100 = [row for row in calendar.suppressed_entries if row.modelo == "100"]
    assert modelo_100, "an entity that files no Modelo 100 is told so"
    assert all(row.verdict is ApplicabilityVerdict.NOT_APPLICABLE for row in modelo_100)
    for row in calendar.suppressed_entries:
        assert row.verdict in _VERDICT_KEYS
        assert row.verdict_words == tr(_VERDICT_KEYS[row.verdict], locale=language.value)
        assert row.verdict_words_language is language
        assert row.reason
        assert row.opens_on <= row.closes_on <= row.adjusted_closes_on
        assert row.period.filing_year == row.filing_year


def test_the_entries_stay_the_obligations_the_calendar_finds_applicable(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    record = _sociedad_limitada(authority_operation)
    taxpayer = projection_for_taxpayer(record, tax_id_default="00000000T", schema=authority_operation.profile_schema())
    window = calendar_query_range(NOW.date())

    def entries(*, show_suppressed: bool) -> set[tuple[str, int, str]]:
        built = build_overview_calendar(
            taxpayer,
            window,
            today=NOW.date(),
            raw_values={},
            operation=authority_operation,
            show_suppressed=show_suppressed,
        )
        return {(entry.modelo, entry.period.filing_year, entry.period.registry_token) for entry in built.entries}

    assert entries(show_suppressed=True) == entries(show_suppressed=False)

    served = _projection(authority_operation, record)
    held_back = {row.semantic_key() for row in served.suppressed_entries}
    assert held_back
    assert held_back.isdisjoint(entry.semantic_key() for entry in served.entries)
    schedule = next(source for source in served.sources if source.item_count is not None)
    assert schedule.item_count == len(served.entries)


def test_an_obligation_the_calendar_could_not_decide_is_not_served_as_excluded(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    taxpayer = projection_for_taxpayer(
        _sociedad_limitada(authority_operation), tax_id_default="00000000T", schema=authority_operation.profile_schema()
    )
    calendar = build_overview_calendar(
        taxpayer,
        calendar_query_range(NOW.date()),
        today=NOW.date(),
        raw_values={},
        operation=authority_operation,
        show_suppressed=True,
    )
    undecided = {
        (row.modelo, row.period.filing_year, row.period.registry_token)
        for row in calendar.suppressed_entries
        if row.verdict is ApplicabilityVerdict.INCOMPLETE
    }
    assert undecided, "the sociedad limitada persona leaves modelos the calendar cannot decide"

    served = {row.semantic_key() for row in project_suppressed_calendar_entries(calendar.suppressed_entries)}

    assert served.isdisjoint(undecided)
    assert served == {
        (row.modelo, row.period.filing_year, row.period.registry_token)
        for row in calendar.suppressed_entries
        if row.verdict is not ApplicabilityVerdict.INCOMPLETE
    }


@pytest.mark.parametrize("verdict", tuple(_VERDICT_KEYS))
@pytest.mark.parametrize("language", _LANGUAGES)
def test_each_excluding_verdict_has_its_own_sentence_in_every_language(
    verdict: ApplicabilityVerdict, language: OutputLanguage
) -> None:
    entry = SuppressedCalendarEntry(
        modelo="100",
        period=Period.from_year_and_code(NOW.year - 1, "0A"),
        opens_on=date(NOW.year, 4, 1),
        closes_on=date(NOW.year, 6, 30),
        adjusted_closes_on=date(NOW.year, 6, 30),
        verdict=verdict,
        reason="registry reason",
    )

    with override_settings(cadrumo_output_language=language.value):
        (served,) = project_suppressed_calendar_entries((entry,))

    assert served.verdict is verdict
    assert served.verdict_words_language is language
    assert served.verdict_words == tr(_VERDICT_KEYS[verdict], locale=language.value)
    assert "workspace." not in served.verdict_words
    assert "%{" not in served.verdict_words
    assert served.reason == "registry reason"


@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_two_excluding_verdicts_read_differently(language: OutputLanguage) -> None:
    sentences = {tr(key, locale=language.value) for key in _VERDICT_KEYS.values()}

    assert len(sentences) == len(_VERDICT_KEYS)


@pytest.mark.parametrize("verdict", [ApplicabilityVerdict.APPLICABLE, ApplicabilityVerdict.INCOMPLETE])
def test_a_served_row_refuses_a_verdict_that_does_not_exclude_the_obligation(verdict: ApplicabilityVerdict) -> None:
    with pytest.raises(ValidationError):
        DeclarationsCalendarSuppressedEntryV1(
            modelo=ModeloCode("100"),
            filing_year=NOW.year - 1,
            period=Period.from_year_and_code(NOW.year - 1, "0A"),
            opens_on=date(NOW.year, 4, 1),
            closes_on=date(NOW.year, 6, 30),
            adjusted_closes_on=date(NOW.year, 6, 30),
            verdict=verdict,
            verdict_words="words",
            verdict_words_language=OutputLanguage.EN,
            reason="reason",
        )


def test_a_held_back_row_survives_the_registered_result_round_trip(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    record = _sociedad_limitada(authority_operation)
    generation = InstalledWorkbenchGenerationProviderV1(
        plain_generation_door(authority_operation, profile=Repository(record))
    )()
    calendar = generation.declarations_calendar.projection
    assert calendar is not None
    assert calendar.suppressed_entries

    public = project_workbench_generation(UUID(PROFILE_ID), generation)
    decoded = WorkbenchGenerationOperationProjection.model_validate_json(public.model_dump_json(), strict=True)
    restored = restore_workbench_generation(decoded)

    public_calendar = decoded.generation.declarations_calendar.projection
    assert public_calendar is not None
    assert len(public_calendar.suppressed_entries) == len(calendar.suppressed_entries)
    assert restored == generation
    assert restored.declarations_calendar.projection is not None
    assert restored.declarations_calendar.projection.suppressed_entries == calendar.suppressed_entries
    assert restored.declarations_calendar.projection.entries == calendar.entries


def test_the_real_overview_builder_supplies_the_dates_the_served_row_carries(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    record = _sociedad_limitada(authority_operation)
    row = _held_back(authority_operation, record)

    (served,) = project_suppressed_calendar_entries((row,))

    assert (served.opens_on, served.closes_on, served.adjusted_closes_on) == (
        row.opens_on,
        row.closes_on,
        row.adjusted_closes_on,
    )
    assert served.period == row.period
