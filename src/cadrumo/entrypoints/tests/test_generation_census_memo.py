"""A session's census classification makes its next Inicio read classify only new journal records.

Every test reads through the composed census reader over a real encrypted
profile bucket and the production operation journal. Journal records are
written through the journal's own create and settlement doors. Each later
read is compared with a full read the memo never touched.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...application.user_profile.censal_readback import CensalHistoryRead
from ...application.workbench_capture_memory import (
    WorkbenchCaptureMemoryOwner,
    WorkbenchCensusMemo,
    WorkbenchCensusMemoKey,
)
from ...core.paths import effective_storage_root
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..censal_readback_composition import StoredCensalHistoryReader
from ..operation_composition import compose_operation_dependencies
from .test_generation_aeat_sync_rechecks import (
    _PROFILE_ID,
    _capture_census,
    _census,
    _CountedCensus,
    _generation_door,
    _observation,
    _other_operations,
    _profile,
    _settle,
    journal_decodes,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_OTHER_PROFILE_ID = UUID("1b2c3d4e-5f60-4718-89a0-b1c2d3e4f506")


@pytest.fixture
def decodes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The journal records the real repository decodes, by operation id."""
    return journal_decodes(monkeypatch)


def _full_history(profile_id: UUID = _PROFILE_ID) -> CensalHistoryRead:
    """What a read with no kept classification answers now."""
    return StoredCensalHistoryReader(profile_id).read()


def _load(memo: WorkbenchCensusMemo, profile_id: UUID = _PROFILE_ID) -> CensalHistoryRead:
    """One Inicio load's census read: each load composes its own reader over the session's memo."""
    return StoredCensalHistoryReader(profile_id, memo=memo).read()


def test_a_second_load_starts_from_the_kept_classification_and_decodes_only_new_records(
    tmp_path: Path, decodes: list[str]
) -> None:
    first = _observation(0)
    with _profile(tmp_path) as operands:
        _other_operations("a", "b", "c", operands=operands)
        _capture_census("d" * 64, operands, first)
        memo = WorkbenchCensusMemo()
        decodes.clear()
        assert _load(memo).observation == first
        assert set(decodes) == {"a" * 64, "b" * 64, "c" * 64, "d" * 64}, "the first load classifies every record"
        _other_operations("e", "f", operands=operands)
        decodes.clear()

        second = _load(memo)

        assert sorted(set(decodes)) == ["d" * 64, "e" * 64, "f" * 64]
        assert second == _full_history()


def test_a_second_generation_in_a_session_reads_only_census_and_new_records_and_publishes_the_same_census(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation, decodes: list[str]
) -> None:
    with _profile(tmp_path) as operands:
        _other_operations("a", "b", "c", operands=operands)
        _capture_census("d" * 64, operands, _observation(0))
        memo = WorkbenchCensusMemo()

        def generation() -> object:
            census = _CountedCensus(StoredCensalHistoryReader(_PROFILE_ID, memo=memo))
            door = _generation_door(authority_operation, census, mid_generation=lambda: None)
            return door.read_workbench_generation_inputs().aeat_sync

        first = generation()
        _other_operations("e", operands=operands)
        decodes.clear()
        second = generation()

        assert set(decodes) == {"d" * 64, "e" * 64}, "only the census record and the new record were decoded"
        assert second == first


def test_a_census_capture_landing_between_loads_is_the_next_loads_answer(tmp_path: Path) -> None:
    first, second = _observation(0), _observation(5)
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        _capture_census("b" * 64, operands, first)
        memo = WorkbenchCensusMemo()
        assert _load(memo).observation == first
        _capture_census("0" * 64, operands, second)

        reloaded = _load(memo)

        assert reloaded.observation == second
        assert reloaded == _full_history()


def test_a_census_capture_in_flight_at_one_load_settles_into_the_next(tmp_path: Path) -> None:
    observation = _observation(0)
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        in_flight = _census("b" * 64)
        memo = WorkbenchCensusMemo()
        assert _load(memo).observation is None
        asyncio.run(_settle(in_flight, operands=operands, observation=observation))

        reloaded = _load(memo)

        assert reloaded.observation == observation
        assert reloaded == _full_history()


def test_a_census_record_removed_between_loads_no_longer_answers(tmp_path: Path) -> None:
    older, newer = _observation(0), _observation(5)
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        _capture_census("b" * 64, operands, older)
        _capture_census("c" * 64, operands, newer)
        memo = WorkbenchCensusMemo()
        assert _load(memo).observation == newer
        OperationJournalRepository(storage_root=effective_storage_root())._repository.path_for("c" * 64).unlink()

        reloaded = _load(memo)

        assert reloaded.observation == older
        assert reloaded == _full_history()
        assert "c" * 64 not in reloaded.classified


def test_a_session_end_drops_the_kept_classification(tmp_path: Path, decodes: list[str]) -> None:
    with _profile(tmp_path) as operands:
        _other_operations("a", "b", operands=operands)
        _capture_census("c" * 64, operands, _observation(0))
        owner = WorkbenchCaptureMemoryOwner()
        _load(owner.for_profile(str(_PROFILE_ID)).census)

        owner.close()
        decodes.clear()
        _load(owner.for_profile(str(_PROFILE_ID)).census)

        assert set(decodes) == {"a" * 64, "b" * 64, "c" * 64}, "the next session classifies every record again"


def test_a_load_running_when_its_session_ends_keeps_nothing_for_the_next(tmp_path: Path, decodes: list[str]) -> None:
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        _capture_census("b" * 64, operands, _observation(0))
        owner = WorkbenchCaptureMemoryOwner()
        ended = owner.for_profile(str(_PROFILE_ID)).census
        owner.close()

        _load(ended)
        decodes.clear()
        _load(owner.for_profile(str(_PROFILE_ID)).census)

        assert set(decodes) == {"a" * 64, "b" * 64}


def test_a_classification_kept_for_another_profile_is_never_a_start(tmp_path: Path, decodes: list[str]) -> None:
    """A memo hands its classification back only under the exact profile and journal it was kept for."""
    with _profile(tmp_path) as operands:
        _other_operations("a", operands=operands)
        _capture_census("b" * 64, operands, _observation(0))
        root = str(effective_storage_root())
        memo = WorkbenchCensusMemo()
        stale = CensalHistoryRead(
            observation=None, classified=frozenset({"a" * 64, "b" * 64}), census_operations=frozenset()
        )
        memo.keep(WorkbenchCensusMemoKey(profile_id=_OTHER_PROFILE_ID, journal_root=root), stale)
        decodes.clear()

        read = _load(memo)

        assert set(decodes) == {"a" * 64, "b" * 64}, "the other profile's classification was not reused"
        assert read == _full_history()
        assert read.observation is not None
        assert memo.recall(WorkbenchCensusMemoKey(profile_id=_PROFILE_ID, journal_root=root)) == read
        assert memo.recall(WorkbenchCensusMemoKey(profile_id=_PROFILE_ID, journal_root=f"{root}-other")) is None


def test_switching_profiles_closes_the_first_profiles_census_memo() -> None:
    owner = WorkbenchCaptureMemoryOwner()
    first = owner.for_profile(str(_PROFILE_ID)).census
    key = WorkbenchCensusMemoKey(profile_id=_PROFILE_ID, journal_root="journal")
    first.keep(key, CensalHistoryRead(observation=None, classified=frozenset(), census_operations=frozenset()))

    second = owner.for_profile(str(_OTHER_PROFILE_ID)).census

    assert first.recall(key) is None
    assert second.recall(key) is None


def test_the_composed_services_drop_the_census_memo_of_the_owner_they_were_given(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    owner = WorkbenchCaptureMemoryOwner()
    key = WorkbenchCensusMemoKey(profile_id=_PROFILE_ID, journal_root="journal")
    history = CensalHistoryRead(observation=None, classified=frozenset(), census_operations=frozenset())
    with _profile(tmp_path):
        services = compose_operation_dependencies(authority_operation=authority_operation, capture_memory=owner)
        try:
            memo = owner.for_profile(str(_PROFILE_ID)).census
            memo.keep(key, history)
            assert memo.recall(key) == history

            services.end_session_reads()

            assert memo.recall(key) is None, "a lock, sign-out or lapsed lease drops the kept classification"
            assert owner.for_profile(str(_PROFILE_ID)).census.recall(key) is None
        finally:
            asyncio.run(services.shutdown())
