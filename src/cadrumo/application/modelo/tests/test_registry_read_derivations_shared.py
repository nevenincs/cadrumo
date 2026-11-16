"""A form read derives the screen stamp and official casilla reading once per pinned generation and coordinate."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from ....domain.calculations.registry.authority_store import SQLiteAuthorityReader
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.modelos.calculation_screen_stamp import CalculationScreenStamp
from ..calculation_screen import calculation_screen_stamp, reading_calculation_screen_stamp
from ..work_review_assembly import (
    _official_casilla_reading,
    _OfficialReadingKey,
    _shared_official_casilla_reading,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "100"
_PERIOD = "0A"


@pytest.fixture
def reader() -> Iterator[SQLiteAuthorityReader]:
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        yield reader
    finally:
        reader.close()


def _stamp(operation: PinnedAuthorityOperation) -> CalculationScreenStamp:
    return reading_calculation_screen_stamp(
        operation, modelo=_MODELO, filing_year=filing_year_envelope().horizon, period=_PERIOD
    )


def _reading_key(operation: PinnedAuthorityOperation) -> _OfficialReadingKey:
    year = filing_year_envelope().horizon
    return _OfficialReadingKey(
        modelo_id=_MODELO,
        filing_year=year,
        period=_PERIOD,
        grade=operation.reachable_authority_grade(_MODELO, filing_year=year, period=_PERIOD),
    )


def test_the_shared_stamp_is_the_stamp_of_the_reading_snapshot(reader: SQLiteAuthorityReader) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())
    snapshot = operation.reading_snapshot(_MODELO, filing_year=filing_year_envelope().horizon, period=_PERIOD)

    assert _stamp(operation) == calculation_screen_stamp(snapshot, operation=operation)


def test_a_second_read_of_the_generation_reuses_the_stamp(reader: SQLiteAuthorityReader) -> None:
    first = _stamp(PinnedAuthorityOperation(reader, reader.pin()))

    assert _stamp(PinnedAuthorityOperation(reader, reader.pin())) is first


def test_another_generation_pin_derives_the_stamp_afresh(reader: SQLiteAuthorityReader) -> None:
    first = _stamp(PinnedAuthorityOperation(reader, reader.pin()))
    other = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        derived = _stamp(PinnedAuthorityOperation(other, other.pin()))

        assert derived is not first
        assert derived == first
    finally:
        other.close()


def test_the_shared_official_reading_is_the_reading_of_the_pinned_snapshot(reader: SQLiteAuthorityReader) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())
    key = _reading_key(operation)
    snapshot = operation.snapshot(key.modelo_id, filing_year=key.filing_year, period=key.period, grade=key.grade)

    shared = _shared_official_casilla_reading(key, operation=operation)
    direct = _official_casilla_reading(snapshot, operation=operation)

    assert dict(shared.estados) == dict(direct.estados)
    assert dict(shared.references) == dict(direct.references)
    assert set(shared.estados) == {casilla.id for casilla in snapshot.revision.casillas}


def test_a_second_read_reuses_the_official_reading_and_another_pin_derives_it_afresh(
    reader: SQLiteAuthorityReader,
) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())
    first = _shared_official_casilla_reading(_reading_key(operation), operation=operation)
    later = PinnedAuthorityOperation(reader, reader.pin())

    assert _shared_official_casilla_reading(_reading_key(later), operation=later) is first
    other = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        other_operation = PinnedAuthorityOperation(other, other.pin())
        derived = _shared_official_casilla_reading(_reading_key(other_operation), operation=other_operation)

        assert derived is not first
        assert dict(derived.estados) == dict(first.estados)
    finally:
        other.close()
