"""Gate: first-party scan roots and the production predicate are defined once.

:mod:`dev.first_party_source` owns which trees development instruments read and
which files inside them are production. This gate reads every non-test module
under ``dev/`` and fails when one of them restates either answer instead of
importing it.

Recognised restatements
    * a first-party root spelled as a literal: ``"src/cadrumo"`` or
      ``"src/cadrumo_harness"`` (with or without a trailing slash), a path
      chain ending at one of them (``root / "src" / "cadrumo"``), a tool root
      joined straight onto a repository root (``repo_root / "dev"``), or a
      collection naming two or more roots;
    * a test-surface or bundled-data test: ``"tests"``, ``"/tests/"`` or
      ``"_data"`` checked for membership in a path, a segment compared equal to
      ``"tests"``, ``"_data"`` or ``conftest``, or a ``startswith`` that names
      the ``_test_`` support prefix.

Where it stops
    A literal that names a location INSIDE a root -- ``"src/cadrumo/_data"``,
    ``root / "src" / "cadrumo" / "locales"`` -- addresses one subject, not a
    scan scope, and is not judged. Neither is a bare ``startswith("test_")``,
    which is pytest's collection convention for picking test files to run,
    nor an exclusion set whose members are already the authority's names.
    Product tests under ``src/`` cannot import development tooling and are not
    judged.

Tool configurations
    Three tools take the production rule in their own dialect rather than as a
    call: vulture's ``exclude`` globs in ``pyproject.toml``, ``.semgrepignore``,
    and the deptry exclusion regexes the suite runs (and the justfile recipe it
    is pinned to). Their text cannot import the authority, so they are judged by
    meaning instead: each must exclude exactly the live files the authority
    rejects within the tool's scope, matched the way that tool matches.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePath
from typing import Final

import pathspec
import pytest

from cadrumo.core.toml import load_toml
from dev._paths import REPO_ROOT, UTF_8
from dev.first_party_source import (
    DEPENDENCY_DECLARATION_ROOTS,
    DEVELOPMENT_TOOLING,
    FIRST_PARTY_ROOTS,
    HARNESS_PACKAGE,
    PACKAGING_HOOKS,
    PRODUCT_PACKAGE,
    is_production_source,
)
from dev.quality.suite import GATES
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AUTHORITY_MODULE: Final[str] = "dev.first_party_source"
_AUTHORITY_PATH: Final[str] = f"{DEVELOPMENT_TOOLING}/first_party_source.py"

_PACKAGE_ROOTS: Final[frozenset[str]] = frozenset({PRODUCT_PACKAGE, HARNESS_PACKAGE})
_PACKAGE_CHAIN_TAILS: Final[frozenset[tuple[str, ...]]] = frozenset(tuple(root.split("/")) for root in _PACKAGE_ROOTS)
_TOOL_ROOTS: Final[frozenset[str]] = frozenset({DEVELOPMENT_TOOLING, PACKAGING_HOOKS})
_ROOT_SPELLINGS: Final[frozenset[str]] = frozenset(FIRST_PARTY_ROOTS) | {f"{root}/" for root in _PACKAGE_ROOTS}

_MEMBERSHIP_SPELLINGS: Final[frozenset[str]] = frozenset({"tests", "/tests/", "tests/", "_data", "/_data/", "_data/"})
_SEGMENT_SPELLINGS: Final[frozenset[str]] = frozenset({"tests", "_data", "conftest.py", "conftest"})
_SUPPORT_PREFIX: Final[str] = "_test_"

#: Floors on what the scan recognised. The live tree holds several hundred
#: development modules and a few dozen that import the authority; a scan that
#: finds far fewer has lost its corpus or its subjects -- a moved tree, a renamed
#: module -- and its clean result would be vacuous.
_MINIMUM_AUTHORITY_CONSUMERS: Final[int] = 25
_MINIMUM_SCANNED_MODULES: Final[int] = 500


@dataclass(frozen=True, order=True)
class Restatement:
    """One place a module restates a scope the authority owns."""

    path: str
    line: int
    shape: str
    text: str

    def render(self) -> str:
        """Render one greppable finding row."""
        return f"{self.path}:{self.line}: {self.shape}: {self.text}"


def _docstring_ids(tree: ast.Module) -> frozenset[int]:
    definitions = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    owners = [tree, *(node for node in ast.walk(tree) if isinstance(node, definitions))]
    return frozenset(
        id(owner.body[0].value)
        for owner in owners
        if owner.body and isinstance(owner.body[0], ast.Expr) and isinstance(owner.body[0].value, ast.Constant)
    )


def _string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _chain(node: ast.BinOp) -> tuple[ast.expr, tuple[str, ...]]:
    """Split a ``/`` path chain into its non-literal base and literal tail."""
    tail: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div) and _string(current.right) is not None:
        tail.insert(0, str(_string(current.right)))
        current = current.left
    return current, tuple(tail)


def _names_a_repository_root(base: ast.expr) -> bool:
    name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else ""
    return "root" in name.casefold()


def _ends_at_a_root(node: ast.BinOp) -> bool:
    """Whether a whole path chain names a first-party root rather than a place inside one."""
    base, tail = _chain(node)
    if any(tail[-len(package) :] == package for package in _PACKAGE_CHAIN_TAILS):
        return True
    return len(tail) == 1 and tail[0] in _TOOL_ROOTS and _names_a_repository_root(base)


def _restatements(tree: ast.Module) -> Iterator[tuple[int, str, str]]:
    docstrings = _docstring_ids(tree)
    parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for node in ast.walk(tree):
        parent = parents.get(id(node))
        value = _string(node)
        if (
            isinstance(node, ast.Constant)
            and value in _ROOT_SPELLINGS - _TOOL_ROOTS
            and id(node) not in docstrings
            and not isinstance(parent, ast.JoinedStr)
        ):
            yield node.lineno, "root literal", repr(value)
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            named = {_string(element) for element in node.elts} & _ROOT_SPELLINGS
            if len(named) >= 2:
                yield node.lineno, "root collection", ast.unparse(node)
        is_chain_head = not (isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div) and parent.left is node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and is_chain_head and _ends_at_a_root(node):
            yield node.lineno, "root path chain", ast.unparse(node)
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if _string(node.left) in _MEMBERSHIP_SPELLINGS and any(
                isinstance(op, ast.In | ast.NotIn) for op in node.ops
            ):
                yield node.lineno, "test-surface membership", ast.unparse(node)
            elif any(isinstance(op, ast.Eq | ast.NotEq) for op in node.ops) and any(
                _string(operand) in _SEGMENT_SPELLINGS for operand in operands
            ):
                yield node.lineno, "test-surface equality", ast.unparse(node)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "startswith"
            and any(_string(constant) == _SUPPORT_PREFIX for argument in node.args for constant in ast.walk(argument))
        ):
            yield node.lineno, "test-support prefix", ast.unparse(node)


def _imports_authority(tree: ast.Module, module: str) -> bool:
    package = module.rsplit(".", 1)[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module == _AUTHORITY_MODULE:
                return True
            if node.level:
                anchor = package.split(".")
                base = anchor[: len(anchor) - (node.level - 1)]
                if ".".join([*base, *([node.module] if node.module else [])]) == _AUTHORITY_MODULE:
                    return True
    return False


@dataclass(frozen=True)
class ScopeCensus:
    """What the scan read, who imports the authority, and every restatement."""

    scanned: int
    consumers: tuple[str, ...]
    restatements: tuple[Restatement, ...]


def census(root: Path) -> ScopeCensus:
    """Read every non-test module under ``root/dev`` except the authority itself."""
    scanned = 0
    consumers: list[str] = []
    found: list[Restatement] = []
    for relative in repository_files(root, under=(DEVELOPMENT_TOOLING,)):
        if relative == _AUTHORITY_PATH or not is_production_source(relative):
            continue
        tree = ast.parse((root / relative).read_text(encoding=UTF_8), filename=relative)
        scanned += 1
        module = relative.removesuffix(".py").replace("/", ".")
        if _imports_authority(tree, module):
            consumers.append(relative)
        found.extend(Restatement(relative, line, shape, text) for line, shape, text in _restatements(tree))
    return ScopeCensus(scanned, tuple(consumers), tuple(sorted(set(found))))


def test_no_development_module_restates_a_first_party_scope() -> None:
    result = census(REPO_ROOT)

    assert result.scanned >= _MINIMUM_SCANNED_MODULES, (
        f"only {result.scanned} development modules were read; the scan lost its corpus and would pass vacuously"
    )
    assert len(result.consumers) >= _MINIMUM_AUTHORITY_CONSUMERS, (
        f"only {len(result.consumers)} modules import {_AUTHORITY_MODULE}; the gate no longer sees its subjects: "
        f"{sorted(result.consumers)}"
    )
    assert not result.restatements, (
        f"these modules restate a scope {_AUTHORITY_MODULE} owns; import it instead:\n  "
        + "\n  ".join(restatement.render() for restatement in result.restatements)
    )


_PLANTED_DEFECTS: Final[dict[str, str]] = {
    "root literal": 'ROOTS = "src/cadrumo"\n',
    "root collection": 'SCANNED = ("dev", "packaging")\n',
    "root path chain": 'from pathlib import Path\nREPO_ROOT = Path(".")\nPACKAGE = REPO_ROOT / "src" / "cadrumo"\n',
    "test-surface membership": 'def keep(path):\n    return "tests" not in path.parts\n',
    "test-surface equality": 'def keep(path):\n    return path.name != "conftest.py"\n',
    "test-support prefix": 'def keep(path):\n    return not path.name.startswith(("test_", "_test_"))\n',
}

_BENIGN: Final[str] = (
    '"""A docstring may say src/cadrumo."""\n'
    "from pathlib import Path\n"
    "from dev.first_party_source import PRODUCT_PACKAGE\n"
    'REPO_ROOT = Path(".")\n'
    'REGISTRY = "src/cadrumo/_data/registry"\n'
    'LOCALES = REPO_ROOT / "src" / "cadrumo" / "locales"\n'
    'RELEASE_PIN = REPO_ROOT / "dev" / "packaging" / "release-python-version"\n'
    'LABEL = f"{PRODUCT_PACKAGE}/"\n'
    "def collected(path):\n"
    '    return path.name.startswith("test_")\n'
)


def _plant(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding=UTF_8)


def test_the_gate_detects_every_planted_restatement_and_spares_specific_paths(tmp_path: Path) -> None:
    for index, source in enumerate(_PLANTED_DEFECTS.values()):
        _plant(tmp_path, f"dev/planted/defect_{index}.py", source)
    _plant(tmp_path, "dev/planted/benign.py", _BENIGN)
    _plant(tmp_path, "dev/planted/tests/test_ignored.py", 'ROOTS = ("src/cadrumo", "dev")\n')
    _plant(tmp_path, _AUTHORITY_PATH, 'PRODUCT_PACKAGE = "src/cadrumo"\n')

    result = census(tmp_path)

    assert {restatement.shape for restatement in result.restatements} == set(_PLANTED_DEFECTS)
    assert {restatement.path for restatement in result.restatements} == {
        f"dev/planted/defect_{index}.py" for index in range(len(_PLANTED_DEFECTS))
    }
    assert result.consumers == ("dev/planted/benign.py",)


#: Fewer live modules than this under a tool's scope means the comparison lost
#: its corpus, and an empty disagreement list would be vacuous.
_MINIMUM_PRODUCT_MODULES: Final[int] = 3000


def _python_files(*roots: str) -> tuple[str, ...]:
    return tuple(path for path in repository_files(REPO_ROOT, under=roots) if path.endswith(".py"))


def _misclassified(files: tuple[str, ...], excluded: Callable[[str], bool]) -> list[str]:
    """Return every file the tool's exclusion and the authority disagree about."""
    assert len(files) >= _MINIMUM_PRODUCT_MODULES, f"only {len(files)} modules in the tool's scope were enumerated"
    assert any(not is_production_source(path) for path in files), "the scope holds no non-production file to judge"
    return [path for path in files if is_production_source(path) == excluded(path)]


def test_vulture_excludes_exactly_what_the_authority_rejects() -> None:
    """Vulture wraps a wildcard-free pattern in ``*`` and fnmatches the native path."""
    configured = load_toml(REPO_ROOT / "pyproject.toml")["tool"]["vulture"]["exclude"]
    patterns = [pattern if any(char in pattern for char in "*?[") else f"*{pattern}*" for pattern in configured]

    def excluded(path: str) -> bool:
        return any(fnmatch(str(REPO_ROOT / path), pattern) for pattern in patterns)

    assert _misclassified(_python_files(PRODUCT_PACKAGE), excluded) == []


def test_semgrepignore_excludes_exactly_what_the_authority_rejects() -> None:
    """``.semgrepignore`` follows gitignore semantics over repository-relative paths."""
    rules = pathspec.GitIgnoreSpec.from_lines((REPO_ROOT / ".semgrepignore").read_text(encoding=UTF_8).splitlines())

    assert _misclassified(_python_files(PRODUCT_PACKAGE), rules.match_file) == []


def test_deptry_excludes_exactly_what_the_authority_rejects() -> None:
    """Deptry searches each regex anywhere in the path, with either separator."""
    command = dict(GATES)["check-dependency-declarations"]
    patterns = [
        re.compile(command[index + 1]) for index, argument in enumerate(command) if argument == "--extend-exclude"
    ]

    def excluded(path: str) -> bool:
        spellings = (path, str(PurePath(path)).replace("/", "\\"))
        verdicts = {any(pattern.search(spelling) for pattern in patterns) for spelling in spellings}
        assert len(verdicts) == 1, f"{path}: the deptry exclusion depends on the path separator"
        return verdicts.pop()

    assert _misclassified(_python_files(*DEPENDENCY_DECLARATION_ROOTS), excluded) == []
