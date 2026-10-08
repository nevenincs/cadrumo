"""Read declared pytest test paths and effective marker configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from cadrumo.core.toml import read_toml
from cadrumo.core.type_guards import is_str_keyed_dict
from dev._paths import UTF_8

_UTF_8: Final[str] = UTF_8


def _pytest_ini_options(root: Path) -> dict[str, object]:
    """Return the ``[tool.pytest.ini_options]`` table, empty when the project declares none."""
    table = read_toml(root / "pyproject.toml", error_factory=RuntimeError)
    for key in ("tool", "pytest", "ini_options"):
        child = table.get(key)
        if not is_str_keyed_dict(child):
            return {}
        table = child
    return table


def configured_testpaths(root: Path) -> tuple[str, ...]:
    """Return the ``testpaths`` a pathless invocation inherits."""
    testpaths = _pytest_ini_options(root).get("testpaths")
    if not isinstance(testpaths, list):
        return ()
    return tuple(str(item) for item in testpaths)


def configured_marker_expression(root: Path) -> str | None:
    """Return the default ``-m`` expression from addopts, if any."""
    captured = _pytest_ini_options(root).get("addopts")
    if not isinstance(captured, str):
        return None
    inner = re.search(r"-m\s+'([^']+)'", captured) or re.search(r'-m\s+"([^"]+)"', captured)
    if inner is None:
        return None
    marker_expression = inner.group(1)
    return marker_expression if isinstance(marker_expression, str) else None
