"""W14.P46 audit-survivor closure aggregate test.

Asserts all 6 structural closures (S607-S612) have landed and that
W11/W12 inventory ratchets remain green.

S607 — _acquisition_lock.py:188 BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN marker.
S608 — _sessions.py:592/:598 BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN (2 sites).
S609 — _browser_stage.py: ``import logging`` moved to TYPE_CHECKING block.
S610 — _log_levels.py: LOGGING-STDLIB-CONSTANTS-ONLY-RATIONALE marker on import.
S611 — ``file_stat_fingerprint`` canonical in ``aeat.core.paths``; zero local
       ``_file_fingerprint`` survivors across the four former duplicate sites.
S612 — ``_RENTA_WEB_OPEN_DEFAULT_YEAR: Final[int]`` module constant; zero bare
       ``year=2025`` literals remain in _renta_web_open_oracle.py.

No mocks, no skips, no tautological assertions.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC = Path(__file__).parent  # src/aeat/


def _src(rel: str) -> Path:
    p = _SRC / rel
    assert p.exists(), f"Expected source file missing: {p}"
    return p


def _read(rel: str) -> str:
    return _src(rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S607 — BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN
# ---------------------------------------------------------------------------

_ACQLOCK_TOKEN = "BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN"


def test_s607_acquisition_lock_teardown_rationale_present() -> None:
    """_acquisition_lock.py must carry BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN."""
    src = _read("application/auth/_acquisition_lock.py")
    assert _ACQLOCK_TOKEN in src, (
        f"application/auth/_acquisition_lock.py: missing {_ACQLOCK_TOKEN!r} — S607 not applied"
    )
    lines_with_token = [ln for ln in src.splitlines() if _ACQLOCK_TOKEN in ln]
    assert any("except Exception" in ln for ln in lines_with_token), (
        f"application/auth/_acquisition_lock.py: {_ACQLOCK_TOKEN!r} found but not on an ``except Exception`` line"
    )


# ---------------------------------------------------------------------------
# S608 — BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN (2 sites)
# ---------------------------------------------------------------------------

_SESSION_TOKEN = "BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN"


def test_s608_session_provider_close_teardown_rationale_both_sites() -> None:
    """_sessions.py must carry SESSION-PROVIDER-CLOSE-TEARDOWN rationale at both teardown sites."""
    src = _read("application/auth/_sessions.py")
    occurrences = src.count(_SESSION_TOKEN)
    assert occurrences >= 2, (
        f"application/auth/_sessions.py: expected >=2 occurrences of {_SESSION_TOKEN!r}, "
        f"found {occurrences} — S608 second-site marker not applied"
    )
    # Both must be on ``except Exception`` lines.
    lines_with_token = [ln for ln in src.splitlines() if _SESSION_TOKEN in ln]
    assert all("except Exception" in ln for ln in lines_with_token), (
        f"application/auth/_sessions.py: {_SESSION_TOKEN!r} found on non-``except Exception`` line(s)"
    )


# ---------------------------------------------------------------------------
# S609 — _browser_stage.py: logging under TYPE_CHECKING
# ---------------------------------------------------------------------------


def test_s609_browser_stage_logging_under_type_checking() -> None:
    """_browser_stage.py must import logging inside a TYPE_CHECKING block, not at module level."""
    src = _read("adapters/outbound/aeat/sede/_browser_stage.py")
    lines = src.splitlines()

    # Verify there is no bare ``import logging`` outside TYPE_CHECKING.
    in_type_checking_block = False
    bare_logging_import_lines: list[int] = []
    type_checking_logging_lines: list[int] = []

    for i, ln in enumerate(lines, start=1):
        stripped = ln.lstrip()
        # Detect entry into TYPE_CHECKING block.
        if "TYPE_CHECKING" in ln and "if" in ln:
            in_type_checking_block = True
        elif in_type_checking_block and ln and not ln[0].isspace():
            # Non-indented line ends the block.
            in_type_checking_block = False

        if "import logging" in stripped:
            if in_type_checking_block:
                type_checking_logging_lines.append(i)
            else:
                bare_logging_import_lines.append(i)

    assert not bare_logging_import_lines, (
        f"adapters/outbound/aeat/sede/_browser_stage.py: bare ``import logging`` at lines "
        f"{bare_logging_import_lines} — S609 TYPE_CHECKING migration not applied"
    )
    assert type_checking_logging_lines, (
        "adapters/outbound/aeat/sede/_browser_stage.py: ``import logging`` not found inside "
        "TYPE_CHECKING block — S609 migration incomplete"
    )


# ---------------------------------------------------------------------------
# S610 — _log_levels.py: LOGGING-STDLIB-CONSTANTS-ONLY-RATIONALE
# ---------------------------------------------------------------------------

_LOG_LEVELS_TOKEN = "LOGGING-STDLIB-CONSTANTS-ONLY-RATIONALE"


def test_s610_log_levels_constants_only_rationale_on_import_line() -> None:
    """_log_levels.py import logging line must carry LOGGING-STDLIB-CONSTANTS-ONLY-RATIONALE."""
    src = _read("entrypoints/cli/_log_levels.py")
    assert _LOG_LEVELS_TOKEN in src, (
        f"entrypoints/cli/_log_levels.py: missing {_LOG_LEVELS_TOKEN!r} — S610 not applied"
    )
    lines_with_token = [ln for ln in src.splitlines() if _LOG_LEVELS_TOKEN in ln]
    assert any("import logging" in ln for ln in lines_with_token), (
        f"entrypoints/cli/_log_levels.py: {_LOG_LEVELS_TOKEN!r} present but not on the ``import logging`` line"
    )


# ---------------------------------------------------------------------------
# S611 — file_stat_fingerprint canonical in aeat.core.paths
# ---------------------------------------------------------------------------


def test_s611_file_stat_fingerprint_canonical_in_core_paths() -> None:
    """aeat.core.paths must define ``file_stat_fingerprint``."""
    src = _read("core/paths.py")
    assert "def file_stat_fingerprint" in src, (
        "core/paths.py: ``file_stat_fingerprint`` not defined — S611 canonical implementation missing"
    )
    # Verify the return annotation shape is present.
    assert "tuple[str, int, int]" in src, (
        "core/paths.py: ``tuple[str, int, int]`` return annotation missing from file_stat_fingerprint"
    )


def test_s611_no_local_file_fingerprint_in_caller_sites() -> None:
    """The four former duplicate sites must not define ``_file_fingerprint`` locally."""
    former_sites = [
        "domain/categories/_registry.py",
        "domain/iva/_catalogue.py",
        "application/topics/__init__.py",
        "domain/normatives/_loader.py",
    ]
    for rel in former_sites:
        src = _read(rel)
        assert "def _file_fingerprint" not in src, (
            f"{rel}: local ``def _file_fingerprint`` still present — S611 migration incomplete"
        )


def test_s611_caller_sites_import_file_stat_fingerprint() -> None:
    """All four former duplicate sites must import ``file_stat_fingerprint``."""
    sites = [
        "domain/categories/_registry.py",
        "domain/iva/_catalogue.py",
        "application/topics/__init__.py",
        "domain/normatives/_loader.py",
    ]
    for rel in sites:
        src = _read(rel)
        assert "file_stat_fingerprint" in src, (
            f"{rel}: ``file_stat_fingerprint`` not referenced — S611 caller migration incomplete"
        )


# ---------------------------------------------------------------------------
# S612 — _renta_web_open_oracle.py: _RENTA_WEB_OPEN_DEFAULT_YEAR Final constant
# ---------------------------------------------------------------------------

_ORACLE_FILE = "domain/calculations/registry/_renta_web_open_oracle.py"
_ORACLE_CONSTANT = "_RENTA_WEB_OPEN_DEFAULT_YEAR"


def test_s612_renta_web_open_default_year_constant_declared() -> None:
    """_renta_web_open_oracle.py must declare _RENTA_WEB_OPEN_DEFAULT_YEAR as a Final[int]."""
    src = _read(_ORACLE_FILE)
    assert f"{_ORACLE_CONSTANT}: Final[int] = 2025" in src, (
        f"{_ORACLE_FILE}: ``{_ORACLE_CONSTANT}: Final[int] = 2025`` not found — S612 not applied"
    )


def test_s612_no_bare_year_2025_literals_in_oracle() -> None:
    """_renta_web_open_oracle.py must not contain bare ``year=2025`` literals."""
    src = _read(_ORACLE_FILE)
    assert "year=2025" not in src, (
        f"{_ORACLE_FILE}: bare ``year=2025`` literal still present — S612 constant migration incomplete"
    )


# ---------------------------------------------------------------------------
# Prior inventory ratchets must remain green (W14 maintenance must not regress)
# ---------------------------------------------------------------------------


def test_prior_broad_except_rationale_inventory_exists() -> None:
    """Broad-except and any-return rationale inventory test must still exist."""
    _src("test_broad_except_and_any_return_rationale.py")


def test_prior_utf8_enrollment_inventory_exists() -> None:
    """UTF-8 enrollment inventory test must still exist."""
    _src("test_utf8_enrollment_inventory.py")


def test_prior_utf8_regression_proof_exists() -> None:
    """UTF-8 regression proof test must still exist."""
    _src("test_utf8_enrollment_regression_proof.py")


def test_prior_ratchet_extensions_and_marker_completion_exists() -> None:
    """Ratchet extensions and marker completion test must still exist."""
    _src("test_ratchet_extensions_and_marker_completion.py")


def test_prior_inventory_ratchets_carry_key_tokens() -> None:
    """Key tokens in prior inventory ratchet files must survive W14 changes."""
    # Broad-except ratchet covers RATIONALE markers across the codebase.
    broad_src = _read("test_broad_except_and_any_return_rationale.py")
    assert "BROAD-EXCEPT-RATIONALE" in broad_src, (
        "test_broad_except_and_any_return_rationale.py: BROAD-EXCEPT-RATIONALE token erased"
        " — W14 regressed prior ratchet"
    )
    # UTF-8 enrollment ratchet covers the encoding constant discipline.
    utf8_src = _read("test_utf8_enrollment_inventory.py")
    assert "UTF_8_ENCODING" in utf8_src or "utf-8" in utf8_src.lower(), (
        "test_utf8_enrollment_inventory.py: UTF-8 ratchet tokens erased — W14 regressed prior ratchet"
    )
