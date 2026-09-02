"""Census of Python APIs that cannot be carried by the supported runtimes.

The project has one source tree with a Python 3.13 floor.  A normal linter can
still miss a compatibility defect when the name is imported through an alias,
when a removed module is loaded dynamically, or when a deprecated API is used
only on a rarely exercised path.  This scanner resolves those *static* forms
without importing the application.

The census is intentionally a finite catalogue of APIs whose removal or
deprecation is established for CPython 3.13 and later.  It is a detector, not
an exemption ledger: every finding names the source location, canonical API,
and the first affected runtime.  The catalogue can be extended when CPython
deprecates another API, while the public result shape remains stable.

Run directly with::

    python -m dev.quality.python_compatibility_scan
    python -m dev.quality.python_compatibility_scan --json compatibility.json

The scan is read-only and covers both ``dev/`` and ``src/`` by default.  Paths
passed on the command line are scanned instead, which makes the same detector
usable as a focused pre-commit check and as a whole-tree quality gate.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, override

from .._paths import REPO_ROOT, UTF_8

__all__ = [
    "CompatibilityFinding",
    "CompatibilityKind",
    "CompatibilityRule",
    "DEFAULT_SOURCE_ROOTS",
    "DEPRECATED_API_RULES",
    "REMOVED_MODULE_RULES",
    "scan_python_compatibility",
    "scan_paths_for_python_compatibility",
    "source_paths",
]


class CompatibilityKind(StrEnum):
    """Classification of one source-level compatibility finding."""

    REMOVED_MODULE = "removed_module"
    REMOVED_API = "removed_api"
    DEPRECATED_API = "deprecated_api"
    PRIVATE_API = "private_api"
    SCAN_ERROR = "scan_error"


@dataclass(frozen=True, slots=True)
class CompatibilityRule:
    """One canonical module or API known not to be a 3.13+ safe dependency."""

    qualified_name: str
    kind: CompatibilityKind
    first_affected: str
    reason: str


@dataclass(frozen=True, slots=True)
class CompatibilityFinding:
    """One removed, deprecated, private, or unscannable source construct."""

    path: Path
    lineno: int
    kind: CompatibilityKind
    api: str
    first_affected: str = ""
    reason: str = ""

    @property
    def category(self) -> CompatibilityKind:
        """Compatibility category, provided as a descriptive alias for callers."""
        return self.kind

    @property
    def location(self) -> str:
        """Render the source location in the form used by quality reports."""
        return f"{self.path}:{self.lineno}"

    @override
    def __str__(self) -> str:
        """Render one grep-friendly finding."""
        suffix = f"; affected since {self.first_affected}" if self.first_affected else ""
        detail = f" - {self.reason}" if self.reason else ""
        subject = self.api or "source"
        return f"{self.location}: {self.kind.value}: {subject}{suffix}{detail}"


def _rule(
    qualified_name: str,
    kind: CompatibilityKind,
    first_affected: str,
    reason: str,
) -> CompatibilityRule:
    return CompatibilityRule(qualified_name, kind, first_affected, reason)


# PEP 594's dead batteries, plus modules removed before the current floor.
# Keeping these as canonical module prefixes lets ``import x.y`` and
# ``from x import y`` share one removal rule.
REMOVED_MODULE_RULES: Final[tuple[CompatibilityRule, ...]] = (
    _rule("aifc", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("audioop", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("cgi", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("cgitb", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("chunk", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("crypt", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("distutils", CompatibilityKind.REMOVED_MODULE, "3.12", "removed from the standard library"),
    _rule("formatter", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library"),
    _rule("imghdr", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("imp", CompatibilityKind.REMOVED_MODULE, "3.12", "removed from the standard library"),
    _rule("lib2to3", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library"),
    _rule("mailcap", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("msilib", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("nis", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("nntplib", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("ossaudiodev", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("pipes", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("sndhdr", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("spwd", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("sunau", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("telnetlib", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("uu", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
    _rule("xdrlib", CompatibilityKind.REMOVED_MODULE, "3.13", "removed from the standard library (PEP 594)"),
)


# These names are still importable in at least one supported interpreter but
# are deprecated, removed, or explicitly private in the modern API contract.
# The rule is matched after import aliases are resolved, so the source need
# not spell the canonical module path.
DEPRECATED_API_RULES: Final[tuple[CompatibilityRule, ...]] = (
    _rule(
        "asyncio.AbstractEventLoopPolicy",
        CompatibilityKind.DEPRECATED_API,
        "3.14",
        "event-loop policy APIs are deprecated; use the active loop/run APIs",
    ),
    _rule(
        "asyncio.get_event_loop_policy",
        CompatibilityKind.DEPRECATED_API,
        "3.14",
        "event-loop policy APIs are deprecated; use the active loop/run APIs",
    ),
    _rule(
        "asyncio.set_event_loop_policy",
        CompatibilityKind.DEPRECATED_API,
        "3.14",
        "event-loop policy APIs are deprecated; use the active loop/run APIs",
    ),
    _rule(
        "asyncio.Task.all_tasks",
        CompatibilityKind.REMOVED_API,
        "3.11",
        "removed asyncio task class helper; use asyncio.all_tasks",
    ),
    _rule(
        "asyncio.Task.current_task",
        CompatibilityKind.REMOVED_API,
        "3.11",
        "removed asyncio task class helper; use asyncio.current_task",
    ),
    _rule(
        "asyncio.coroutine",
        CompatibilityKind.REMOVED_API,
        "3.11",
        "removed generator-based coroutine decorator",
    ),
    _rule(
        "collections.Callable",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.Callable",
    ),
    _rule(
        "collections.Container",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.Container",
    ),
    _rule(
        "collections.Iterable",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.Iterable",
    ),
    _rule(
        "collections.Mapping",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.Mapping",
    ),
    _rule(
        "collections.MutableMapping",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.MutableMapping",
    ),
    _rule(
        "collections.MutableSequence",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.MutableSequence",
    ),
    _rule(
        "collections.MutableSet",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.MutableSet",
    ),
    _rule(
        "collections.Sequence",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.Sequence",
    ),
    _rule(
        "collections.Set",
        CompatibilityKind.REMOVED_API,
        "3.10",
        "moved to collections.abc.Set",
    ),
    _rule(
        "datetime.datetime.utcnow",
        CompatibilityKind.DEPRECATED_API,
        "3.12",
        "returns a naive UTC datetime; use datetime.now(datetime.UTC)",
    ),
    _rule(
        "datetime.datetime.utcfromtimestamp",
        CompatibilityKind.DEPRECATED_API,
        "3.12",
        "returns a naive UTC datetime; use datetime.fromtimestamp(..., datetime.UTC)",
    ),
    _rule(
        "importlib.resources.contents",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy resource API; use files().iterdir()",
    ),
    _rule(
        "importlib.resources.open_binary",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy resource API; use files().joinpath().open()",
    ),
    _rule(
        "importlib.resources.open_text",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy resource API; use files().joinpath().open()",
    ),
    _rule(
        "importlib.resources.path",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy resource API; use as_file(files().joinpath())",
    ),
    _rule(
        "importlib.resources.read_binary",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy resource API; use files().joinpath().read_bytes()",
    ),
    _rule(
        "importlib.resources.read_text",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy resource API; use files().joinpath().read_text()",
    ),
    _rule(
        "inspect.formatargspec",
        CompatibilityKind.REMOVED_API,
        "3.11",
        "removed inspect helper; use Signature APIs",
    ),
    _rule(
        "inspect.getargspec",
        CompatibilityKind.REMOVED_API,
        "3.11",
        "removed inspect helper; use inspect.signature",
    ),
    _rule(
        "inspect.getargvalues",
        CompatibilityKind.DEPRECATED_API,
        "3.11",
        "legacy inspect helper; prefer Signature APIs",
    ),
    _rule(
        "locale.getdefaultlocale",
        CompatibilityKind.REMOVED_API,
        "3.15",
        "removed locale helper; use getlocale or a configured locale",
    ),
    _rule(
        "platform.linux_distribution",
        CompatibilityKind.REMOVED_API,
        "3.8",
        "removed platform helper; use an operating-system specific provider",
    ),
    _rule(
        "ssl.wrap_socket",
        CompatibilityKind.DEPRECATED_API,
        "3.12",
        "deprecated SSL helper; use SSLContext.wrap_socket",
    ),
)

_PRIVATE_TYPING_MODULES: Final[frozenset[str]] = frozenset({"typing", "typing_extensions"})
_DEFAULT_EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
    }
)
DEFAULT_SOURCE_ROOTS: Final[tuple[Path, ...]] = (REPO_ROOT / "dev", REPO_ROOT / "src")


def _dotted_name(node: ast.AST) -> str | None:
    """Return a dotted spelling for a name/attribute AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _constant_string(node: ast.AST | None) -> str | None:
    """Return a literal string, excluding interpolated/dynamic expressions."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _prefix_rule(name: str, rules: tuple[CompatibilityRule, ...]) -> CompatibilityRule | None:
    """Find an exact rule or a module-prefix rule for ``name``."""
    for rule in rules:
        if name == rule.qualified_name or name.startswith(f"{rule.qualified_name}."):
            return rule
    return None


def _rule_for_name(name: str) -> CompatibilityRule | None:
    """Resolve a canonical API name against the compatibility catalogue."""
    removed_module = _prefix_rule(name, REMOVED_MODULE_RULES)
    if removed_module is not None:
        return removed_module
    direct = _prefix_rule(name, DEPRECATED_API_RULES)
    if direct is not None:
        return direct
    module, _, member = name.rpartition(".")
    if module in _PRIVATE_TYPING_MODULES and member.startswith("_"):
        return _rule(
            name,
            CompatibilityKind.PRIVATE_API,
            "all supported versions",
            "private typing implementation names are not a cross-version API",
        )
    return None


def _module_binding_for_import(module: str, alias: ast.alias) -> tuple[str, str]:
    """Return the bound local name and canonical module for ``import``."""
    if alias.asname:
        return alias.asname, alias.name
    return alias.name.split(".", 1)[0], alias.name.split(".", 1)[0]


def _finding(
    path: Path,
    node: ast.AST,
    rule: CompatibilityRule,
    *,
    api: str | None = None,
) -> CompatibilityFinding:
    """Build one finding using the node's source line."""
    return CompatibilityFinding(
        path=path,
        lineno=getattr(node, "lineno", 0),
        kind=rule.kind,
        api=api or rule.qualified_name,
        first_affected=rule.first_affected,
        reason=rule.reason,
    )


class _CompatibilityAnalyzer(ast.NodeVisitor):
    """Resolve import aliases and report compatibility-sensitive references."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.module_bindings: dict[str, str] = {}
        self.symbol_bindings: dict[str, str] = {}
        self.findings: list[CompatibilityFinding] = []

    def _add(self, node: ast.AST, name: str) -> None:
        rule = _rule_for_name(name)
        if rule is None:
            return
        self.findings.append(_finding(self.path, node, rule, api=name))

    def _resolved(self, node: ast.AST) -> str | None:
        """Resolve a local name/attribute through the imports seen in the module."""
        if isinstance(node, ast.Name):
            # An unbound local called ``chunk`` or ``datetime`` is not evidence
            # that the standard-library module was imported.  Returning the raw
            # spelling here made ordinary variables look like removed modules
            # (for example, a local ``chunk.write_bytes`` helper).  Only an
            # import-established identity is safe to carry across a module.
            return self.symbol_bindings.get(node.id) or self.module_bindings.get(node.id)
        if isinstance(node, ast.Attribute):
            parent = self._resolved(node.value)
            return f"{parent}.{node.attr}" if parent else None
        return None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound, module = _module_binding_for_import(alias.name, alias)
            self.module_bindings[bound] = module
            self._add(node, module)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            # Relative imports cannot target a stdlib compatibility rule by
            # spelling alone.  A relative import may still import an aliased
            # local object, which has no static stdlib identity here.
            self.generic_visit(node)
            return
        module = node.module or ""
        module_rule = _rule_for_name(module)
        if module_rule is not None:
            self.findings.append(_finding(self.path, node, module_rule, api=module))
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            canonical = f"{module}.{alias.name}" if module else alias.name
            self.symbol_bindings[bound] = canonical
            self._add(node, canonical)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        resolved = self._resolved(node)
        if resolved is not None:
            self._add(node, resolved)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # A direct ``from M import deprecated_name`` is caught at the import
        # node.  This second check catches a call/reference made through the
        # imported local name while preserving the exact source line.
        if isinstance(node.ctx, ast.Load):
            resolved = self._resolved(node)
            if resolved is not None and resolved != node.id:
                self._add(node, resolved)

    def visit_Call(self, node: ast.Call) -> None:
        function = self._resolved(node.func) or _dotted_name(node.func)
        if function in {"importlib.import_module", "__import__"} and node.args:
            imported = _constant_string(node.args[0])
            if imported is not None:
                self._add(node, imported)
        self.generic_visit(node)


def _deduplicate(findings: list[CompatibilityFinding]) -> tuple[CompatibilityFinding, ...]:
    """Keep one stable row for a source location/API/category combination."""
    unique = {
        (item.path.resolve(), item.lineno, item.kind, item.api): item
        for item in findings
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.path.as_posix(), item.lineno, item.kind.value, item.api),
        )
    )


def scan_python_compatibility(path: Path, source: str | None = None) -> tuple[CompatibilityFinding, ...]:
    """Return compatibility findings for one Python source file.

    A read error belongs to the caller because this function accepts source
    text explicitly.  A syntax error is reported as a scan finding rather than
    silently discarded; the separate parser gate can then provide the full
    repository-wide syntax verdict.
    """
    text = source if source is not None else path.read_text(encoding=UTF_8)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as error:
        rule = CompatibilityRule(
            qualified_name="<syntax>",
            kind=CompatibilityKind.SCAN_ERROR,
            first_affected="3.13",
            reason=f"cannot build an AST: {error.msg}",
        )
        return (_finding(path, error, rule, api="<syntax>"),)
    analyzer = _CompatibilityAnalyzer(path)
    analyzer.visit(tree)
    return _deduplicate(analyzer.findings)


def _source_files(root: Path) -> tuple[Path, ...]:
    """Enumerate Python files below one source root without importing it."""
    if not root.is_dir():
        return ()
    found: list[Path] = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in _DEFAULT_EXCLUDED_DIRS]
        found.extend(Path(directory) / name for name in filenames if name.endswith(".py"))
    return tuple(sorted(found, key=lambda path: path.as_posix()))


def source_paths(roots: tuple[Path, ...] = DEFAULT_SOURCE_ROOTS) -> tuple[Path, ...]:
    """Return all Python files under the supplied compatibility roots."""
    return tuple(sorted((path for root in roots for path in _source_files(root)), key=lambda path: path.as_posix()))


def scan_paths_for_python_compatibility(paths: tuple[Path, ...]) -> tuple[CompatibilityFinding, ...]:
    """Return deterministic findings for the supplied Python files."""
    findings: list[CompatibilityFinding] = []
    for path in sorted(paths, key=lambda candidate: candidate.as_posix()):
        try:
            findings.extend(scan_python_compatibility(path))
        except (OSError, UnicodeError) as error:
            rule = CompatibilityRule(
                qualified_name="<read>",
                kind=CompatibilityKind.SCAN_ERROR,
                first_affected="3.13",
                reason=f"cannot read source: {error}",
            )
            findings.append(_finding(path, ast.Pass(), rule, api="<read>"))
    return _deduplicate(findings)


def _display(path: Path) -> str:
    """Render a repo-relative path where possible."""
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    """Print compatibility findings and return a quality-gate exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("paths", nargs="*", type=Path, help="Python files or roots to scan")
    parser.add_argument("--json", dest="json_path", type=Path, help="write findings as JSON")
    args = parser.parse_args(argv)

    if args.paths:
        paths = tuple(
            path
            for candidate in args.paths
            for path in (_source_files(candidate) if candidate.is_dir() else (candidate,))
            if path.suffix == ".py"
        )
    else:
        paths = source_paths()
    findings = scan_paths_for_python_compatibility(paths)

    for item in findings:
        print(f"python_compatibility path={_display(item.path)} line={item.lineno} "
              f"kind={item.kind.value} api={item.api} first_affected={item.first_affected}")
        if item.reason:
            print(f"  {item.reason}")

    if args.json_path is not None:
        payload = [
            {
                "path": _display(item.path),
                "lineno": item.lineno,
                "kind": item.kind.value,
                "api": item.api,
                "first_affected": item.first_affected,
                "reason": item.reason,
            }
            for item in findings
        ]
        args.json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding=UTF_8)
        print(f"Wrote {len(payload)} compatibility finding(s) to {args.json_path}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
