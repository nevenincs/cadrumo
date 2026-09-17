"""Merge-gate test selection from a pull request's changed files."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..change_scope import (
    CHANGE_CLASS_RULES,
    CONTRACT_TARGETS,
    ChangeScope,
    compute_change_scope,
    main,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _write(root: Path, relative: str, text: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Build ``src/<pkg>`` with a leaf, a consumer importing it, an unrelated module and a core."""
    name = f"scopepkg_{uuid.uuid4().hex}"
    for relative in (
        f"src/{name}/__init__.py",
        f"src/{name}/leaf/__init__.py",
        f"src/{name}/leaf/tests/__init__.py",
        f"src/{name}/consumer/__init__.py",
        f"src/{name}/consumer/tests/__init__.py",
        f"src/{name}/unrelated/__init__.py",
        f"src/{name}/unrelated/tests/__init__.py",
        f"src/{name}/core/__init__.py",
        f"src/{name}/core/tests/__init__.py",
        f"src/{name}/untested/__init__.py",
    ):
        _write(tmp_path, relative)
    _write(tmp_path, f"src/{name}/leaf/value.py", "VALUE = 1\n")
    _write(tmp_path, f"src/{name}/consumer/use.py", f"from {name}.leaf.value import VALUE\n")
    _write(tmp_path, f"src/{name}/unrelated/other.py", "OTHER = 2\n")
    _write(tmp_path, f"src/{name}/core/base.py", "BASE = 3\n")
    _write(tmp_path, f"src/{name}/untested/thing.py", "THING = 4\n")
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    return name


def _scope(root: Path, name: str, files: list[str], *, max_targets: int = 40) -> ChangeScope:
    return compute_change_scope(
        files,
        root=root,
        packages=(name,),
        fanout=(f"{name}.core",),
        max_targets=max_targets,
    )


def test_python_change_selects_its_nearest_owning_tests(tmp_path: Path, package: str) -> None:
    scope = _scope(tmp_path, package, [f"src/{package}/unrelated/other.py"])

    assert not scope.too_broad
    assert scope.targets == (*CONTRACT_TARGETS, f"src/{package}/unrelated/tests")


def test_reverse_importer_tests_are_selected(tmp_path: Path, package: str) -> None:
    scope = _scope(tmp_path, package, [f"src/{package}/leaf/value.py"])

    assert not scope.too_broad
    assert f"src/{package}/leaf/tests" in scope.targets
    assert f"src/{package}/consumer/tests" in scope.targets
    assert f"src/{package}/unrelated/tests" not in scope.targets


def test_importer_selection_follows_the_live_import(tmp_path: Path, package: str) -> None:
    _write(tmp_path, f"src/{package}/consumer/use.py", "VALUE = 1\n")

    scope = _scope(tmp_path, package, [f"src/{package}/leaf/value.py"])

    assert f"src/{package}/consumer/tests" not in scope.targets


def test_changed_test_file_selects_its_own_tests_directory(tmp_path: Path, package: str) -> None:
    scope = _scope(tmp_path, package, [f"src/{package}/leaf/tests/test_value.py"])

    assert scope.targets == (*CONTRACT_TARGETS, f"src/{package}/leaf/tests")


def test_unknown_path_under_src_still_maps(tmp_path: Path, package: str) -> None:
    scope = _scope(
        tmp_path,
        package,
        [f"src\\{package}\\leaf\\deleted\\nested\\gone.py", f"src/{package}/unrelated/notes.txt"],
    )

    assert not scope.too_broad
    assert f"src/{package}/leaf/tests" in scope.targets
    assert f"src/{package}/unrelated/tests" in scope.targets


def test_python_change_without_owning_tests_is_never_silent(tmp_path: Path, package: str) -> None:
    (tmp_path / "src" / package / "leaf" / "tests" / "__init__.py").unlink()
    (tmp_path / "src" / package / "leaf" / "tests").rmdir()

    scope = _scope(tmp_path, package, [f"src/{package}/leaf/value.py"])

    assert scope.too_broad
    assert scope.reason is not None and "value.py" in scope.reason
    assert scope.targets == CONTRACT_TARGETS


def test_importer_without_owning_tests_is_too_broad(tmp_path: Path, package: str) -> None:
    _write(tmp_path, f"src/{package}/untested/thing.py", f"from {package}.leaf.value import VALUE\n")

    scope = _scope(tmp_path, package, [f"src/{package}/leaf/value.py"])

    assert scope.too_broad
    assert scope.reason is not None and f"{package}.untested.thing" in scope.reason


def test_python_outside_every_change_class_is_too_broad(tmp_path: Path) -> None:
    scope = compute_change_scope(["scripts/loose.py"], root=tmp_path)

    assert scope.too_broad
    assert scope.targets == CONTRACT_TARGETS


def test_fanout_package_change_is_too_broad(tmp_path: Path, package: str) -> None:
    scope = _scope(tmp_path, package, [f"src/{package}/core/base.py"])

    assert scope.too_broad
    assert scope.reason is not None and "fan-out" in scope.reason
    assert scope.targets == CONTRACT_TARGETS


def test_selection_above_the_limit_is_too_broad(tmp_path: Path, package: str) -> None:
    files = [f"src/{package}/leaf/value.py", f"src/{package}/unrelated/other.py"]

    within = _scope(tmp_path, package, files, max_targets=3)
    beyond = _scope(tmp_path, package, files, max_targets=2)

    assert not within.too_broad
    assert beyond.too_broad
    assert beyond.reason is not None and "limit of 2" in beyond.reason
    assert beyond.targets == CONTRACT_TARGETS


def _rule_targets(name: str) -> tuple[str, ...]:
    return next(rule.targets for rule in CHANGE_CLASS_RULES if rule.name == name)


@pytest.mark.parametrize(
    ("path", "rule"),
    [
        ("src/cadrumo/_data/registry/aeat/modelo_303/2025.toml", "registry-data"),
        ("src/cadrumo/_data/registry/authority/authority-0123abcd.sqlite3", "authority"),
        ("src/cadrumo/_data/registry/authority/authority.current.json", "authority"),
        ("src/cadrumo/locales/es/LC_MESSAGES/cadrumo.po", "locales"),
        ("justfile", "justfile"),
    ],
)
def test_non_python_class_maps_to_its_declared_targets(tmp_path: Path, path: str, rule: str) -> None:
    scope = compute_change_scope([path], root=tmp_path)

    assert not scope.too_broad
    assert _rule_targets(rule)
    assert set(_rule_targets(rule)) <= set(scope.targets)
    assert not scope.ci_contracts


@pytest.mark.parametrize("path", ["conftest.py", "src/cadrumo/domain/conftest.py", "pyproject.toml", "uv.lock"])
def test_broad_change_class_is_too_broad(tmp_path: Path, path: str) -> None:
    scope = compute_change_scope([path], root=tmp_path)

    assert scope.too_broad
    assert scope.reason is not None and path in scope.reason
    assert scope.targets == CONTRACT_TARGETS


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", "dev/ci/change_scope.py", "dev/registry/bindings.py"])
def test_ci_and_dev_changes_flag_contracts_without_src_targets(tmp_path: Path, path: str) -> None:
    scope = compute_change_scope([path], root=tmp_path)

    assert scope.ci_contracts
    assert not scope.too_broad
    assert scope.targets == CONTRACT_TARGETS


def test_unclassified_non_python_change_selects_only_the_contract_set(tmp_path: Path) -> None:
    scope = compute_change_scope(["docs/guide.md"], root=tmp_path)

    assert scope == ChangeScope(targets=CONTRACT_TARGETS, ci_contracts=False, too_broad=False, reason=None)


def test_declared_targets_exist_in_the_repository() -> None:
    declared = {target for rule in CHANGE_CLASS_RULES for target in rule.targets}

    assert CONTRACT_TARGETS
    assert sorted(target for target in declared if not (REPO_ROOT / target).exists()) == []


def test_cli_prints_targets_one_per_line(capsys: pytest.CaptureFixture[str]) -> None:
    requested: list[str] = []

    def source(base: str) -> tuple[str, ...]:
        requested.append(base)
        return ("justfile",)

    assert main(["--base", "origin/main"], changed_files_source=source) == 0

    assert requested == ["origin/main"]
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(set(lines))
    assert set(lines) == {*CONTRACT_TARGETS, *_rule_targets("justfile")}


def test_cli_json_reports_the_full_selection(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--base", "main", "--json"], changed_files_source=lambda _base: ("uv.lock", ".github/x.yml"))

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["targets"] == list(CONTRACT_TARGETS)
    assert payload["ci_contracts"] is True
    assert payload["too_broad"] is True
    assert "uv.lock" in payload["reason"]
    assert "too broad" in captured.err
