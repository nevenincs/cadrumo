"""A profile with no taxpayer model still shows when its own declarations are due.

An undeclared taxpayer model leaves the generic obligation schedule unavailable,
but a declaration the profile already holds has its own registry window. Its
deadline and its place among the covered modelos must survive, and the list must
not advise a modelo the profile already has a declaration for.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ..modelo.declarations_calendar import DeclarationsCalendarSource
from ..modelo.declarations_list import DeclarationListGroup, declaration_list_rows
from ..overview.calendar_models import OverviewCalendarEntrySource
from ..overview.home import HomeAvailability
from .workbench_generation_support import NOW, PROFILE_ID, Repository, plain_generation_door, profile_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = NOW.year
_LOCAL_MODELOS = ("303", "390")


def _work_unit(operation: PinnedAuthorityOperation, modelo: str, filing_year: int, code: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, code)
    revision_id = operation.snapshot(modelo, filing_year=filing_year, period=code).revision.id
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=PROFILE_ID, modelo=modelo, filing_year=filing_year, period=period, revision_id=revision_id
        ),
        bucket_id=PROFILE_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"local {modelo}",
        created_at=NOW,
        updated_at=NOW,
    )


def _list_inputs(operation: PinnedAuthorityOperation):
    units = (
        _work_unit(operation, "303", _YEAR, "1T"),
        _work_unit(operation, "390", _YEAR - 1, "0A"),
    )
    catalogue = WorkUnitCatalogue.model_construct(work_units={unit.work_unit_id: unit for unit in units})
    door = plain_generation_door(
        operation,
        profile=Repository(profile_record(operation)),
        work_units=cast(Any, Repository(catalogue)),
    )
    inputs = door.read_declaration_list_inputs()
    assert inputs.workspace is not None
    return inputs.workspace, inputs.calendar


def test_an_undeclared_profile_keeps_each_local_declarations_own_deadline(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    workspace, calendar = _list_inputs(authority_operation)

    schedule = next(source for source in calendar.sources if source.source is DeclarationsCalendarSource.SCHEDULE)
    assert schedule.availability is HomeAvailability.UNAVAILABLE
    assert {entry.modelo for entry in calendar.entries} == set(_LOCAL_MODELOS)
    assert all(entry.source is OverviewCalendarEntrySource.LOCAL_WORK_UNIT for entry in calendar.entries)

    rows = {row.modelo: row for row in declaration_list_rows(workspace, calendar) if row.declaration is not None}
    assert set(rows) == set(_LOCAL_MODELOS)
    for row in rows.values():
        assert row.calendar is not None
        assert row.calendar.closes_on >= row.calendar.opens_on


def test_a_modelo_with_a_local_declaration_is_not_advised(authority_operation: PinnedAuthorityOperation) -> None:
    workspace, calendar = _list_inputs(authority_operation)

    advised = {item.modelo for item in calendar.coverage.advised}
    assert advised.isdisjoint(_LOCAL_MODELOS)
    assert advised, "the rest of the obligation universe stays undetermined"
    maybe = {
        row.modelo for row in declaration_list_rows(workspace, calendar) if row.group is DeclarationListGroup.MAYBE
    }
    assert maybe == advised
