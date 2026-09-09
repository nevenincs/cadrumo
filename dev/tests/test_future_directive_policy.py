"""The project admits exactly one ``__future__`` directive.

Every tracked module either carries ``from __future__ import annotations`` or
no future statement at all. A second annotation model in the tree would make
the same source mean different things in different files, so the population is
read from the live git inventory rather than an enumerated list.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Final

import pytest

from .._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ALLOWED_FUTURE_FEATURES: Final[frozenset[str]] = frozenset({"annotations"})

_EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {".git", ".vault", "_build", "build", "dist", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
)


def _tracked_python_files() -> tuple[Path, ...]:
    """Return every tracked Python file, from git rather than a declared list."""
    output = subprocess.check_output(("git", "ls-files", "-z"), cwd=REPO_ROOT, text=False)  # noqa: S607
    paths = {(REPO_ROOT / raw.decode("utf-8")) for raw in output.split(b"\0") if raw}
    return tuple(
        sorted(
            (
                path
                for path in paths
                if path.suffix == ".py" and path.is_file() and not any(part in _EXCLUDED_DIRS for part in path.parts)
            ),
            key=lambda path: path.as_posix(),
        )
    )


def _future_directive_violations(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Return project future imports other than the one supported directive.

    The check reads the AST rather than matching text, so a mention in a
    docstring or a test fixture cannot masquerade as an executable future
    statement.
    """
    violations: list[str] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as error:  # pragma: no cover - unreadable file is its own defect
            violations.append(f"{path}: unreadable: {error}")
            continue
        try:
            tree = ast.parse(source, filename=str(path), mode="exec")
        except SyntaxError as error:
            violations.append(f"{path}:{error.lineno}: SyntaxError: {error.msg}")
            continue
        for statement in tree.body:
            if not isinstance(statement, ast.ImportFrom) or statement.module != "__future__":
                continue
            forbidden = sorted(alias.name for alias in statement.names if alias.name not in _ALLOWED_FUTURE_FEATURES)
            if forbidden:
                relative = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
                violations.append(
                    f"{relative}:{statement.lineno}: unsupported future directive(s): " + ", ".join(forbidden),
                )
    return tuple(sorted(violations))


def test_future_directive_scan_detects_legacy_directives(tmp_path: Path) -> None:
    """A removed future feature cannot re-enter the project unnoticed."""
    source = tmp_path / "legacy_future.py"
    source.write_text(
        "from __future__ import annotations, division\nvalue = 1 / 2\n",
        encoding="utf-8",
    )

    violations = _future_directive_violations((source,))

    assert len(violations) == 1
    assert "unsupported future directive(s): division" in violations[0]


def test_future_directive_scan_accepts_annotations_and_plain_modules(tmp_path: Path) -> None:
    """The established directive and modules without one are both valid."""
    annotated = tmp_path / "annotated.py"
    annotated.write_text("from __future__ import annotations\nvalue: Missing = None\n", encoding="utf-8")
    plain = tmp_path / "plain.py"
    plain.write_text("value = 1\n", encoding="utf-8")

    assert _future_directive_violations((annotated, plain)) == ()


def test_the_scanned_population_is_not_empty() -> None:
    """An empty inventory would make the live assertion below vacuous."""
    assert len(_tracked_python_files()) > 500


def test_live_project_uses_annotations_as_its_only_future_directive() -> None:
    """Every tracked project module must share the one annotation model."""
    assert _future_directive_violations(_tracked_python_files()) == ()
