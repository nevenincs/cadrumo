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
