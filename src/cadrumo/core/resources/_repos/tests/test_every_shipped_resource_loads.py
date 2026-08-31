"""Every bundled resource file this package ships must actually load.

The festivos calendars shipped unloadable. The boundary model whose docstring
says it coerces TOML scalars into typed fields carried a strict config, strict
refuses that coercion, and so ``load_holiday_calendar`` raised for 2024, 2025 and
2026 alike. Its one production caller catches the error, falls back to the
unshifted date and logs at DEBUG, so the AEAT business-day deadline rule was
inert for every shipped year with nothing on the surface to say so.

The sibling tests here do load calendars, and they were red -- but they name
their years as literals, ``get(2024)`` and ``get(2025)``. That is the shape this
file exists to replace. A data family grows by having a file added to it, and a
test that names the years it knows about cannot notice the one that arrives
next: ``festivos-2026.toml`` was shipped and covered by nothing.

So the years are DISCOVERED from disk. The gate is over the property "every file
we ship can be read by the loader that owns it", not over a count of files or a
list of years, and it gets stronger on its own each time a file is added.

A loader that refuses is not always a defect in the loader -- a malformed file is
the other explanation -- but it is always a defect, which is what makes the
assertion worth making unconditionally.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ....resources._boundary import bundled_path
from ..holiday_calendars import HolidayCalendarRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: ``festivos-2026.toml`` -> ``2026``.
_YEAR_IN_NAME = re.compile(r"(\d{4})")


def _shipped_calendar_years() -> tuple[int, ...]:
    """Every year this package ships a festivos calendar for, read from disk."""
    calendars = Path(bundled_path("registry", "aeat", "calendars"))
    years = sorted(
        int(match.group(1))
        for path in calendars.glob("festivos-*.toml")
        if (match := _YEAR_IN_NAME.search(path.name)) is not None
    )
    return tuple(years)


def test_the_calendar_directory_is_not_empty() -> None:
    """Anti-vacuity: an empty discovery would make the load check pass over nothing.

    The failure this whole file guards against was silent, so a gate that can go
    quiet the same way is not worth having. If the directory moves or the naming
    changes, this fails rather than the suite going green over zero files.
    """
    years = _shipped_calendar_years()

    assert years, "no festivos-{year}.toml files were discovered; the gate below would prove nothing"


def test_every_shipped_holiday_calendar_loads() -> None:
    """Each shipped calendar loads through the real repository, no year hardcoded."""
    # Catching bare Exception is the point: any refusal at all means the file
    # does not load, and narrowing to the errors we happen to expect would
    # reintroduce the blind spot -- the original failure was a pydantic
    # ValidationError nobody predicted a TOML loader would raise.
    repository = HolidayCalendarRepository()
    failures: list[str] = []
    for year in _shipped_calendar_years():
        try:
            calendar = repository.get(year)
        except Exception as exc:
            failures.append(f"{year}: {type(exc).__name__}: {exc}")
            continue
        if calendar is None:
            failures.append(f"{year}: loaded as None")

    assert not failures, (
        "these bundled holiday calendars do not load, so the AEAT business-day "
        f"deadline shift silently falls back to the unshifted date for them: {failures}"
    )


def test_a_loaded_calendar_carries_holidays() -> None:
    """Loading must yield content, not an empty shell that parses.

    A calendar with no holidays would satisfy the check above while shifting
    nothing, which is indistinguishable from the failure that prompted this file.
    """
    repository = HolidayCalendarRepository()
    empty: list[int] = []
    for year in _shipped_calendar_years():
        calendar = repository.get(year)
        national = getattr(calendar, "national", ())
        if not national:
            empty.append(year)

    assert not empty, f"these calendars parsed but declare no national holidays: {empty}"
