"""Refuse development-progress censuses and engine-live switches in production.

Product behavior must follow live registry and capability boundaries.  A module-level
collection labelled as stub/implemented/ignored progress, or a Settings field that
turns one named engine "live", makes shipped code depend on a development campaign.
Those declarations drift as soon as capability work lands.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
SHIPPED_ROOT: Final[Path] = _REPO_ROOT / "src" / "cadrumo"
_PROGRESS_WORDS: Final[tuple[str, ...]] = (
    "STUB",
    "IMPLEMENTED",
    "UNIMPLEMENTED",
    "IGNORED",
    "NOT_YET",
)
_PROGRESS_DOCSTRING_MARKERS: Final[tuple[str, ...]] = (
    "DECLARED, NOT YET REACHED",
    "IMPLEMENTED, NOT YET REACHED",
)


def _assigned_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    if len(targets) == 1 and isinstance(targets[0], ast.Name):
        return targets[0].id
    return None


def production_metastate(root: Path) -> list[str]:
    """Return development-relative declarations found in shipped modules."""
    findings: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            docstring = ast.get_docstring(node, clean=False) or ""
            marker = next((value for value in _PROGRESS_DOCSTRING_MARKERS if value in docstring), None)
            if marker is None:
                continue
            name = "<module>" if isinstance(node, ast.Module) else node.name
            findings.append(
                f"{relative}:{getattr(node, 'lineno', 1)}: development-status declaration {name} ({marker})",
            )
        for node in tree.body:
            if isinstance(node, ast.Assign | ast.AnnAssign):
                name = _assigned_name(node)
                if name and name.isupper() and any(word in name for word in _PROGRESS_WORDS):
                    findings.append(f"{relative}:{node.lineno}: progress census {name}")
            if not isinstance(node, ast.ClassDef) or node.name != "Settings":
                if not isinstance(node, ast.ClassDef) or not node.name.endswith("Authority"):
                    continue
                for member in node.body:
                    if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                        name = member.target.id
                        if name.startswith("_") and name.endswith("_gaps"):
                            findings.append(f"{relative}:{member.lineno}: authority review residue {name}")
                continue
            for member in node.body:
                if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                    name = member.target.id
                    if name.endswith("_engine_live"):
                        findings.append(f"{relative}:{member.lineno}: engine rollout switch {name}")
    return sorted(findings)


def main() -> int:
    """Print violations and fail when production knows development progress."""
    findings = production_metastate(SHIPPED_ROOT)
    for finding in findings:
        print(finding)
    if findings:
        print("\nDelete development metastate; derive behavior at the owning product capability boundary.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
