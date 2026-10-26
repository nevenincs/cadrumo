"""A pinned operation shares each validated snapshot only under every input it depends on."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.time.clock import frozen_clock
from ..authority import PinnedAuthorityOperation
from ..authority_artifact import AuthorityComponentQuery, AuthorityGenerationPin
from ..authority_location import bundled_authority_descriptor_path
from ..authority_store import SQLiteAuthorityReader
from ..schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "303"
_YEAR = 2025
_PERIOD = "4T"


class _ForwardingReader:
    """A reader over the same generation that owns no accounted cache of its own."""

    def __init__(self, reader: SQLiteAuthorityReader) -> None:
        self._reader = reader

    def pin(self) -> AuthorityGenerationPin:
        return self._reader.pin()

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        return self._reader.load(query, pin=pin)

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        return self._reader.component_queries()


@pytest.fixture
def reader() -> Iterator[SQLiteAuthorityReader]:
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        yield reader
    finally:
        reader.close()


def _snapshot(
    operation: PinnedAuthorityOperation,
    *,
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
    on: date | None = None,
) -> RegistrySnapshot:
    return operation.snapshot(_MODELO, filing_year=_YEAR, period=_PERIOD, on=on, grade=grade)


def test_a_repeated_coordinate_returns_the_identical_snapshot(reader: SQLiteAuthorityReader) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())

    first = _snapshot(operation)

    assert _snapshot(operation) is first
    assert _snapshot(PinnedAuthorityOperation(reader, reader.pin())) is first


def test_concurrent_requests_for_one_coordinate_share_one_snapshot(reader: SQLiteAuthorityReader) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())
    barrier = Barrier(4)

    def request(_: int) -> RegistrySnapshot:
        barrier.wait()
        return _snapshot(operation)

    with ThreadPoolExecutor(max_workers=4) as executor:
        snapshots = tuple(executor.map(request, range(4)))

    assert all(snapshot is snapshots[0] for snapshot in snapshots)


def test_grade_and_reference_date_are_part_of_the_shared_coordinate(reader: SQLiteAuthorityReader) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())

    filing = _snapshot(operation)
    applicability = _snapshot(operation, grade=RegistryAuthorityGrade.APPLICABILITY)
    dated = _snapshot(operation, on=date(_YEAR + 1, 1, 20))

    assert applicability is not filing
    assert dated is not filing
    assert dated is not applicability
    assert _snapshot(operation, grade=RegistryAuthorityGrade.APPLICABILITY) is applicability
    assert _snapshot(operation, on=date(_YEAR + 1, 1, 20)) is dated


def test_a_new_madrid_date_revalidates_rather_than_reusing_the_previous_day(reader: SQLiteAuthorityReader) -> None:
    operation = PinnedAuthorityOperation(reader, reader.pin())

    with frozen_clock(datetime(2026, 3, 10, 12, tzinfo=UTC)):
        first_day = _snapshot(operation)
        assert _snapshot(operation) is first_day
    with frozen_clock(datetime(2026, 3, 11, 12, tzinfo=UTC)):
        next_day = _snapshot(operation)

    assert next_day is not first_day
    assert next_day.revision.id == first_day.revision.id


def test_another_reader_incarnation_never_serves_this_generations_snapshot(reader: SQLiteAuthorityReader) -> None:
    first = _snapshot(PinnedAuthorityOperation(reader, reader.pin()))
    other = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        assert other.pin() != reader.pin()
        assert other.pin().logical_generation == reader.pin().logical_generation
        assert _snapshot(PinnedAuthorityOperation(other, other.pin())) is not first
    finally:
        other.close()


def test_a_reader_without_the_accounted_cache_builds_every_snapshot_afresh(reader: SQLiteAuthorityReader) -> None:
    published = _snapshot(PinnedAuthorityOperation(reader, reader.pin()))
    forwarding = _ForwardingReader(reader)
    operation = PinnedAuthorityOperation(forwarding, forwarding.pin())

    first = _snapshot(operation)

    assert first is not published
    assert _snapshot(operation) is not first


def test_a_shared_snapshot_is_charged_for_its_own_members_not_again_for_its_components(
    reader: SQLiteAuthorityReader,
) -> None:
    forwarding = _ForwardingReader(reader)
    _snapshot(PinnedAuthorityOperation(forwarding, forwarding.pin()))
    components = reader.stats()

    _snapshot(PinnedAuthorityOperation(reader, reader.pin()))
    shared = reader.stats()

    assert shared.entries == components.entries + 1
    assert 0 < shared.retained_weight - components.retained_weight <= 64 * 1024
    assert shared.retained_weight <= shared.budget
