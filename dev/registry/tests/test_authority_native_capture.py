"""Concurrency and ownership proofs for native registry authority capture.

Capture coordinates are minted by an authority reconstructed from a signed
publication, the only authority the product runtime reads. These tests publish
the compiled bundled modelo under a test key and load it through the same
package-resource seam the runtime uses, so every capture below is taken from a
real artifact-backed authority rather than a development compilation, which
carries no capture incarnation at all.
"""

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
from threading import Barrier, Event, Lock, Thread
from typing import Final, cast

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.ed25519_signing import generate_ed25519_keypair_hex
from cadrumo.core.hashing import sha256_hex
from cadrumo.core.identity import ContentDigest
from cadrumo.domain.calculations.registry import authority as authority_module
from cadrumo.domain.calculations.registry.authority import (
    RegistryAuthorityCapture,
    RegistryAuthorityCurrentCoordinate,
    RegistryAuthorityProjection,
    ValidatedRegistryAuthority,
    bundled_authority,
)
from cadrumo.domain.calculations.registry.authority_artifact import AuthorityArtifact, write_authority_artifact
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection
from cadrumo.tests import REPO_ROOT
from dev.registry.compiler.authority import compile_validated_authority, compiled_bundled_authority
from dev.registry.maintenance_support import reset_registry_caches

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODEL0_ID = "130"
_FILING_YEAR = 2026
_PERIOD = "1T"
_CAPTURE_WORKERS = 8
_REGISTRY_SOURCE = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
_AUTHORITY_SOURCE = _REGISTRY_SOURCE / "authority.py"
_FACADE_SOURCE = _REGISTRY_SOURCE / "__init__.py"
_PUBLICATION_DIGEST: Final = sha256_hex(b"native-capture-publication")
_FOREIGN_PUBLICATION_DIGEST: Final = sha256_hex(b"native-capture-foreign-publication")


def _ignore_registry_reset() -> None:
    return


@dataclass(slots=True)
class _AuthorityLifecycleProbe:
    """Coordinate tests through the authority owner's real reset milestones."""

    on_reset_requested: Callable[[], None] = _ignore_registry_reset
    on_reset_acquired: Callable[[], None] = _ignore_registry_reset

    def registry_cache_reset_requested(self) -> None:
        self.on_reset_requested()

    def registry_cache_reset_acquired(self) -> None:
        self.on_reset_acquired()


@dataclass(frozen=True, slots=True)
class _Publication:
    """A signed, package-shaped authority publication and the key that verifies it."""

    root: Path
    public_key_hex: str


def _publish(root: Path, *, identity_digest: str) -> _Publication:
    """Sign the compiled bundled modelo under a fresh test key, laid out as the package resource."""
    compiled = compiled_bundled_authority()
    keys = generate_ed25519_keypair_hex()
    artifact_path = root / "registry" / "authority" / "authority.json"
    artifact_path.parent.mkdir(parents=True)
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(compiled.modelo(_MODEL0_ID),),
            catalogues=compiled.catalogues,
            identity_digest=identity_digest,
        ),
        signing_private_key_hex=keys.private_key_hex,
    )
    return _Publication(root=root, public_key_hex=keys.public_key_hex)


def _use_publication(monkeypatch: pytest.MonkeyPatch, publication: _Publication) -> None:
    """Point the runtime's package-resource seam at ``publication`` for one test."""
    bundled_data_root = authority_module._bundled_path()

    def staged_path(*parts: str) -> Path:
        if parts[:2] == ("registry", "authority"):
            return publication.root.joinpath(*parts)
        return bundled_data_root.joinpath(*parts)

    monkeypatch.setattr(authority_module, "_bundled_path", staged_path)
    monkeypatch.setattr(authority_module, "_BUNDLED_AUTHORITY_VERIFICATION_PUBLIC_KEY_HEX", publication.public_key_hex)


@pytest.fixture(scope="module")
def publication(tmp_path_factory: pytest.TempPathFactory) -> _Publication:
    return _publish(tmp_path_factory.mktemp("publication"), identity_digest=_PUBLICATION_DIGEST)


@pytest.fixture
def published_authority(monkeypatch: pytest.MonkeyPatch, publication: _Publication) -> ValidatedRegistryAuthority:
    _use_publication(monkeypatch, publication)
    return bundled_authority()


def test_native_capture_selects_the_existing_inspection_or_snapshot_authority(
    published_authority: ValidatedRegistryAuthority,
) -> None:
    inspection_capture = published_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    snapshot_capture = published_authority.capture_law_selected_projection(
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
    assert snapshot_capture.generation == published_authority.read_current_coordinate().generation


def test_native_capture_accepts_a_current_coordinate_from_its_own_domain(
    published_authority: ValidatedRegistryAuthority,
) -> None:
    """Capture validity is a typed same-domain comparison, not an integer check."""
    capture = published_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    current = published_authority.read_current_coordinate()

    assert capture.require_current(current) is capture
    assert current.require_current(capture) is current


def test_a_development_compilation_mints_no_capture_coordinate() -> None:
    """Only a signed publication can mint a coordinate; a compiled authority refuses rather than fabricating one."""
    with pytest.raises(RegistrySnapshotError, match="another process incarnation"):
        compiled_bundled_authority().read_current_coordinate()


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
    nonce, and ``published_authority`` is session-scoped, so a rebuild left
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
    identity = authority_module.canonical_authority_root_pair(  # process-boundary proof
        registry_root,
        source_root,
    )
    domain = authority_module._authority_comparison_domain(identity)  # process-boundary proof
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


def test_native_capture_refuses_a_coordinate_from_a_distinct_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    published_authority: ValidatedRegistryAuthority,
) -> None:
    """Equal-looking generations from different signed publications cannot compare."""
    capture = published_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    _use_publication(monkeypatch, _publish(tmp_path, identity_digest=_FOREIGN_PUBLICATION_DIGEST))
    foreign_current = bundled_authority().read_current_coordinate()
    same_generation_foreign_current = RegistryAuthorityCurrentCoordinate(
        comparison_domain=foreign_current.comparison_domain,
        generation=capture.generation,
    )

    assert capture.comparison_domain != foreign_current.comparison_domain
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
    owner_identity = authority_module.canonical_authority_root_pair(  # exact owner-domain proof
        registry_root,
        source_root,
    )
    foreign_identity = authority_module.canonical_authority_root_pair(  # exact owner-domain proof
        registry_root,
        alternate_source_root,
    )
    owner_domain = authority_module._authority_comparison_domain(  # exact owner-domain proof
        owner_identity
    )
    foreign_domain = authority_module._authority_comparison_domain(  # exact owner-domain proof
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


def test_native_capture_refuses_a_real_child_process_coordinate(
    publication: _Publication,
    published_authority: ValidatedRegistryAuthority,
) -> None:
    """The domain nonce prevents a child process from comparing parent captures of the same publication."""
    capture = published_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    child_program = "\n".join(
        (
            "import json",
            "import sys",
            "from pathlib import Path",
            "from cadrumo.domain.calculations.registry import authority as authority_module",
            "root, key = Path(sys.argv[1]), sys.argv[2]",
            "bundled_data_root = authority_module._bundled_path()",
            "def staged_path(*parts):",
            "    if parts[:2] == ('registry', 'authority'):",
            "        return root.joinpath(*parts)",
            "    return bundled_data_root.joinpath(*parts)",
            "authority_module._bundled_path = staged_path",
            "authority_module._BUNDLED_AUTHORITY_VERIFICATION_PUBLIC_KEY_HEX = key",
            "current = authority_module.bundled_authority().read_current_coordinate()",
            "print(json.dumps({'comparison_domain': current.comparison_domain, 'generation': current.generation}))",
        )
    )
    environment = os.environ.copy()
    source_path = str(REPO_ROOT / "src")
    environment["PYTHONPATH"] = source_path + os.pathsep + environment.get("PYTHONPATH", "")
    child = subprocess.run(  # noqa: S603 - fixed interpreter and in-repository test program
        (sys.executable, "-c", child_program, str(publication.root), publication.public_key_hex),
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


def test_an_unresolvable_registry_root_is_refused_before_compilation(tmp_path: Path) -> None:
    """A missing physical root pair is refused by name rather than compiled as an empty registry."""
    missing = tmp_path / "missing"

    with pytest.raises(RegistrySnapshotError, match="must resolve"):
        compile_validated_authority(missing, missing)


def test_an_unchanged_bundled_tree_compiles_once_per_process() -> None:
    """The development compilation is keyed by the tree's identity, so an unchanged tree reuses one authority."""
    assert compiled_bundled_authority() is compiled_bundled_authority()


def test_fork_rebuilds_active_reader_state_and_refuses_every_inherited_coordinate(
    published_authority: ValidatedRegistryAuthority,
) -> None:
    """A child neither waits on inherited locks nor accepts parent authority values.

    Branched on the platform rather than skipped, in the same shape as the case
    policy above: where the interpreter offers no ``fork`` there is no inherited
    load state to refuse, and that absence is asserted -- ``win32`` is the only
    supported platform without it -- so the case reports a real verdict on every
    host instead of a green that read nothing.
    """
    if not hasattr(os, "fork"):
        assert sys.platform == "win32", (
            f"{sys.platform} offers no os.fork; a POSIX host that lost it would silently "
            "retire this proof rather than exercise the fork barrier"
        )
        return

    capture = published_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    parent_current = published_authority.read_current_coordinate()
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
                lambda: published_authority.read_current_coordinate(),
                lambda: published_authority.capture_law_selected_projection(
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
            fresh = bundled_authority()
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
    child_result = json.loads(child_bytes)

    assert not reader.is_alive()
    assert os.waitstatus_to_exitcode(status) == 0
    assert "error" not in child_result
    assert child_result["inherited_refusals"] == 4
    assert child_result["fresh_domain"] != parent_current.comparison_domain


def test_native_capture_snapshot_is_isolated_from_the_authority_cache(
    published_authority: ValidatedRegistryAuthority,
) -> None:
    captured = published_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )
    cached = published_authority.snapshot(
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
    published_authority: ValidatedRegistryAuthority,
) -> None:
    """Every public snapshot and capture owns its complete detached projection graph."""
    exposed_before = published_authority.snapshot(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    before_capture = published_authority.capture_law_selected_projection(
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
        return published_authority.capture_law_selected_projection(
            _MODEL0_ID,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            grade=RegistryAuthorityGrade.FILING,
        )

    def read_snapshot() -> RegistrySnapshot:
        barrier.wait()
        return published_authority.snapshot(
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
    published_authority: ValidatedRegistryAuthority,
) -> None:
    barrier = Barrier(_CAPTURE_WORKERS)

    def capture() -> RegistryAuthorityCapture:
        barrier.wait()
        return published_authority.capture_law_selected_projection(
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
    assert {capture.generation for capture in captures} == {published_authority.read_current_coordinate().generation}


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
