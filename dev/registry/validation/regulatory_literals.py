"""Validate regulatory-looking literals embedded in modelo-conditional branches."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from dev.quality.unread_inputs import report_unread

PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo"
REGISTRY_PACKAGE_ROOT = PACKAGE_ROOT / "domain" / "calculations" / "registry"


@dataclass(frozen=True, slots=True, order=True)
class RegulatoryLiteralFinding:
    """One modelo branch that also fixes a numeric product value in code."""

    module: str
    symbol: str
    modelo_codes: tuple[str, ...]
    literals: tuple[int | float, ...]


def _enclosing_symbols(tree: ast.Module) -> dict[int, str]:
    spans: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            spans.append((node.lineno, node.end_lineno or node.lineno, node.name))
    spans.sort(key=lambda item: item[1] - item[0])
    mapping: dict[int, str] = {}
    for start, end, name in spans:
        for line in range(start, end + 1):
            mapping.setdefault(line, name)
    return mapping


def _modelo_members(node: ast.AST) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                f"M{child.args[0].value}"
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "Modelo"
                and len(child.args) == 1
                and isinstance(child.args[0], ast.Constant)
                and isinstance(child.args[0].value, str)
            }
        )
    )


def _numeric_literals(node: ast.AST) -> tuple[int | float, ...]:
    return tuple(
        sorted(
            {
                child.value
                for child in ast.walk(node)
                if isinstance(child, ast.Constant)
                and isinstance(child.value, int | float)
                and not isinstance(child.value, bool)
                and child.value not in {0, 1}
            }
        )
    )


def _candidate_modules(package_root: Path, registry_root: Path) -> Iterator[Path]:
    registry = registry_root.resolve()
    for path in sorted(package_root.rglob("*.py")):
        resolved = path.resolve()
        if resolved.is_relative_to(registry) or "tests" in path.parts or path.name == "conftest.py":
            continue
        yield path


def derive_regulatory_literal_findings(
    package_root: Path = PACKAGE_ROOT,
    registry_root: Path = REGISTRY_PACKAGE_ROOT,
) -> tuple[RegulatoryLiteralFinding, ...]:
    """Derive every modelo branch that also embeds a non-trivial numeric literal."""
    findings: set[RegulatoryLiteralFinding] = set()
    unread: list[str] = []
    for path in _candidate_modules(package_root, registry_root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as error:
            unread.append(f"{path}: {type(error).__name__}: {error}")
            continue
        symbols = _enclosing_symbols(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.If | ast.Match):
                continue
            condition = node.test if isinstance(node, ast.If) else node.subject
            modelos = _modelo_members(condition)
            literals = _numeric_literals(condition)
            if modelos and literals:
                findings.add(
                    RegulatoryLiteralFinding(
                        module=path.relative_to(package_root.parent.parent).as_posix(),
                        symbol=symbols.get(node.lineno, "<module>"),
                        modelo_codes=modelos,
                        literals=literals,
                    )
                )
    report_unread(
        "modelo regulatory literal scan",
        "a regulatory literal inside an unread modelo branch is absent from these findings",
        unread,
    )
    return tuple(sorted(findings))


__all__ = ["RegulatoryLiteralFinding", "derive_regulatory_literal_findings"]
