"""Layer 3 structural write-guard for the ``aeat filing reconcile`` CLI.

Narrowly scoped to the new ``_reconcile.py`` source + its ``test_reconcile.py``
test file introduced by #239 Phase 4. The sibling commands inside
``src/aeat/cli/filing/__init__.py`` (``complementaria submit``,
``build_complementaria_cmd``, ``submit_complementaria_cmd`` …) and
``test_filing_cli.py`` intentionally speak the ``submit`` / ``enviar`` /
``send`` vocabulary because they route through the audited submission
engine in :mod:`aeat.submission`; they are **not** covered by this
guard. The reconcile surface must stay read-only by construction.

Mirrors the sidecar-fixture pattern already established by
``src/aeat/filing/reconciliation/test_no_write_surface.py`` (#239
Phase 3) and ``src/aeat/remote/test_no_write_surface.py`` (#239
Phase 1). The fixture is a plain-text file so no forbidden token
materialises in any guarded Python source.

Coverage:

1. No guarded module contains a forbidden Playwright-mutating fragment.
2. No guarded module contains a forbidden call-context verb invocation.
3. No guarded module pairs ``requests.`` / ``session.`` /
   ``Request(..., method=...)`` with a forbidden mutating HTTP verb.
4. No guarded module materialises the forbidden write-mode literal.
5. No symbol exported by the reconcile source module (its ``__all__``)
   matches any forbidden prefix.
6. The fixture file lives as a plain-text sidecar, not as a Python
   module.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

from ._reconcile import __all__ as reconcile_public_api

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


_CLI_FILING_ROOT: Final[Path] = Path(__file__).resolve().parent
_FIXTURE_PATH: Final[Path] = _CLI_FILING_ROOT / "_no_write_surface_fixture.txt"


def _guarded_paths() -> list[Path]:
    """Return the narrow set of files this guard walks."""
    return [
        _CLI_FILING_ROOT / "_reconcile.py",
        _CLI_FILING_ROOT / "test_reconcile.py",
    ]


def _load_fixture() -> dict[str, list[str]]:
    """Parse the fixture into typed forbidden-token buckets."""
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


def test_guarded_paths_exist() -> None:
    """Every guarded path is present on disk."""
    missing = [str(path) for path in _guarded_paths() if not path.is_file()]
    assert missing == [], f"guarded files missing: {missing!r}"


def test_no_playwright_fragments() -> None:
    """No guarded module carries a Playwright-mutating fragment."""
    fragments = _FIXTURE["playwright_fragment"]
    offenders: list[tuple[str, int, str, str]] = []
    for path in _guarded_paths():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            lowered = line.casefold()
            for fragment in fragments:
                if fragment.casefold() in lowered:
                    offenders.append((str(path), lineno, fragment, line))
    assert offenders == [], f"forbidden Playwright fragments in aeat.cli.filing reconcile: {offenders!r}"


def test_no_call_context_write_verbs() -> None:
    """No guarded module has a forbidden verb in a function-call context."""
    verbs = _FIXTURE["call_verb"]
    verb_re = re.compile(
        rf"\b({'|'.join(re.escape(v) for v in verbs)})\s*\(",
        re.IGNORECASE,
    )
    offenders: list[tuple[str, int, str]] = []
    for path in _guarded_paths():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if verb_re.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], f"forbidden call-context verbs in aeat.cli.filing reconcile: {offenders!r}"


def test_no_mutating_http_verbs() -> None:
    """No guarded module pairs an HTTP client with a mutating verb."""
    verbs = _FIXTURE["http_verb"]
    verb_group = "|".join(re.escape(v) for v in verbs)
    verb_re = re.compile(
        rf"(requests|session)\.({verb_group})\b|urllib\.request\.Request\([^)]*method=[^)]*({verb_group})",
        re.IGNORECASE,
    )
    offenders: list[tuple[str, int, str]] = []
    for path in _guarded_paths():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if verb_re.search(line):
                offenders.append((str(path), lineno, line))
    assert offenders == [], f"forbidden HTTP verbs in aeat.cli.filing reconcile: {offenders!r}"


def test_no_write_mode_literal() -> None:
    """No guarded module materialises the forbidden mutating-mode literal."""
    parts = _FIXTURE["literal_mode_write_parts"]
    if len(parts) < 3:
        pytest.fail("fixture missing literal_mode_write_parts entries")
    key, sep, value = parts[0], parts[1], parts[2]
    forbidden_kwarg = f'{key}{sep}"{value}"'
    forbidden_typed = f'{key}: Literal["{value}"]'
    offenders: list[tuple[str, str]] = []
    for path in _guarded_paths():
        source = path.read_text(encoding="utf-8")
        normalised = re.sub(r"\s+", "", source).casefold()
        for candidate in (forbidden_kwarg, forbidden_typed):
            needle = re.sub(r"\s+", "", candidate).casefold()
            if needle in normalised:
                offenders.append((str(path), candidate))
    assert offenders == [], f"forbidden mutating-mode literal in aeat.cli.filing reconcile: {offenders!r}"


def test_public_api_rejects_write_verb_prefixes() -> None:
    """No symbol exported by the reconcile module matches a forbidden prefix."""
    prefixes = _FIXTURE["prefix"]
    prefix_re = re.compile(rf"^({'|'.join(re.escape(p) for p in prefixes)})", re.IGNORECASE)
    offenders = [name for name in reconcile_public_api if prefix_re.match(name)]
    assert offenders == [], f"reconcile __all__ exposes forbidden names: {offenders!r}"


def test_fixture_file_exists_as_sidecar() -> None:
    """The fixture lives as a plain-text sidecar, not a Python module."""
    assert _FIXTURE_PATH.exists()
    assert _FIXTURE_PATH.suffix != ".py"
