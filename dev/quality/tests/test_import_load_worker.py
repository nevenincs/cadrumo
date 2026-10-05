"""An exhaustive import census remains complete across separately bounded inventories."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from cadrumo.tests.module_target_inventory import assert_all_target_sets_current, load_all_target_sets
from dev._paths import REPO_ROOT
from dev.quality import import_load_worker
from dev.quality.import_authority import read_authority
from dev.quality.import_binding_inventory import read_modules
from dev.quality.import_check_models import AuthorityRead, RootPackage
from dev.quality.import_dynamic_targets import metadata_target_set_targets
from dev.quality.import_load_probe import governed_load_targets, main
from dev.quality.import_target_evaluation import TargetEvaluationContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_compile_command_refreshes_worker_partitions_after_source_moves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renamed module disappears from every consumer's finite target set."""
    read = read_authority(REPO_ROOT)
    assert read.authority is not None and not read.broken
    roots = tuple(RootPackage(root.name, tmp_path / root.name) for root in read.authority.roots)
    for root in roots:
        root.path.mkdir()
        (root.path / "__init__.py").write_text("", encoding="utf-8")
        (root.path / "old.py").write_text("", encoding="utf-8")
    authority = replace(read.authority, repository=tmp_path, roots=roots)
    monkeypatch.setattr("dev.quality.import_load_probe.read_authority", lambda *_args: AuthorityRead(authority))
    assert main(["--root", str(tmp_path), "--compile-targets"]) == 0
    for root in roots:
        (root.path / "old.py").rename(root.path / "new.py")
    assert main(["--root", str(tmp_path), "--compile-targets"]) == 0

    aggregate = "dev/quality/metadata/import_load_targets.json"
    expected = governed_load_targets(authority)
    assert_all_target_sets_current(aggregate, repository=tmp_path)
    assert load_all_target_sets(aggregate, repository=tmp_path) == expected
    for root in roots:
        partition = f"dev/quality/metadata/import_load_targets.{root.name}.json"
        assert_all_target_sets_current(partition, repository=tmp_path)
        assert load_all_target_sets(partition, repository=tmp_path) == (root.name, f"{root.name}.new")
    attempted: list[str] = []
    monkeypatch.setattr(import_load_worker.importlib, "import_module", attempted.append)
    report = import_load_worker.load_declared_targets(tmp_path)
    assert tuple(sorted(attempted)) == expected
    assert report["attempted"] == len(expected)
    assert report["failures"] == []


def test_actual_subordinate_resolver_proves_each_complete_root_census() -> None:
    """Conservative assignment unions never turn separate roots into an open import."""
    read = read_authority(REPO_ROOT)
    assert read.authority is not None and not read.broken
    modules, findings = read_modules(
        replace(read.authority, roots=(RootPackage("dev.quality", REPO_ROOT / "dev/quality"),))
    )
    assert not findings
    module = modules["dev.quality.import_load_worker"]
    context = TargetEvaluationContext(module.tree, module.name)
    expected = {
        frozenset(load_all_target_sets(f"dev/quality/metadata/import_load_targets.{root.name}.json"))
        for root in read.authority.roots
    }
    resolved: list[frozenset[str]] = []
    for call in ast.walk(module.tree):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "importlib"
            and call.func.attr == "import_module"
        ):
            targets, exhaustive = metadata_target_set_targets(call.args[0], call.lineno, module, context, REPO_ROOT)
            assert targets is not None and exhaustive
            resolved.append(targets)
    assert len(resolved) == len(expected) and set(resolved) == expected


def test_root_partitions_cover_the_complete_governed_census_and_keep_all_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No target disappears or runs twice when one root exceeds the aggregate limit."""
    read = read_authority(REPO_ROOT)
    assert read.authority is not None and not read.broken
    expected = governed_load_targets(read.authority)
    partitioned: list[str] = []
    for root in read.authority.roots:
        metadata = f"dev/quality/metadata/import_load_targets.{root.name}.json"
        assert_all_target_sets_current(metadata, repository=REPO_ROOT)
        partitioned.extend(load_all_target_sets(metadata, repository=REPO_ROOT))
    assert tuple(sorted(partitioned)) == expected
    attempted: list[str] = []
    fail_import, fail_exit = expected[0], expected[-1]

    def import_without_side_effects(name: str) -> None:
        attempted.append(name)
        if name == fail_import:
            raise ModuleNotFoundError("synthetic missing dependency", name="synthetic_dependency")
        if name == fail_exit:
            raise SystemExit(7)

    monkeypatch.setattr(import_load_worker.importlib, "import_module", import_without_side_effects)
    result = import_load_worker.load_declared_targets(REPO_ROOT)
    assert tuple(sorted(attempted)) == expected
    assert result["attempted"] == len(expected)
    assert result["target_digest"] == hashlib.sha256("\n".join(expected).encode("utf-8")).hexdigest()
    failures = result["failures"]
    assert isinstance(failures, list)
    assert [failure["module"] for failure in failures] == [fail_import, fail_exit]
    assert [failure["error"] for failure in failures] == ["ModuleNotFoundError", "SystemExit"]


def test_native_backend_rejects_unimplemented_or_injected_module_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """A syntactically valid backend label never grants an arbitrary import."""
    from dev.packaging.native import layout

    def unexpected_import(name: str) -> None:
        pytest.fail(f"unimplemented backend attempted an import: {name}")

    monkeypatch.setattr(layout.importlib, "import_module", unexpected_import)
    for name in ("linux", "os", "windows_verify", "../windows", ""):
        with pytest.raises(ValueError, match="implemented enrollment"):
            layout.backend({"backend": name})
