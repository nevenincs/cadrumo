"""Fresh-source bootstrap behavior of the authority packaging hook."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _hook_module() -> ModuleType:
    path = REPO_ROOT / "packaging" / "authority" / "hatch_build.py"
    spec = importlib.util.spec_from_file_location("cadrumo_authority_hatch_build_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_source_tree_bootstraps_repo_root_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = _hook_module()
    expected = tmp_path / ".authority"
    calls: list[tuple[Path, Path]] = []

    def publish(build_root: Path, destination: Path) -> Path:
        calls.append((build_root, destination))
        return destination

    monkeypatch.delenv("CADRUMO_AUTHORITY_ROOT", raising=False)
    monkeypatch.setattr(hook, "_publish_source_tree_authority", publish)

    assert hook._authority_root(tmp_path) == expected
    assert calls == [(tmp_path, expected)]


def test_embedded_sdist_authority_never_runs_source_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = _hook_module()
    embedded = tmp_path / "src" / "cadrumo" / "_data" / "registry" / "authority"
    embedded.mkdir(parents=True)
    monkeypatch.delenv("CADRUMO_AUTHORITY_ROOT", raising=False)
    monkeypatch.setattr(
        hook,
        "_publish_source_tree_authority",
        lambda *_args: pytest.fail("sdist rebuild must consume its embedded authority"),
    )

    assert hook._authority_root(tmp_path) == embedded


def test_explicit_missing_override_does_not_fall_back_to_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = _hook_module()
    (tmp_path / ".authority").mkdir()
    monkeypatch.setenv("CADRUMO_AUTHORITY_ROOT", str(tmp_path / "missing"))

    assert hook._authority_root(tmp_path) is None
