"""Production modules must obtain UTC time via :func:`aeat.core.time.now`.

Rule
----
No production module under ``src/aeat/`` may call ``datetime.now(UTC)``
or ``datetime.now(tz=UTC)`` inline. All call-sites delegate to
:func:`aeat.core.time._clock.now` so the production clock is uniform
and traceable.

Exclusions (permanent)
----------------------
- ``test_*.py`` files: test suites exercise clock behaviour directly.
- ``src/aeat/core/time/_clock.py``: the canonical implementation itself.
- ``src/aeat/adapters/persistence/storage/envelope/_repository_test_suite.py``:
  shared test-suite helper (treated as test infrastructure).
- ``src/aeat/tests/secure_sql.py``: test-support module.

Documented escape-hatch pattern
-------------------------------
Conditional defaults of the shape
``if now is not None else datetime.now(...)`` are permitted on
constructor / helper signatures that already accept an injectable clock
argument named ``now``. The enclosing function's signature carries the
propagation contract; the inline call is the documented fallback when
the caller passes nothing.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = pathlib.Path(__file__).parent.parent
_CLOCK_MODULE = _SRC_ROOT / "core" / "time" / "_clock.py"
_TEST_INFRA_MODULES: frozenset[pathlib.Path] = frozenset(
    {
        _SRC_ROOT / "adapters" / "persistence" / "storage" / "envelope" / "_repository_test_suite.py",
        _SRC_ROOT / "tests" / "secure_sql.py",
    },
)
_ESCAPE_HATCH_PATTERN = re.compile(
    r"if\s+now\s+is\s+not\s+None\s+else\s+datetime\.now\s*\(",
)
_VIOLATION_PATTERNS: tuple[str, ...] = (
    "datetime.now(UTC)",
    "datetime.now(tz=UTC)",
)


def _is_excluded(path: pathlib.Path) -> bool:
    if path.name.startswith("test_") or "tests" in path.parts:
        return True
    if path in _TEST_INFRA_MODULES:
        return True
    try:
        path.relative_to(_CLOCK_MODULE.parent)
        return path.name == _CLOCK_MODULE.name
    except ValueError:
        return False


def _collect_violations() -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline clock call."""
    repo_root = _SRC_ROOT.parent.parent
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if _is_excluded(path):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern in _VIOLATION_PATTERNS:
                if pattern not in line:
                    continue
                code_part = line.split("#")[0]
                if _ESCAPE_HATCH_PATTERN.search(code_part):
                    continue
                pattern_idx = code_part.find(pattern)
                if pattern_idx > 0:
                    pre = code_part[:pattern_idx].rstrip()
                    if pre and pre[-1] in ('"', "'"):
                        continue
                rel = path.relative_to(repo_root).as_posix()
                violations.append(f"{rel}:{lineno}")
                break
    return violations


def test_no_inline_datetime_now_utc() -> None:
    """Production modules MUST route UTC time through :func:`now`."""
    violations = _collect_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline datetime.now(UTC) call(s) outside the canonical clock module:\n  {joined}\n\n"
            "Replace each call with now() from aeat.core.time. The only permitted\n"
            "inline pattern is the documented escape hatch:\n"
            "    timestamp = now if now is not None else datetime.now(UTC)\n"
            "on signatures that already accept an injectable ``now`` argument.",
        )
