"""Fail while a published exact-unused name has no production importer."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

from ..audit.unreachable_code import UnreachableCodeOutcome, run_unreachable_code_scan

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PACKAGE_ROOT = REPO_ROOT / "src" / "cadrumo"


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


def _imported_pairs(tree: ast.Module) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            tail = node.module.rsplit(".", 1)[-1]
            pairs.update((tail, alias.name) for alias in node.names)
    return pairs


def _audit_key(path: Path, root: Path) -> str:
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
        if "__pycache__" in path.parts or "tests" in path.parts or path.name.startswith("test_"):
            continue
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            unread.append(path.relative_to(root).as_posix())
    if unread:
        raise RuntimeError(f"unconsumed-export scan unreadable for {len(unread)} file(s): {unread}")

    consumed = set().union(*(_imported_pairs(tree) for tree in trees.values())) if trees else set()
    return tuple(
        sorted(
            UnconsumedExport(path.relative_to(root).as_posix(), name)
            for path, tree in trees.items()
            for name in _declared_exports(tree)
            if (path.stem, name) not in consumed and (_audit_key(path, root), name) in unused
        ),
    )


def run_gate(root: Path = _PACKAGE_ROOT) -> UnconsumedExportVerdict:
    """Measure the live package, refusing an unavailable reachability scan."""
    result = run_unreachable_code_scan(REPO_ROOT)
    if result.outcome is UnreachableCodeOutcome.ERROR:
        raise RuntimeError(f"reachability scan unavailable, coverage unproven: {result.reason}")
    unused = {(str(finding.path).replace("\\", "/"), finding.name) for finding in result.symbols}
    return UnconsumedExportVerdict(find_unconsumed(root, unused))


def main() -> int:
    """Print the live set and fail until it is empty."""
    verdict = run_gate()
    stream = sys.stdout if verdict.is_clean else sys.stderr
    stream.write(verdict.report() + "\n")
    return 0 if verdict.is_clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
