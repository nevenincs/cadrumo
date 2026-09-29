"""Fresh-source bootstrap behavior of the authority packaging hook."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
from pathlib import Path
from types import ModuleType
from typing import Generic, TypeVar

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


def _initialize(hook: ModuleType, root: Path, *, version: str, target_name: str) -> dict[str, object]:
    """Run the real hook's ``initialize`` for one target and return its build data."""
    instance = hook.CustomBuildHook(str(root), {}, None, None, str(root), target_name)
    build_data: dict[str, object] = {}
    instance.initialize(version, build_data)
    return build_data


def _record_resolutions(hook: ModuleType, monkeypatch: pytest.MonkeyPatch, pair_root: Path) -> list[Path]:
    """Stand the resolution in with a published pair, recording each request."""
    pair_root.mkdir(parents=True, exist_ok=True)
    descriptor = pair_root / "authority.current.json"
    database = pair_root / ("authority-" + "0" * 64 + ".sqlite3")
    resolved: list[Path] = []

    def resolve(build_root: Path) -> Path:
        resolved.append(build_root)
        return pair_root

    monkeypatch.setattr(hook, "_authority_root", resolve)
    monkeypatch.setattr(hook, "_selected_pair", lambda _root: (descriptor, database))
    return resolved


def test_an_editable_build_told_to_skip_resolves_no_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lint job's editable install must not compile a registry it never reads."""
    hook = _hook_module()
    resolved = _record_resolutions(hook, monkeypatch, tmp_path / "pair")
    monkeypatch.setenv("CADRUMO_EDITABLE_AUTHORITY", "skip")

    assert _initialize(hook, tmp_path, version="editable", target_name="wheel") == {}
    assert resolved == []


def test_a_real_distribution_ignores_the_editable_skip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DISCRIMINATING: no wheel may ship without its authority because of an env knob."""
    hook = _hook_module()
    resolved = _record_resolutions(hook, monkeypatch, tmp_path / "pair")
    monkeypatch.setenv("CADRUMO_EDITABLE_AUTHORITY", "skip")

    build_data = _initialize(hook, tmp_path, version="standard", target_name="wheel")

    assert resolved == [tmp_path]
    assert build_data["force_include"], "the wheel lost its authority payload"


def test_an_editable_build_still_resolves_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A checkout's first sync keeps publishing the authority it will need."""
    hook = _hook_module()
    resolved = _record_resolutions(hook, monkeypatch, tmp_path / "pair")
    monkeypatch.delenv("CADRUMO_EDITABLE_AUTHORITY", raising=False)

    assert _initialize(hook, tmp_path, version="editable", target_name="wheel") == {}
    assert resolved == [tmp_path]


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


def test_a_current_publication_is_read_without_publishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A copy of the session's current publication describes the live sources, so it is reused."""
    hook = _hook_module()
    current = Path(os.environ["CADRUMO_AUTHORITY_ROOT"])
    descriptor = json.loads((current / "authority.current.json").read_text(encoding="utf-8"))
    published = tmp_path / ".authority"
    published.mkdir()
    shutil.copy2(current / "authority.current.json", published / "authority.current.json")
    shutil.copy2(current / descriptor["database"], published / descriptor["database"])
    monkeypatch.delenv("CADRUMO_AUTHORITY_ROOT", raising=False)
    monkeypatch.setattr(
        hook,
        "_publish_source_tree_authority",
        lambda *_args: pytest.fail("a current publication must be read, not republished"),
    )

    assert hook._authority_root(tmp_path) == published


def test_a_descriptor_that_describes_no_current_generation_is_republished(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory holding a descriptor proves a publication happened, not that it is current."""
    hook = _hook_module()
    published = tmp_path / ".authority"
    published.mkdir()
    (published / "authority.current.json").write_text("{}", encoding="utf-8")
    calls: list[tuple[Path, Path]] = []

    def publish(build_root: Path, destination: Path) -> Path:
        calls.append((build_root, destination))
        return destination

    monkeypatch.delenv("CADRUMO_AUTHORITY_ROOT", raising=False)
    monkeypatch.setattr(hook, "_publish_source_tree_authority", publish)

    assert hook._authority_root(tmp_path) == published
    assert calls == [(tmp_path, published)]


def test_an_interrupted_publication_is_completed_rather_than_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A directory a failed publication created, holding no descriptor, is not a publication."""
    hook = _hook_module()
    interrupted = tmp_path / ".authority"
    (interrupted / "authority-candidate-left-behind").mkdir(parents=True)
    calls: list[tuple[Path, Path]] = []

    def publish(build_root: Path, destination: Path) -> Path:
        calls.append((build_root, destination))
        return destination

    monkeypatch.delenv("CADRUMO_AUTHORITY_ROOT", raising=False)
    monkeypatch.setattr(hook, "_publish_source_tree_authority", publish)

    assert hook._authority_root(tmp_path) == interrupted
    assert calls == [(tmp_path, interrupted)]


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

    with pytest.raises(FileNotFoundError, match=r"configured \$CADRUMO_AUTHORITY_ROOT directory is unavailable"):
        hook._authority_root(tmp_path)


def test_hook_module_loads_with_one_parameter_nongeneric_hatchling_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The current isolated backend may not expose the former two-parameter API."""
    import hatchling.builders.config as builder_config_module
    import hatchling.builders.hooks.plugin.interface as hook_interface_module

    class CurrentBuilderConfig:
        """Model Hatchling's concrete current configuration type."""

    CurrentBuilderConfigType = TypeVar("CurrentBuilderConfigType")

    class CurrentBuildHookInterface(Generic[CurrentBuilderConfigType]):
        """Model Hatchling's one-parameter current build-hook interface."""

    monkeypatch.setattr(builder_config_module, "BuilderConfig", CurrentBuilderConfig)
    monkeypatch.setattr(hook_interface_module, "BuildHookInterface", CurrentBuildHookInterface)

    hook = _hook_module()

    assert hook.CustomBuildHook.__orig_bases__ == (CurrentBuildHookInterface[CurrentBuilderConfig],)
