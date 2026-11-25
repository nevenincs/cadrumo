"""The six coded payer facts raise their unset warning on a real profile record.

``withholding.has_employees``,
``withholding.pays_professionals_with_retencion``,
``withholding.pays_rent_with_retencion``,
``withholding.pays_capital_income_with_retencion``,
``withholding.pays_non_resident_income_with_retencion`` and
``iva.does_intracomunitario`` each declare an unset-warning locale key in
:data:`~cadrumo.application.overview.calendar_warnings.PROFILE_FIELD_WARNING_LOCALE_KEYS`,
yet no calendar could reach it while the setup binding catalogue forced a
``false`` default onto an absent path: the projection always carried an answer,
so the gap never existed to report. With the default gone the warning is
reachable, and this exercises it through the production calendar rather than
through the warning helper alone.

Both canonical projections are covered, because the calendar's ``raw_values``
argument is fed from either one depending on the caller:
:func:`~cadrumo.application.user_profile.projections.record_to_path_values`
keys the six facts at their dotted schema path, while
:func:`~cadrumo.application.user_profile.projections.record_to_values` keys
them at the registry selector token the applicability rules name. A warning
that only resolves under one shape is a surface-dependent gap, which is why
neither shape is assumed to stand for the other.

A stated ``false`` must silence the warning exactly as a stated ``true``
does. That is the whole point of the three-state contract: *I have no
employees* is an answer, and reporting it as a profile gap would send the
operator back to a question already answered.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ...user_profile.projections import (
    projection_for_taxpayer,
    record_to_path_values,
    record_to_values,
)
from ...user_profile.tests.payer_fact_record_support import (
    PAYER_FACT_GATED_MODELOS,
    PAYER_FACT_PATHS,
    payer_fact_record,
)
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendar, OverviewCalendarRange
from ..calendar_warnings import PROFILE_FIELD_WARNING_LOCALE_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HORIZON = PublishedGovernedFactSource().supported_filing_years().horizon
"""The registry's own last globally authored filing year.

The warnings under test are about profile answers, not about a year, so the
reference date is taken from the support envelope rather than written down:
a literal year would start standing outside the envelope the moment the
registry moves its horizon, and the rows would disappear for a reason that
has nothing to do with a payer fact.
"""

_TODAY = date(_HORIZON, 10, 19)
_RANGE = OverviewCalendarRange(from_date=date(_HORIZON, 1, 1), to_date=date(_HORIZON + 1, 2, 1))
"""A span wide enough to surface the periodic withholding and intracommunity rows.

It covers the horizon year whole and reaches into the following January,
because the fourth-quarter and annual windows of a year open after it ends.
"""

PAYER_FACT_WARNING_CODES = (
    "has_employees",
    "pays_professionals_with_retencion",
    "pays_rent_with_retencion",
    "pays_capital_income_with_retencion",
    "pays_non_resident_income_with_retencion",
    "does_intracomunitario",
)
"""The registry selector token each payer fact's warning is coded by.

:func:`~cadrumo.application.overview.calendar_warnings.build_completeness_and_warnings`
codes a profile-gap warning by the gating key, and the gating keys come from
the applicability rules, which name the selector rather than the schema path.
"""

_PROJECTION_SHAPES = ("path", "selector")


def _raw_values(
    record_answer: bool | None,
    shape: str,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[Mapping[str, object], OverviewCalendar]:
    """Build the calendar from one record under one of the two projection shapes."""
    record = payer_fact_record(operation, answer=record_answer)
    schema = operation.profile_schema()
    raw: Mapping[str, object] = (
        record_to_path_values(record) if shape == "path" else record_to_values(record, schema=schema)
    )
    calendar = build_overview_calendar(
        projection_for_taxpayer(record, schema=schema),
        _RANGE,
        operation=operation,
        today=_TODAY,
        raw_values=raw,
    )
    return raw, calendar


def _payer_warning_codes(calendar: OverviewCalendar) -> frozenset[str]:
    return frozenset(warning.code for warning in calendar.warnings) & frozenset(PAYER_FACT_WARNING_CODES)


def test_every_payer_fact_warning_code_declares_its_locale_key() -> None:
    """The codes asserted below are the ones the module declares a sentence for."""
    assert frozenset(PAYER_FACT_WARNING_CODES) <= frozenset(PROFILE_FIELD_WARNING_LOCALE_KEYS)
    assert len(PAYER_FACT_WARNING_CODES) == len(PAYER_FACT_PATHS)


@pytest.mark.parametrize("shape", _PROJECTION_SHAPES)
def test_an_unanswered_payer_fact_warns_on_the_calendar(
    shape: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    raw, calendar = _raw_values(None, shape, operation=authority_operation)

    assert not [key for key in (*PAYER_FACT_WARNING_CODES, *PAYER_FACT_PATHS) if key in raw]
    assert _payer_warning_codes(calendar) == frozenset(PAYER_FACT_WARNING_CODES)
    assert frozenset(PAYER_FACT_WARNING_CODES) <= frozenset(calendar.completeness.defaulted_keys)
    for warning in calendar.warnings:
        if warning.code in PAYER_FACT_WARNING_CODES:
            assert warning.message == PROFILE_FIELD_WARNING_LOCALE_KEYS[warning.code]
            assert warning.affected_modelos


@pytest.mark.parametrize("shape", _PROJECTION_SHAPES)
@pytest.mark.parametrize("answer", [True, False])
def test_an_answered_payer_fact_raises_no_calendar_warning(
    shape: str,
    answer: bool,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    raw, calendar = _raw_values(answer, shape, operation=authority_operation)

    rendered = "true" if answer else "false"
    keys = PAYER_FACT_PATHS if shape == "path" else PAYER_FACT_WARNING_CODES
    assert [raw.get(key) for key in keys] == [rendered] * len(keys)
    assert not _payer_warning_codes(calendar)
    assert not frozenset(PAYER_FACT_WARNING_CODES) & frozenset(calendar.completeness.defaulted_keys)
    assert frozenset(PAYER_FACT_WARNING_CODES) <= frozenset(calendar.completeness.explicitly_set_keys)


@pytest.mark.parametrize("shape", _PROJECTION_SHAPES)
def test_the_unanswered_warning_names_the_modelos_the_fact_gates(
    shape: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A warning that named no gated modelo would not tell the operator what is at stake."""
    _raw, calendar = _raw_values(None, shape, operation=authority_operation)

    named = frozenset(
        modelo
        for warning in calendar.warnings
        if warning.code in PAYER_FACT_WARNING_CODES
        for modelo in warning.affected_modelos
    )
    assert frozenset(PAYER_FACT_GATED_MODELOS) <= named
