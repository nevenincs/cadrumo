"""Audit module and object-name uniqueness and singularity across ``src/`` and ``dev/``.

The enforced surface is public modules and their module-level classes, enums, and
functions outside test modules. Private and test declarations are still inventoried
and their exact-name collisions are reported as advisory findings. Methods and nested
declarations are not independent module objects and are therefore outside this audit.

Usage::

    python -m dev.audit.object_names
    python -m dev.audit.object_names --json
    python -m dev.audit.object_names --full
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from .._paths import REPO_ROOT

_DECLARATION_NODES: Final = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_ENUM_BASES: Final[frozenset[str]] = frozenset({"Enum", "Flag", "IntEnum", "IntFlag", "StrEnum"})
_NON_PLURAL_SUFFIXES: Final[tuple[str, ...]] = (
    "access",
    "address",
    "alias",
    "analysis",
    "axis",
    "basis",
    "business",
    "class",
    "corpus",
    "census",
    "locus",
    "process",
    "series",
    "species",
    "status",
)
_FUNCTION_PLURAL_NOUNS: Final[frozenset[str]] = frozenset(
    {
        "casillas",
        "details",
        "entries",
        "errors",
        "facts",
        "formulas",
        "invoices",
        "items",
        "markers",
        "options",
        "records",
        "refusals",
        "resources",
        "surfaces",
        "transactions",
    }
)
_PASCAL_WORD: Final[re.Pattern[str]] = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
_TEXT_LIMIT: Final[int] = 50


class ObjectNameKind(StrEnum):
    """Kinds of independently bound module objects inspected by the audit."""

    CLASS = "class"
    ENUM = "enum"
    FUNCTION = "function"
    MODULE = "module"


class ObjectNameFindingKind(StrEnum):
    """Failure families emitted by the audit."""

    DUPLICATE = "duplicate-name"
    PLURAL = "plural-name"
    SOURCE_ERROR = "source-error"


@dataclass(frozen=True, slots=True)
class ObjectNameDeclaration:
    """One module-level class, enum, or function declaration."""

    name: str
    kind: ObjectNameKind
    path: str
    line: int
    public: bool
    test: bool
    overload: bool

    @property
    def enforced(self) -> bool:
        """Whether this declaration belongs to the zero-tolerance surface."""
        return self.public and not self.test


@dataclass(frozen=True, slots=True)
class ObjectNameFinding:
    """One deterministic audit finding."""

    kind: ObjectNameFindingKind
    name: str
    enforced: bool
    sites: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class ObjectNameAuditResult:
    """Complete declaration population and its findings."""

    declarations: tuple[ObjectNameDeclaration, ...]
    findings: tuple[ObjectNameFinding, ...]

    @property
    def enforced_findings(self) -> tuple[ObjectNameFinding, ...]:
        """Findings that make the check fail."""
        return tuple(finding for finding in self.findings if finding.enforced)


def _base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return ""


def _kind(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> ObjectNameKind:
    if not isinstance(node, ast.ClassDef):
        return ObjectNameKind.FUNCTION
    if any(_base_name(base) in _ENUM_BASES for base in node.bases):
        return ObjectNameKind.ENUM
    return ObjectNameKind.CLASS


def _is_test_path(relative: Path) -> bool:
    return relative.name.startswith("test_") or "tests" in relative.parts


def _relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_overload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(_base_name(decorator) == "overload" for decorator in node.decorator_list)


def _module_declarations(tree: ast.Module) -> Iterable[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield declarations bound by module execution, including control-flow branches."""

    def descend(node: ast.AST) -> Iterable[ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _DECLARATION_NODES):
                yield child
                continue
            if isinstance(child, ast.Lambda):
                continue
            yield from descend(child)

    return descend(tree)


def declarations_in_source(source: str, path: str, *, test: bool = False) -> tuple[ObjectNameDeclaration, ...]:
    """Parse one source string and return its independently bound declarations."""
    tree = ast.parse(source, filename=path)
    declarations = (
        ObjectNameDeclaration(
            name=node.name,
            kind=_kind(node),
            path=path,
            line=node.lineno,
            public=not node.name.startswith("_"),
            test=test,
            overload=isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_overload(node),
        )
        for node in _module_declarations(tree)
    )
    return tuple(sorted(declarations, key=lambda item: (item.name, item.kind, item.line)))


def _python_files(roots: Iterable[Path]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (path for root in roots if root.is_dir() for path in root.rglob("*.py") if "__pycache__" not in path.parts),
            key=lambda path: path.as_posix(),
        )
    )


def collect_declarations(
    roots: Sequence[Path], repo_root: Path
) -> tuple[tuple[ObjectNameDeclaration, ...], tuple[ObjectNameFinding, ...]]:
    """Read both source roots, returning declarations and fail-closed source errors."""
    declarations: list[ObjectNameDeclaration] = []
    errors: list[ObjectNameFinding] = []
    for root in roots:
        if root.is_dir():
            continue
        relative = _relative(root, repo_root)
        errors.append(
            ObjectNameFinding(
                kind=ObjectNameFindingKind.SOURCE_ERROR,
                name=relative,
                enforced=True,
                sites=(f"{relative}:0",),
                detail="required source root is missing",
            )
        )
    for path in _python_files(roots):
        relative = Path(_relative(path, repo_root))
        is_test = _is_test_path(relative)
        declarations.append(
            ObjectNameDeclaration(
                name=path.stem,
                kind=ObjectNameKind.MODULE,
                path=relative.as_posix(),
                line=1,
                public=not path.stem.startswith("_"),
                test=is_test,
                overload=False,
            )
        )
        try:
            source = path.read_text(encoding="utf-8")
            declarations.extend(declarations_in_source(source, relative.as_posix(), test=is_test))
        except (OSError, UnicodeError, SyntaxError) as exc:
            line = exc.lineno if isinstance(exc, SyntaxError) and exc.lineno is not None else 0
            errors.append(
                ObjectNameFinding(
                    kind=ObjectNameFindingKind.SOURCE_ERROR,
                    name=relative.as_posix(),
                    enforced=True,
                    sites=(f"{relative.as_posix()}:{line}",),
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
    return (
        tuple(sorted(declarations, key=lambda item: (item.path, item.line, item.kind, item.name))),
        tuple(sorted(errors, key=lambda item: item.name)),
    )


def _last_noun(declaration: ObjectNameDeclaration) -> str | None:
    if declaration.kind is ObjectNameKind.FUNCTION:
        words = declaration.name.split("_")
        return words[0] if len(words) == 1 else None
    if declaration.kind is ObjectNameKind.MODULE:
        words = declaration.name.split("_")
        return words[-1] if words else None
    words = _PASCAL_WORD.findall(declaration.name)
    return words[-1].lower() if words else None


def _looks_plural(word: str | None, kind: ObjectNameKind) -> bool:
    if word is None or len(word) < 4 or word.endswith(_NON_PLURAL_SUFFIXES):
        return False
    if kind is ObjectNameKind.FUNCTION:
        return word in _FUNCTION_PLURAL_NOUNS
    return word.endswith("s") and not word.endswith("ss")


def analyse(
    declarations: Sequence[ObjectNameDeclaration], source_errors: Sequence[ObjectNameFinding] = ()
) -> ObjectNameAuditResult:
    """Compile exact-name collisions and conservative plural-name findings."""
    findings = list(source_errors)
    by_name: dict[str, list[ObjectNameDeclaration]] = defaultdict(list)
    for declaration in declarations:
        by_name[declaration.name].append(declaration)

    for name, named in sorted(by_name.items()):
        comparable = [item for item in named if not (item.name == "main" and item.kind is ObjectNameKind.FUNCTION)]
        # A valid overload family has exactly one concrete implementation and one or
        # more @overload declarations. Every other repeated binding stays visible.
        by_site: dict[tuple[str, ObjectNameKind], list[ObjectNameDeclaration]] = defaultdict(list)
        for item in comparable:
            by_site[(item.path, item.kind)].append(item)
        distinct: list[ObjectNameDeclaration] = []
        for local in by_site.values():
            concrete = [item for item in local if not item.overload]
            if len(concrete) == 1 and len(concrete) < len(local):
                distinct.append(concrete[0])
            else:
                distinct.extend(local)
        if len(distinct) < 2:
            continue
        sites = tuple(
            f"{item.path}:{item.line} ({item.kind})"
            for item in sorted(distinct, key=lambda item: (item.path, item.line, item.kind))
        )
        enforced = sum(item.enforced for item in distinct) > 1
        scope = "public declaration collision" if enforced else "private/test declaration collision"
        findings.append(ObjectNameFinding(ObjectNameFindingKind.DUPLICATE, name, enforced, sites, scope))

    for declaration in declarations:
        noun = _last_noun(declaration)
        if not declaration.enforced or not _looks_plural(noun, declaration.kind):
            continue
        findings.append(
            ObjectNameFinding(
                ObjectNameFindingKind.PLURAL,
                declaration.name,
                True,
                (f"{declaration.path}:{declaration.line} ({declaration.kind})",),
                f"public declaration ends in plural-looking noun {noun!r}",
            )
        )

    return ObjectNameAuditResult(
        declarations=tuple(declarations),
        findings=tuple(sorted(findings, key=lambda item: (item.kind, item.name, item.sites))),
    )


def scan(roots: Sequence[Path], repo_root: Path) -> ObjectNameAuditResult:
    """Collect and analyse declarations below the requested roots."""
    declarations, source_errors = collect_declarations(roots, repo_root)
    return analyse(declarations, source_errors)


def to_json(result: ObjectNameAuditResult) -> dict[str, object]:
    """Return the stable machine-readable report."""
    enforced = result.enforced_findings
    return {
        "summary": {
            "declarations": len(result.declarations),
            "findings": len(result.findings),
            "enforced_findings": len(enforced),
            "advisory_findings": len(result.findings) - len(enforced),
        },
        "findings": [asdict(finding) for finding in result.findings],
    }


def render_text(result: ObjectNameAuditResult, *, full: bool = False) -> str:
    """Render a concise report, optionally without the terminal cap."""
    enforced = result.enforced_findings
    lines = [
        f"object-name audit: {len(result.declarations)} declarations, "
        f"{len(enforced)} enforced finding(s), {len(result.findings) - len(enforced)} advisory finding(s)",
    ]
    shown = result.findings if full else result.findings[:_TEXT_LIMIT]
    for finding in shown:
        posture = "FAIL" if finding.enforced else "ADVISORY"
        lines.append(f"[{posture}] {finding.kind}: {finding.name} - {finding.detail}")
        lines.extend(f"    {site}" for site in finding.sites)
    if len(shown) < len(result.findings):
        lines.append(f"... {len(result.findings) - len(shown)} more; rerun with --full or --json")
    return "\n".join(lines)


def exit_code(result: ObjectNameAuditResult) -> int:
    """Map a completed audit to the contributor command contract."""
    return 1 if result.enforced_findings else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the repository audit; return one when the enforced surface is not unique."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Emit stable machine-readable findings.")
    parser.add_argument("--full", action="store_true", help="Do not cap text findings.")
    args = parser.parse_args(argv)

    result = scan((REPO_ROOT / "src", REPO_ROOT / "dev"), REPO_ROOT)
    if args.json:
        print(json.dumps(to_json(result), indent=2, sort_keys=True))
    else:
        print(render_text(result, full=args.full))
    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
