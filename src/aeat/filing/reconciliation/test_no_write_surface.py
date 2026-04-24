"""Layer 3 structural write-guard for the reconciliation subpackage.

Walks every ``.py`` file under this package and asserts none contains
forbidden tokens enumerated in the adjacent fixture file. The fixture
is a plain-text sidecar so no forbidden token has to appear in any
importable Python source - not in the records, not in the comparator,
not in the test that enforces the contract. The test therefore covers
itself without whitelisting its own path.

Mirrors the Phase 1 grep guard under
``src/aeat/remote/test_no_write_surface.py``; each subpackage owns
its own guard so a future contributor adding a new file under either
tree picks up the right discipline by colocation.

Coverage:

1. No module contains a forbidden Playwright-mutating fragment.
2. No module contains a forbidden call-context verb invocation.
3. No module pairs ``requests.`` / ``session.`` / ``Request(... method=...)``
   with a forbidden mutating HTTP verb.
4. No module materialises the forbidden write-mode literal in any form.
5. No symbol in the sealed public ``__all__`` tuple matches any
   forbidden prefix.
6. The fixture file lives as a plain-text sidecar, not as a Python
   module; the test asserts this so a refactor cannot accidentally
   convert it into importable source.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from . import __all__ as reconciliation_public_api

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


_RECONCILIATION_ROOT: Final[Path] = Path(__file__).resolve().parent
_FIXTURE_PATH: Final[Path] = _RECONCILIATION_ROOT / "_no_write_surface_fixture.txt"


def _load_fixture() -> dict[str, list[str]]:
    """Parse the fixture file into typed forbidden-token buckets."""
    buckets: dict[str, list[str]] = {
        "prefix": [],
        "call_verb": [],
        "playwright_fragment": [],
        "http_verb": [],
        "literal_mode_write_parts": [],
    }
    for raw in _FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "literal_mode_write_parts":
            buckets[key].extend(part.strip() for part in value.split(","))
        elif key in buckets:
            buckets[key].append(value)
    return buckets


_FIXTURE = _load_fixture()


def _iter_module_py_files() -> list[Path]:
    return sorted(path for path in _RECONCILIATION_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def test_no_playwright_fragments() -> None:
    """Every module is free of the Playwright-mutating fragments."""
    fragments = _FIXTURE["playwright_fragment"]
    offenders: list[tuple[str, int, str, str]] = []
    for path in _iter_module_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.casefold()
            for fragment in fragments:
                if fragment.casefold() in lowered:
                    offenders.append((str(path), lineno, fragment, line))
    assert offenders == [], f"forbidden Playwright fragments in aeat.filing.reconciliation: {offenders!r}"


def test_no_call_context_write_verbs() -> None:
    """No module has a forbidden verb in a function-call context."""
    verbs = _FIXTURE["call_verb"]
    verb_re = re.compile(
        rf"\b({'|'.join(re.escape(v) for v in verbs)})\s*\(",
        re.IGNORECASE,
    )
    offenders: list[tuple[str, int, str]] = []
    for path in _iter_module_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if verb_re.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], f"forbidden call-context verbs in aeat.filing.reconciliation: {offenders!r}"


def test_no_mutating_http_verbs() -> None:
    """No module carries a forbidden HTTP verb in a mutating context."""
    verbs = _FIXTURE["http_verb"]
    verb_group = "|".join(re.escape(v) for v in verbs)
    verb_re = re.compile(
        rf"(requests|session)\.({verb_group})\b|urllib\.request\.Request\([^)]*method=[^)]*({verb_group})",
        re.IGNORECASE,
    )
    offenders: list[tuple[str, int, str]] = []
    for path in _iter_module_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if verb_re.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], f"forbidden HTTP verbs in aeat.filing.reconciliation: {offenders!r}"


def test_no_write_mode_literal() -> None:
    """No module materialises the forbidden mutating-mode literal."""
    parts = _FIXTURE["literal_mode_write_parts"]
    if len(parts) < 3:
        pytest.fail("fixture missing literal_mode_write_parts entries")
    key, sep, value = parts[0], parts[1], parts[2]
    # Compose the two forbidden shapes at runtime; the full string
    # therefore never materialises in any Python source.
    forbidden_kwarg = f'{key}{sep}"{value}"'
    forbidden_typed = f'{key}: Literal["{value}"]'
    offenders: list[tuple[str, str]] = []
    for path in _iter_module_py_files():
        source = path.read_text(encoding="utf-8")
        normalised = re.sub(r"\s+", "", source).casefold()
        for candidate in (forbidden_kwarg, forbidden_typed):
            needle = re.sub(r"\s+", "", candidate).casefold()
            if needle in normalised:
                offenders.append((str(path), candidate))
    assert offenders == [], f"forbidden mutating-mode literal in aeat.filing.reconciliation: {offenders!r}"


def test_public_api_rejects_write_verb_prefixes() -> None:
    """No symbol in the sealed public tuple uses a forbidden prefix."""
    prefixes = _FIXTURE["prefix"]
    prefix_re = re.compile(rf"^({'|'.join(re.escape(p) for p in prefixes)})", re.IGNORECASE)
    offenders = [name for name in reconciliation_public_api if prefix_re.match(name)]
    assert offenders == [], f"public API exposes forbidden names: {offenders!r}"


def test_fixture_file_exists_as_sidecar() -> None:
    """The fixture lives as a plain-text sidecar, not as a Python module."""
    assert _FIXTURE_PATH.exists()
    assert _FIXTURE_PATH.suffix != ".py"
