"""A Spanish calendar date or year is read from ``today_madrid``, never from the UTC clock.

``now()`` reports the UTC instant, whose date is still yesterday's for up to two
hours every Spanish night. A default year, a register's today or a search
window's end taken from ``now().year`` or ``now().date()`` therefore lands on the
wrong side of a year or day boundary in that window, so every such read goes
through :func:`cadrumo.core.time.clock.today_madrid`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parents[4]
_CLOCK = Path("cadrumo/core/time/clock.py")


def _reads_utc_civil_date(node: ast.Attribute) -> bool:
    """Return whether ``node`` is ``now().year`` or ``now().date``."""
    return (
        node.attr in {"year", "date"}
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "now"
    )


def utc_civil_date_reads(src: Path) -> list[str]:
    """List every ``now().year`` and ``now().date`` read in shipped sources under ``src``."""
    found: list[str] = []
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(src)
        if "tests" in relative.parts or relative == _CLOCK:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        found.extend(
            f"{relative.as_posix()}:{node.lineno}"
            for node in ast.walk(module)
            if isinstance(node, ast.Attribute) and _reads_utc_civil_date(node)
        )
    return found


def test_no_shipped_module_reads_the_civil_date_from_the_utc_clock() -> None:
    assert utc_civil_date_reads(_SRC) == []


@pytest.mark.parametrize("read", ["now().year", "now().date()"])
def test_a_planted_utc_civil_date_read_is_found(tmp_path: Path, read: str) -> None:
    module = tmp_path / "cadrumo" / "application" / "defaults.py"
    module.parent.mkdir(parents=True)
    module.write_text(f"def default_year():\n    return {read}\n", encoding="utf-8")
    (tmp_path / "cadrumo" / "application" / "tests").mkdir()
    (tmp_path / "cadrumo" / "application" / "tests" / "test_defaults.py").write_text(
        f"def test_it():\n    assert {read}\n", encoding="utf-8"
    )

    assert utc_civil_date_reads(tmp_path) == ["cadrumo/application/defaults.py:2"]
