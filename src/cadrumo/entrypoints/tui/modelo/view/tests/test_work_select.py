"""What the work-unit picker hands back to the caller that ran it.

The picker is reached from the command line, which reads its RESULT rather
than watching it: ``ModeloWorkSelectApp(units).run()`` returns the chosen
``work_unit_id``, or ``None`` when the operator leaves without choosing.
That return value is the whole contract between the CLI and this surface,
and nothing exercised it -- the package had no test module for the picker
at all, only a foreign-host narrowing check elsewhere. A surface whose only
output is a return value, with no test reading that value, can change how
it terminates without anything noticing.

Driven through the real host and real key presses rather than by calling
the screen's methods, because the mechanism under test is precisely the
handoff between screen and host: a screen that dismissed nothing, or a host
that never carried the dismissal out, would both leave the methods intact.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ......core.modelo import Modelo
from ......core.period import Period
from ......domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..work_select import ModeloWorkSelectApp

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "13000000-0000-4000-8000-000000000451"
_INSTANT = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_TERMINAL_SIZE = (100, 30)


def _unit(name: str, *, filing_year: int) -> WorkUnit:
    """Build one work unit the picker can render and return."""
    period = Period.from_year_and_code(filing_year, "4T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M303.value,
            filing_year=filing_year,
            period=period,
            revision_id="2026",
        ),
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M303.value,
        filing_year=filing_year,
        period=period,
        revision_id="2026",
        name=name,
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


@pytest.mark.asyncio
async def test_confirming_a_row_returns_that_work_unit_id() -> None:
    """Enter on the focused row hands its id back through the run result."""
    units = (_unit("First", filing_year=2025), _unit("Second", filing_year=2026))
    app = ModeloWorkSelectApp(units)
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

    assert app.return_value == units[1].work_unit_id, (
        f"the picker must return the id of the row the operator confirmed, not {app.return_value!r}"
    )


@pytest.mark.asyncio
async def test_quitting_returns_nothing_rather_than_a_row() -> None:
    """Leaving without choosing is an ordinary outcome, not a failure."""
    app = ModeloWorkSelectApp((_unit("Only", filing_year=2026),))
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()

    assert app.return_value is None, "quitting must not return a work unit"


@pytest.mark.asyncio
async def test_an_empty_catalogue_says_so_and_still_returns_nothing() -> None:
    """No work units is a state the picker shows, not one it crashes on."""
    app = ModeloWorkSelectApp(())
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        empty = app.screen.query_one("#modelo-select-empty")
        assert empty.display, "an empty catalogue must show its empty notice"
        await pilot.press("escape")
        await pilot.pause()

    assert app.return_value is None
