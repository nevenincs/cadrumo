"""Fail while a published exact-unused name has no production importer.

The subject is every package under ``src/`` (``SOURCE_PACKAGES``), and every
one of them is also a consumer: an export a sibling package imports in
production is consumed, wherever the two live. Exact-unused evidence comes
from the reachability scan, so a source package that scan does not audit has
no evidence to join against. Such a package is refused rather than reported
clean, because an empty join over an unaudited package would read as zero.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from dev.audit.unreachable_code import run_unreachable_code_scan
from dev.audit.unreachable_models import Confidence, UnreachableCodeOutcome
from dev.audit.unreachable_tree import ShippedTreeSpec
from dev.first_party_source import SOURCE_PACKAGES, is_production_source

from .source_import_analysis import module_name_for, resolve_relative_import

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SOURCE_ROOTS = tuple(REPO_ROOT / package for package in SOURCE_PACKAGES)


@dataclass(frozen=True, order=True, slots=True)
class UnconsumedExport:
    """One exported exact-unused name with no production importer."""

    path: str
    name: str


@dataclass(frozen=True, slots=True)
class UnconsumedExportVerdict:
    """The complete live unconsumed-export population."""

    findings: tuple[UnconsumedExport, ...]
    packages: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        """Whether every exact-unused export has a production importer."""
        return not self.findings

    def report(self) -> str:
        """Name the measured packages and every current finding."""
        counts = {package: 0 for package in self.packages}
        for finding in self.findings:
            package = finding.path.split("/", 1)[0]
            counts[package] = counts.get(package, 0) + 1
        scope = ", ".join(f"{package}={count}" for package, count in counts.items())
        if self.is_clean:
            return f"unconsumed-export coverage: no findings ({scope})"
        lines = [f"unconsumed-export coverage: {len(self.findings)} finding(s); expected zero ({scope})"]
        lines.extend(f"  + {finding.path}:{finding.name}" for finding in self.findings)
        return "\n".join(lines)


def _declared_exports(tree: ast.Module) -> tuple[str, ...]:
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.List | ast.Tuple):
            continue
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            return tuple(
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
    return ()


def _imported_pairs(tree: ast.Module, module: str, is_package: bool) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(module, is_package, node.level, node.module)
            if base is not None and base:
                pairs.update((base, alias.name) for alias in node.names)
    return pairs


def _audit_key(path: Path, root: Path) -> str:
    """Spell ``path`` the way the reachability scan keys its findings.

    The scan names a repository package by its repository-relative path; a
    synthetic tree has no repository, so its paths are keyed from its own
    ``src``. Testing the root's location rather than the path's matters: a
    test tree placed inside the checkout must still key from its own root.
    """
    if root.parent == REPO_ROOT / "src":
        return path.relative_to(REPO_ROOT).as_posix()
    return path.relative_to(root.parent).as_posix()


def find_unconsumed(
    roots: tuple[Path, ...],
    unused: set[tuple[str, str]],
    *,
    consumer_roots: tuple[Path, ...] = (),
) -> tuple[UnconsumedExport, ...]:
    """Join live exports, production imports, and exact-unused audit findings.

    Every module under ``roots`` is both a subject and a consumer; modules
    under ``consumer_roots`` only consume. Findings are named relative to
    each root's ``src`` directory, so the package is part of the path.
    """
    trees: dict[Path, tuple[Path, ast.Module]] = {}
    unread: list[str] = []
    for source_root in (*roots, *consumer_roots):
        if not source_root.is_dir():
            raise RuntimeError(f"unconsumed-export consumer root is unavailable: {source_root}")
        for path in sorted(source_root.rglob("*.py")):
            if not is_production_source(path, root=source_root):
                continue
            try:
                trees[path] = (source_root, ast.parse(path.read_bytes(), filename=str(path)))
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                unread.append(f"{path}: {type(error).__name__}: {error}")
    if unread:
        raise RuntimeError(f"unconsumed-export scan unreadable for {len(unread)} file(s): {unread}")

    consumed: set[tuple[str, str]] = set()
    for path, (source_root, tree) in trees.items():
        module = module_name_for(path, src_root=source_root.parent)
        consumed.update(_imported_pairs(tree, module, path.name == "__init__.py"))
    return tuple(
        sorted(
            UnconsumedExport(path.relative_to(root.parent).as_posix(), name)
            for path, (root, tree) in trees.items()
            if root in roots
            for name in _declared_exports(tree)
            if (module_name_for(path, src_root=root.parent), name) not in consumed
            and (_audit_key(path, root), name) in unused
        ),
    )


def run_gate(roots: tuple[Path, ...] = _SOURCE_ROOTS) -> UnconsumedExportVerdict:
    """Measure the live packages, refusing an unavailable or narrower reachability scan."""
    spec = ShippedTreeSpec.from_repository(REPO_ROOT)
    unaudited = sorted(root.name for root in roots if root.name not in spec.packages)
    if unaudited:
        raise RuntimeError(
            f"reachability scan does not audit {', '.join(unaudited)}; their exports have no exact-unused "
            "evidence, so coverage is unproven",
        )
    result = run_unreachable_code_scan(REPO_ROOT)
    if result.outcome is UnreachableCodeOutcome.ERROR:
        raise RuntimeError(f"reachability scan unavailable, coverage unproven: {result.reason}")
    unused = {
        (str(finding.path).replace("\\", "/"), finding.name)
        for finding in result.symbols
        if finding.confidence is Confidence.EXACT
    }
    return UnconsumedExportVerdict(find_unconsumed(roots, unused), tuple(root.name for root in roots))


def main() -> int:
    """Print the live set and fail until it is empty."""
    verdict = run_gate()
    stream = sys.stdout if verdict.is_clean else sys.stderr
    stream.write(verdict.report() + "\n")
    return 0 if verdict.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
