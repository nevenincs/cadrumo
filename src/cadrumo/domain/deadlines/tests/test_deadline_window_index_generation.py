"""The deadline-window index is reused per authority generation, never across one."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.authority_artifact import AuthorityGenerationPin
from .. import engine as deadline_engine
from ..engine import indexed_deadline_windows

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2025
_OTHER_GENERATION = AuthorityGenerationPin(logical_generation="a" * 64, reader_incarnation="b" * 64)


@dataclass
class _RepinnedOperation:
    """The real operation's data under a stated generation identity."""

    operation: PinnedAuthorityOperation
    generation: AuthorityGenerationPin

    def pin(self) -> AuthorityGenerationPin:
        return self.generation

    def __getattr__(self, name: str) -> Any:
        return getattr(self.operation, name)


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as leased:
        yield leased


@pytest.fixture(autouse=True)
def _empty_index() -> Iterator[None]:
    """Each test starts from an empty index and leaves the process one."""
    deadline_engine._DEADLINE_WINDOW_INDEX.clear()
    yield
    deadline_engine._DEADLINE_WINDOW_INDEX.clear()


@pytest.fixture
def projections(monkeypatch: pytest.MonkeyPatch) -> list[tuple[AuthorityGenerationPin, int]]:
    projected: list[tuple[AuthorityGenerationPin, int]] = []
    project = deadline_engine._project_deadline_windows

    def counting(operation: Any, year: int) -> Any:
        projected.append((operation.pin(), year))
        return project(operation, year)

    monkeypatch.setattr(deadline_engine, "_project_deadline_windows", counting)
    return projected


def test_the_same_generation_is_projected_once(
    operation: PinnedAuthorityOperation,
    projections: list[tuple[AuthorityGenerationPin, int]],
) -> None:
    first = indexed_deadline_windows(operation, _YEAR)
    second = indexed_deadline_windows(operation, _YEAR)

    assert first, "the bundled generation must carry deadline windows, or reuse proves nothing"
    assert second is first
    assert len(projections) == 1


def test_another_generation_is_projected_again(
    operation: PinnedAuthorityOperation,
    projections: list[tuple[AuthorityGenerationPin, int]],
) -> None:
    """TEETH: a different generation identity never reads the index of another."""
    leased = indexed_deadline_windows(operation, _YEAR)
    repinned = _RepinnedOperation(operation=operation, generation=_OTHER_GENERATION)

    # CAST-RATIONALE-REPINNED-OPERATION: the wrapper delegates every attribute
    # to the leased operation and overrides only the generation identity, which
    # is the axis under test; the parameter type names the concrete operation.
    other = indexed_deadline_windows(cast("PinnedAuthorityOperation", repinned), _YEAR)

    assert [pin for pin, _ in projections] == [operation.pin(), _OTHER_GENERATION]
    assert other is not leased
    assert other == leased, "the same content under a stated other generation still projects equally"


def test_another_year_is_projected_again(
    operation: PinnedAuthorityOperation,
    projections: list[tuple[AuthorityGenerationPin, int]],
) -> None:
    indexed_deadline_windows(operation, _YEAR)
    indexed_deadline_windows(operation, _YEAR - 1)
    indexed_deadline_windows(operation, _YEAR)

    assert [year for _, year in projections] == [_YEAR, _YEAR - 1]


def test_the_index_stays_bounded(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deadline_engine, "_project_deadline_windows", lambda operation, year: ())
    for index in range(deadline_engine._DEADLINE_WINDOW_INDEX_LIMIT + 2):
        generation = AuthorityGenerationPin(logical_generation=f"{index:064x}", reader_incarnation="c" * 64)
        repinned = _RepinnedOperation(operation=operation, generation=generation)
        # CAST-RATIONALE-REPINNED-OPERATION: as above; only the identity varies.
        indexed_deadline_windows(cast("PinnedAuthorityOperation", repinned), _YEAR)

    assert len(deadline_engine._DEADLINE_WINDOW_INDEX) == deadline_engine._DEADLINE_WINDOW_INDEX_LIMIT


def _hydrating_projection(operation: PinnedAuthorityOperation, year: int) -> set[tuple[str, str, object]]:
    """Select every window's owner by hydrating the selected revision, as callers outside the index do."""
    owned: set[tuple[str, str, object]] = set()
    for modelo_id in operation.modelo_ids():
        for metadata in operation.modelo_directory(modelo_id).revisions:
            for window in metadata.deadline_windows:
                if window.filing_year != year:
                    continue
                selected = operation.revision_for_context(
                    modelo_id,
                    filing_year=window.filing_year,
                    period=window.period.registry_token,
                )
                if selected.id == metadata.id:
                    owned.add((modelo_id, str(metadata.id), window))
    return owned


@pytest.mark.parametrize("year", [_YEAR - 1, _YEAR, _YEAR + 1])
def test_metadata_selection_owns_the_same_windows_as_hydrated_selection(
    operation: PinnedAuthorityOperation,
    year: int,
) -> None:
    projected = indexed_deadline_windows(operation, year)
    assert projected, f"the bundled generation must carry {year} deadline windows"

    assert {(modelo, str(revision.id), window) for modelo, revision, window in projected} == _hydrating_projection(
        operation,
        year,
    )


@dataclass
class _CountingOperation:
    """The real operation, counting the complete revisions it hydrates."""

    operation: PinnedAuthorityOperation
    hydrated: list[tuple[str, str]]

    def revision(self, modelo_id: str, revision_id: str) -> Any:
        self.hydrated.append((str(modelo_id), revision_id))
        return self.operation.revision(modelo_id, revision_id)

    def revision_for_context(self, modelo_id: str, **selection: Any) -> Any:
        revision = self.operation.revision_for_context(modelo_id, **selection)
        self.hydrated.append((str(modelo_id), str(revision.id)))
        return revision

    def __getattr__(self, name: str) -> Any:
        return getattr(self.operation, name)


def test_projection_hydrates_no_revision(operation: PinnedAuthorityOperation) -> None:
    """TEETH: the directory metadata answers ownership and filing schedules; no revision is hydrated."""
    counting = _CountingOperation(operation=operation, hydrated=[])

    # CAST-RATIONALE-COUNTING-OPERATION: the wrapper delegates every attribute
    # to the leased operation and only records hydration, the axis under test.
    projected = deadline_engine._project_deadline_windows(cast("PinnedAuthorityOperation", counting), _YEAR)

    assert projected, "the bundled generation must carry deadline windows, or a zero count proves nothing"
    assert counting.hydrated == []


def test_each_window_carries_the_filing_schedules_of_its_hydrated_owner(operation: PinnedAuthorityOperation) -> None:
    """Every projected window answers filing-schedule applicability exactly as its hydrated owner does.

    A year the generation carries no window for must project none, exactly as
    the hydrating derivation owns none.
    """
    compared = 0
    for year in range(2024, 2028):
        projected = indexed_deadline_windows(operation, year)
        assert {(modelo, str(metadata.id), window) for modelo, metadata, window in projected} == (
            _hydrating_projection(operation, year)
        )
        for modelo, metadata, window in projected:
            hydrated = operation.revision_for_context(
                modelo,
                filing_year=window.filing_year,
                period=window.period.registry_token,
            )
            assert hydrated.id == metadata.id
            assert metadata.filing_schedules == hydrated.filing_schedules, (modelo, str(metadata.id), window.id)
            compared += 1
    assert compared, "the bundled generation must carry deadline windows in 2024-2027, or equality proves nothing"
