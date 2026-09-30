"""The workbench header's deadline and day count agree with the calendar row of the same declaration.

The calendar is built over 2025 for a declared autónomo from the real deadline
engine and published authority, as the declarations calendar builds it, on a
day in April. For every declaration it lists, the deadline the workbench reads
for that modelo and period, and the words the header shows for it, name the
calendar row's effective date and count the days from the same day: the days
left to a window still open, and a window already closed as passed.
"""

from __future__ import annotations

from datetime import date

import pytest

from ......application.modelo.work_form_service import modelo_form_deadline
from ......application.overview.calendar import build_overview_calendar
from ......application.overview.calendar_models import OverviewCalendarRange
from ......application.overview.tests.calendar_test_support import profile
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.calculations.registry.authority import bundled_indexed_authority
from ......domain.deadlines.engine import DeadlineEngine
from ......domain.modelos.codes import ModeloCode
from ..header import deadline_view
from ..wording import date_text
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TODAY = date(2025, 4, 10)
_YEAR = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31))


def _calendar_words(effective: date) -> str:
    """What the header should say for a calendar row closing on ``effective``, counted from the same day."""
    shown = date_text(effective, OutputLanguage.EN)
    if effective < _TODAY:
        return tr("tui.modelo.workbench.header.deadline_passed", locale="en", date=shown)
    if effective == _TODAY:
        return tr("tui.modelo.workbench.header.deadline_today", locale="en", date=shown)
    return tr("tui.modelo.workbench.header.deadline", locale="en", date=shown, days=(effective - _TODAY).days)


@pytest.mark.timeout(300)
def test_the_header_names_the_calendar_rows_date_and_counts_its_days_from_the_same_day() -> None:
    compared: list[tuple[str, str, str]] = []
    with bundled_indexed_authority().operation() as operation, override_settings(cadrumo_output_language="en"):
        taxpayer = profile()
        calendar = build_overview_calendar(
            taxpayer, _YEAR, operation=operation, today=_TODAY, engine=DeadlineEngine(authority=operation)
        )
        for entry in calendar.entries:
            deadline = modelo_form_deadline(
                operation,
                ModeloCode(entry.modelo),
                entry.period,
                holiday_territory=taxpayer.holiday_territory,
                reference_on=_TODAY,
            )
            assert deadline is not None, f"the workbench reads no deadline for {entry.modelo} {entry.period}"
            assert deadline.nominal_closes_on == entry.closes_on
            assert deadline.closes_on == entry.adjusted_closes_on
            view = deadline_view(
                synthetic_form().model_copy(update={"deadline": deadline}), OutputLanguage.EN, recorded=False
            )
            assert view is not None
            label = f"Modelo {entry.modelo} {entry.period}"
            compared.append((label, view.text, _calendar_words(entry.adjusted_closes_on)))

    assert len(compared) >= 2, "the calendar lists the year's declarations"
    assert any("passed" in expected for _, _, expected in compared), "a window already closed is compared"
    assert any("days left" in expected for _, _, expected in compared), "a window still open is compared"
    for label, shown, expected in compared:
        assert shown == expected, f"{label}: the header says {shown!r}, the calendar row {expected!r}"
