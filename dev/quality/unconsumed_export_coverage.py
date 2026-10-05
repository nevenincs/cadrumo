"""Fail while a published exact-unused name has no production importer."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from dev.audit.unreachable_code import run_unreachable_code_scan
from dev.audit.unreachable_models import Confidence, UnreachableCodeOutcome
from dev.first_party_source import PRODUCT_PACKAGE, is_production_source

from .source_import_analysis import module_name_for, resolve_relative_import

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PACKAGE_ROOT = REPO_ROOT / PRODUCT_PACKAGE


@dataclass(frozen=True, order=True, slots=True)
class UnconsumedExport:
    """One exported exact-unused name with no production importer."""

    path: str
    name: str


@dataclass(frozen=True, slots=True)
class UnconsumedExportVerdict:
    """The complete live unconsumed-export population."""

    findings: tuple[UnconsumedExport, ...]

    @property
    def is_clean(self) -> bool:
        """Whether every exact-unused export has a production importer."""
        return not self.findings

    def report(self) -> str:
        """Name every current finding."""
        if self.is_clean:
            return "unconsumed-export coverage: no findings"
        lines = [f"unconsumed-export coverage: {len(self.findings)} finding(s); expected zero"]
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
            if base:
                pairs.update((base, alias.name) for alias in node.names)
    return pairs


def _audit_key(path: Path, root: Path) -> str:
    if root != _PACKAGE_ROOT:
        return path.relative_to(root.parent).as_posix()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.relative_to(root.parent).as_posix()


def find_unconsumed(
    root: Path,
    unused: set[tuple[str, str]],
) -> tuple[UnconsumedExport, ...]:
    """Join live exports, production imports, and exact-unused audit findings."""
    trees: dict[Path, ast.Module] = {}
    unread: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if not is_production_source(path, root=root):
            continue
        try:
            trees[path] = ast.parse(path.read_bytes(), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as error:
            unread.append(f"{path.relative_to(root).as_posix()}: {type(error).__name__}: {error}")
    if unread:
        raise RuntimeError(f"unconsumed-export scan unreadable for {len(unread)} file(s): {unread}")

    consumed: set[tuple[str, str]] = set()
    for path, tree in trees.items():
        consumed.update(_imported_pairs(tree, module_name_for(path, src_root=root.parent), path.name == "__init__.py"))
    return tuple(
        sorted(
            UnconsumedExport(path.relative_to(root).as_posix(), name)
            for path, tree in trees.items()
            for name in _declared_exports(tree)
            if (module_name_for(path, src_root=root.parent), name) not in consumed
            and (_audit_key(path, root), name) in unused
        ),
    )


def run_gate(root: Path = _PACKAGE_ROOT) -> UnconsumedExportVerdict:
    """Measure the live package, refusing an unavailable reachability scan."""
    result = run_unreachable_code_scan(REPO_ROOT)
    if result.outcome is UnreachableCodeOutcome.ERROR:
        raise RuntimeError(f"reachability scan unavailable, coverage unproven: {result.reason}")
    unused = {
        (str(finding.path).replace("\\", "/"), finding.name)
        for finding in result.symbols
        if finding.confidence is Confidence.EXACT
    }
    return UnconsumedExportVerdict(find_unconsumed(root, unused))


def main() -> int:
    """Print the live set and fail until it is empty."""
    verdict = run_gate()
    stream = sys.stdout if verdict.is_clean else sys.stderr
    stream.write(verdict.report() + "\n")
    return 0 if verdict.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
