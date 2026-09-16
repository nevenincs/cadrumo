"""Mechanically find code that may restate the registry support-year authority.

The sweep reads the canonical TOML declaration first, then parses Python syntax and
TOML data.  It intentionally emits candidates rather than claiming every tax-year
literal is wrong: legal vintages, revision identities, and test boundary examples are
valid uses of concrete years.
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.toml import TomlDecodeError, parse_toml

AUTHORITY = Path("src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml")
DEFAULT_ROOTS = (Path("src"), Path("dev"), Path("tests"), Path("test"))
YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
POLICY_WORDS = frozenset(
    {
        "support",
        "supported",
        "filing",
        "coverage",
        "range",
        "floor",
        "horizon",
        "ceiling",
        "year",
        "years",
        "ejercicio",
        "ejercicios",
        "period",
        "periods",
    }
)


@dataclass(frozen=True)
class Finding:
    """One mechanically detected candidate for human classification."""

    path: Path
    line: int
    kind: str
    years: tuple[int, ...]
    context: str


def _canonical_bounds(repo: Path) -> tuple[int, int, int | None]:
    payload = parse_toml((repo / AUTHORITY).read_text(encoding="utf-8"))
    declaration = payload.get("supported_filing_years")
    if not isinstance(declaration, dict):
        raise ValueError("supported_filing_years authority must be a TOML table")
    floor = declaration.get("floor")
    horizon = declaration.get("horizon")
    hard_ceiling = declaration.get("hard_ceiling")
    if (
        not isinstance(floor, int)
        or isinstance(floor, bool)
        or not isinstance(horizon, int)
        or isinstance(horizon, bool)
        or (hard_ceiling is not None and (not isinstance(hard_ceiling, int) or isinstance(hard_ceiling, bool)))
    ):
        raise ValueError("supported_filing_years authority has invalid bounds")
    return floor, horizon, hard_ceiling


def _source_line(lines: list[str], line: int) -> str:
    return lines[line - 1].strip() if 0 < line <= len(lines) else ""


def _names(node: ast.AST) -> set[str]:
    values: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            values.update(re.split(r"_+", child.id.lower()))
        elif isinstance(child, ast.Attribute):
            values.update(re.split(r"_+", child.attr.lower()))
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.update(re.findall(r"[a-z]+", child.value.lower()))
    return values


def _literal_years(node: ast.AST) -> tuple[int, ...]:
    return tuple(
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, int)
        and not isinstance(child.value, bool)
        and 2000 <= child.value <= 2099
    )


def _python_findings(path: Path, repo: Path, canonical: set[int]) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    findings: list[Finding] = []
    for node in ast.walk(tree):
        kind: str | None = None
        years: tuple[int, ...] = ()
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            years = _literal_years(node)
            if len(set(years)) >= 2:
                kind = "enumerated-year-container"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            years = _literal_years(node)
            if years:
                kind = "literal-range-call"
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            years = _literal_years(node)
            words = _names(node)
            if years and words & POLICY_WORDS:
                kind = "policy-named-assignment"
        elif isinstance(node, ast.Compare):
            years = _literal_years(node)
            words = _names(node)
            if years and words & POLICY_WORDS:
                kind = "policy-year-comparison"
        if kind is None:
            continue
        unique = tuple(sorted(set(years)))
        if not unique or not (set(unique) & canonical):
            continue
        line = getattr(node, "lineno", None)
        if not isinstance(line, int):
            continue
        finding = Finding(path.relative_to(repo), line, kind, unique, _source_line(lines, line))
        if finding not in findings:
            findings.append(finding)
    return findings


def _walk_toml(value: object, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], object]]:
    rows: list[tuple[tuple[str, ...], object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(_walk_toml(child, (*prefix, str(key))))
    elif isinstance(value, list):
        rows.append((prefix, value))
        for index, child in enumerate(value):
            rows.extend(_walk_toml(child, (*prefix, str(index))))
    else:
        rows.append((prefix, value))
    return rows


def _toml_findings(path: Path, repo: Path, canonical: set[int]) -> list[Finding]:
    if path.resolve() == (repo / AUTHORITY).resolve():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        payload = parse_toml(text)
    except TomlDecodeError:
        return []
    findings: list[Finding] = []
    for keys, value in _walk_toml(payload):
        words = set(re.findall(r"[a-z]+", "_".join(keys).lower()))
        if not words & POLICY_WORDS:
            continue
        rendered = repr(value)
        years = tuple(sorted({int(year) for year in YEAR_RE.findall(rendered)} & canonical))
        if len(years) < 2:
            continue
        needle = keys[-1] if keys else ""
        line = next((i for i, row in enumerate(text.splitlines(), 1) if needle in row), 1)
        findings.append(Finding(path.relative_to(repo), line, "toml-policy-enumeration", years, ".".join(keys)))
    return findings


def sweep(repo: Path, roots: tuple[Path, ...]) -> list[Finding]:
    """Return candidate policy restatements beneath the requested roots."""
    floor, horizon, _ = _canonical_bounds(repo)
    canonical = set(range(floor, horizon + 1))
    findings: list[Finding] = []
    for root in roots:
        absolute = repo / root
        if not absolute.exists():
            continue
        for path in absolute.rglob("*"):
            if any(part in {".venv", "node_modules", "__pycache__"} for part in path.parts):
                continue
            if path.suffix == ".py":
                findings.extend(_python_findings(path, repo, canonical))
            elif path.suffix == ".toml":
                findings.extend(_toml_findings(path, repo, canonical))
    return sorted(set(findings), key=lambda row: (str(row.path), row.line, row.kind))


def main() -> int:
    """Run the sweep and print a stable, line-oriented candidate report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("roots", nargs="*", type=Path, default=DEFAULT_ROOTS)
    args = parser.parse_args()
    repo = args.repo.resolve()
    floor, horizon, hard_ceiling = _canonical_bounds(repo)
    findings = sweep(repo, tuple(args.roots))
    print(f"authority={AUTHORITY} floor={floor} horizon={horizon} hard_ceiling={hard_ceiling}")
    print(f"candidates={len(findings)}")
    for row in findings:
        years = ",".join(map(str, row.years))
        print(f"{row.path}:{row.line}\t{row.kind}\t[{years}]\t{row.context}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
