"""Select the pytest targets a pull request's changed files can affect.

The merge gate runs a narrowed selection rather than the whole suite, so the
narrowing must never under-select silently. Selection has four sources:

- a changed Python file under ``src/`` selects the ``tests/`` directory of its
  nearest ancestor that owns one;
- the direct importers of a changed first-party module, found through the
  ``grimp`` import graph, select their own owning ``tests/`` directories;
- non-Python change classes select the fixed targets declared in
  ``CHANGE_CLASS_RULES``;
- the fixed contract set in ``CONTRACT_TARGETS`` is always selected.

A selection that cannot be narrowed honestly -- one above ``MAX_TARGETS``, one
touching a fan-out package such as ``cadrumo.core``, a rule declared broad, or a
Python change with no owning tests -- is reported with ``too_broad=True`` and a
reason. Its targets are then only the contract set, and the caller is expected
to print the reason as a visible advisory.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import grimp
from grimp.exceptions import GrimpException

from dev._paths import REPO_ROOT

__all__ = [
    "CHANGE_CLASS_RULES",
    "CONTRACT_TARGETS",
    "FANOUT_PACKAGES",
    "FIRST_PARTY_PACKAGES",
    "MAX_TARGETS",
    "ChangeClassRule",
    "ChangeScope",
    "compute_change_scope",
    "git_changed_files",
    "main",
]

#: Selections with more non-contract targets than this run the contract set only.
MAX_TARGETS: Final = 40

#: First-party packages whose import graph widens the selection.
FIRST_PARTY_PACKAGES: Final = ("cadrumo", "cadrumo_harness")

#: Packages whose changes fan out across the product; narrowing them is not honest.
FANOUT_PACKAGES: Final = ("cadrumo.core",)

_SOURCE_ROOT: Final = "src"
_TESTS_DIR: Final = "tests"
_GIT_TIMEOUT_SECONDS: Final = 60


@dataclass(frozen=True, slots=True)
class ChangeClassRule:
    """One change class: the paths it matches and what a match selects.

    ``patterns`` are repository-relative globs matched with
    ``PurePosixPath.full_match``. ``broad_reason`` marks a class whose change
    cannot be narrowed; ``contract`` marks a rule that belongs to the always-run
    contract set rather than to a path class.
    """

    name: str
    patterns: tuple[str, ...]
    targets: tuple[str, ...] = ()
    ci_contracts: bool = False
    broad_reason: str | None = None
    contract: bool = False

    def matches(self, path: str) -> bool:
        """Return whether ``path`` falls in this change class."""
        pure = PurePosixPath(path)
        return any(pure.full_match(pattern) for pattern in self.patterns)


CHANGE_CLASS_RULES: Final[tuple[ChangeClassRule, ...]] = (
    ChangeClassRule(
        name="contract",
        patterns=(),
        targets=(
            "dev/tests/test_import_quality_gate.py",
            "dev/tests/test_exit_code_contract.py",
            "dev/ci/tests/test_change_scope.py",
        ),
        contract=True,
    ),
    ChangeClassRule(
        name="authority",
        patterns=("**/authority-*.sqlite3", "**/authority.current.json", "**/authority.current.json.lock"),
        targets=(
            "src/cadrumo/application/registry/tests",
            "src/cadrumo/domain/calculations/registry/tests",
        ),
    ),
    ChangeClassRule(
        name="registry-data",
        patterns=("src/cadrumo/_data/registry/**",),
        targets=(
            "src/cadrumo/application/registry/tests",
            "src/cadrumo/domain/calculations/registry/tests",
            "src/cadrumo/domain/calculations/registry/facts/tests",
            "dev/registry/tests",
        ),
    ),
    ChangeClassRule(
        name="locales",
        patterns=("src/cadrumo/locales/**",),
        targets=("src/cadrumo/core/i18n/tests", "dev/locales/tests"),
    ),
    ChangeClassRule(
        name="conftest",
        patterns=("**/conftest.py",),
        broad_reason="a conftest.py change alters fixtures for every test beneath it",
    ),
    ChangeClassRule(
        name="pyproject",
        patterns=("pyproject.toml",),
        broad_reason="pyproject.toml changes dependencies, packaging and pytest configuration",
    ),
    ChangeClassRule(
        name="lockfile",
        patterns=("uv.lock",),
        broad_reason="uv.lock changes the resolved dependency set",
    ),
    ChangeClassRule(
        name="justfile",
        patterns=("justfile",),
        targets=("dev/tests/test_dev_cli_justfile_wiring.py",),
    ),
    ChangeClassRule(
        name="ci-contracts",
        patterns=(".github/**", "dev/**"),
        ci_contracts=True,
    ),
)


@dataclass(frozen=True, slots=True)
class ChangeScope:
    """The selection for one set of changed files."""

    targets: tuple[str, ...]
    ci_contracts: bool
    too_broad: bool
    reason: str | None

    def to_json(self) -> dict[str, object]:
        """Return the machine-readable selection payload."""
        return {
            "targets": list(self.targets),
            "ci_contracts": self.ci_contracts,
            "too_broad": self.too_broad,
            "reason": self.reason,
        }


def _contract_targets(rules: Sequence[ChangeClassRule]) -> tuple[str, ...]:
    return tuple(target for rule in rules if rule.contract for target in rule.targets)


CONTRACT_TARGETS: Final = _contract_targets(CHANGE_CLASS_RULES)


def git_changed_files(base: str, root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return the files changed between the merge base of ``base`` and ``HEAD``."""
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git executable not found on PATH")
    command = [git, "diff", "--name-only", f"{base}...HEAD"]
    completed = subprocess.run(
        command,
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    return tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _normalise(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/").strip()).as_posix().removeprefix("./")


def _owning_tests(path: str, root: Path) -> str | None:
    """Return the enclosing ``tests/`` directory, else that of the nearest ancestor owning one.

    The walk uses only directory existence, so a deleted or not-yet-known path
    still resolves through whichever ancestors remain.
    """
    parts = PurePosixPath(path).parts
    for depth in range(len(parts) - 1, 1, -1):
        ancestor = PurePosixPath(*parts[:depth])
        if ancestor.name == _TESTS_DIR:
            return ancestor.as_posix()
        if (root / ancestor / _TESTS_DIR).is_dir():
            return (ancestor / _TESTS_DIR).as_posix()
    return None


def _module_name(path: str, packages: Sequence[str]) -> str | None:
    pure = PurePosixPath(path)
    if pure.suffix != ".py" or pure.parts[0] != _SOURCE_ROOT or len(pure.parts) < 3:
        return None
    parts = list(pure.with_suffix("").parts[1:])
    if parts[0] not in packages:
        return None
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_path(module: str, graph_roots: dict[str, Path], root: Path) -> str | None:
    top = module.split(".", 1)[0]
    package_dir = graph_roots.get(top)
    if package_dir is None:
        return None
    relative = PurePosixPath(*module.split(".")[1:])
    candidate = package_dir / relative
    for path in (candidate / "__init__.py", candidate.with_suffix(".py")):
        if path.is_file():
            return path.relative_to(root).as_posix()
    return None


def _in_fanout(module: str, fanout: Sequence[str]) -> bool:
    return any(module == package or module.startswith(f"{package}.") for package in fanout)


def _importers(modules: Iterable[str], packages: Sequence[str]) -> dict[str, set[str]]:
    wanted = sorted(set(modules))
    if not wanted:
        return {}
    graph = grimp.build_graph(*packages, cache_dir=None)
    present = graph.modules
    return {module: graph.find_modules_that_directly_import(module) for module in wanted if module in present}


def compute_change_scope(
    changed_files: Iterable[str],
    *,
    root: Path = REPO_ROOT,
    rules: Sequence[ChangeClassRule] = CHANGE_CLASS_RULES,
    packages: Sequence[str] = FIRST_PARTY_PACKAGES,
    fanout: Sequence[str] = FANOUT_PACKAGES,
    max_targets: int = MAX_TARGETS,
) -> ChangeScope:
    """Compute the pytest selection for ``changed_files`` relative to ``root``."""
    contract = _contract_targets(rules)
    selected: set[str] = set()
    ci_contracts = False
    reasons: list[str] = []
    changed_modules: set[str] = set()

    for raw in changed_files:
        path = _normalise(raw)
        if not path:
            continue
        matched = [rule for rule in rules if not rule.contract and rule.matches(path)]
        for rule in matched:
            selected.update(rule.targets)
            ci_contracts = ci_contracts or rule.ci_contracts
            if rule.broad_reason is not None:
                reasons.append(f"{path}: {rule.broad_reason}")
        is_python = path.endswith(".py")
        under_src = path.startswith(f"{_SOURCE_ROOT}/")
        if under_src and (is_python or not matched):
            owner = _owning_tests(path, root)
            if owner is None:
                reasons.append(f"{path}: no ancestor below {_SOURCE_ROOT}/ owns a tests/ directory")
            else:
                selected.add(owner)
            module = _module_name(path, packages)
            if module is not None:
                changed_modules.add(module)
                if _in_fanout(module, fanout):
                    reasons.append(f"{path}: {module} is in a fan-out package")
        elif is_python and not matched:
            reasons.append(f"{path}: Python change outside every declared change class")

    graph_roots = {package: root / _SOURCE_ROOT / package for package in packages}
    try:
        importers = _importers(changed_modules, packages)
    except GrimpException as error:
        importers = {}
        reasons.append(f"import graph unavailable: {error}")
    for module in sorted(importers):
        for importer in sorted(importers[module]):
            importer_path = _module_path(importer, graph_roots, root)
            owner = None if importer_path is None else _owning_tests(importer_path, root)
            if owner is None:
                reasons.append(f"{importer} imports {module} but has no owning tests/ directory")
            else:
                selected.add(owner)

    narrowed = selected.difference(contract)
    if len(narrowed) > max_targets:
        reasons.append(f"{len(narrowed)} targets exceed the limit of {max_targets}")
    if reasons:
        return ChangeScope(targets=contract, ci_contracts=ci_contracts, too_broad=True, reason="; ".join(reasons))
    return ChangeScope(
        targets=(*contract, *sorted(narrowed)),
        ci_contracts=ci_contracts,
        too_broad=False,
        reason=None,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    changed_files_source: Callable[[str], Sequence[str]] | None = None,
) -> int:
    """Print the selection for the changes since ``--base``; always exit 0."""
    parser = argparse.ArgumentParser(prog="python -m dev.ci.change_scope", description=__doc__)
    parser.add_argument("--base", required=True, help="git ref the pull request merges into")
    parser.add_argument("--json", action="store_true", help="emit the full selection as JSON")
    arguments = parser.parse_args(argv)

    source = changed_files_source if changed_files_source is not None else git_changed_files
    scope = compute_change_scope(source(arguments.base))
    if arguments.json:
        print(json.dumps(scope.to_json(), indent=2))
    else:
        print("\n".join(scope.targets))
    if scope.too_broad:
        print(f"change scope too broad; running the contract set only: {scope.reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
