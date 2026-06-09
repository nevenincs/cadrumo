"""Ratchet extensions and rationale-marker completion.

Asserts that the following ratchet and marker changes are in place:

(a) dev/ ratchet extension in test_utf8_enrollment_inventory.py and
    dev/quality/relative_imports.py fixed (no bare encoding="utf-8").

(b) _google_drive.py Any-return markers complete (4 sites).

(c) sha256 allowlist commentary present in test_utf8_enrollment_inventory.py.

(d) _stdio.py stdlib-logger rationale present in
    test_any_return_rationale_markers.py.

No mocks, no skips, no tautological assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TESTS_DIR = Path(__file__).parent
_AEAT_DIR = _TESTS_DIR.parent
_REPO_ROOT = _AEAT_DIR.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source(path: Path) -> str:
    assert path.exists(), f"Expected file not found: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# (a) scripts/ ratchet landed and check_relative_imports.py clean
# ---------------------------------------------------------------------------

_UTF8_INVENTORY_TEST = _TESTS_DIR / "test_utf8_enrollment_inventory.py"
_CHECK_REL_IMPORTS = _REPO_ROOT / "dev" / "quality" / "relative_imports.py"


def test_dev_ratchet_exists_in_utf8_inventory() -> None:
    """test_utf8_enrollment_inventory.py must define the dev/ ratchet function."""
    src = _source(_UTF8_INVENTORY_TEST)
    assert "test_no_bare_utf8_literals_in_dev" in src, (
        "test_utf8_enrollment_inventory.py: dev/ ratchet function not found"
    )
    assert "_DEV_ROOT" in src, (
        "test_utf8_enrollment_inventory.py: _DEV_ROOT constant not found — dev/ tree scope not defined"
    )
    assert "_DEV_KNOWN_VIOLATING" in src, (
        "test_utf8_enrollment_inventory.py: _DEV_KNOWN_VIOLATING ratchet set not found"
    )


def test_check_relative_imports_uses_local_utf8_constant() -> None:
    """relative_imports.py must define _UTF_8 constant and not use bare encoding="utf-8"."""
    src = _source(_CHECK_REL_IMPORTS)
    assert '_UTF_8: Final[str] = "utf-8"' in src, "dev/quality/relative_imports.py: _UTF_8 constant not found"
    # The bare literal must not survive outside the constant definition line itself.
    lines_with_bare = [(i + 1, ln) for i, ln in enumerate(src.splitlines()) if 'encoding="utf-8"' in ln]
    assert not lines_with_bare, 'dev/quality/relative_imports.py: bare encoding="utf-8" survived at ' + ", ".join(
        f"line {i}: {ln.strip()!r}" for i, ln in lines_with_bare
    )


# ---------------------------------------------------------------------------
# (b) _google_drive.py Any-return markers (4 sites)
# ---------------------------------------------------------------------------

_GOOGLE_DRIVE = _AEAT_DIR / "adapters/outbound/storage/_google_drive.py"
_GOOGLE_DRIVE_TOKEN = "ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY"
_GOOGLE_DRIVE_FUNCS = (
    "_service_factory",
    "_get_service",
    "_execute",
    "_build_media_body",
)


@pytest.mark.parametrize("func_name", _GOOGLE_DRIVE_FUNCS)
def test_google_drive_any_return_markers_present(func_name: str) -> None:
    """Each -> Any site in _google_drive.py must carry the build-factory rationale marker."""
    lines = _source(_GOOGLE_DRIVE).splitlines()
    matching = [(i + 1, ln) for i, ln in enumerate(lines) if f"def {func_name}(" in ln]
    assert matching, f"_google_drive.py: def {func_name} not found"
    lineno, def_line = matching[0]
    assert _GOOGLE_DRIVE_TOKEN in def_line, (
        f"_google_drive.py:{lineno} def {func_name}: missing {_GOOGLE_DRIVE_TOKEN!r}"
    )


# ---------------------------------------------------------------------------
# (c) sha256 allowlist commentary documented in utf8 inventory test
# ---------------------------------------------------------------------------


def test_sha256_allowlist_sites_documented_in_utf8_inventory() -> None:
    """test_utf8_enrollment_inventory.py must enumerate the 4 sha256 protocol-exempt sites."""
    src = _source(_UTF8_INVENTORY_TEST)
    exempt_files = (
        "_source_profile.py",
        "_iva_wallet_reconciliation.py",
        "_source_resolver.py",
        "_borrador_binding.py",
    )
    for filename in exempt_files:
        assert filename in src, (
            f"test_utf8_enrollment_inventory.py: sha256 allowlist commentary missing reference to {filename!r}"
        )


# ---------------------------------------------------------------------------
# (d) _stdio.py rationale enrolled in test_any_return_rationale_markers.py
# ---------------------------------------------------------------------------

_RATIONALE_INVENTORY = _TESTS_DIR / "test_any_return_rationale_markers.py"


def test_stdio_logger_rationale_enrolled_in_inventory() -> None:
    """test_any_return_rationale_markers.py must contain the _stdio.py stdlib-logger test."""
    src = _source(_RATIONALE_INVENTORY)
    assert "test_stdio_stdlib_logger_rationale_present" in src, (
        "test_any_return_rationale_markers.py: _stdio.py logger rationale test not found"
    )
    assert "_STDIO_MODULE" in src, "test_any_return_rationale_markers.py: _STDIO_MODULE path constant not found"
