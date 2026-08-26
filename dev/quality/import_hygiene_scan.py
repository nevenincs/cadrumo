"""Import-hygiene scanner for top-level-export centralisation.

Discovery-phase tool: builds an inventory of cross-package private imports,
shim/re-export modules, and redundantly re-exported symbols across
``src/cadrumo``. READ-ONLY: it does not modify production code.

A forwarding layer has two syntaxes and the scanner reads both. Written as
import aliases it has zero real definitions, which :func:`module_body_defs`
sees; written as wrapper definitions
(``def foo(a, *, b): return _real_foo(a, b=b)``) it evades that test by
construction, because such a module defines plenty of its own things. Family 2
covers the first syntax and Family 2b the second; they are one rule, and they
live together so a fix to one cannot silently leave the other behind.

It is also the SINGLE AUTHORITY for the one-way ``src/`` -> ``dev/`` boundary.
The boundary is absolute, by operator ruling: no module under ``src/`` --
shipped or test, ``cadrumo`` or ``cadrumo-harness`` -- may have ANY awareness of
the ``dev/`` tree. Family 5 detects an IMPORT of ``dev.*`` (static or dynamic),
Family 6 detects a module building a PATH into the ``dev/`` tree at runtime,
and Family 10 detects PROSE awareness -- a comment, docstring or multi-line
string that names the dev tree. The three are one rule with three syntaxes,
and they live together here so a fix to one cannot silently leave the other
behind. Consumers assert against these functions rather than re-implementing
them; the boundary gate under ``dev/quality/tests`` is one such consumer. The
former shipped-only scope was widened by ruling, never by drift: a
wheel-excluded test importing ``dev.*`` is no installed-user defect, but the
ruling targets absolute awareness, not installed-user breakage.

Families 8 and 9 are the two ends of one broken edge, and they live together
for the same reason. A deletion that lands without its consumer sweep leaves
either a consumer pointing at something gone (family 8) or a module nothing
points at any more (family 9); a check that sees only one end reports the split
as clean half the time. Both are whole-tree questions by construction -- no
per-commit or per-file gate can answer either -- so both are computed over the
complete first-party census rather than a changed-file subset.

Re-run with:

    python -m dev.quality.import_hygiene_scan [--json OUT.json] [--top N]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import io
import json
import re
import sys
import tokenize
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory

from .._paths import REPO_ROOT, UTF_8

SRC_ROOT = REPO_ROOT / "src"
PKG_ROOT = SRC_ROOT / "cadrumo"
_UTF_8: Final[str] = UTF_8

RETIRED_TUI_PACKAGE: Final[str] = "cadrumo.adapters.inbound.tui"
RETIRED_TUI_ROOT: Final[Path] = PKG_ROOT / "adapters" / "inbound" / "tui"
CANONICAL_TUI_PACKAGE: Final[str] = "cadrumo.entrypoints.tui"
_DETECTOR_PATH: Final[Path] = Path(__file__).resolve()

_LIVE_INVENTORY_EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {".git", ".vault", "_build", "build", "dist", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)


def tracked_live_files() -> tuple[Path, ...]:
    """Return tracked repository files, excluding only archive/generated trees."""
    import subprocess

    output = subprocess.check_output(("git", "ls-files", "-z"), cwd=REPO_ROOT, text=False)  # noqa: S607
    return tuple(
        sorted(
            {
                (REPO_ROOT / raw.decode(_UTF_8)).resolve()
                for raw in output.split(b"\0")
                if raw
                and (REPO_ROOT / raw.decode(_UTF_8)).is_file()
                and not any(part in _LIVE_INVENTORY_EXCLUDED_DIRS for part in (REPO_ROOT / raw.decode(_UTF_8)).parts)
            },
            key=lambda path: path.as_posix(),
        )
    )


@dataclass(frozen=True, slots=True)
class CanonicalAuthorityTarget:
    """One public defining module and the symbols it alone owns."""

    module: str
    path: Path
    symbols: frozenset[str]


@dataclass(frozen=True, slots=True)
class DelegatingWrapperRule:
    """A forbidden wrapper shape around one canonical callable."""

    kind: str
    delegated_symbol: str
    collaborator_symbols: frozenset[str] = frozenset()
    receiver_methods: frozenset[tuple[str, str]] = frozenset()
    keyword_source_methods: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True, slots=True)
class SubstitutableNaturalScanRule:
    """A forbidden natural-key scan that can substitute for canonical selection."""

    kind: str
    collection_names: frozenset[str]
    collection_methods: frozenset[str]
    coordinate_names: frozenset[str]
    minimum_coordinates: int = 2


@dataclass(frozen=True, slots=True)
class CanonicalAuthoritySpec:
    """Declarative configuration for a canonical import/authority census."""

    targets: tuple[CanonicalAuthorityTarget, ...]
    retired_modules: frozenset[str] = frozenset()
    facade_modules: frozenset[str] = frozenset()
    inert_modules: frozenset[str] = frozenset()
    export_container_names: frozenset[str] = frozenset(
        {"__all__", "_EXPORTS", "_EXPORT_MAP", "_LAZY_EXPORTS"}
    )
    wrapper_rules: tuple[DelegatingWrapperRule, ...] = ()
    natural_scan_rules: tuple[SubstitutableNaturalScanRule, ...] = ()
    forbidden_text_references: frozenset[str] = frozenset()
    text_suffixes: frozenset[str] = frozenset(
        {".cfg", ".ini", ".json", ".md", ".py", ".pyi", ".rst", ".toml", ".txt", ".yaml", ".yml"}
    )
    forbid_import_aliases: bool = True
    forbid_qualified_access: bool = True


@dataclass(frozen=True, slots=True)
class CanonicalAuthorityViolation:
    """One provenance-resolved breach of a canonical authority specification."""

    path: Path
    kind: str
    lineno: int = 0
    detail: str = ""


@dataclass
class _AuthorityScope:
    qualified: dict[str, str] = field(default_factory=dict)
    strings: dict[str, str] = field(default_factory=dict)
    literals: dict[str, ast.AST] = field(default_factory=dict)

    def child(self) -> _AuthorityScope:
        return _AuthorityScope(self.qualified.copy(), self.strings.copy(), self.literals.copy())


def _authority_module_name(path: Path) -> str:
    resolved = path.resolve()
    for root in (SRC_ROOT.resolve(), REPO_ROOT.resolve()):
        try:
            return module_name_for(resolved, src_root=root)
        except ValueError:
            continue
    return path.stem


def _static_string(node: ast.AST, scope: _AuthorityScope) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return scope.strings.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left, scope)
        right = _static_string(node.right, scope)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                part = _static_string(value.value, scope)
            else:
                part = _static_string(value, scope)
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    return None


def _qualified_value(node: ast.AST, scope: _AuthorityScope) -> str | None:
    if isinstance(node, ast.Name):
        return scope.qualified.get(node.id) or (
            node.id if node.id in {"__import__", "delattr", "dict", "getattr", "setattr"} else None
        )
    if isinstance(node, ast.Attribute):
        base = _qualified_value(node.value, scope)
        return f"{base}.{node.attr}" if base else None
    if not isinstance(node, ast.Call):
        return None
    function = _qualified_value(node.func, scope)
    if function in {"importlib.import_module", "__import__"} and node.args:
        return _static_string(node.args[0], scope)
    if function == "getattr" and len(node.args) >= 2:
        base = _qualified_value(node.args[0], scope)
        attribute = _static_string(node.args[1], scope)
        return f"{base}.{attribute}" if base and attribute else None
    return None


def _literal_strings(node: ast.AST, scope: _AuthorityScope, seen: frozenset[str] = frozenset()) -> set[str]:
    if isinstance(node, ast.Name) and node.id in scope.literals and node.id not in seen:
        return _literal_strings(scope.literals[node.id], scope, seen | {node.id})
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return {value for item in node.elts for value in _literal_strings(item, scope, seen)}
    if isinstance(node, ast.Dict):
        return {
            value
            for item in (*node.keys, *node.values)
            if item is not None
            for value in _literal_strings(item, scope, seen)
        }
    if isinstance(node, ast.Call) and _bare_callable_name(node.func) == "dict":
        return {
            value for argument in node.args for value in _literal_strings(argument, scope, seen)
        } | {
            value
            for keyword in node.keywords
            for value in (({keyword.arg} if keyword.arg else set()) | _literal_strings(keyword.value, scope, seen))
        }
    value = _static_string(node, scope)
    return {value} if value is not None else set()


def _bare_callable_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _scope_nodes(statements: Iterable[ast.stmt]) -> Iterable[ast.AST]:
    """Yield nodes owned by one scope, excluding nested definition bodies."""
    pending: list[ast.AST] = list(statements)
    while pending:
        node = pending.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pending.extend(node.decorator_list)
            pending.append(node.args)
            if node.returns is not None:
                pending.append(node.returns)
            continue
        if isinstance(node, ast.ClassDef):
            pending.extend((*node.decorator_list, *node.bases, *node.keywords))
            continue
        if isinstance(node, ast.Lambda):
            continue
        for child in ast.iter_child_nodes(node):
            pending.append(child)


class _CanonicalAuthorityAnalyzer:
    def __init__(self, path: Path, tree: ast.Module, spec: CanonicalAuthoritySpec) -> None:
        self.path = path
        self.tree = tree
        self.spec = spec
        self.module = _authority_module_name(path)
        self.targets = {symbol: target for target in spec.targets for symbol in target.symbols}
        self.target_modules = {target.module for target in spec.targets}
        self.qualified_targets = {
            f"{target.module}.{symbol}" for target in spec.targets for symbol in target.symbols
        }
        self.violations: list[CanonicalAuthorityViolation] = []

    def add(self, kind: str, node: ast.AST, detail: str = "") -> None:
        violation = CanonicalAuthorityViolation(self.path, kind, getattr(node, "lineno", 0), detail)
        if violation not in self.violations:
            self.violations.append(violation)

    def run(self) -> list[CanonicalAuthorityViolation]:
        self._scan_scope(self.tree.body, _AuthorityScope())
        return self.violations

    def _scan_scope(self, statements: list[ast.stmt], scope: _AuthorityScope) -> None:
        self._populate_scope(statements, scope)
        for node in _scope_nodes(statements):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._check_definition(node)
            elif isinstance(node, ast.Import):
                self._check_import(node, scope)
            elif isinstance(node, ast.ImportFrom):
                self._check_import_from(node, scope)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                self._check_assignment(node, scope)
            elif isinstance(node, ast.Call):
                self._check_dynamic_call(node, scope)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                self._check_qualified_access(node, scope)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                self._check_name_load(node, scope)
            elif isinstance(node, ast.arg) and node.annotation is not None:
                self._check_annotation(node.annotation, scope)
        definitions = (
            node
            for node in _scope_nodes(statements)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        for definition in definitions:
            if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_wrapper(definition, scope)
                self._check_natural_scan(definition)
            self._scan_scope(definition.body, scope.child())

    def _populate_scope(self, statements: list[ast.stmt], scope: _AuthorityScope) -> None:
        nodes = tuple(_scope_nodes(statements))
        for node in nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".", 1)[0]
                    scope.qualified[bound] = alias.name if alias.asname else bound
            elif isinstance(node, ast.ImportFrom):
                target = resolve_relative_import(
                    self.module, self.path.name == "__init__.py", node.level, node.module
                )
                if target:
                    for alias in node.names:
                        scope.qualified[alias.asname or alias.name] = f"{target}.{alias.name}"
        assignments = sorted(
            (node for node in nodes if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for node in assignments:
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                scope.literals[target.id] = node.value
                string = _static_string(node.value, scope)
                qualified = _qualified_value(node.value, scope)
                if string is None:
                    scope.strings.pop(target.id, None)
                else:
                    scope.strings[target.id] = string
                if qualified is None:
                    scope.qualified.pop(target.id, None)
                else:
                    scope.qualified[target.id] = qualified

    def _check_definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        target = self.targets.get(node.name)
        if target is not None and self.path.resolve() != target.path.resolve():
            self.add("duplicate authority definition", node, node.name)

    def _check_import(self, node: ast.Import, scope: _AuthorityScope) -> None:
        if self.module in self.spec.inert_modules:
            self.add("non-inert package import", node)
        for alias in node.names:
            if alias.name in self.spec.retired_modules:
                self.add("retired private module import", node, alias.name)

    def _check_import_from(self, node: ast.ImportFrom, scope: _AuthorityScope) -> None:
        target = resolve_relative_import(self.module, self.path.name == "__init__.py", node.level, node.module)
        if target is None:
            return
        if self.module in self.spec.inert_modules and target != "__future__":
            self.add("non-inert package import", node, target)
        if target in self.spec.retired_modules:
            self.add("retired private module import", node, target)
        for alias in node.names:
            qualified = f"{target}.{alias.name}"
            authority = self.targets.get(alias.name)
            if alias.name == "*" and target in self.target_modules | self.spec.facade_modules:
                self.add("wildcard authority import", node, target)
            if qualified in self.spec.retired_modules:
                self.add("retired private module import", node, qualified)
            if target in self.spec.facade_modules and (authority is not None or qualified in self.target_modules):
                self.add("facade import/package access", node, qualified)
            if authority is not None and target != authority.module:
                self.add("non-canonical authority import", node, qualified)
            if authority is not None and alias.asname and self.spec.forbid_import_aliases:
                self.add("aliased authority import", node, f"{qualified} as {alias.asname}")

    def _check_assignment(self, node: ast.Assign | ast.AnnAssign, scope: _AuthorityScope) -> None:
        if node.value is None:
            return
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        for target in targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Call)
                and _bare_callable_name(target.value.func) == "globals"
                and _static_string(target.slice, scope) in self.targets
            ):
                self.add("dynamic authority export", node, _static_string(target.slice, scope) or "")
        for name in names & self.targets.keys():
            if self.path.resolve() != self.targets[name].path.resolve():
                self.add("duplicate authority binding", node, name)
        qualified = _qualified_value(node.value, scope)
        if names and qualified in self.qualified_targets and not names & self.targets.keys():
            self.add("aliased authority binding", node, qualified)
        if names & self.spec.export_container_names:
            exported = _literal_strings(node.value, scope) & self.targets.keys()
            if exported and self.module not in self.target_modules:
                self.add("indirect authority export", node, ", ".join(sorted(exported)))

    def _check_dynamic_call(self, node: ast.Call, scope: _AuthorityScope) -> None:
        function = _qualified_value(node.func, scope)
        if function == "setattr" and len(node.args) >= 2:
            base = _qualified_value(node.args[0], scope)
            attribute = _static_string(node.args[1], scope)
            expression = f"{base}.{attribute}" if base and attribute else None
            if expression in self.qualified_targets or any(
                expression == f"{facade}.{symbol}"
                for facade in self.spec.facade_modules
                for symbol in self.targets
            ):
                self.add("dynamic authority export", node, expression or "")
        if function in {"importlib.import_module", "__import__"} and node.args:
            imported = _static_string(node.args[0], scope)
            if imported in self.spec.retired_modules:
                self.add("dynamic authority import/access", node, imported or "")
        expression = _qualified_value(node, scope)
        if expression in self.spec.retired_modules:
            self.add("dynamic authority import/access", node, expression or "")
        elif expression in self.qualified_targets and self.spec.forbid_qualified_access:
            self.add("qualified authority access", node, expression or "")
        elif any(expression == f"{facade}.{symbol}" for facade in self.spec.facade_modules for symbol in self.targets):
            self.add("facade import/package access", node, expression or "")

    def _check_qualified_access(self, node: ast.Attribute, scope: _AuthorityScope) -> None:
        expression = _qualified_value(node, scope)
        if expression in self.spec.retired_modules:
            self.add("retired qualified authority access", node, expression or "")
        elif expression in self.qualified_targets and self.spec.forbid_qualified_access:
            self.add("qualified authority access", node, expression or "")
        elif any(expression == f"{facade}.{symbol}" for facade in self.spec.facade_modules for symbol in self.targets):
            self.add("facade import/package access", node, expression or "")

    def _check_name_load(self, node: ast.Name, scope: _AuthorityScope) -> None:
        target = self.targets.get(node.id)
        if target is None or self.path.resolve() == target.path.resolve():
            return
        if scope.qualified.get(node.id) != f"{target.module}.{node.id}":
            self.add("indirect authority symbol consumer", node, node.id)

    def _check_annotation(self, node: ast.AST, scope: _AuthorityScope) -> None:
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            return
        names = set(re.findall(r"\b[A-Za-z_]\w*\b", node.value)) & self.targets.keys()
        for name in names:
            target = self.targets[name]
            if self.path.resolve() != target.path.resolve() and scope.qualified.get(name) != f"{target.module}.{name}":
                self.add("indirect authority symbol consumer", node, name)

    def _check_wrapper(self, node: ast.FunctionDef | ast.AsyncFunctionDef, parent: _AuthorityScope) -> None:
        if "tests" in self.path.parts or self.path.name.startswith("test_"):
            return
        scope = parent.child()
        self._populate_scope(node.body, scope)
        calls = [item for item in _scope_nodes(node.body) if isinstance(item, ast.Call)]
        for delegated_call in calls:
            delegated = _qualified_value(delegated_call.func, scope)
            for rule in self.spec.wrapper_rules:
                target = self.targets.get(rule.delegated_symbol)
                expected = f"{target.module}.{rule.delegated_symbol}" if target else rule.delegated_symbol
                if delegated not in {expected, rule.delegated_symbol}:
                    continue
                collaborators = {_qualified_value(call.func, scope) or _bare_callable_name(call.func) for call in calls}
                collaborator_names = {name.rsplit(".", 1)[-1] for name in collaborators}
                receiver_methods = {
                    (call.func.value.id, call.func.attr)
                    for call in calls
                    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                }
                keyword_sources = {
                    (keyword.arg, source.func.attr)
                    for keyword in delegated_call.keywords
                    if keyword.arg is not None
                    for source in self._keyword_source_calls(keyword.value, scope)
                    if isinstance(source.func, ast.Attribute)
                }
                if (
                    rule.collaborator_symbols & collaborator_names
                    or rule.receiver_methods & receiver_methods
                    or rule.keyword_source_methods & keyword_sources
                ):
                    self.add(rule.kind, node, node.name)

    @staticmethod
    def _keyword_source_calls(value: ast.AST, scope: _AuthorityScope) -> tuple[ast.Call, ...]:
        if isinstance(value, ast.Call):
            return (value,)
        if isinstance(value, ast.Name) and isinstance(source := scope.literals.get(value.id), ast.Call):
            return (source,)
        return ()

    def _check_natural_scan(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if (
            "tests" in self.path.parts
            or self.path.name.startswith("test_")
            or any(self.path.resolve() == target.path.resolve() for target in self.spec.targets)
        ):
            return
        for loop in (
            item
            for item in _scope_nodes(node.body)
            if isinstance(item, (ast.For, ast.AsyncFor, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp))
        ):
            generators = (
                loop.generators
                if isinstance(loop, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp))
                else (loop,)
            )
            for generator in generators:
                target_node = generator.target
                iterator = generator.iter
                if not isinstance(target_node, ast.Name) or not isinstance(iterator, ast.Call):
                    continue
                if not isinstance(iterator.func, ast.Attribute) or not isinstance(iterator.func.value, ast.Name):
                    continue
                candidate = target_node.id
                coordinates = {
                    child.attr
                    for child in ast.walk(loop)
                    if isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == candidate
                }
                for rule in self.spec.natural_scan_rules:
                    if (
                        iterator.func.value.id in rule.collection_names
                        and iterator.func.attr in rule.collection_methods
                        and len(coordinates & rule.coordinate_names) >= rule.minimum_coordinates
                    ):
                        self.add(rule.kind, node, node.name)


def scan_canonical_authority(
    spec: CanonicalAuthoritySpec, paths: Iterable[Path] | None = None
) -> list[CanonicalAuthorityViolation]:
    """Scan tracked live Python files against one declarative authority spec."""
    candidates = tracked_live_files() if paths is None else tuple(paths)
    violations: list[CanonicalAuthorityViolation] = []
    definitions: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    for path in candidates:
        if path.suffix.lower() in spec.text_suffixes and spec.forbidden_text_references:
            try:
                text = path.read_text(encoding=_UTF_8, errors="replace")
            except OSError:
                text = ""
            for reference in spec.forbidden_text_references:
                if reference in text:
                    violations.append(
                        CanonicalAuthorityViolation(path, "retired authority string", detail=reference)
                    )
        if path.suffix.lower() not in {".py", ".pyi"}:
            continue
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions[node.name].append((path, node.lineno))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                if isinstance(node.value, ast.Attribute):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                for target in targets:
                    if isinstance(target, ast.Name):
                        definitions[target.id].append((path, node.lineno))
        violations.extend(_CanonicalAuthorityAnalyzer(path, tree, spec).run())
    for target in spec.targets:
        for symbol in target.symbols:
            sites = definitions.get(symbol, [])
            expected = [(path, line) for path, line in sites if path.resolve() == target.path.resolve()]
            if len(expected) != 1:
                violations.append(
                    CanonicalAuthorityViolation(
                        target.path,
                        "missing canonical definition" if not expected else "duplicate canonical definition",
                        detail=symbol,
                    )
                )
    return sorted(violations, key=lambda item: (item.path.as_posix(), item.lineno, item.kind, item.detail))


def public_definition_names(path: Path) -> frozenset[str]:
    """Return public top-level function and class definitions from one module."""
    tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    return frozenset(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    )


class TuiRetirementRemnantKind(StrEnum):
    """A direct route by which the retired TUI can re-enter the tree."""

    MODULE = "module"
    IMPORT = "import"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class TuiRetirementRemnant:
    """One currently reachable retired-TUI module or reference."""

    kind: TuiRetirementRemnantKind
    importer_mod: str
    importer_path: str
    lineno: int
    target: str


# ---------------------------------------------------------------------------
# Module path helpers
# ---------------------------------------------------------------------------


def module_name_for(path: Path, *, src_root: Path = SRC_ROOT) -> str:
    """Return the dotted module name for a file under ``src_root``.

    Args:
        path: The module file to name.
        src_root: Source root the name is taken relative to. Injectable so a
            caller can resolve names inside a synthetic tree; defaults to the
            repository's real ``src/``.
    """
    rel = path.relative_to(src_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def is_test_module(mod: str, path: Path) -> bool:
    """True if the module is a test module (under ``tests/`` or ``test_*``)."""
    parts = path.parts
    if "tests" in parts:
        return True
    last = mod.rsplit(".", 1)[-1]
    return last.startswith("test_") or last == "conftest"


def has_private_component(mod: str) -> bool:
    """True if any dotted component (other than a dunder) starts with '_'."""
    return any(part.startswith("_") and not (part.startswith("__") and part.endswith("__")) for part in mod.split("."))


def is_underscore_named(name: str) -> bool:
    """True if ``name`` is a private-convention identifier (leading '_', not a dunder).

    Mirrors the private-component test above but for a single bare identifier
    (an ``__all__`` entry), not a dotted module path.
    """
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def owning_package(mod: str) -> str:
    """Return the package that owns a private module.

    Ownership rule: for a private module ``A.B._C...`` (first private
    component at index k), the owning package is ``A.B`` -- everything
    strictly before the first private component. If the module itself has
    no private component, it owns itself (not expected to be called in that
    case).
    """
    parts = mod.split(".")
    for i, part in enumerate(parts):
        if part.startswith("_") and not (part.startswith("__") and part.endswith("__")):
            return ".".join(parts[:i])
    return mod


def resolve_relative_import(
    importer_mod: str, importer_is_pkg: bool, level: int, node_module: str | None
) -> str | None:
    """Resolve a (possibly relative) ``from`` import target to an absolute name.

    Mirrors Python's import-system semantics for relative ``from`` imports.
    """
    if level == 0:
        return node_module

    importer_parts = importer_mod.split(".")
    # For a package (__init__.py), "its own package" is itself; the base for
    # relative resolution starts at the package itself for level=1.
    base_parts = importer_parts if importer_is_pkg else importer_parts[:-1]

    # level=1 means "current package" (base_parts as-is); each extra level
    # strips one more component.
    strip = level - 1
    if strip > 0:
        if strip > len(base_parts):
            return None
        base_parts = base_parts[: len(base_parts) - strip]

    if node_module:
        return ".".join(base_parts + node_module.split("."))
    return ".".join(base_parts) if base_parts else None


# ---------------------------------------------------------------------------
# Facade boundary discovery
# ---------------------------------------------------------------------------


@dataclass
class FacadeInfo:
    """A package __init__.py and the ``__all__`` export surface it declares."""

    package: str
    path: Path
    all_names: list[str] = field(default_factory=list)
    has_real_all: bool = False
    is_pure_reexport_shape: bool = False


def dunder_all_assignment_value(node: ast.stmt) -> ast.expr | None:
    """Return the assigned value expression if ``node`` assigns ``__all__``.

    Handles both the plain form (``__all__ = [...]``, :class:`ast.Assign`) and
    the annotated form (``__all__: list[str] = [...]``, :class:`ast.AnnAssign`).
    An annotated declaration with no value (``__all__: list[str]``) yields
    ``None``, same as any other statement that is not an ``__all__`` binding.
    """
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
        return node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
        return node.value
    return None


def discover_facades() -> dict[str, FacadeInfo]:
    """Enumerate every __init__.py carrying a real ``__all__`` literal.

    A "real" ``__all__`` is a non-empty list/tuple/set of string constants,
    assigned via either the plain (``__all__ = [...]``) or annotated
    (``__all__: list[str] = [...]``) form.
    """
    facades: dict[str, FacadeInfo] = {}
    for init_path in scan_directory(
        PKG_ROOT, pattern="__init__.py", recursive=True, prune_directories=("__pycache__",)
    ):
        mod = module_name_for(init_path)
        try:
            src = init_path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(init_path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        all_names: list[str] = []
        has_real_all = False
        for node in ast.walk(tree):
            value = dunder_all_assignment_value(node)
            if value is None or not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                continue
            names = [elt.value for elt in value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
            if names:
                all_names.extend(names)
                has_real_all = True
        facades[mod] = FacadeInfo(package=mod, path=init_path, all_names=all_names, has_real_all=has_real_all)
    return facades


# ---------------------------------------------------------------------------
# Violation family 4: underscore-named entries in a public ``__all__``
# ---------------------------------------------------------------------------


@dataclass
class UnderscoreInAllViolation:
    """A private-named symbol (leading '_', not a dunder) exported in a facade's ``__all__``.

    A public facade exporting a private-named symbol contradicts the
    single-canonical-source policy: the leading underscore signals "not part
    of the public contract" everywhere else in the codebase, but listing the
    name in ``__all__`` advertises it as exactly that. Every hit needs a
    per-symbol disposition -- promote to a public name (rename + sweep every
    consumer) or drop it from the facade (it stays importable intra-package,
    just not on the public surface).
    """

    package: str
    path: str
    name: str


def find_underscore_in_all_violations(facades: dict[str, FacadeInfo]) -> list[UnderscoreInAllViolation]:
    """Return every ``__all__`` entry across all facades that is underscore-named."""
    violations: list[UnderscoreInAllViolation] = []
    for pkg, info in facades.items():
        if not info.has_real_all:
            continue
        for name in info.all_names:
            if is_underscore_named(name):
                violations.append(
                    UnderscoreInAllViolation(
                        package=pkg,
                        path=str(info.path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        name=name,
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


@dataclass
class ImportSite:
    """A single ``import`` / ``from`` statement resolved to its target module."""

    importer_mod: str
    importer_path: Path
    lineno: int
    target_mod: str
    imported_names: list[str]
    is_test: bool
    in_type_checking: bool


def type_checking_guarded_nodes(tree: ast.Module) -> set[int]:
    """Return the ``id()`` of every node under an ``if TYPE_CHECKING:`` guard.

    The one canonical answer to "is this statement type-only?", shared by the
    import walk and the wrapper-binding map so the two cannot disagree about
    what the guard covers.
    """
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_guard = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if is_guard:
            guarded.update(id(child) for child in ast.walk(node))
    return guarded


def walk_module_imports(path: Path, *, src_root: Path = SRC_ROOT) -> list[ImportSite]:
    """Parse a module and return every resolved import site it contains.

    Args:
        path: The module file to parse.
        src_root: Source root the importer's dotted name is taken relative to.
    """
    try:
        src = path.read_text(encoding=_UTF_8)
        tree = ast.parse(src, filename=str(path))
    except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
        return []

    mod = module_name_for(path, src_root=src_root)
    is_pkg = path.name == "__init__.py"
    sites: list[ImportSite] = []
    test_flag = is_test_module(mod, path)

    type_checking_nodes = type_checking_guarded_nodes(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = resolve_relative_import(mod, is_pkg, node.level, node.module)
            if target is None:
                continue
            names = [alias.name for alias in node.names]
            sites.append(
                ImportSite(
                    importer_mod=mod,
                    importer_path=path,
                    lineno=node.lineno,
                    target_mod=target,
                    imported_names=names,
                    is_test=test_flag,
                    in_type_checking=id(node) in type_checking_nodes,
                )
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                sites.append(
                    ImportSite(
                        importer_mod=mod,
                        importer_path=path,
                        lineno=node.lineno,
                        target_mod=alias.name,
                        imported_names=[],
                        is_test=test_flag,
                        in_type_checking=id(node) in type_checking_nodes,
                    )
                )
    return sites


# ---------------------------------------------------------------------------
# Violation family 1: cross-package private import
# ---------------------------------------------------------------------------


@dataclass
class PrivateImportViolation:
    """A cross-package import that reaches into another package's private module."""

    importer_mod: str
    importer_path: str
    lineno: int
    target_mod: str
    owning_package: str
    imported_names: list[str]
    is_test: bool
    in_type_checking: bool


def find_private_import_violations(all_sites: list[ImportSite]) -> list[PrivateImportViolation]:
    """Return every import site that reaches into a foreign package's privates."""
    violations: list[PrivateImportViolation] = []
    for site in all_sites:
        if not site.target_mod.startswith("cadrumo"):
            continue
        if not has_private_component(site.target_mod):
            continue
        owner = owning_package(site.target_mod)
        importer = site.importer_mod
        # Legitimate: importer is under the owning package (sibling/descendant),
        # OR importer *is* the owning package's own __init__ building its facade.
        if importer == owner or importer.startswith(owner + "."):
            continue
        violations.append(
            PrivateImportViolation(
                importer_mod=importer,
                importer_path=str(site.importer_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                lineno=site.lineno,
                target_mod=site.target_mod,
                owning_package=owner,
                imported_names=site.imported_names,
                is_test=site.is_test,
                in_type_checking=site.in_type_checking,
            )
        )
    return violations


class TuiBoundaryViolationKind(StrEnum):
    """Static syntax families that can bypass the dedicated TUI boundary."""

    STATIC_IMPORT = "static_import"
    TYPE_ONLY_IMPORT = "type_only_import"
    REEXPORT = "reexport"
    DYNAMIC_IMPORT = "dynamic_import"
    ANNOTATION = "annotation"
    REGISTRATION = "registration"
    TEXTUAL_LOCATION = "textual_location"
    PRIVATE_FACADE = "private_facade"


@dataclass(frozen=True)
class TuiBoundaryViolation:
    """One exact AST reach that violates D11's TUI dependency direction."""

    importer_mod: str
    importer_path: str
    lineno: int
    target: str
    kind: TuiBoundaryViolationKind


def _targets_module(value: str, module: str) -> bool:
    return value == module or value.startswith(module + ".") or value.startswith(module + ":")


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _expression_reference(node: ast.expr, aliases: dict[str, str]) -> str | None:
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    root = aliases.get(current.id, current.id)
    return ".".join((root, *reversed(parts)))


def _annotation_references(tree: ast.Module, aliases: dict[str, str]) -> tuple[tuple[int, str], ...]:
    annotations: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotations.extend(arg.annotation for arg in (*node.args.posonlyargs, *node.args.args) if arg.annotation)
            annotations.extend(arg.annotation for arg in (*node.args.kwonlyargs,) if arg.annotation)
            if node.args.vararg and node.args.vararg.annotation:
                annotations.append(node.args.vararg.annotation)
            if node.args.kwarg and node.args.kwarg.annotation:
                annotations.append(node.args.kwarg.annotation)
            if node.returns:
                annotations.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
    found: set[tuple[int, str]] = set()
    for annotation in annotations:
        for node in ast.walk(annotation):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add((node.lineno, node.value))
            elif isinstance(node, (ast.Name, ast.Attribute)) and (target := _expression_reference(node, aliases)):
                found.add((node.lineno, target))
    return tuple(
        sorted(
            (line, target)
            for line, target in found
            if not any(other_line == line and other.startswith(target + ".") for other_line, other in found)
        )
    )


def _registration_references(tree: ast.Module, aliases: dict[str, str]) -> tuple[tuple[int, str], ...]:
    """Return TUI-shaped values passed through any call boundary.

    Registration APIs have no stable verb vocabulary: decorators, registries,
    plugin managers and dependency containers all accept the same module or
    object reference under arbitrary method names.  The semantic fact is the
    TUI reference crossing a call boundary, so resolve every argument rather
    than maintaining registrar spellings.
    """
    found: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = _called_function_name(node.func)
        if called in _DYNAMIC_IMPORT_CALLABLES:
            continue
        values = [*node.args, *(keyword.value for keyword in node.keywords)]
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                if _targets_module(value.value, CANONICAL_TUI_PACKAGE):
                    found.add((value.lineno, value.value))
            elif (target := _expression_reference(value, aliases)) and _targets_module(target, CANONICAL_TUI_PACKAGE):
                found.add((value.lineno, target))
    return tuple(sorted(found))


def find_tui_boundary_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[TuiBoundaryViolation]:
    """Reject every statically visible bypass of the canonical TUI boundary."""
    violations: list[TuiBoundaryViolation] = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        aliases = _import_aliases(tree)
        importer = module_name_for(path, src_root=src_root)
        relative = path.relative_to(src_root).as_posix()
        inside_tui = importer == CANONICAL_TUI_PACKAGE or importer.startswith(CANONICAL_TUI_PACKAGE + ".")

        for site in walk_module_imports(path, src_root=src_root):
            target = site.target_mod
            if not inside_tui and _targets_module(target, CANONICAL_TUI_PACKAGE):
                kind = (
                    TuiBoundaryViolationKind.TYPE_ONLY_IMPORT
                    if site.in_type_checking
                    else TuiBoundaryViolationKind.STATIC_IMPORT
                )
                if path.name == "__init__.py":
                    kind = TuiBoundaryViolationKind.REEXPORT
                violations.append(TuiBoundaryViolation(importer, relative, site.lineno, target, kind))
            if (
                inside_tui
                and target.startswith("cadrumo.")
                and any(is_underscore_named(name) for name in site.imported_names)
            ):
                private_target = next(name for name in site.imported_names if is_underscore_named(name))
                violations.append(
                    TuiBoundaryViolation(
                        importer,
                        relative,
                        site.lineno,
                        f"{target}.{private_target}",
                        TuiBoundaryViolationKind.PRIVATE_FACADE,
                    )
                )
            if (target == "textual" or target.startswith("textual.")) and not inside_tui:
                violations.append(
                    TuiBoundaryViolation(
                        importer, relative, site.lineno, target, TuiBoundaryViolationKind.TEXTUAL_LOCATION
                    )
                )
            if inside_tui and target.startswith("cadrumo.") and has_private_component(target):
                owner = owning_package(target)
                if importer != owner and not importer.startswith(owner + "."):
                    violations.append(
                        TuiBoundaryViolation(
                            importer, relative, site.lineno, target, TuiBoundaryViolationKind.PRIVATE_FACADE
                        )
                    )

        for lineno, target in iter_dynamic_import_targets(path):
            if not inside_tui and _targets_module(target, CANONICAL_TUI_PACKAGE):
                violations.append(
                    TuiBoundaryViolation(importer, relative, lineno, target, TuiBoundaryViolationKind.DYNAMIC_IMPORT)
                )
            if inside_tui and target.startswith("cadrumo.") and has_private_component(target):
                violations.append(
                    TuiBoundaryViolation(importer, relative, lineno, target, TuiBoundaryViolationKind.PRIVATE_FACADE)
                )

        for kind, references in (
            (TuiBoundaryViolationKind.ANNOTATION, _annotation_references(tree, aliases)),
            (TuiBoundaryViolationKind.REGISTRATION, _registration_references(tree, aliases)),
        ):
            for lineno, target in references:
                if not inside_tui and _targets_module(target, CANONICAL_TUI_PACKAGE):
                    violations.append(TuiBoundaryViolation(importer, relative, lineno, target, kind))
                if inside_tui and target.startswith("cadrumo.") and has_private_component(target):
                    violations.append(
                        TuiBoundaryViolation(
                            importer, relative, lineno, target, TuiBoundaryViolationKind.PRIVATE_FACADE
                        )
                    )

    return sorted(violations, key=lambda item: (item.importer_path, item.lineno, item.kind, item.target))


# ---------------------------------------------------------------------------
# Violation family 5: shipped module importing the unshipped dev tooling
# ---------------------------------------------------------------------------

DEV_TOOLING_ROOT: Final[str] = "dev"

PYPROJECT_PATH: Final[Path] = REPO_ROOT / "pyproject.toml"

# Callables whose first string-literal argument names a module to import. A
# dynamically-built target is invisible to the AST import walk above, so a
# `dev.` reach expressed this way would otherwise slip the family entirely --
# the exact blind spot that makes a gate pass while missing what it guards.
_DYNAMIC_IMPORT_CALLABLES: Final[frozenset[str]] = frozenset({"import_module", "__import__"})


@dataclass
class DevToolingImportViolation:
    """A module under ``src/`` that imports the unshipped ``dev/`` tooling."""

    importer_mod: str
    importer_path: str
    lineno: int
    target_mod: str
    imported_names: list[str]
    is_dynamic: bool


def targets_dev_tooling(mod: str) -> bool:
    """True if ``mod`` names the ``dev`` tooling root or anything beneath it."""
    return mod == DEV_TOOLING_ROOT or mod.startswith(DEV_TOOLING_ROOT + ".")


def wheel_exclude_globs(pyproject_path: Path = PYPROJECT_PATH) -> tuple[str, ...]:
    """Return the wheel target's exclude globs, read from the packaging config.

    Read rather than restated so the shipped/unshipped boundary this module
    reasons about stays true if the packaging excludes change. A missing table
    raises: silently defaulting to "nothing is excluded" would make every
    module look shipped, and defaulting to "everything" would mute the gate.
    """
    data = tomllib.loads(pyproject_path.read_text(encoding=_UTF_8))
    excludes = data["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]
    return tuple(str(glob) for glob in excludes)


def is_shipped_module(
    path: Path,
    *,
    src_root: Path = SRC_ROOT,
    exclude_globs: tuple[str, ...] | None = None,
) -> bool:
    """True if ``path`` lands in the installed wheel.

    A module is shipped unless the packaging config excludes it. Note this is
    NOT the same partition as :func:`is_test_module`: a package-root
    ``conftest.py`` carries no ``tests/`` path component, so it ships and is
    treated as shipped here even though it is test infrastructure by name.

    Args:
        path: Module file to classify.
        src_root: Source root ``path`` is relative to.
        exclude_globs: Wheel exclude globs; read from the packaging config when
            omitted.
    """
    globs = wheel_exclude_globs() if exclude_globs is None else exclude_globs
    rel = "src/" + path.relative_to(src_root).as_posix()
    for glob in globs:
        # A bare directory glob ("src/cadrumo/tests") excludes the tree under it;
        # fnmatch's '*' spans '/', so the recursive forms match as written.
        if fnmatch.fnmatchcase(rel, glob) or rel.startswith(glob.rstrip("*").rstrip("/") + "/"):
            return False
    return True


def iter_dynamic_import_targets(path: Path) -> list[tuple[int, str]]:
    """Return every ``(lineno, module)`` pair from a string-literal dynamic import.

    Only a literal first argument is resolvable by static reading; a target
    assembled from variables is out of reach here and is left to review.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
        return []

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            called = func.attr
        elif isinstance(func, ast.Name):
            called = func.id
        else:
            continue
        if called not in _DYNAMIC_IMPORT_CALLABLES:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append((node.lineno, first.value))
    return found


def find_dev_tooling_import_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[DevToolingImportViolation]:
    """Return every module under ``src_root`` that imports ``dev.``.

    Absolute by operator ruling: no module under ``src/`` -- shipped or test --
    may import the ``dev/`` tree, which ships in neither the wheel nor the
    sdist. The former shipped-only scope encoded the installed-user defect only;
    the ruling widens the boundary to all awareness, so a test that needs dev
    tooling lives under ``dev/`` itself and is swept here as a violation too.

    Args:
        py_files: Module files to scan.
        src_root: Source root importer names are resolved against.
    """
    violations: list[DevToolingImportViolation] = []
    for path in py_files:
        mod = module_name_for(path, src_root=src_root)
        rel = str(path.relative_to(src_root)).replace("\\", "/")
        for site in walk_module_imports(path, src_root=src_root):
            if targets_dev_tooling(site.target_mod):
                violations.append(
                    DevToolingImportViolation(
                        importer_mod=mod,
                        importer_path=rel,
                        lineno=site.lineno,
                        target_mod=site.target_mod,
                        imported_names=site.imported_names,
                        is_dynamic=False,
                    )
                )
        for lineno, target in iter_dynamic_import_targets(path):
            if targets_dev_tooling(target):
                violations.append(
                    DevToolingImportViolation(
                        importer_mod=mod,
                        importer_path=rel,
                        lineno=lineno,
                        target_mod=target,
                        imported_names=[],
                        is_dynamic=True,
                    )
                )
    return sorted(violations, key=lambda v: (v.importer_path, v.lineno, v.target_mod))


# ---------------------------------------------------------------------------
# Violation family 6: shipped module building a path into the unshipped dev tree
# ---------------------------------------------------------------------------

# Leading segments that carry no path identity of their own.
_RELATIVE_MARKERS: Final[frozenset[str]] = frozenset({".", ".."})

# Callables that assemble a filesystem path from separate segment arguments, so
# a bare "dev" argument names the dev directory. `join` is deliberately gated on
# an arity of two or more: `sep.join(iterable)` is a string operation with a
# single argument and must never be read as a path assembly.
_SEGMENT_JOIN_CALLABLES: Final[frozenset[str]] = frozenset({"join"})
_PATH_FACTORY_CALLABLES: Final[frozenset[str]] = frozenset(
    {
        "Path",
        "PurePath",
        "PosixPath",
        "PurePosixPath",
        "WindowsPath",
        "PureWindowsPath",
        "joinpath",
    }
)


class DevPathForm(StrEnum):
    """The syntactic shape a shipped module used to reach into ``dev/``."""

    LITERAL = "literal"
    PATH_JOIN = "path_join"
    CALL_JOIN = "call_join"
    FSTRING = "fstring"


@dataclass
class DevPathReachViolation:
    """A shipped module under ``src/`` that builds a path into the ``dev/`` tree."""

    module_path: str
    lineno: int
    form: DevPathForm
    detail: str


def _posix_segments(value: str) -> list[str]:
    r"""Split ``value`` into path segments on either separator.

    Windows and POSIX separators are folded together so ``"dev\\x.json"`` and
    ``"dev/x.json"`` are the same path to this scanner.
    """
    return value.replace("\\", "/").split("/")


def names_dev_directory(value: str) -> bool:
    """True if ``value`` is a *relative* path whose leading component is ``dev``.

    Segment-aware, never a substring test. Three discriminations carry the
    precision of this whole family:

    * An **absolute** ``/dev/...`` value is a POSIX device node, not the repo
      tree. Shipped code opens ``"/dev/tty"`` to read a secret without echo and
      is correct to do so; firing there would red the gate on sound code and
      teach the next author to weaken it. What actually delivers that silence
      today is the segment-equality rule below, not the ``startswith("/")``
      guard: an absolute value splits to a LEADING EMPTY segment, the
      relative-marker skip advances over ``.`` and ``..`` only, so the scan
      compares ``""`` against ``dev`` and stops. The explicit guard is
      defence-in-depth against exactly one future widening -- folding ``""``
      into the relative-marker skip so ``"/dev/x"`` normalises like
      ``"./dev/x"``, which would otherwise re-open the device-path false
      positive with no test naming it. Keep the guard and the marker set in
      view together; neither is redundant with the other under that change.
    * A segment must **equal** ``dev``. ``devengada``, ``devolucion``,
      ``device`` and ``dev.example.com`` are all near-misses this codebase
      really contains.
    * ``dev`` must be used as a **directory** -- something has to follow it. A
      bare ``"dev"`` string carries no path meaning on its own; it is caught by
      the join forms below, which supply the surrounding path context.

    A value containing a newline is prose (a docstring or a message), never a
    path literal, and is rejected; docstrings are skipped wholesale by
    :func:`_docstring_constant_ids`. A single-line NON-docstring string that
    begins with a dev path -- an assertion message, say -- is still reported.
    That is deliberate: narrowing further (rejecting any value containing a
    space) would let ``"dev/my baseline.json"`` through, and in a hard-zero
    boundary gate an over-fire costs a reword while an under-fire ships a
    broken wheel. A shipped module has no business naming the dev tree even in
    prose.
    """
    if not value or "\n" in value or "\r" in value:
        return False
    normalised = value.replace("\\", "/")
    if normalised.startswith("/"):
        return False
    segments = normalised.split("/")
    index = 0
    while index < len(segments) and segments[index] in _RELATIVE_MARKERS:
        index += 1
    return index + 1 < len(segments) and segments[index] == DEV_TOOLING_ROOT


def _continues_into_dev_directory(text: str) -> bool:
    """True for an f-string tail like ``"/dev/x.json"`` that follows a root interpolation.

    Read only for a constant segment PRECEDED by an interpolation, where the
    leading separator joins onto an interpolated root rather than marking an
    absolute path. That preceding-interpolation requirement is what keeps a
    plain ``f"/dev/null"`` out: with nothing interpolated before it, the value
    is an absolute device path and is judged by :func:`names_dev_directory`.

    The empty leading segment carries the other half: the tail must BEGIN with
    a separator, so ``dev`` sits directly under the interpolated root. A tail
    like ``"-sandbox/dev/notes.json"`` glues the interpolation into its own
    first segment, naming a ``dev`` directory one level below a DIFFERENT tree
    -- not this repository's.
    """
    segments = _posix_segments(text)
    return len(segments) >= 2 and segments[0] == "" and segments[1] == DEV_TOOLING_ROOT


def _is_bare_dev_segment(node: ast.expr) -> bool:
    """True if ``node`` is the string constant ``"dev"``."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == DEV_TOOLING_ROOT


def _divided_dev_segment(node: ast.BinOp) -> str | None:
    """Return a detail string if ``node`` is a ``pathlib`` join onto ``"dev"``.

    Matches ``PROJECT_ROOT / "dev"`` -- the realistic form of this violation,
    since a bare ``open("dev/x.json")`` is CWD-relative and would not survive a
    single test run from outside the repo root. ``PROJECT_ROOT`` is exported
    from ``cadrumo.core.paths``, so a shipped module can anchor a fully working
    dev-tree read this way and break only once installed as a wheel.

    Both operands are checked: ``Path.__rtruediv__`` makes ``"dev" / root`` a
    valid join too. Only the BARE ``"dev"`` segment matches here; a
    ``root / "dev/x.json"`` operand is already a dev path literal and is
    reported once, by :func:`names_dev_directory`, rather than twice.
    """
    if not isinstance(node.op, ast.Div):
        return None
    if _is_bare_dev_segment(node.right) or _is_bare_dev_segment(node.left):
        return f'{ast.unparse(node)!s} (path join onto "{DEV_TOOLING_ROOT}")'
    return None


def _called_function_name(func: ast.expr) -> str | None:
    """Return the trailing callable name of ``func``, or ``None`` if unreadable."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _call_assembled_dev_segment(node: ast.Call) -> str | None:
    """Return a detail string if ``node`` assembles a path from a ``"dev"`` segment.

    Covers ``os.path.join(root, "dev", "x.json")`` and the ``Path(root, "dev")``
    / ``root.joinpath("dev")`` factory forms. ``join`` requires two or more
    arguments so ``"".join(parts)`` -- a string operation, not a path assembly
    -- can never match.
    """
    name = _called_function_name(node.func)
    if name is None:
        return None
    if name in _SEGMENT_JOIN_CALLABLES:
        if len(node.args) < 2:
            return None
    elif name not in _PATH_FACTORY_CALLABLES:
        return None
    if any(_is_bare_dev_segment(arg) for arg in node.args):
        return f'{name}(...) with a "{DEV_TOOLING_ROOT}" path segment'
    return None


def _joined_str_dev_parts(node: ast.JoinedStr) -> list[str]:
    """Return every constant part of an f-string that reaches into ``dev/``.

    An f-string hides the reach from a constant scan: ``f"{root}/dev/x.json"``
    stores the segment as the constant ``"/dev/x.json"``, which starts with a
    separator and matches no ``dev/`` prefix.
    """
    parts: list[str] = []
    interpolated = False
    for part in node.values:
        if isinstance(part, ast.FormattedValue):
            interpolated = True
            continue
        if not isinstance(part, ast.Constant) or not isinstance(part.value, str):
            continue
        text = part.value
        if names_dev_directory(text) or (interpolated and _continues_into_dev_directory(text)):
            parts.append(text)
    return parts


def _docstring_constant_ids(tree: ast.Module) -> set[int]:
    """Return the node ids of every module, class, and function docstring.

    A docstring is documentation, never a runtime path read. Several shipped
    modules legitimately name ``dev/`` tooling in their prose (the terminology
    handbook authoring tool, the corpus extractor), and that prose must not be
    read as a dependency.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


def dev_path_hits(tree: ast.Module) -> list[tuple[int, DevPathForm, str]]:
    """Return every ``(lineno, form, detail)`` dev-tree reach in one parsed module."""
    skip = _docstring_constant_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(id(part) for part in node.values if isinstance(part, ast.Constant))

    hits: list[tuple[int, DevPathForm, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            hits.extend((node.lineno, DevPathForm.FSTRING, text) for text in _joined_str_dev_parts(node))
        elif isinstance(node, ast.BinOp):
            detail = _divided_dev_segment(node)
            if detail is not None:
                hits.append((node.lineno, DevPathForm.PATH_JOIN, detail))
        elif isinstance(node, ast.Call):
            detail = _call_assembled_dev_segment(node)
            if detail is not None:
                hits.append((node.lineno, DevPathForm.CALL_JOIN, detail))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and names_dev_directory(node.value)
        ):
            hits.append((node.lineno, DevPathForm.LITERAL, node.value))
    return hits


def find_dev_path_reach_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[DevPathReachViolation]:
    r"""Return every module under ``src_root`` that builds a ``dev/`` path.

    This is the metadata loophole an import scan alone cannot see: a module
    reading a dev artifact at runtime does not import ``dev.*`` but is just as
    broken for every installed user, because ``dev/`` ships in neither the
    wheel nor the sdist. Family 5 catches the code dependency; this family
    catches the data dependency. Absolute by operator ruling -- every module
    under ``src/``, test trees included, is swept.

    Four forms are detected, because the boundary breaks in all four and a
    scanner covering only the first is a scanner that cannot see the realistic
    case:

    * ``literal`` -- ``"dev/baseline.json"``, ``"./dev/..."``, ``"..\dev\..."``
    * ``path_join`` -- ``PROJECT_ROOT / "dev" / "baseline.json"``
    * ``call_join`` -- ``os.path.join(root, "dev", ...)``, ``Path(root, "dev")``
    * ``fstring`` -- ``f"{root}/dev/baseline.json"``

    **Construction is the trigger, not the read.** A reach is reported where
    the path is BUILT, without requiring an adjacent ``open``/``read_text``
    call. Demanding proof of a read would reopen the hole this family exists to
    close: a module constant assigned once and consumed elsewhere (exactly how
    the real baselines in the excluded test tree are written) would then pass
    while depending on a dev artifact at runtime. No module under ``src/`` has
    a legitimate reason to name the dev tree at all.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve relative paths.
    """
    violations: list[DevPathReachViolation] = []
    for path in py_files:
        rel = path.relative_to(src_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        violations.extend(
            DevPathReachViolation(rel, lineno, form, detail) for lineno, form, detail in dev_path_hits(tree)
        )
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.form, v.detail))


# ---------------------------------------------------------------------------
# Violation family 10: prose awareness of the dev tree under src/
# ---------------------------------------------------------------------------


#: Live top-level names of the dev tree, read from disk at scan time so this
#: family tracks the tree it guards without a maintained list. Only a path or
#: module reference naming a REAL dev child fires -- ``dev.example.com``,
#: ``devengada`` and another tree's ``dev`` directory stay silent.
def _dev_tree_children() -> frozenset[str]:
    """Return the dev tree's current top-level entries, or empty on read failure."""
    try:
        return frozenset(
            entry.name for entry in (REPO_ROOT / DEV_TOOLING_ROOT).iterdir() if not entry.name.startswith(".")
        )
    except OSError:
        return frozenset()


_DEV_TREE_CHILDREN: Final[frozenset[str]] = _dev_tree_children()


def prose_token_names_dev_tree(token: str) -> bool:
    """True if one whitespace-delimited prose token names this repo's dev tree.

    Prose tokens are comment, docstring and multi-line-string words, so the
    same three discriminations as :func:`names_dev_directory` carry the
    precision here: the token must START with ``dev`` (an absolute ``/dev/tty``
    device path and a mid-path ``-sandbox/dev/...`` segment do not), a ``dev``
    must name a REAL top-level child of the dev tree (``dev.example.com`` and
    a bare word ``dev`` do not), and the slash form accepts a trailing ``dev/``
    as a bare folder reference.
    """
    stripped = token.strip("()[]{}`'\"<>,:;")
    if not stripped.startswith(DEV_TOOLING_ROOT):
        return False
    segments = stripped.replace("\\", "/").split("/")
    if len(segments) >= 2:
        return segments[1] in _DEV_TREE_CHILDREN or segments[1] == ""
    dotted = stripped.split(".")
    return len(dotted) >= 2 and dotted[1] in _DEV_TREE_CHILDREN


def _comment_lines(source: str) -> list[tuple[int, str]]:
    """Return every ``(lineno, text)`` COMMENT line in ``source``."""
    lines: list[tuple[int, str]] = []
    try:
        stream = io.StringIO(source).readline
        for tok in tokenize.generate_tokens(stream):
            if tok.type == tokenize.COMMENT:
                lines.append((tok.start[0], tok.string))
    except (tokenize.TokenError, IndentationError, UnicodeDecodeError):
        pass
    return lines


def _prose_string_lines(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` for every docstring and multi-line string line.

    Docstrings are prose by definition and are swept regardless of length --
    the former Family 6 skip made a one-line docstring naming the dev tree
    invisible. A multi-line NON-docstring string is prose too and is swept;
    single-line non-docstring strings stay Family 6's jurisdiction, so no line
    is reported by two families.
    """
    docstring_ids = _docstring_constant_ids(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        is_doc = id(node) in docstring_ids
        if not is_doc and "\n" not in node.value:
            continue
        for offset, line in enumerate(node.value.splitlines()):
            out.append((node.lineno + offset, line))
    return out


@dataclass
class DevProseViolation:
    """A comment, docstring or multi-line string in a src module naming the dev tree."""

    module_path: str
    lineno: int
    source_kind: str  # "comment" | "string"
    detail: str


def find_dev_prose_violations(
    py_files: Iterable[Path],
    *,
    src_root: Path = SRC_ROOT,
) -> list[DevProseViolation]:
    """Return every prose site under ``src_root`` that names the dev tree.

    The awareness half of the boundary, by operator ruling: even a comment or
    docstring naming ``dev/`` is forbidden under ``src/``. The precision rules
    are the same ones the path family documents -- device nodes, near-miss
    Spanish stems, and other trees' ``dev`` directories stay silent.

    Args:
        py_files: Module files to scan.
        src_root: Source root used to resolve relative paths.
    """
    violations: list[DevProseViolation] = []
    for path in py_files:
        rel = path.relative_to(src_root).as_posix()
        try:
            source = path.read_text(encoding=_UTF_8)
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for lineno, text in _prose_string_lines(tree):
            for token in text.split():
                if prose_token_names_dev_tree(token):
                    violations.append(DevProseViolation(rel, lineno, "string", text.strip()))
                    break
        for lineno, text in _comment_lines(source):
            for token in text.split():
                if prose_token_names_dev_tree(token):
                    violations.append(DevProseViolation(rel, lineno, "comment", text.strip()))
                    break
    return sorted(violations, key=lambda v: (v.module_path, v.lineno, v.source_kind))


# ---------------------------------------------------------------------------
# Violation family 7: production import of a demoted registry raw-loader symbol
# ---------------------------------------------------------------------------

REGISTRY_LOADER_PACKAGE: Final[str] = "cadrumo.domain.calculations.registry.loader"
REGISTRY_LOADER_OWNER_PACKAGE: Final[str] = "cadrumo.domain.calculations.registry"

#: Raw-loader-and-unguarded-entry-point names demoted from the registry
#: loader module's public contract (W01.P04.S10 for the four loader names,
#: W01.P04.S34 for ``build_snapshot`` -- the plan's own text calls it "the
#: same unguarded-entry-point class as the raw loader family"). Each had zero
#: cross-package production OR test consumers at demotion time, EXCEPT
#: ``build_snapshot``, whose only external caller at demotion time was a test
#: fixture (confirmed by an AST scan over ``walk_module_imports``, not a text
#: grep -- a multi-line ``from ... import (...)`` block hides a name from a
#: per-line regex, which is exactly how ``collect_registry_tree_fingerprints``
#: was nearly misclassified here). Test callers of a demoted name are never
#: gated below (``site.is_test`` short-circuits); ``build_snapshot`` has since
#: gained more of them, routed through the ``domain.calculations.registry.tests``
#: facade rather than this package directly. The eight raw-loader siblings that stayed
#: exported (``load_registry_tree``, ``load_legal_parameters_only``,
#: ``load_catalogue_file``, ``load_modelo_directory``, ``load_modelo_file``,
#: ``load_modelo_path``, ``clear_fingerprint_cache``,
#: ``collect_registry_tree_fingerprints``) each answer a real external need
#: documented at their call sites -- import-time cycle avoidance for the
#: IRPF/IVA/transactions parameter readers, a deliberate unvalidated-tree read
#: for conformance auditing, or the runtime schema loader's own TTL cache
#: layered atop the canonical fingerprint collector -- and are out of scope
#: for this family; only demoted names are gated.
DEMOTED_REGISTRY_LOADER_SYMBOLS: Final[frozenset[str]] = frozenset(
    {
        "ModeloRevisionSource",
        "ModeloSource",
        "build_snapshot",
        "discover_modelo_sources",
        "load_modelo_source",
    }
)


@dataclass
class RegistryLoaderImportViolation:
    """A production import of a demoted registry raw-loader symbol."""

    importer_mod: str
    importer_path: str
    lineno: int
    imported_names: list[str]


def find_registry_loader_import_violations(
    all_sites: list[ImportSite], *, src_root: Path = SRC_ROOT
) -> list[RegistryLoaderImportViolation]:
    """Return every PRODUCTION import site naming a demoted raw-loader symbol.

    Scoped to non-test sites outside the registry package itself, which still
    reaches its own loader internals directly. The registry package is the
    loader's implementation boundary; other production consumers name the
    public ``authority`` module instead.

    Args:
        all_sites: Import sites to scan, from :func:`walk_module_imports`.
        src_root: Source root ``importer_path`` is resolved relative to;
            injectable so a caller can scan a synthetic tree (matches the
            convention of the other planted-import families in this module).
    """
    violations: list[RegistryLoaderImportViolation] = []
    for site in all_sites:
        if site.is_test:
            continue
        if site.target_mod != REGISTRY_LOADER_PACKAGE:
            continue
        if site.importer_mod == REGISTRY_LOADER_OWNER_PACKAGE or site.importer_mod.startswith(
            REGISTRY_LOADER_OWNER_PACKAGE + "."
        ):
            continue
        hit = [name for name in site.imported_names if name in DEMOTED_REGISTRY_LOADER_SYMBOLS]
        if not hit:
            continue
        try:
            importer_path = str(site.importer_path.relative_to(src_root)).replace("\\", "/")
        except ValueError:
            importer_path = str(site.importer_path).replace("\\", "/")
        violations.append(
            RegistryLoaderImportViolation(
                importer_mod=site.importer_mod,
                importer_path=importer_path,
                lineno=site.lineno,
                imported_names=hit,
            )
        )
    return sorted(violations, key=lambda v: (v.importer_path, v.lineno))


# ---------------------------------------------------------------------------
# Violation family 8: dangling first-party import targets
# ---------------------------------------------------------------------------


FIRST_PARTY_ROOT: Final[str] = "cadrumo"


class DanglingImportKind(StrEnum):
    """Which half of an import edge no longer resolves."""

    MISSING_MODULE = "missing_module"
    MISSING_EXPORT = "missing_export"


@dataclass(frozen=True)
class DanglingImportTarget:
    """One first-party import edge whose target no longer exists.

    The two halves of a deletion that landed without its consumer sweep.
    ``MISSING_MODULE`` is the module itself gone with an importer left behind;
    ``MISSING_EXPORT`` is the module still present but the named symbol dropped
    from it -- the subtler half, and the one that reproduced live on this tree.

    This family exists because the mechanism that already computes the same
    fact tree-wide -- the type checker, over ``src`` with
    ``allowed-unresolved-imports = []`` -- carries hundreds of unrelated
    diagnostics at rest, so one new dangling edge is indistinguishable from the
    standing noise. A family scoped to exactly this rule can hold a clean floor
    and therefore actually bite. It is deliberately NOT a second import
    resolver: it answers one question the whole-tree checker answers too, but
    at a granularity that can be gated at zero.
    """

    importer_mod: str
    importer_path: str
    lineno: int
    target_mod: str
    symbol: str | None
    kind: DanglingImportKind
    is_test: bool


def first_party_module_path(mod: str, *, src_root: Path = SRC_ROOT) -> Path | None:
    """Resolve a dotted first-party module name to its file, or ``None``.

    Returns the package ``__init__.py`` for a package and the plain module
    file otherwise, mirroring the import system's own preference order.
    """
    rel = Path(*mod.split("."))
    package_init = src_root / rel / "__init__.py"
    if package_init.is_file():
        return package_init
    plain = src_root / rel.with_suffix(".py")
    if plain.is_file():
        return plain
    return None


def module_export_surface(path: Path) -> tuple[frozenset[str], bool]:
    """Return every module-level name a module binds, and whether that is complete.

    Completeness is the load-bearing half. A module answering attribute access
    through a PEP 562 ``__getattr__``, or re-exporting through ``from x import
    *``, binds names no AST walk can enumerate, so its surface is reported
    NOT enumerable and :func:`find_dangling_first_party_imports` declines to
    judge any symbol against it. Declining is the only sound answer there: a
    detector that guessed would report every lazily-resolved export as
    dangling.

    The walk is deliberately generous about binding forms -- tuple unpacking
    (``a, b = factory()``), PEP 695 ``type`` aliases, ``for``/``with`` targets,
    walrus bindings, and import aliases all bind a module-level name, and each
    was observed as a false positive before it was handled.
    """
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return frozenset(), False

    names: set[str] = set()
    enumerable = True
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if node.name == "__getattr__":
                enumerable = False
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(sub.id for sub in ast.walk(target) if isinstance(sub, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            names.add(node.name.id)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.NamedExpr)):
            names.update(
                sub.id for sub in ast.walk(node) if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store)
            )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    enumerable = False
                else:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return frozenset(names), enumerable


def _is_first_party(mod: str) -> bool:
    return mod == FIRST_PARTY_ROOT or mod.startswith(FIRST_PARTY_ROOT + ".")


def find_dangling_first_party_imports(
    all_sites: Iterable[ImportSite], *, src_root: Path = SRC_ROOT
) -> list[DanglingImportTarget]:
    """Return every first-party import edge whose target no longer resolves.

    Args:
        all_sites: Import sites to scan, from :func:`walk_module_imports`.
        src_root: Source root the first-party names resolve against;
            injectable so a caller can scan a synthetic tree.
    """
    dangling: list[DanglingImportTarget] = []
    surfaces: dict[str, tuple[frozenset[str], bool]] = {}

    for site in all_sites:
        target = site.target_mod
        if not _is_first_party(target):
            continue
        importer_path = str(site.importer_path).replace("\\", "/")
        target_path = first_party_module_path(target, src_root=src_root)
        if target_path is None:
            dangling.append(
                DanglingImportTarget(
                    importer_mod=site.importer_mod,
                    importer_path=importer_path,
                    lineno=site.lineno,
                    target_mod=target,
                    symbol=None,
                    kind=DanglingImportKind.MISSING_MODULE,
                    is_test=site.is_test,
                )
            )
            continue

        if target not in surfaces:
            surfaces[target] = module_export_surface(target_path)
        surface, enumerable = surfaces[target]
        if not enumerable:
            continue

        is_package = target_path.name == "__init__.py"
        for name in site.imported_names:
            if name == "*" or (name.startswith("__") and name.endswith("__")):
                continue
            if name in surface:
                continue
            # `from package import submodule` binds a module, not a name in
            # the package body; it resolves whenever the submodule file exists.
            if is_package and first_party_module_path(f"{target}.{name}", src_root=src_root) is not None:
                continue
            dangling.append(
                DanglingImportTarget(
                    importer_mod=site.importer_mod,
                    importer_path=importer_path,
                    lineno=site.lineno,
                    target_mod=target,
                    symbol=name,
                    kind=DanglingImportKind.MISSING_EXPORT,
                    is_test=site.is_test,
                )
            )
    return sorted(dangling, key=lambda d: (d.importer_path, d.lineno, d.symbol or ""))


# ---------------------------------------------------------------------------
# Violation family 9: orphaned modules (the other end of the same edge)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrphanedModule:
    """A shipped module nothing in the first-party tree reaches.

    The opposite direction of :class:`DanglingImportTarget`: family 8 finds the
    consumer left behind by a deleted module, family 9 finds the module left
    behind by a deleted consumer. Both are one deletion landing without its
    sweep, and neither is visible to the other's check.

    ``is_reexport_surface`` marks the subset the "no standing non-``__init__``
    re-export bridge modules" rule names directly: a bridge whose last importer
    is gone forwards nothing to nobody, and unlike a module with real
    definitions there is no reading under which it is dormant-but-intended.
    """

    mod: str
    path: str
    is_reexport_surface: bool
    is_test: bool


#: Filenames a running system reaches without any module importing them: a
#: package body, a ``python -m`` entry point, and pytest's own two path-loaded
#: shapes. A zero-importer verdict on these says nothing, so they are excluded
#: by SHAPE rather than by name -- there is no per-module allowlist here.
_NON_IMPORTED_REACH_FILENAMES: Final[frozenset[str]] = frozenset({"__init__.py", "__main__.py", "conftest.py"})


def _string_constants(path: Path) -> set[str]:
    """Return every string constant in a module, for dynamic-reach detection."""
    try:
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


def first_party_census_files(*, repo_root: Path = REPO_ROOT) -> list[tuple[Path, Path]]:
    """Return every first-party ``.py`` file that can reach a shipped module.

    Each entry pairs the file with the source root its own dotted name is
    taken relative to, because the three first-party trees do not share one:
    the package sits under ``src/``, the harness distribution vendors its own
    ``src/`` root, and the development tooling is rooted at the repository.
    Resolving a tree against the wrong root silently mis-resolves its relative
    imports, which drops real reach and manufactures orphans.
    """
    roots = (
        (repo_root / "src" / "cadrumo", repo_root / "src"),
        (repo_root / "src" / "cadrumo-harness" / "src", repo_root / "src" / "cadrumo-harness" / "src"),
        (repo_root / "dev", repo_root),
    )
    census: list[tuple[Path, Path]] = []
    for tree, src_root in roots:
        if not tree.is_dir():
            continue
        census.extend(
            (path, src_root)
            for path in scan_directory(tree, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        )
    return census


def _named_by_any_string(path: Path, mod: str, rel: str, string_pool: Iterable[str]) -> bool:
    """True if some string constant in the tree names this module.

    Four shapes were observed reaching a real module through a string the
    import graph cannot follow, and all four must count or a live module reads
    as orphaned: the full dotted name (a subprocess ``-m`` target), the
    repo-relative path, the relative registration suffix ``.<stem>`` (the lazy
    CLI command table), and the bare filename (a path-assembling probe that
    joins directory parts and ends in ``"<stem>.py"``).

    The bias is deliberate and one-directional. Counting a coincidental string
    as reach costs a missed orphan; MISSING a real reach reports a live module
    as dead, and that is the verdict somebody acts on by deleting it.
    """
    suffix = f".{path.stem}"
    filename = path.name
    return any(
        text in (mod, rel, filename) or text.endswith(suffix) or text.endswith(f"/{filename}") for text in string_pool
    )


def find_orphaned_modules(
    package_files: Iterable[Path],
    census_files: Iterable[tuple[Path, Path]],
    reexport_paths: Iterable[str],
    *,
    repo_root: Path = REPO_ROOT,
    src_root: Path = SRC_ROOT,
) -> list[OrphanedModule]:
    """Return every module under the package that nothing reaches.

    Args:
        package_files: The candidate modules -- the shipped package tree.
        census_files: ``(file, source root)`` pairs for every file that may
            REACH a candidate, from :func:`first_party_census_files`. This
            must span the whole first-party tree, not just the package: a
            module read as orphaned purely because its only importers lived in
            a sibling distribution and the development tooling, and a
            false-orphan verdict is the one failure that would get a live
            module deleted.
        reexport_paths: Repo-relative paths of the pure-re-export modules
            family 2 found, used to mark the bridge subset.
        repo_root: Root the reported paths are relative to.
        src_root: Source root the candidates' dotted names are taken relative
            to; injectable so a caller can scan a synthetic tree.

    A module counts as reached by a static import, by a dynamic
    ``importlib.import_module`` target, or by ANY string constant naming it --
    a lazy CLI command table, a subprocess ``-m`` target and a path-based test
    probe all reach a module through a string the import graph cannot see, and
    each was observed on this tree.
    """
    census = list(census_files)
    reached: set[str] = set()
    string_pool: set[str] = set()

    for path, census_src_root in census:
        for site in walk_module_imports(path, src_root=census_src_root):
            reached.add(site.target_mod)
            for name in site.imported_names:
                reached.add(f"{site.target_mod}.{name}")
        for _lineno, target in iter_dynamic_import_targets(path):
            reached.add(target)
        string_pool |= _string_constants(path)

    bridges = frozenset(reexport_paths)
    orphans: list[OrphanedModule] = []
    for path in package_files:
        if path.name in _NON_IMPORTED_REACH_FILENAMES or path.name.startswith("test_"):
            continue
        mod = module_name_for(path, src_root=src_root)
        if mod in reached:
            continue
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        if _named_by_any_string(path, mod, rel, string_pool):
            continue
        orphans.append(
            OrphanedModule(
                mod=mod,
                path=rel,
                is_reexport_surface=rel in bridges,
                is_test=is_test_module(mod, path),
            )
        )
    return sorted(orphans, key=lambda o: o.path)


# ---------------------------------------------------------------------------
# Violation family 2: shim / pure re-export / alias modules
# ---------------------------------------------------------------------------


@dataclass
class ShimModule:
    """A module flagged as a shim / pure re-export / English-alias surface.

    ``is_test`` mirrors :attr:`ImportSite.is_test`: the scanner still WALKS the
    test tree (unlike an early `continue` on :func:`is_test_module`, which would
    make the family's reach silently narrower than the codebase-wide "no
    standing non-``__init__`` re-export bridge modules" rule it is named for),
    but the strict Family-2 baseline equality gate governs the production
    (``is_test=False``) subset only -- the same split Family 1 already applies
    to :attr:`ImportSite.is_test`. A test-tree bridge is reported as its own
    named category rather than silently absent from every count.
    """

    mod: str
    path: str
    reason: str
    detail: str
    is_test: bool


SPANISH_ALIAS_HINTS = {
    "vat": "iva",
    "census": "censo",
    "form": "modelo",
    "receipt": "justificante",
    "box": "casilla",
    "invoice_draft": "borrador",
    "authorization": "apoderamiento",
    "withholding": "retencion",
    "filing": "declaracion",
}


def _flatten_module_level_branches(stmts: list[ast.stmt]) -> Iterable[ast.stmt]:
    """Yield ``stmts``, replacing each ``If``/``Try`` with its own branch contents.

    An optional-dependency fallback (``try: import real / except ImportError:
    class Fallback: ...``), a ``TYPE_CHECKING`` split, or a platform/feature
    branch all place real module-level statements one level below
    ``tree.body`` -- exactly the shape :mod:`adapters.outbound.aeat._playwright`
    uses to define fallback exception classes only when the optional
    ``browser`` extra is absent. A def-counting walk that stops at
    ``tree.body`` never reaches them, so a module built entirely from such a
    branch counts as zero real defs and misclassifies as a pure re-export
    shim.

    Recurses through ``If.body``/``If.orelse`` and ``Try.body``/
    ``Try.handlers[*].body``/``Try.orelse``/``Try.finalbody``, arbitrarily
    nested (an ``if`` inside a ``try`` inside an ``if``, as in the real
    ``_playwright.py`` shape). Does NOT descend into a ``FunctionDef``/
    ``AsyncFunctionDef``/``ClassDef`` body -- those are counted as one real
    def each by the caller and their own internals are not module-level
    surface.
    """
    for node in stmts:
        if isinstance(node, ast.If):
            yield from _flatten_module_level_branches(node.body)
            yield from _flatten_module_level_branches(node.orelse)
        elif isinstance(node, ast.Try):
            yield from _flatten_module_level_branches(node.body)
            for handler in node.handlers:
                yield from _flatten_module_level_branches(handler.body)
            yield from _flatten_module_level_branches(node.orelse)
            yield from _flatten_module_level_branches(node.finalbody)
        else:
            yield node


def module_body_defs(tree: ast.Module) -> tuple[int, int, int]:
    """Return (n_imports_stmts, n_real_defs, n_all_assigns).

    ``__future__`` imports are excluded from the import count (every module
    may carry one; it is not "re-export" signal). Annotated assignments
    (``NAME: Type = value``, e.g. a module-level typed constant/data record)
    count as real defs, same as a plain ``Assign``, a PEP 695 ``TypeAlias``,
    a function, or a class --
    UNLESS the value is a bare ``Name`` reference (``Foo = _internal.Foo`` /
    ``Foo = Foo``), which is itself a re-export alias, not a real definition.

    The walk looks inside module-level ``if``/``try`` branches (see
    :func:`_flatten_module_level_branches`) so a symbol defined only under a
    ``TYPE_CHECKING`` split or an optional-dependency fallback still counts;
    what counts as a real def there is identical to the top level -- the
    bare-alias exclusion applies the same way inside a branch as outside one.
    """
    n_imports = 0
    n_defs = 0
    n_all = 0
    for node in _flatten_module_level_branches(tree.body):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            n_imports += 1
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            n_all += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.TypeAlias)):
            n_defs += 1
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue  # docstring
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, (ast.Name, ast.Attribute)):
                # Bare re-export alias (Foo = Bar / Foo = mod.Bar); not a
                # real definition.
                continue
            n_defs += 1
    return n_imports, n_defs, n_all


def find_shim_modules(py_files: list[Path], facades: dict[str, FacadeInfo]) -> list[ShimModule]:
    """Return modules whose shape or naming marks them as shim / alias surfaces."""
    shims: list[ShimModule] = []
    for path in py_files:
        if path.name == "__init__.py":
            continue  # __init__ facades are expected to be import+__all__
        if path.name == "__main__.py":
            # Entry-point module: `from .cli import app` + `if __name__ ==
            # "__main__": app()` is the standard `python -m pkg` pattern, not
            # a Family-2 shim/pure-reexport surface.
            continue
        try:
            src = path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        mod = module_name_for(path)
        test_flag = is_test_module(mod, path)

        n_imports, n_defs, n_all = module_body_defs(tree)

        # Pure re-export shape: only imports (+ optional __all__), zero
        # real function/class definitions, and at least one import. Walked
        # for the test tree too (never skipped): a test-only bridge is a
        # different policy question from a production one, but it must be
        # counted, not silently invisible to this family's reach.
        if n_imports > 0 and n_defs == 0:
            shims.append(
                ShimModule(
                    mod=mod,
                    path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                    reason="pure_reexport_shape",
                    detail=f"{n_imports} import stmt(s), 0 real defs, __all__={'yes' if n_all else 'no'}",
                    is_test=test_flag,
                )
            )

        # English-alias-over-Spanish-stem heuristic: module basename contains
        # an English hint token and the sibling directory also contains a
        # same-shaped Spanish-stem module.
        base = path.stem.lstrip("_")
        for en_hint, es_stem in SPANISH_ALIAS_HINTS.items():
            if en_hint in base.lower() and es_stem not in base.lower():
                sibling_es = path.with_name(path.name.replace(en_hint, es_stem))
                if sibling_es.exists() and sibling_es != path:
                    shims.append(
                        ShimModule(
                            mod=mod,
                            path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                            reason="english_alias_over_spanish_stem",
                            detail=f"hint='{en_hint}' sibling='{sibling_es.relative_to(REPO_ROOT)}'",
                            is_test=test_flag,
                        )
                    )

        # Compat/deprecation naming heuristic.
        lowered = mod.lower()
        for marker in ("_compat", "_legacy", "_deprecated", "_shim", "_bridge"):
            if marker in lowered:
                shims.append(
                    ShimModule(
                        mod=mod,
                        path=str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                        reason="compat_naming_marker",
                        detail=f"marker='{marker}'",
                        is_test=test_flag,
                    )
                )
    return shims


# ---------------------------------------------------------------------------
# Violation family 2b: forwarding layers written as wrapper DEFINITIONS
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DelegateWrapper:
    """One public callable whose entire body forwards to another package.

    The second syntax of the same rule :class:`ShimModule` enforces. A
    forwarding layer written as import aliases has zero real definitions and
    :func:`module_body_defs` sees it; a forwarding layer written as
    ``def foo(a, *, b): return _real_foo(a, b=b)`` evades that test BY
    CONSTRUCTION, because a module full of wrapper definitions has plenty of
    real definitions and a def-counting check always answers "yes, this module
    defines its own things".

    ``is_test`` mirrors :attr:`ShimModule.is_test`: the test tree is walked and
    tagged, never skipped, but the production policy governs the
    ``is_test=False`` subset.
    """

    mod: str
    path: str
    function: str
    lineno: int
    target_mod: str
    target: str
    is_test: bool


# staticmethod/classmethod only rebind how the callable receives its first
# argument; they leave WHAT the call does untouched, so a forwarding body under
# one is still a forwarding body. Every other decorator gives the callable a
# role beyond forwarding -- a pydantic ``field_validator``/``field_serializer``
# hook, a ``property``, a cache, a Typer command registration -- and a body that
# delegates to the canonical implementation is then exactly what the
# centralisation policy asks for, not a bridge around it.
_BINDING_ONLY_DECORATORS: Final[frozenset[str]] = frozenset({"staticmethod", "classmethod"})


def _decorator_root_name(node: ast.expr) -> str:
    current: ast.expr = node
    if isinstance(current, ast.Call):
        current = current.func
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def _carries_role_decorator(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if any decorator gives the callable a role beyond plain forwarding."""
    return any(_decorator_root_name(node) not in _BINDING_ONLY_DECORATORS for node in fn.decorator_list)


def module_import_bindings(tree: ast.Module, mod: str, *, is_package: bool) -> dict[str, str]:
    """Map each module-level import binding to the module it was imported FROM.

    ``from ..storage import custody`` binds ``custody`` to
    ``cadrumo.adapters.persistence.storage`` -- the module the name came from,
    not the name's own dotted path -- because that is the package whose surface
    a wrapper around ``custody.<anything>`` reaches into.

    A binding made under ``if TYPE_CHECKING:`` still counts, on the same
    reading the cross-package private-import family already applies: the
    ownership rule governs WHERE a symbol lives, never WHEN its module
    executes, so deferring an import to type-check time does not change which
    package owns the name. A runtime binding of the same name WINS, though --
    a module that imports a symbol for real and re-imports it under the guard
    for typing reaches the runtime one, and that is the package the wrapper
    actually forwards into.
    """
    guarded = type_checking_guarded_nodes(tree)
    runtime: dict[str, str] = {}
    type_only: dict[str, str] = {}
    for node in ast.walk(tree):
        sink = type_only if id(node) in guarded else runtime
        if isinstance(node, ast.ImportFrom):
            target = resolve_relative_import(mod, is_package, node.level, node.module)
            if not target:
                continue
            for alias in node.names:
                sink[alias.asname or alias.name] = target
        elif isinstance(node, ast.Import):
            for alias in node.names:
                sink[alias.asname or alias.name.split(".", 1)[0]] = alias.name
    return {**type_only, **runtime}


def iter_module_level_callables(tree: ast.Module) -> Iterable[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Yield ``(qualname, node)`` for every module-level function and method.

    Walks through module-level ``if``/``try`` branches via
    :func:`_flatten_module_level_branches`, so a wrapper defined only under a
    platform or optional-dependency branch is still reached.
    """
    for node in _flatten_module_level_branches(tree.body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for member in _flatten_module_level_branches(node.body):
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{member.name}", member


def sole_forwarded_call(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    """Return the one call a body consists of, or ``None`` if it does more.

    The body must be exactly one statement after its docstring, and that
    statement must return the call's value unchanged or discard it (a void
    forward). Anything that wraps, unpacks, compares, or branches on the result
    is a real definition, not a forward.
    """
    body = list(fn.body)
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        body = body[1:]
    if len(body) != 1:
        return None
    statement = body[0]
    if isinstance(statement, (ast.Return, ast.Expr)):
        value = statement.value
    else:
        return None
    if isinstance(value, ast.Await):
        value = value.value
    return value if isinstance(value, ast.Call) else None


def forwards_own_parameters_only(call: ast.Call, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if every argument is a bare reference to one of ``fn``'s parameters.

    This is the line between a forwarding wrapper and a translating adapter.
    An adapter changes something observable at the boundary: it converts a
    handle, supplies an argument the caller never gave, reshapes a value on the
    way in. Each of those makes an argument something other than a bare
    parameter name, and each is a real decision the wrapper owns. A wrapper
    whose every argument is a bare parameter reference owns no decision at all:
    same values in, same value out, and its only effect is to move the import
    site. That is an import alias written with ``def``.

    A keyword may be RELABELLED (``subject=`` forwarded as ``field_name=``) and
    the call is still a forward: relabelling an argument is not translating it.
    """
    arguments = fn.args
    parameters = {parameter.arg for parameter in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)} - {
        "self",
        "cls",
    }
    if arguments.vararg:
        parameters.add(arguments.vararg.arg)
    if arguments.kwarg:
        parameters.add(arguments.kwarg.arg)

    passed: list[ast.expr] = []
    for positional in call.args:
        passed.append(positional.value if isinstance(positional, ast.Starred) else positional)
    passed.extend(keyword.value for keyword in call.keywords)
    return all(isinstance(node, ast.Name) and node.id in parameters for node in passed)


def find_delegate_wrapper_shims(py_files: list[Path], *, src_root: Path = SRC_ROOT) -> list[DelegateWrapper]:
    """Return every public callable that only re-calls another package's symbol.

    Four conditions, all required, each drawing part of the line between a
    forwarding wrapper and a legitimate module:

    - The callable is PUBLIC by name. A private ``_helper`` is module-local
      shorthand, not a standing bridge -- nothing outside the module may import
      it without tripping the cross-package private-import family.
    - It carries no role decorator (see :func:`_carries_role_decorator`).
    - Its body is one call whose value is returned unchanged or discarded (see
      :func:`sole_forwarded_call`).
    - Every argument is a bare reference to one of its own parameters (see
      :func:`forwards_own_parameters_only`), and the callee resolves through a
      module-level import to a first-party package that is NOT the wrapper's
      own. A package facade assembling its own surface from its own private
      modules therefore never appears here, which is the shape the policy
      explicitly permits.

    Args:
        py_files: Module files to scan.
        src_root: Source root module names and reported paths resolve against;
            injectable so a caller can scan a synthetic tree, matching the
            convention of the other families in this module.
    """

    def reported_path(path: Path) -> str:
        try:
            relative = path.relative_to(REPO_ROOT)
        except ValueError:
            relative = path.relative_to(src_root.parent)
        return str(relative).replace("\\", "/")

    wrappers: list[DelegateWrapper] = []
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        mod = module_name_for(path, src_root=src_root)
        bindings = module_import_bindings(tree, mod, is_package=path.name == "__init__.py")
        test_flag = is_test_module(mod, path)

        for qualname, fn in iter_module_level_callables(tree):
            if is_underscore_named(fn.name) or _carries_role_decorator(fn):
                continue
            call = sole_forwarded_call(fn)
            if call is None or not forwards_own_parameters_only(call, fn):
                continue
            target = _expression_reference(call.func, {})
            if target is None:
                continue
            root = target.split(".", 1)[0]
            target_mod = bindings.get(root)
            if target_mod is None or target_mod.split(".", 1)[0] != PKG_ROOT.name:
                continue
            owner = owning_package(target_mod)
            if mod == owner or mod.startswith(owner + "."):
                continue
            wrappers.append(
                DelegateWrapper(
                    mod=mod,
                    path=reported_path(path),
                    function=qualname,
                    lineno=fn.lineno,
                    target_mod=target_mod,
                    target=target,
                    is_test=test_flag,
                )
            )
    return sorted(wrappers, key=lambda w: (w.path, w.function))


# ---------------------------------------------------------------------------
# Violation family 3: redundant re-exports (symbol in >1 __all__, or
# imported from both a private submodule and a facade across the codebase)
# ---------------------------------------------------------------------------


@dataclass
class MultiSourcedSymbol:
    """A symbol exported / consumed from more than one module surface."""

    symbol: str
    facades: list[str]
    private_sources: list[str]
    consumed_from_facade_by: list[str]
    consumed_from_private_by: list[str]
    confidence: str = "high"  # "high" (same resolved origin) | "name_collision" (different origins; likely unrelated)


def _facade_export_origins(facades: dict[str, FacadeInfo]) -> dict[str, dict[str, set[str]]]:
    """Resolve each facade's ``__all__`` name to its absolute origin module(s).

    Best-effort: only direct ``from X import Name [as Alias]`` statements in the
    ``__init__`` body are resolved; a name built by other means is simply absent
    from this map.
    """
    origins: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for pkg, info in facades.items():
        if not info.has_real_all:
            continue
        try:
            src = info.path.read_text(encoding=_UTF_8)
            tree = ast.parse(src, filename=str(info.path))
        except (FileNotFoundError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = resolve_relative_import(pkg, True, node.level, node.module)
                if not target:
                    continue
                for alias in node.names:
                    exported_as = alias.asname or alias.name
                    if exported_as in info.all_names:
                        origins[pkg][exported_as].add(target)
    return origins


def find_multi_sourced_symbols(facades: dict[str, FacadeInfo], all_sites: list[ImportSite]) -> list[MultiSourcedSymbol]:
    """Return symbols reachable from more than one facade / private surface."""
    # Map symbol -> set of facades whose __all__ contains it.
    symbol_to_facades: dict[str, set[str]] = defaultdict(set)
    for pkg, info in facades.items():
        if not info.has_real_all:
            continue
        for name in info.all_names:
            symbol_to_facades[name].add(pkg)

    facade_export_origins = _facade_export_origins(facades)

    # Map symbol -> set of private modules it's imported FROM (target private
    # module -> imported name), restricted to cadrumo.* targets.
    symbol_private_sources: dict[str, set[str]] = defaultdict(set)
    symbol_facade_consumers: dict[str, set[str]] = defaultdict(set)
    symbol_private_consumers: dict[str, set[str]] = defaultdict(set)

    facade_targets = {pkg for pkg, info in facades.items() if info.has_real_all}

    for site in all_sites:
        if not site.target_mod.startswith("cadrumo"):
            continue
        for name in site.imported_names:
            if name == "*":
                continue
            if has_private_component(site.target_mod):
                symbol_private_sources[name].add(site.target_mod)
                symbol_private_consumers[name].add(site.importer_mod)
            elif site.target_mod in facade_targets:
                symbol_facade_consumers[name].add(site.importer_mod)

    results: list[MultiSourcedSymbol] = []

    def _is_ancestor_or_descendant(a: str, b: str) -> bool:
        return a == b or a.startswith(b + ".") or b.startswith(a + ".")

    # Case A: symbol declared __all__ in more than one facade package. Split
    # by confidence: "hierarchical_rollup" when every pair of declaring
    # facades is in a parent/child (umbrella aggregator) relationship -- this
    # codebase's umbrella packages (e.g. `cadrumo.adapters.persistence.storage`
    # over its `.envelope` / `.bucket` / `.crypto` sub-facades,
    # `cadrumo.core.errors` over `.registry`) deliberately roll up child-facade
    # symbols into a parent convenience facade, which is NOT the violation
    # this family targets; "high" when at least two declaring facades are
    # NOT in an ancestor/descendant relationship AND resolve the name to the
    # SAME underlying origin module (genuine structural duplication across
    # orthogonal packages); "name_collision" when every non-hierarchical pair
    # resolves to different origins (near-certainly two unrelated symbols
    # sharing a name, e.g. two domains each defining their own `Settings`).
    for symbol, pkgs in symbol_to_facades.items():
        if len(pkgs) <= 1:
            continue
        pkg_list = sorted(pkgs)
        all_hierarchical = all(
            _is_ancestor_or_descendant(pkg_list[i], pkg_list[j])
            for i in range(len(pkg_list))
            for j in range(i + 1, len(pkg_list))
        )
        origin_sets = [facade_export_origins.get(pkg, {}).get(symbol, set()) for pkg in pkgs]
        origin_counts: Counter[str] = Counter()
        for s in origin_sets:
            for o in s:
                origin_counts[o] += 1
        shared_origin = any(c > 1 for c in origin_counts.values())
        if all_hierarchical:
            confidence = "hierarchical_rollup"
        elif shared_origin:
            confidence = "high"
        else:
            confidence = "name_collision"
        results.append(
            MultiSourcedSymbol(
                symbol=symbol,
                facades=pkg_list,
                private_sources=sorted(symbol_private_sources.get(symbol, [])),
                consumed_from_facade_by=sorted(symbol_facade_consumers.get(symbol, [])),
                consumed_from_private_by=sorted(symbol_private_consumers.get(symbol, [])),
                confidence=confidence,
            )
        )

    # Case B: symbol importable from a facade AND actually imported from a
    # private submodule by real consumers elsewhere (not the owning facade
    # building itself) AND also imported from the facade by some consumer.
    for symbol, priv_mods in symbol_private_sources.items():
        facade_consumers = symbol_facade_consumers.get(symbol, set())
        priv_consumers = symbol_private_consumers.get(symbol, set())
        # Only interesting if the symbol also appears in >=1 facade __all__
        # and is genuinely consumed (not just declared) from both shapes.
        if symbol in symbol_to_facades and facade_consumers and priv_consumers:
            # Exclude consumers that are simply the owning package building
            # its own facade (those are legitimate, not redundant); a
            # private-module consumer that lives INSIDE the owner is fine,
            # only flag if some consumer is outside the owning package.
            owners = {owning_package(p) for p in priv_mods}
            outside_priv_consumers = set()
            for c in priv_consumers:
                if not any(c == own or c.startswith(own + ".") for own in owners):
                    outside_priv_consumers.add(c)
            if outside_priv_consumers and facade_consumers:
                existing = next((r for r in results if r.symbol == symbol), None)
                if existing is None:
                    results.append(
                        MultiSourcedSymbol(
                            symbol=symbol,
                            facades=sorted(symbol_to_facades[symbol]),
                            private_sources=sorted(priv_mods),
                            consumed_from_facade_by=sorted(facade_consumers),
                            consumed_from_private_by=sorted(outside_priv_consumers),
                            confidence="high",
                        )
                    )
    return results


# ---------------------------------------------------------------------------
# Fix-strategy analysis: precondition promotions vs. simple consumer rewrites
# ---------------------------------------------------------------------------


@dataclass
class FixClassification:
    """Whether a cross-package symbol needs facade promotion or a consumer rewrite."""

    owning_package: str
    symbol: str
    already_in_facade: bool
    consumer_count: int
    consumer_modules: list[str]


def classify_fix_strategy(
    priv_violations: list[PrivateImportViolation], facades: dict[str, FacadeInfo]
) -> list[FixClassification]:
    """Classify each cross-package (owning_package, symbol) pair by fix strategy.

    A symbol already present in the owning package's ``__all__`` is a simple
    consumer-side rewrite; an absent one is a precondition facade promotion that
    must land before consumers can switch.
    """
    pair_consumers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for v in priv_violations:
        if v.is_test:
            continue  # precondition sizing is driven by production consumers
        for name in v.imported_names:
            if name == "*":
                continue
            pair_consumers[(v.owning_package, name)].add(v.importer_mod)

    results: list[FixClassification] = []
    for (owner, symbol), consumers in pair_consumers.items():
        facade_info = facades.get(owner)
        already = bool(facade_info and facade_info.has_real_all and symbol in facade_info.all_names)
        results.append(
            FixClassification(
                owning_package=owner,
                symbol=symbol,
                already_in_facade=already,
                consumer_count=len(consumers),
                consumer_modules=sorted(consumers),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Retired TUI fixed point
# ---------------------------------------------------------------------------


class TuiRetirementScanError(RuntimeError):
    """A fixed-point input could not be read or parsed."""


def _parse_tui_retirement_input(path: Path, *, repo_root: Path) -> ast.Module:
    """Parse one fixed-point input without silently dropping unreadable code."""
    try:
        return ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        try:
            locator = path.relative_to(repo_root).as_posix()
        except ValueError:
            locator = path.as_posix()
        raise TuiRetirementScanError(
            f"cannot parse TUI retirement fixed-point input {locator}: {type(error).__name__}"
        ) from error


def _retired_tui_string_references(
    tree: ast.Module,
    *,
    is_detector_module: bool = False,
) -> tuple[tuple[int, str], ...]:
    """Return every dotted or repository-path retired-TUI reference in Python strings."""
    detector_declaration_values = {
        id(node.value)
        for node in tree.body
        if is_detector_module
        and isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "RETIRED_TUI_PACKAGE"
        and isinstance(node.value, ast.Constant)
        and node.value.value == RETIRED_TUI_PACKAGE
    }
    retired_path = RETIRED_TUI_ROOT.relative_to(REPO_ROOT).as_posix()
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            id(node) in detector_declaration_values
            or not isinstance(node, ast.Constant)
            or not isinstance(node.value, str)
        ):
            continue
        normalized = node.value.replace("\\", "/")
        for prefix in (RETIRED_TUI_PACKAGE, retired_path):
            offset = 0
            while (start := normalized.find(prefix, offset)) >= 0:
                end = start + len(prefix)
                before = normalized[start - 1] if start else ""
                after = normalized[end : end + 1]
                if (not before or not (before.isalnum() or before in "._")) and (
                    not after or not (after.isalnum() or after == "_")
                ):
                    target = prefix
                    suffix = normalized[end:]
                    if prefix == RETIRED_TUI_PACKAGE and suffix.startswith("."):
                        parts = [part for part in suffix[1:].split(".") if part.isidentifier()]
                        target = ".".join((RETIRED_TUI_PACKAGE, *parts)) if parts else RETIRED_TUI_PACKAGE
                    locator_line = node.lineno + normalized[:start].count("\n")
                    found.append((locator_line, target))
                offset = end
    return tuple(sorted(found))


def find_retired_tui_remnants(
    *,
    repo_root: Path = REPO_ROOT,
    src_root: Path = SRC_ROOT,
    package_root: Path = PKG_ROOT,
    retired_root: Path = RETIRED_TUI_ROOT,
    development_root: Path | None = None,
    detector_path: Path | None = None,
) -> tuple[TuiRetirementRemnant, ...]:
    """Derive the zero-remnant fixed point from live modules and consumer syntax.

    There is no historic census to ratchet: the retired package, every direct
    import, and every qualified string reference must be absent from the current
    source tree. Parsing every candidate fails closed so malformed source cannot
    make a remnant disappear from the proof.
    """
    remnants: list[TuiRetirementRemnant] = []
    development_root = repo_root / "dev" if development_root is None else development_root
    detector_path = _DETECTOR_PATH if detector_path is None else detector_path

    if retired_root.is_dir():
        for path in scan_directory(retired_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",)):
            remnants.append(
                TuiRetirementRemnant(
                    kind=TuiRetirementRemnantKind.MODULE,
                    importer_mod=module_name_for(path, src_root=src_root),
                    importer_path=path.relative_to(repo_root).as_posix(),
                    lineno=1,
                    target=module_name_for(path, src_root=src_root),
                )
            )

    source_files = (
        scan_directory(package_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        if package_root.is_dir()
        else []
    )
    development_files = (
        scan_directory(development_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",))
        if development_root.is_dir()
        else []
    )
    for path in (*source_files, *development_files):
        scan_root = src_root if src_root in path.parents else repo_root
        tree = _parse_tui_retirement_input(path, repo_root=repo_root)
        importer = module_name_for(path, src_root=scan_root)
        relative = path.relative_to(repo_root).as_posix()
        for site in walk_module_imports(path, src_root=scan_root):
            if _targets_module(site.target_mod, RETIRED_TUI_PACKAGE):
                remnants.append(
                    TuiRetirementRemnant(
                        kind=TuiRetirementRemnantKind.IMPORT,
                        importer_mod=importer,
                        importer_path=relative,
                        lineno=site.lineno,
                        target=site.target_mod,
                    )
                )
        for lineno, target in _retired_tui_string_references(tree, is_detector_module=path.resolve() == detector_path):
            remnants.append(
                TuiRetirementRemnant(
                    kind=TuiRetirementRemnantKind.REFERENCE,
                    importer_mod=importer,
                    importer_path=relative,
                    lineno=lineno,
                    target=target,
                )
            )

    return tuple(sorted(remnants, key=lambda item: (item.importer_path, item.lineno, item.kind, item.target)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Scan ``src/cadrumo`` and print the import-hygiene inventory report."""
    # Prose violations carry arbitrary source text (Spanish prose, en-dashes);
    # a cp1252 console would crash printing them.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Write full inventory as JSON to this path")
    parser.add_argument("--top", type=int, default=20, help="Top-N offender modules to print")
    args = parser.parse_args()

    py_files = list(scan_directory(PKG_ROOT, pattern="*.py", recursive=True, prune_directories=("__pycache__",)))

    # The dev-boundary families sweep every module under src/, the harness
    # distribution included, while the import-hygiene census proper stays
    # scoped to the cadrumo package whose module names it resolves.
    harness_root = SRC_ROOT / "cadrumo-harness" / "src"
    dev_boundary_files = list(py_files)
    if harness_root.is_dir():
        dev_boundary_files += scan_directory(
            harness_root, pattern="*.py", recursive=True, prune_directories=("__pycache__",)
        )

    facades = discover_facades()
    real_facades = {pkg: info for pkg, info in facades.items() if info.has_real_all}

    all_sites: list[ImportSite] = []
    for path in py_files:
        all_sites.extend(walk_module_imports(path))

    priv_violations = find_private_import_violations(all_sites)
    shims = find_shim_modules(py_files, facades)
    delegate_wrappers = find_delegate_wrapper_shims(py_files)
    multi_sourced = find_multi_sourced_symbols(facades, all_sites)
    fix_classes = classify_fix_strategy(priv_violations, facades)
    underscore_in_all = find_underscore_in_all_violations(facades)
    dev_tooling_imports = find_dev_tooling_import_violations(dev_boundary_files)
    dev_path_reaches = find_dev_path_reach_violations(dev_boundary_files)
    dev_prose_violations = find_dev_prose_violations(dev_boundary_files)
    registry_loader_imports = find_registry_loader_import_violations(all_sites)
    dangling_imports = find_dangling_first_party_imports(all_sites)
    orphaned_modules = find_orphaned_modules(
        py_files,
        first_party_census_files(),
        (s.path for s in shims if s.reason == "pure_reexport_shape"),
    )
    retired_tui_remnants = find_retired_tui_remnants()

    # ---- Reporting ----
    print(f"Scanned {len(py_files)} .py files under {PKG_ROOT}")
    print(f"Dev-boundary sweep covers {len(dev_boundary_files)} files (cadrumo + harness distribution)")
    print(f"Discovered {len(facades)} __init__.py files; {len(real_facades)} carry a real, non-empty __all__.")
    print()
    print("=== FACADE BOUNDARY SET (packages with real __all__) ===")
    for pkg in sorted(real_facades):
        print(f"  {pkg}  ({len(real_facades[pkg].all_names)} exported names)")
    print()

    print(f"=== FAMILY 1: cross-package private imports: {len(priv_violations)} total ===")
    non_test = [v for v in priv_violations if not v.is_test]
    test_only = [v for v in priv_violations if v.is_test]
    print(f"  non-test: {len(non_test)}   test-only: {len(test_only)}")
    by_owner = Counter(v.owning_package for v in priv_violations)
    print("  by owning package (target):")
    for owner, cnt in by_owner.most_common(30):
        print(f"    {cnt:4d}  {owner}")
    print()
    by_target_mod = Counter(v.target_mod for v in priv_violations)
    print(f"  top {args.top} offender private target modules:")
    for mod, cnt in by_target_mod.most_common(args.top):
        print(f"    {cnt:4d}  {mod}")
    print()
    by_importer_area = Counter(".".join(v.importer_mod.split(".")[:3]) for v in priv_violations)
    print("  by importer area (top-3 dotted segments):")
    for area, cnt in by_importer_area.most_common(30):
        print(f"    {cnt:4d}  {area}")
    print()

    print(f"=== FAMILY 2: shim/alias/pure-reexport modules: {len(shims)} total ===")
    shims_non_test = [s for s in shims if not s.is_test]
    shims_test = [s for s in shims if s.is_test]
    print(f"  production: {len(shims_non_test)}   test-tree: {len(shims_test)}")
    by_reason = Counter(s.reason for s in shims)
    for reason, cnt in by_reason.most_common():
        print(f"  {cnt:4d}  {reason}")
    print()
    for s in shims:
        print(f"  [{'test' if s.is_test else 'prod'}][{s.reason}] {s.path} :: {s.detail}")
    print()

    print(f"=== FAMILY 2b: forwarding wrappers (the same rule, written as defs): {len(delegate_wrappers)} total ===")
    wrappers_non_test = [w for w in delegate_wrappers if not w.is_test]
    print(f"  production: {len(wrappers_non_test)}   test-tree: {len(delegate_wrappers) - len(wrappers_non_test)}")
    print("  (a public callable whose whole body re-calls another package's symbol with its own")
    print("   arguments unchanged; it owns no decision, so it is an import alias written with def)")
    for w in delegate_wrappers:
        print(f"  [{'test' if w.is_test else 'prod'}] {w.path}:{w.lineno} {w.function} -> {w.target} [{w.target_mod}]")
    print()

    by_confidence = Counter(m.confidence for m in multi_sourced)
    print(f"=== FAMILY 3: redundant / multi-sourced symbols: {len(multi_sourced)} total ===")
    print(f"  by confidence: {dict(by_confidence)}")
    print("  (name_collision = same name, different resolved origin -- likely unrelated symbols, LOW priority)")
    print("  (hierarchical_rollup = umbrella parent facade re-exporting a child facade's symbol -- NOT a violation)")
    print()
    _order = {"high": 0, "name_collision": 1, "hierarchical_rollup": 2}
    for m in sorted(multi_sourced, key=lambda x: (_order.get(x.confidence, 9), x.symbol)):
        print(f"  [{m.confidence}] {m.symbol}")
        print(f"    facades: {m.facades}")
        print(f"    private_sources: {m.private_sources}")
        print(f"    consumed_from_facade_by: {len(m.consumed_from_facade_by)} sites")
        print(
            f"    consumed_from_private_by: {len(m.consumed_from_private_by)} sites -> {m.consumed_from_private_by[:5]}"
        )
    print()

    print(f"=== FAMILY 4: underscore-named entries in __all__: {len(underscore_in_all)} total ===")
    print("  (a public facade exporting a private-named symbol; every hit needs a per-symbol disposition:")
    print("   rename to a public name and sweep consumers, or drop it from __all__)")
    by_underscore_owner = Counter(v.package for v in underscore_in_all)
    for owner, cnt in by_underscore_owner.most_common():
        print(f"    {cnt:4d}  {owner}")
    print()
    for v in sorted(underscore_in_all, key=lambda x: (x.package, x.name)):
        print(f"  [{v.package}] {v.name}  ({v.path})")
    print()

    print(f"=== FAMILY 5: src modules importing the dev tooling: {len(dev_tooling_imports)} total ===")
    print("  (absolute boundary: no module under src/ -- shipped or test -- may import dev/")
    print("   a test needing dev tooling lives under dev/ itself)")
    for v in dev_tooling_imports:
        kind = "dynamic" if v.is_dynamic else "static"
        print(f"  [{kind}] {v.importer_path}:{v.lineno} -> {v.target_mod}")
    print()

    print(f"=== FAMILY 6: src modules building a path into the dev tree: {len(dev_path_reaches)} total ===")
    print("  (the metadata half of the same boundary: no import statement, but the module still")
    print("   names a path into dev/; move the artifact under src/cadrumo/_data/ or the test to dev/)")
    for reach in dev_path_reaches:
        print(f"  [{reach.form}] {reach.module_path}:{reach.lineno} -> {reach.detail!r}")
    print()

    print(f"=== FAMILY 10: prose naming the dev tree under src/: {len(dev_prose_violations)} total ===")
    print("  (comments, docstrings and multi-line strings: awareness is forbidden even where")
    print("   no code path reads the tree; reword to neutral prose)")
    for v in dev_prose_violations:
        print(f"  [{v.source_kind}] {v.module_path}:{v.lineno} -> {v.detail!r}")
    print()

    print(f"=== FAMILY 7: production imports of a demoted raw-loader symbol: {len(registry_loader_imports)} total ===")
    print(f"  (demoted set: {sorted(DEMOTED_REGISTRY_LOADER_SYMBOLS)})")
    for v in registry_loader_imports:
        print(f"  {v.importer_path}:{v.lineno} imports {v.imported_names} from {REGISTRY_LOADER_PACKAGE}")
    print()

    print(f"=== FAMILY 8: dangling first-party import targets: {len(dangling_imports)} total ===")
    print("  (a deletion that landed without its consumer sweep, seen from the consumer end;")
    print("   the whole-tree type checker computes the same fact but carries too much unrelated")
    print("   noise at rest for one new edge to be visible in it)")
    for d in dangling_imports:
        symbol = f" :: {d.symbol}" if d.symbol else ""
        print(f"  [{d.kind}][{'test' if d.is_test else 'prod'}] {d.importer_path}:{d.lineno} -> {d.target_mod}{symbol}")
    print()

    print(f"=== FAMILY 9: orphaned modules (nothing in the first-party tree reaches them): {len(orphaned_modules)} ===")
    print("  (the same deletion seen from the other end: the module left behind when its last")
    print("   consumer went. Reach counts static imports, dynamic importlib targets and any")
    print("   string constant naming the module, across src/, the harness distribution and dev/)")
    orphan_bridges = [o for o in orphaned_modules if o.is_reexport_surface]
    print(f"  of which pure re-export bridges: {len(orphan_bridges)}")
    for o in orphaned_modules:
        kind = "reexport-bridge" if o.is_reexport_surface else "defines-its-own"
        print(f"  [{kind}][{'test' if o.is_test else 'prod'}] {o.path}")
    print()

    print(f"=== FIX STRATEGY: precondition promotions vs. simple consumer rewrites ({len(fix_classes)} pairs) ===")
    needs_promotion = [f for f in fix_classes if not f.already_in_facade]
    simple_rewrite = [f for f in fix_classes if f.already_in_facade]
    print(f"  distinct (owning_package, symbol) pairs consumed cross-package (production only): {len(fix_classes)}")
    print(f"  NEEDS FACADE PROMOTION FIRST (symbol absent from owning __all__): {len(needs_promotion)} pairs")
    print(f"  SIMPLE CONSUMER REWRITE (symbol already in owning __all__):       {len(simple_rewrite)} pairs")
    total_consumer_sites_promo = sum(f.consumer_count for f in needs_promotion)
    total_consumer_sites_rewrite = sum(f.consumer_count for f in simple_rewrite)
    print(f"  production import sites behind promotion-needed pairs: {total_consumer_sites_promo}")
    print(f"  production import sites behind already-facaded pairs:  {total_consumer_sites_rewrite}")
    print()
    print("  --- batches: symbols needing PROMOTION, grouped by owning package ---")
    promo_by_owner: dict[str, list[FixClassification]] = defaultdict(list)
    for f in needs_promotion:
        promo_by_owner[f.owning_package].append(f)
    for owner in sorted(promo_by_owner, key=lambda o: -len(promo_by_owner[o])):
        items = promo_by_owner[owner]
        symbols = sorted({f.symbol for f in items})
        n_sites = sum(f.consumer_count for f in items)
        print(f"    {owner}  :: {len(symbols)} symbol(s) to promote, {n_sites} consumer site(s)")
        print(f"      symbols: {symbols}")
    print()
    print("  --- batches: symbols ALREADY facaded, grouped by owning package (pure consumer rewrite) ---")
    rewrite_by_owner: dict[str, list[FixClassification]] = defaultdict(list)
    for f in simple_rewrite:
        rewrite_by_owner[f.owning_package].append(f)
    for owner in sorted(rewrite_by_owner, key=lambda o: -len(rewrite_by_owner[o])):
        items = rewrite_by_owner[owner]
        symbols = sorted({f.symbol for f in items})
        n_sites = sum(f.consumer_count for f in items)
        print(f"    {owner}  :: {len(symbols)} symbol(s), {n_sites} consumer site(s)")
    print()

    distinct_files_to_edit = {v.importer_path for v in priv_violations if not v.is_test}
    distinct_symbols_all = {f.symbol for f in fix_classes}
    print("=== MAGNITUDE ===")
    print(f"  distinct production files with >=1 cross-package private import: {len(distinct_files_to_edit)}")
    print(f"  distinct (owner, symbol) pairs touched: {len(fix_classes)}")
    print(f"  distinct symbol names touched: {len(distinct_symbols_all)}")
    print(f"  distinct symbols needing facade promotion: {len({f.symbol for f in needs_promotion})}")
    print(f"  distinct owning packages needing >=1 promotion: {len(promo_by_owner)}")
    print(f"  production forwarding wrappers (Family 2b): {len(wrappers_non_test)}")
    print(f"  underscore-named __all__ entries (Family 4): {len(underscore_in_all)}")
    print(f"  src modules importing dev/ tooling (Family 5): {len(dev_tooling_imports)}")
    print(f"  src modules reaching a dev/ path (Family 6): {len(dev_path_reaches)}")
    print(f"  src prose naming the dev tree (Family 10): {len(dev_prose_violations)}")
    print(f"  production imports of a demoted registry raw-loader symbol (Family 7): {len(registry_loader_imports)}")
    print(f"  dangling first-party import targets (Family 8): {len(dangling_imports)}")
    print(f"  orphaned modules (Family 9): {len(orphaned_modules)}")
    print(f"  retired TUI fixed-point remnants: {len(retired_tui_remnants)}")
    print()

    if args.json:
        payload = {
            "facades": {
                pkg: {"path": str(info.path.relative_to(REPO_ROOT)).replace("\\", "/"), "all_names": info.all_names}
                for pkg, info in real_facades.items()
            },
            "private_import_violations": [
                {
                    "importer_mod": v.importer_mod,
                    "importer_path": v.importer_path,
                    "lineno": v.lineno,
                    "target_mod": v.target_mod,
                    "owning_package": v.owning_package,
                    "imported_names": v.imported_names,
                    "is_test": v.is_test,
                    "in_type_checking": v.in_type_checking,
                }
                for v in priv_violations
            ],
            "shim_modules": [
                {"mod": s.mod, "path": s.path, "reason": s.reason, "detail": s.detail, "is_test": s.is_test}
                for s in shims
            ],
            "delegate_wrapper_shims": [
                {
                    "mod": w.mod,
                    "path": w.path,
                    "function": w.function,
                    "lineno": w.lineno,
                    "target_mod": w.target_mod,
                    "target": w.target,
                    "is_test": w.is_test,
                }
                for w in delegate_wrappers
            ],
            "multi_sourced_symbols": [
                {
                    "symbol": m.symbol,
                    "facades": m.facades,
                    "private_sources": m.private_sources,
                    "consumed_from_facade_by": m.consumed_from_facade_by,
                    "consumed_from_private_by": m.consumed_from_private_by,
                    "confidence": m.confidence,
                }
                for m in multi_sourced
            ],
            "fix_classification": [
                {
                    "owning_package": f.owning_package,
                    "symbol": f.symbol,
                    "already_in_facade": f.already_in_facade,
                    "consumer_count": f.consumer_count,
                    "consumer_modules": f.consumer_modules,
                }
                for f in fix_classes
            ],
            "dev_tooling_import_violations": [
                {
                    "importer_path": v.importer_path,
                    "lineno": v.lineno,
                    "target_mod": v.target_mod,
                    "is_dynamic": v.is_dynamic,
                }
                for v in dev_tooling_imports
            ],
            "dev_path_reach_violations": [
                {
                    "module_path": reach.module_path,
                    "lineno": reach.lineno,
                    "form": str(reach.form),
                    "detail": reach.detail,
                }
                for reach in dev_path_reaches
            ],
            "dev_prose_violations": [
                {
                    "module_path": v.module_path,
                    "lineno": v.lineno,
                    "source_kind": v.source_kind,
                    "detail": v.detail,
                }
                for v in dev_prose_violations
            ],
            "underscore_in_all_violations": [
                {"package": v.package, "path": v.path, "name": v.name} for v in underscore_in_all
            ],
            "registry_loader_import_violations": [
                {
                    "importer_mod": v.importer_mod,
                    "importer_path": v.importer_path,
                    "lineno": v.lineno,
                    "imported_names": v.imported_names,
                }
                for v in registry_loader_imports
            ],
            "dangling_first_party_imports": [
                {
                    "importer_mod": d.importer_mod,
                    "importer_path": d.importer_path,
                    "lineno": d.lineno,
                    "target_mod": d.target_mod,
                    "symbol": d.symbol,
                    "kind": str(d.kind),
                    "is_test": d.is_test,
                }
                for d in dangling_imports
            ],
            "orphaned_modules": [
                {
                    "mod": o.mod,
                    "path": o.path,
                    "is_reexport_surface": o.is_reexport_surface,
                    "is_test": o.is_test,
                }
                for o in orphaned_modules
            ],
            "retired_tui_remnants": [
                {
                    "kind": str(remnant.kind),
                    "importer_mod": remnant.importer_mod,
                    "importer_path": remnant.importer_path,
                    "lineno": remnant.lineno,
                    "target": remnant.target,
                }
                for remnant in retired_tui_remnants
            ],
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding=_UTF_8, newline="\n")
        print(f"Wrote full JSON inventory to {args.json}")

    if not retired_tui_remnants:
        return 0
    print("=== RETIRED TUI FIXED POINT: VIOLATED ===")
    for remnant in retired_tui_remnants:
        print(f"  {remnant.kind}: {remnant.importer_path}:{remnant.lineno} -> {remnant.target}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
