"""Concurrency and ownership proofs for native registry authority capture."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from shutil import copytree
from threading import Barrier, Event, Lock, Thread
from typing import Final, cast

import pytest

import cadrumo.domain.calculations.registry.authority as authority_module
from cadrumo.domain.calculations.registry.authority import (
    RegistryAuthorityCapture,
    RegistryAuthorityCurrentCoordinate,
    RegistryAuthorityProjection,
    ValidatedRegistryAuthority,
    bundled_authority,
    reset_registry_caches,
)
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from .....core import RegistryAuthorityGrade
from .....core.directory_scan import scan_directory
from .....core.identity import ContentDigest
from .....tests import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODEL0_ID = "130"
_FILING_YEAR = 2026
_PERIOD = "1T"
_CAPTURE_WORKERS = 8
_REGISTRY_SOURCE = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
_AUTHORITY_SOURCE = _REGISTRY_SOURCE / "authority.py"
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
    assert snapshot_capture.generation == registry_authority.read_current_coordinate().generation


def test_native_capture_accepts_a_current_coordinate_from_its_own_domain(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Capture validity is a typed same-domain comparison, not an integer check."""
    capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    current = registry_authority.read_current_coordinate()

    assert capture.require_current(current) is capture
    assert current.require_current(capture) is current


def test_native_coordinate_values_expose_only_the_public_opaque_contract() -> None:
    """Dataclass reflection cannot reveal roots, PID, nonce, or internal binding."""
    opaque_domain = cast(ContentDigest, "0" * 64)
    capture = RegistryAuthorityCapture(
        projection=cast(RegistryAuthorityProjection, object()),
        comparison_domain=opaque_domain,
        generation=1,
    )
    current = RegistryAuthorityCurrentCoordinate(comparison_domain=opaque_domain, generation=1)

    assert tuple(field.name for field in fields(capture)) == ("projection", "comparison_domain", "generation")
    assert tuple(field.name for field in fields(current)) == ("comparison_domain", "generation")
    assert set(asdict(capture)) == {"projection", "comparison_domain", "generation"}
    assert set(asdict(current)) == {"comparison_domain", "generation"}


_AUTHORITY_PROCESS_STATE_GLOBALS: Final = (
    "_authority_process_pid",
    "_authority_process_nonce",
    "_authority_process_domains",
    "_authority_state_lock",
    "_authority_load_barrier",
    "_authority_load_states",
    "_authority_generation",
    "_authority_reset_epoch",
)


@pytest.fixture(autouse=True)
def restored_authority_process_state() -> Iterator[None]:
    """Confine an emulated after-fork rebuild to the test that performs it.

    ``_rebuild_authority_process_state`` re-keys the module-global incarnation
    nonce, and ``registry_authority`` is session-scoped, so a rebuild left
    standing hands every later test in the session an authority the
    creator-process guard refuses -- a failure that reads as a defect in
    whichever test happens to run next rather than as leakage from this one.

    AUTOUSE because the rebuild is not the only writer of this state:
    ``reset_registry_caches()`` re-keys the same eight globals, and several
    tests here call it as the very behaviour under test. Applying the guard to
    one test left the others free to poison their successors -- reproduced
    directly by running the reset test and then any later capture test, where
    the reset passes and the NEXT test fails with "belongs to another process
    incarnation". Every test in this module now restores what it re-keyed, so a
    failure here means the test's own subject, never its predecessor's leakage.
    """
    saved = {name: getattr(authority_module, name) for name in _AUTHORITY_PROCESS_STATE_GLOBALS}
    # `_invalidate_authority_generations` CLEARS `_authority_load_states` IN
    # PLACE rather than rebinding it, so the entry saved above is a reference to
    # the very dict the reset empties -- restoring it hands back the emptied
    # object and every later capture is refused by the `state is None` clause of
    # `_require_current_capture_incarnation`, reported as an "observed registry
    # identity transition". Snapshot the CONTENTS and repopulate.
    saved_load_states = dict(authority_module._authority_load_states)  # pyright: ignore[reportPrivateUsage]
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(authority_module, name, value)
        authority_module._authority_load_states.clear()  # pyright: ignore[reportPrivateUsage]
        authority_module._authority_load_states.update(saved_load_states)  # pyright: ignore[reportPrivateUsage]


def test_process_state_rebuild_refuses_preexisting_public_coordinates(
    tmp_path: Path,
    restored_authority_process_state: None,
) -> None:
    """Internal domain custody rejects inherited values without a DTO binding field."""
    registry_root = tmp_path / "registry-root"
    source_root = tmp_path / "source-root"
    registry_root.mkdir()
    source_root.mkdir()
    identity = authority_module._canonical_authority_root_pair(  # pyright: ignore[reportPrivateUsage]  # process-boundary proof
        registry_root,
        source_root,
    )
    domain = authority_module._authority_comparison_domain(identity)  # pyright: ignore[reportPrivateUsage]  # process-boundary proof
    capture = RegistryAuthorityCapture(
        projection=cast(RegistryAuthorityProjection, object()),
        comparison_domain=domain,
        generation=1,
    )
    current = RegistryAuthorityCurrentCoordinate(comparison_domain=domain, generation=1)

    authority_module._rebuild_authority_process_state()  # pyright: ignore[reportPrivateUsage]  # emulate after-fork callback

    with pytest.raises(RegistrySnapshotError, match="another process incarnation"):
        capture.require_current(current)
    with pytest.raises(RegistrySnapshotError, match="another process incarnation"):
        current.require_current(capture)


def test_native_capture_refuses_a_coordinate_from_a_distinct_registry_root(
    tmp_path: Path,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Equal-looking generations from different physical owners cannot compare."""
    copied_root = tmp_path / "registry-copy"
    copytree(registry_authority.root, copied_root)
    other = ValidatedRegistryAuthority.load(copied_root, source_root=registry_authority.source_root)
    capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    switched_root_current = other.read_current_coordinate()
    same_generation_foreign_current = RegistryAuthorityCurrentCoordinate(
        comparison_domain=switched_root_current.comparison_domain,
        generation=capture.generation,
    )

    assert capture.comparison_domain != switched_root_current.comparison_domain
    with pytest.raises(RegistrySnapshotError, match="physical-root process domain"):
        capture.require_current(same_generation_foreign_current)


def test_native_capture_refuses_a_coordinate_from_a_distinct_source_root_only(
    tmp_path: Path,
) -> None:
    """Changing only the physical source root creates a foreign comparison domain."""
    registry_root = tmp_path / "registry-root"
    source_root = tmp_path / "source-root-a"
    alternate_source_root = tmp_path / "source-root-b"
    registry_root.mkdir()
    source_root.mkdir()
    alternate_source_root.mkdir()
    owner_identity = authority_module._canonical_authority_root_pair(  # pyright: ignore[reportPrivateUsage]  # exact owner-domain proof
        registry_root,
        source_root,
    )
    foreign_identity = authority_module._canonical_authority_root_pair(  # pyright: ignore[reportPrivateUsage]  # exact owner-domain proof
        registry_root,
        alternate_source_root,
    )
    owner_domain = authority_module._authority_comparison_domain(  # pyright: ignore[reportPrivateUsage]  # exact owner-domain proof
        owner_identity
    )
    foreign_domain = authority_module._authority_comparison_domain(  # pyright: ignore[reportPrivateUsage]  # exact owner-domain proof
        foreign_identity
    )
    capture = RegistryAuthorityCapture(
        projection=cast(RegistryAuthorityProjection, object()),
        comparison_domain=owner_domain,
        generation=1,
    )
    foreign_current = RegistryAuthorityCurrentCoordinate(
        comparison_domain=foreign_domain,
        generation=1,
    )

    with pytest.raises(RegistrySnapshotError, match="physical-root process domain"):
        capture.require_current(foreign_current)


def test_native_capture_refuses_a_reset_stale_coordinate_in_its_same_domain(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A reset advances currentness without inventing a new physical domain."""
    stale_capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )

    reset_registry_caches()
    current = bundled_authority().read_current_coordinate()

    assert stale_capture.comparison_domain == current.comparison_domain
    assert stale_capture.generation != current.generation
    with pytest.raises(RegistrySnapshotError, match="no longer current"):
        stale_capture.require_current(current)


def test_native_capture_refuses_a_real_child_process_coordinate(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The domain nonce prevents a child process from comparing parent captures."""
    capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    child_program = "\n".join(
        (
            "import json",
            "import sys",
            "from pathlib import Path",
            "from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority",
            "authority = ValidatedRegistryAuthority.load(Path(sys.argv[1]), source_root=Path(sys.argv[2]))",
            "current = authority.read_current_coordinate()",
            "print(json.dumps({'comparison_domain': current.comparison_domain, 'generation': current.generation}))",
        )
    )
    environment = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get("PYTHONPATH", "")
    child = subprocess.run(  # noqa: S603 - fixed interpreter and in-repository test program
        (sys.executable, "-c", child_program, str(registry_authority.root), str(registry_authority.source_root)),
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        check=True,
        text=True,
        timeout=180,
    )
    child_current = RegistryAuthorityCurrentCoordinate(**json.loads(child.stdout))

    assert child_current.comparison_domain != capture.comparison_domain
    with pytest.raises(RegistrySnapshotError, match="another process incarnation"):
        capture.require_current(child_current)


def test_native_authority_coalesces_relative_dot_and_symlink_root_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """All aliases of one physical root pair share one load state and domain."""
    monkeypatch.chdir(REPO_ROOT)
    relative_root = registry_authority.root.relative_to(REPO_ROOT) / "."
    relative_source_root = registry_authority.source_root.relative_to(REPO_ROOT) / "."
    relative = ValidatedRegistryAuthority.load(relative_root, source_root=relative_source_root)

    assert relative is registry_authority
    assert relative.read_current_coordinate() == registry_authority.read_current_coordinate()

    registry_link = tmp_path / "registry-link"
    source_link = tmp_path / "source-link"
    try:
        registry_link.symlink_to(registry_authority.root, target_is_directory=True)
        source_link.symlink_to(registry_authority.source_root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    linked = ValidatedRegistryAuthority.load(registry_link, source_root=source_link)

    assert linked is registry_authority
    assert linked.read_current_coordinate() == registry_authority.read_current_coordinate()


def test_native_authority_applies_the_platform_case_policy(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Case aliases coalesce exactly when the host path policy coalesces them."""
    upper_root = Path(str(registry_authority.root).upper())
    upper_source_root = Path(str(registry_authority.source_root).upper())
    if upper_root.exists() and upper_source_root.exists():
        alias = ValidatedRegistryAuthority.load(upper_root, source_root=upper_source_root)
        if upper_root.samefile(registry_authority.root) and upper_source_root.samefile(registry_authority.source_root):
            assert alias is registry_authority
            assert alias.read_current_coordinate() == registry_authority.read_current_coordinate()
        else:
            assert alias is not registry_authority
            assert alias.read_current_coordinate().comparison_domain != (
                registry_authority.read_current_coordinate().comparison_domain
            )
    else:
        with pytest.raises(RegistrySnapshotError, match="must resolve"):
            ValidatedRegistryAuthority.load(upper_root, source_root=upper_source_root)


def test_native_authority_fails_closed_on_unresolvable_roots(tmp_path: Path) -> None:
    """A missing physical owner pair never enters the process load-state map."""
    missing = tmp_path / "missing"

    with pytest.raises(RegistrySnapshotError, match="must resolve"):
        ValidatedRegistryAuthority.load(missing, source_root=missing)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork semantics")
def test_fork_rebuilds_active_reader_state_and_refuses_every_inherited_coordinate(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A child neither waits on inherited locks nor accepts parent authority values."""
    capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    parent_current = registry_authority.read_current_coordinate()
    reader_entered = Event()
    release_reader = Event()

    def active_reader() -> None:
        with authority_module._authority_load_barrier.read():  # pyright: ignore[reportPrivateUsage]  # real fork-barrier proof
            reader_entered.set()
            assert release_reader.wait(timeout=30)

    reader = Thread(target=active_reader)
    reader.start()
    assert reader_entered.wait(timeout=10)
    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:  # pragma: no cover - exercised in the forked process
        os.close(read_fd)
        result: dict[str, object]
        try:
            inherited_refusals = 0
            for exercise in (
                lambda: registry_authority.read_current_coordinate(),
                lambda: registry_authority.capture_law_selected_projection(
                    _MODEL0_ID,
                    filing_year=_FILING_YEAR,
                    period=_PERIOD,
                ),
                lambda: capture.require_current(parent_current),
                lambda: parent_current.require_current(capture),
            ):
                try:
                    exercise()
                except RegistrySnapshotError:
                    inherited_refusals += 1
            fresh = ValidatedRegistryAuthority.load(
                registry_authority.root,
                source_root=registry_authority.source_root,
            )
            fresh_current = fresh.read_current_coordinate()
            result = {
                "inherited_refusals": inherited_refusals,
                "fresh_domain": fresh_current.comparison_domain,
            }
        except BaseException as exc:
            result = {"error": f"{type(exc).__name__}: {exc}"}
        os.write(write_fd, json.dumps(result).encode("utf-8"))
        os.close(write_fd)
        os._exit(0)

    os.close(write_fd)
    release_reader.set()
    reader.join(timeout=10)
    child_bytes = os.read(read_fd, 65536)
    os.close(read_fd)
    _, status = os.waitpid(child_pid, 0)
    result = json.loads(child_bytes)

    assert not reader.is_alive()
    assert os.waitstatus_to_exitcode(status) == 0
    assert "error" not in result
    assert result["inherited_refusals"] == 4
    assert result["fresh_domain"] != parent_current.comparison_domain


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
    assert {capture.generation for capture in captures} == {registry_authority.read_current_coordinate().generation}


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
        registry_authority.read_current_coordinate()

    reloaded = bundled_authority()
    after_reset = reloaded.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )

    assert after_reset.projection == before_reset.projection
    assert after_reset.generation > before_reset.generation
    assert after_reset.generation == reloaded.read_current_coordinate().generation


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
    assert {authority.read_current_coordinate().generation for authority in authorities} == {
        authorities[0].read_current_coordinate().generation,
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
        returned[0].read_current_coordinate()

    current = ValidatedRegistryAuthority.load(
        registry_authority.root,
        source_root=registry_authority.source_root,
        lifecycle_observer=lifecycle,
    )
    assert construct_count == 2
    assert current.read_current_coordinate().generation > returned_generation
    assert published_generations == [returned_generation, current.read_current_coordinate().generation]


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
        and node.name
        in {
            "capture_law_selected_projection",
            "read_current_coordinate",
        }
    }
    assert authority_methods == {
        "capture_law_selected_projection",
        "read_current_coordinate",
    }

    production_capture_homes = tuple(
        path.relative_to(_REGISTRY_SOURCE).as_posix()
        for path in scan_directory(_REGISTRY_SOURCE, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "capture_law_selected_projection" in path.read_text(encoding="utf-8")
    )
    assert production_capture_homes == ("authority.py",)
    assert "RegistryAuthorityCapture" not in facade_source
    assert ast.parse(facade_source).body[-1].__class__ is ast.AnnAssign
