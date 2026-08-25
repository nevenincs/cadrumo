"""Concurrency and ownership proofs for native registry authority capture."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event, Lock, Thread

import pytest

from .....core import RegistryAuthorityGrade, scan_directory
from .....tests import REPO_ROOT
from .. import _authority as authority_module
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

    captured_ref = next(iter(captured.projection.legal))
    captured.projection.legal.pop(captured_ref)

    assert captured_ref in cached.legal


def test_native_capture_isolated_from_public_snapshot_alias_mutation_before_and_during_capture(
    monkeypatch: pytest.MonkeyPatch,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Public mutable snapshot copies can never alter the authority-private capture source."""
    exposed = registry_authority.snapshot(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    )
    removed_before_capture = next(iter(exposed.legal))
    exposed.legal.pop(removed_before_capture)

    before_capture = registry_authority.capture_law_selected_projection(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        grade=RegistryAuthorityGrade.FILING,
    )
    assert isinstance(before_capture.projection, RegistrySnapshot)
    assert removed_before_capture in before_capture.projection.legal

    cache_key = (_MODEL0_ID, _FILING_YEAR, _PERIOD, None, None, RegistryAuthorityGrade.FILING)
    canonical = registry_authority._snapshots[cache_key]
    copy_started = Event()
    release_copy = Event()
    original_model_copy = RegistrySnapshot.model_copy

    def block_canonical_copy(self: RegistrySnapshot, *args: object, **kwargs: object) -> RegistrySnapshot:
        if self is canonical and kwargs.get("deep") is True:
            copy_started.set()
            assert release_copy.wait(timeout=10)
        return original_model_copy(self, *args, **kwargs)

    monkeypatch.setattr(RegistrySnapshot, "model_copy", block_canonical_copy)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending_capture = executor.submit(
            registry_authority.capture_law_selected_projection,
            _MODEL0_ID,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            grade=RegistryAuthorityGrade.FILING,
        )
        assert copy_started.wait(timeout=10)
        removed_during_capture = next(iter(exposed.legal))
        exposed.legal.pop(removed_during_capture)
        release_copy.set()
        during_capture = pending_capture.result(timeout=10)

    assert isinstance(during_capture.projection, RegistrySnapshot)
    assert removed_during_capture in during_capture.projection.legal
    assert removed_before_capture in registry_authority.snapshot(
        _MODEL0_ID,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
    ).legal


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

    assert all(isinstance(capture.projection, RegistrySnapshot) for capture in captures)
    assert {capture.projection.revision.id for capture in captures} == {"2019-y-siguientes"}
    assert len({id(capture.projection) for capture in captures}) == _CAPTURE_WORKERS
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
    monkeypatch: pytest.MonkeyPatch,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """One simultaneous cold identity load publishes exactly one authority generation."""
    reset_registry_caches()
    original_construct = authority_module._construct_authority
    construct_count = 0
    count_lock = Lock()

    def count_construct(*args: object, **kwargs: object) -> ValidatedRegistryAuthority:
        nonlocal construct_count
        with count_lock:
            construct_count += 1
        return original_construct(*args, **kwargs)

    monkeypatch.setattr(authority_module, "_construct_authority", count_construct)
    barrier = Barrier(_CAPTURE_WORKERS)

    def cold_load() -> ValidatedRegistryAuthority:
        barrier.wait()
        return ValidatedRegistryAuthority.load(
            registry_authority.root,
            source_root=registry_authority.source_root,
        )

    with ThreadPoolExecutor(max_workers=_CAPTURE_WORKERS) as executor:
        authorities = tuple(executor.map(lambda _: cold_load(), range(_CAPTURE_WORKERS)))

    assert construct_count == 1
    assert len({id(authority) for authority in authorities}) == 1
    assert {authority.read_current_generation() for authority in authorities} == {
        authorities[0].read_current_generation(),
    }


def test_reset_drains_an_inflight_load_before_clearing_authority_publication(
    monkeypatch: pytest.MonkeyPatch,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """A load that began before reset cannot republish itself after reset completes."""
    reset_registry_caches()
    original_construct = authority_module._construct_authority
    construct_entered = Event()
    release_construct = Event()
    reset_called = Event()
    invalidation_entered = Event()
    returned: list[ValidatedRegistryAuthority] = []
    failure: list[BaseException] = []
    construct_count = 0

    def block_first_construct(*args: object, **kwargs: object) -> ValidatedRegistryAuthority:
        nonlocal construct_count
        construct_count += 1
        if construct_count == 1:
            construct_entered.set()
            assert release_construct.wait(timeout=10)
        return original_construct(*args, **kwargs)

    original_invalidate = authority_module._invalidate_authority_generations

    def observe_invalidation() -> None:
        invalidation_entered.set()
        original_invalidate()

    original_reset = authority_module._AUTHORITY_LOAD_BARRIER.reset

    @contextmanager
    def observe_reset_barrier():
        reset_called.set()
        with original_reset():
            yield

    monkeypatch.setattr(authority_module, "_construct_authority", block_first_construct)
    monkeypatch.setattr(authority_module, "_invalidate_authority_generations", observe_invalidation)
    monkeypatch.setattr(authority_module._AUTHORITY_LOAD_BARRIER, "reset", observe_reset_barrier)

    def load_in_background() -> None:
        try:
            returned.append(
                ValidatedRegistryAuthority.load(
                    registry_authority.root,
                    source_root=registry_authority.source_root,
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted immediately below
            failure.append(exc)

    loader = Thread(target=load_in_background)
    loader.start()
    assert construct_entered.wait(timeout=10)

    resetter = Thread(target=reset_registry_caches)
    resetter.start()
    assert reset_called.wait(timeout=10)
    assert not invalidation_entered.wait(timeout=0.5)

    release_construct.set()
    loader.join(timeout=20)
    resetter.join(timeout=20)

    assert not loader.is_alive()
    assert not resetter.is_alive()
    assert not failure
    assert invalidation_entered.is_set()
    assert len(returned) == 1
    with pytest.raises(RegistrySnapshotError, match="invalidated by cache reset"):
        returned[0].read_current_generation()

    current = ValidatedRegistryAuthority.load(
        registry_authority.root,
        source_root=registry_authority.source_root,
    )
    assert construct_count == 2
    assert current.read_current_generation() > returned[0]._capture_generation


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
        if isinstance(node, ast.FunctionDef) and node.name in {"capture_law_selected_projection", "read_current_generation"}
    }
    assert authority_methods == {"capture_law_selected_projection", "read_current_generation"}

    production_capture_homes = tuple(
        path.relative_to(_REGISTRY_SOURCE).as_posix()
        for path in scan_directory(_REGISTRY_SOURCE, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "capture_law_selected_projection" in path.read_text(encoding="utf-8")
    )
    assert production_capture_homes == ("_authority.py",)
    assert "RegistryAuthorityCapture" in facade_source
