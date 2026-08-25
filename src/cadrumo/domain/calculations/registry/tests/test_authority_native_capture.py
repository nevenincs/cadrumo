"""Concurrency and ownership proofs for native registry authority capture."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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
