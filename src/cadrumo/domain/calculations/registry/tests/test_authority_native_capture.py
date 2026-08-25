"""Concurrency and ownership proofs for native registry authority capture."""

from __future__ import annotations

import ast
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Barrier, Event, Lock, Thread

import pytest

from .....core import RegistryAuthorityGrade, scan_directory
from .....tests import REPO_ROOT
from .. import (
    RegistryAuthorityCapture,
    RegistryRevisionInspection,
    RegistrySnapshot,
    RegistrySnapshotError,
    ValidatedRegistryAuthority,
    bundled_authority,
    reset_registry_caches,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODEL0_ID = "130"
_FILING_YEAR = 2026
_PERIOD = "1T"
_CAPTURE_WORKERS = 8
_REGISTRY_SOURCE = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
_AUTHORITY_SOURCE = _REGISTRY_SOURCE / "_authority.py"
_FACADE_SOURCE = _REGISTRY_SOURCE / "__init__.py"


def _ignore_authority_scope(root: Path, source_root: Path) -> None:
    del root, source_root


def _ignore_authority_publication(root: Path, source_root: Path, generation: int) -> None:
    del root, source_root, generation


def _ignore_registry_reset() -> None:
    return


@dataclass(slots=True)
class _AuthorityLifecycleProbe:
    """Coordinate tests through the authority owner's real lifecycle milestones."""

    on_construction_started: Callable[[Path, Path], None] = _ignore_authority_scope
    on_published: Callable[[Path, Path, int], None] = _ignore_authority_publication
    on_reset_requested: Callable[[], None] = _ignore_registry_reset
    on_reset_acquired: Callable[[], None] = _ignore_registry_reset

    def authority_construction_started(self, *, root: Path, source_root: Path) -> None:
        self.on_construction_started(root, source_root)

    def authority_published(self, *, root: Path, source_root: Path, generation: int) -> None:
        self.on_published(root, source_root, generation)

    def registry_cache_reset_requested(self) -> None:
        self.on_reset_requested()

    def registry_cache_reset_acquired(self) -> None:
        self.on_reset_acquired()


def test_native_capture_selects_the_existing_inspection_or_snapshot_authority(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    inspection_capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    snapshot_capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )

    assert isinstance(inspection_capture, RegistryAuthorityCapture)
    assert isinstance(inspection_capture.projection, RegistryRevisionInspection)
    assert isinstance(snapshot_capture.projection, RegistrySnapshot)
    assert inspection_capture.projection.revision_id == snapshot_capture.projection.revision.id
    assert inspection_capture.generation == snapshot_capture.generation
    assert snapshot_capture.generation == registry_authority.read_current_generation()


def test_native_capture_snapshot_is_isolated_from_the_authority_cache(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    captured = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )
    cached = registry_authority.snapshot(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )

    assert isinstance(captured.projection, RegistrySnapshot)
    assert captured.projection is not cached
    assert captured.projection.legal is not cached.legal
    assert isinstance(captured.projection.legal, dict)
    assert captured.projection.legal == cached.legal
    captured_ref = next(iter(captured.projection.legal))
    assert captured.projection.legal[captured_ref] is not cached.legal[captured_ref]


def test_native_capture_isolated_from_public_snapshot_aliases_before_and_during_concurrent_reads(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Every public snapshot and capture owns its complete detached projection graph."""
    exposed_before = registry_authority.snapshot(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    before_capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )
    assert isinstance(before_capture.projection, RegistrySnapshot)
    assert before_capture.projection.legal == exposed_before.legal
    assert before_capture.projection.legal is not exposed_before.legal

    barrier = Barrier(2)

    def capture() -> RegistryAuthorityCapture:
        barrier.wait()
        return registry_authority.capture_law_selected_projection(
            _MODEL0_ID,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            grade=RegistryAuthorityGrade.FILING,
        )

    def read_snapshot() -> RegistrySnapshot:
        barrier.wait()
        return registry_authority.snapshot(
            _MODEL0_ID,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        pending_capture = executor.submit(capture)
        pending_snapshot = executor.submit(read_snapshot)
        during_capture = pending_capture.result(timeout=10)
        exposed_during = pending_snapshot.result(timeout=10)

    assert isinstance(during_capture.projection, RegistrySnapshot)
    assert during_capture.projection.legal == exposed_during.legal
    assert during_capture.projection.legal is not exposed_during.legal
    captured_ref = next(iter(during_capture.projection.legal))
    assert during_capture.projection.legal[captured_ref] is not exposed_during.legal[captured_ref]


def test_native_capture_is_atomic_across_concurrent_snapshot_reads(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    barrier = Barrier(_CAPTURE_WORKERS)

    def capture() -> RegistryAuthorityCapture:
        barrier.wait()
        return registry_authority.capture_law_selected_projection(
            _MODEL0_ID,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            grade=RegistryAuthorityGrade.FILING,
        )

    with ThreadPoolExecutor(max_workers=_CAPTURE_WORKERS) as executor:
        captures = tuple(executor.map(lambda _: capture(), range(_CAPTURE_WORKERS)))

    snapshots = tuple(capture.projection for capture in captures if isinstance(capture.projection, RegistrySnapshot))
    assert len(snapshots) == _CAPTURE_WORKERS
    assert {snapshot.revision.id for snapshot in snapshots} == {"2019-y-siguientes"}
    assert len({id(snapshot) for snapshot in snapshots}) == _CAPTURE_WORKERS
    assert {capture.generation for capture in captures} == {registry_authority.read_current_generation()}


def test_native_capture_rejects_an_old_authority_after_reset_and_refuses_aba_reuse(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    before_reset = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )

    reset_registry_caches()

    with pytest.raises(RegistrySnapshotError, match="invalidated by cache reset"):
        registry_authority.capture_law_selected_projection(
            _MODEL0_ID,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            grade=RegistryAuthorityGrade.FILING,
        )
    with pytest.raises(RegistrySnapshotError, match="invalidated by cache reset"):
        registry_authority.read_current_generation()

    reloaded = bundled_authority()
    after_reset = reloaded.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )

    assert after_reset.projection == before_reset.projection
    assert after_reset.generation > before_reset.generation
    assert after_reset.generation == reloaded.read_current_generation()


def test_native_authority_load_is_singleflight_per_observed_identity(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """One simultaneous cold identity load publishes exactly one authority generation."""
    reset_registry_caches()
    construct_count = 0
    count_lock = Lock()

    def count_construct(root: Path, source_root: Path) -> None:
        nonlocal construct_count
        assert root == registry_authority.root
        assert source_root == registry_authority.source_root
        with count_lock:
            construct_count += 1

    lifecycle = _AuthorityLifecycleProbe(on_construction_started=count_construct)
    barrier = Barrier(_CAPTURE_WORKERS)

    def cold_load() -> ValidatedRegistryAuthority:
        barrier.wait()
        return ValidatedRegistryAuthority.load(
            registry_authority.root,
            source_root=registry_authority.source_root,
            lifecycle_observer=lifecycle,
        )

    with ThreadPoolExecutor(max_workers=_CAPTURE_WORKERS) as executor:
        authorities = tuple(executor.map(lambda _: cold_load(), range(_CAPTURE_WORKERS)))

    assert construct_count == 1
    assert len({id(authority) for authority in authorities}) == 1
    assert {authority.read_current_generation() for authority in authorities} == {
        authorities[0].read_current_generation(),
    }


def test_native_authority_construction_overlaps_for_distinct_owner_roots(
    tmp_path: Path,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Unrelated owner roots must enter long authority construction together.

    The lifecycle milestone is emitted at the real construction boundary:
    holding a process-global lifecycle lock across compilation would strand
    the first worker at the barrier and prevent the second root from arriving.
    """
    root_a = tmp_path / "registry-a"
    root_a.mkdir()
    source_root = registry_authority.source_root
    root_b = tmp_path / "registry-b"
    root_b.mkdir()
    reset_registry_caches()

    first_construct_entered = Event()
    both_constructs_entered = Event()
    release_construct = Event()
    construct_barrier = Barrier(2)
    entered_scopes: set[tuple[Path, Path]] = set()
    entered_lock = Lock()
    returned: list[ValidatedRegistryAuthority] = []
    failures: list[Exception] = []

    def block_construct(root: Path, construct_source_root: Path) -> None:
        with entered_lock:
            entered_scopes.add((root, construct_source_root))
            if len(entered_scopes) == 1:
                first_construct_entered.set()
        construct_barrier.wait(timeout=10)
        both_constructs_entered.set()
        assert release_construct.wait(timeout=10)

    lifecycle = _AuthorityLifecycleProbe(on_construction_started=block_construct)

    def load(root: Path) -> None:
        try:
            returned.append(
                ValidatedRegistryAuthority.load(
                    root,
                    source_root=source_root,
                    lifecycle_observer=lifecycle,
                )
            )
        except Exception as exc:  # pragma: no cover - asserted immediately below
            failures.append(exc)

    workers = (Thread(target=load, args=(root_a,)), Thread(target=load, args=(root_b,)))
    try:
        for worker in workers:
            worker.start()
        assert first_construct_entered.wait(timeout=10)
        assert both_constructs_entered.wait(timeout=10)
    finally:
        release_construct.set()
        for worker in workers:
            worker.join(timeout=30)

    assert all(not worker.is_alive() for worker in workers)
    assert entered_scopes == {
        (root_a.resolve(), source_root.resolve()),
        (root_b.resolve(), source_root.resolve()),
    }
    assert not returned
    assert len(failures) == 2


def test_reset_drains_an_inflight_load_before_clearing_authority_publication(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A load that began before reset cannot republish itself after reset completes."""
    reset_registry_caches()
    construct_entered = Event()
    release_construct = Event()
    reset_called = Event()
    reset_acquired = Event()
    returned: list[ValidatedRegistryAuthority] = []
    failure: list[Exception] = []
    published_generations: list[int] = []
    construct_count = 0

    def block_first_construct(root: Path, source_root: Path) -> None:
        nonlocal construct_count
        assert root == registry_authority.root
        assert source_root == registry_authority.source_root
        construct_count += 1
        if construct_count == 1:
            construct_entered.set()
            assert release_construct.wait(timeout=10)

    def observe_publication(root: Path, source_root: Path, generation: int) -> None:
        assert root == registry_authority.root
        assert source_root == registry_authority.source_root
        published_generations.append(generation)

    def observe_reset_request() -> None:
        reset_called.set()

    lifecycle = _AuthorityLifecycleProbe(
        on_construction_started=block_first_construct,
        on_published=observe_publication,
        on_reset_requested=observe_reset_request,
        on_reset_acquired=reset_acquired.set,
    )

    def load_in_background() -> None:
        try:
            returned.append(
                ValidatedRegistryAuthority.load(
                    registry_authority.root,
                    source_root=registry_authority.source_root,
                    lifecycle_observer=lifecycle,
                )
            )
        except Exception as exc:  # pragma: no cover - asserted immediately below
            failure.append(exc)

    def reset_in_background() -> None:
        reset_registry_caches(lifecycle_observer=lifecycle)

    loader = Thread(target=load_in_background)
    loader.start()
    assert construct_entered.wait(timeout=10)

    resetter = Thread(target=reset_in_background)
    resetter.start()
    assert reset_called.wait(timeout=10)
    assert not reset_acquired.wait(timeout=0.5)

    release_construct.set()
    loader.join(timeout=20)
    resetter.join(timeout=20)

    assert not loader.is_alive()
    assert not resetter.is_alive()
    assert not failure
    assert reset_acquired.is_set()
    assert len(returned) == 1
    assert len(published_generations) == 1
    returned_generation = published_generations[0]
    with pytest.raises(RegistrySnapshotError, match="invalidated by cache reset"):
        returned[0].read_current_generation()

    current = ValidatedRegistryAuthority.load(
        registry_authority.root,
        source_root=registry_authority.source_root,
        lifecycle_observer=lifecycle,
    )
    assert construct_count == 2
    assert current.read_current_generation() > returned_generation
    assert published_generations == [returned_generation, current.read_current_generation()]


def test_concurrent_resets_are_exclusive_owner_transitions() -> None:
    """A second reset cannot clear caches until the first writer has completed."""
    first_reset_acquired = Event()
    release_first = Event()
    second_reset_acquired = Event()
    acquired_count = 0
    count_lock = Lock()

    def block_first_reset() -> None:
        nonlocal acquired_count
        with count_lock:
            acquired_count += 1
            ordinal = acquired_count
        if ordinal == 1:
            first_reset_acquired.set()
            assert release_first.wait(timeout=10)
        else:
            second_reset_acquired.set()

    lifecycle = _AuthorityLifecycleProbe(on_reset_acquired=block_first_reset)

    def reset() -> None:
        reset_registry_caches(lifecycle_observer=lifecycle)

    first = Thread(target=reset)
    second = Thread(target=reset)
    first.start()
    assert first_reset_acquired.wait(timeout=10)
    second.start()
    assert not second_reset_acquired.wait(timeout=0.5)

    release_first.set()
    first.join(timeout=10)
    second.join(timeout=10)

    assert not first.is_alive()
    assert not second.is_alive()
    assert acquired_count == 2


def test_native_capture_has_one_public_registry_home_without_workspace_coupling() -> None:
    authority_source = _AUTHORITY_SOURCE.read_text(encoding="utf-8")
    facade_source = _FACADE_SOURCE.read_text(encoding="utf-8")
    authority_tree = ast.parse(authority_source, filename=str(_AUTHORITY_SOURCE))

    assert "ModeloWorkspace" not in authority_source
    assert "ModeloWorkspace" not in facade_source
    assert {node.name for node in authority_tree.body if isinstance(node, ast.ClassDef)} >= {
        "RegistryAuthorityCapture",
        "ValidatedRegistryAuthority",
    }
    authority_methods = {
        node.name
        for node in ast.walk(authority_tree)
        if isinstance(node, ast.FunctionDef)
        and node.name in {"capture_law_selected_projection", "read_current_generation"}
    }
    assert authority_methods == {"capture_law_selected_projection", "read_current_generation"}

    production_capture_homes = tuple(
        path.relative_to(_REGISTRY_SOURCE).as_posix()
        for path in scan_directory(_REGISTRY_SOURCE, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "capture_law_selected_projection" in path.read_text(encoding="utf-8")
    )
    assert production_capture_homes == ("_authority.py",)
    assert "RegistryAuthorityCapture" in facade_source
