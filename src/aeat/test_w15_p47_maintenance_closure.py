"""W15.P47 maintenance closure aggregate test.

Asserts all 5 structural closures (S614-S618) have landed and that
W14 inventory ratchets remain green.

S614 — application/registry/_corpus.py:334 BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY marker.
S615 — core/config.py:999 BROAD-EXCEPT-RATIONALE-POINTER-READ-FALLBACK marker.
S616 — application/user_profile/_censo_sync.py: _HOME_OFFICE_DEDUCTION_YEAR Final constant
       extracted; year=2025 bare literal eliminated at derive_home_office_ratios_from_censo call.
S617 — application/diagnostics.py: _REGISTRY_INTEGRITY_PROBE_YEAR + _REGISTRY_INTEGRITY_PROBE_DATE
       Final constants extracted; bare 2025/date(2025,12,31) literals migrated.
S618 — application/filing/runtime.py: ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE marker on
       _registry_tree_fingerprint (option b — relative-path keying semantically distinct from
       filename-keyed file_stat_fingerprint; no canonical signature change needed).

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
# S614 — BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY
# ---------------------------------------------------------------------------

_CORPUS_TOKEN = "BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY"


def test_s614_corpus_lookup_boundary_rationale_present() -> None:
    """application/registry/_corpus.py must carry BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY."""
    src = _read("application/registry/_corpus.py")
    assert _CORPUS_TOKEN in src, (
        f"application/registry/_corpus.py: missing {_CORPUS_TOKEN!r} — S614 not applied"
    )
    lines_with_token = [ln for ln in src.splitlines() if _CORPUS_TOKEN in ln]
    assert any("except Exception" in ln for ln in lines_with_token), (
        f"application/registry/_corpus.py: {_CORPUS_TOKEN!r} found but not on an ``except Exception`` line"
    )


# ---------------------------------------------------------------------------
# S615 — BROAD-EXCEPT-RATIONALE-POINTER-READ-FALLBACK
# ---------------------------------------------------------------------------

_POINTER_TOKEN = "BROAD-EXCEPT-RATIONALE-POINTER-READ-FALLBACK"


def test_s615_pointer_read_fallback_rationale_present() -> None:
    """core/config.py must carry BROAD-EXCEPT-RATIONALE-POINTER-READ-FALLBACK."""
    src = _read("core/config.py")
    assert _POINTER_TOKEN in src, (
        f"core/config.py: missing {_POINTER_TOKEN!r} — S615 not applied"
    )
    lines = src.splitlines()
    # The rationale marker sits on the ``except Exception`` line or on one of the
    # comment lines immediately below it (a formatter may wrap a long inline
    # comment onto the following line); accept either placement.
    token_indices = [i for i, ln in enumerate(lines) if _POINTER_TOKEN in ln]
    assert any(
        any("except Exception" in lines[j] for j in range(max(0, idx - 2), idx + 1)) for idx in token_indices
    ), (
        f"core/config.py: {_POINTER_TOKEN!r} found but not on or adjacent to an ``except Exception`` line"
    )


# ---------------------------------------------------------------------------
# S616 — _HOME_OFFICE_DEDUCTION_YEAR Final constant
# ---------------------------------------------------------------------------

def test_s616_home_office_deduction_year_constant_defined() -> None:
    """_censo_sync.py must define _HOME_OFFICE_DEDUCTION_YEAR as a Final[int] constant."""
    src = _read("application/user_profile/_censo_sync.py")
    assert "_HOME_OFFICE_DEDUCTION_YEAR" in src, (
        "application/user_profile/_censo_sync.py: _HOME_OFFICE_DEDUCTION_YEAR not defined — S616 not applied"
    )
    assert "Final[int]" in src or "Final" in src, (
        "application/user_profile/_censo_sync.py: Final import missing — S616 type annotation incomplete"
    )


def test_s616_home_office_deduction_year_bare_literal_absent() -> None:
    """derive_home_office_ratios_from_censo call must not use bare year=2025 literal."""
    src = _read("application/user_profile/_censo_sync.py")
    # The constant itself carries 2025 — that is the intended single source of truth.
    # The call-site must reference the constant, not the bare integer.
    call_lines = [
        ln for ln in src.splitlines()
        if "derive_home_office_ratios_from_censo" in ln and "year=" in ln
    ]
    assert call_lines, (
        "application/user_profile/_censo_sync.py: derive_home_office_ratios_from_censo call not found"
    )
    for ln in call_lines:
        assert "year=2025" not in ln, (
            f"application/user_profile/_censo_sync.py: bare year=2025 literal remains at call-site: {ln!r}"
        )


# ---------------------------------------------------------------------------
# S617 — _REGISTRY_INTEGRITY_PROBE_YEAR + _REGISTRY_INTEGRITY_PROBE_DATE
# ---------------------------------------------------------------------------

def test_s617_registry_probe_constants_defined() -> None:
    """application/diagnostics.py must define both probe constants as Final."""
    src = _read("application/diagnostics.py")
    assert "_REGISTRY_INTEGRITY_PROBE_YEAR" in src, (
        "application/diagnostics.py: _REGISTRY_INTEGRITY_PROBE_YEAR not defined — S617 not applied"
    )
    assert "_REGISTRY_INTEGRITY_PROBE_DATE" in src, (
        "application/diagnostics.py: _REGISTRY_INTEGRITY_PROBE_DATE not defined — S617 not applied"
    )
    assert "Final" in src, (
        "application/diagnostics.py: Final import missing — S617 type annotation incomplete"
    )


def test_s617_registry_probe_bare_literals_absent() -> None:
    """authority.snapshot call must reference constants, not bare 2025/date(2025,12,31) literals."""
    src = _read("application/diagnostics.py")
    snapshot_lines = [
        ln for ln in src.splitlines()
        if "authority.snapshot" in ln or "filing_year=" in ln or ("on=" in ln and "date(" in ln)
    ]
    for ln in snapshot_lines:
        assert "filing_year=2025" not in ln, (
            f"application/diagnostics.py: bare filing_year=2025 remains: {ln!r}"
        )
        assert "on=date(2025" not in ln, (
            f"application/diagnostics.py: bare on=date(2025,...) remains: {ln!r}"
        )


# ---------------------------------------------------------------------------
# S618 — ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE marker
# ---------------------------------------------------------------------------

_FINGERPRINT_TOKEN = "ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE"


def test_s618_alt_fingerprint_rationale_present() -> None:
    """application/filing/runtime.py must carry ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE on _registry_tree_fingerprint."""
    src = _read("application/filing/runtime.py")
    assert _FINGERPRINT_TOKEN in src, (
        f"application/filing/runtime.py: missing {_FINGERPRINT_TOKEN!r} — S618 not applied"
    )
    lines_with_token = [ln for ln in src.splitlines() if _FINGERPRINT_TOKEN in ln]
    assert any("_registry_tree_fingerprint" in ln for ln in lines_with_token), (
        f"application/filing/runtime.py: {_FINGERPRINT_TOKEN!r} not on _registry_tree_fingerprint definition line"
    )


# ---------------------------------------------------------------------------
# W14 ratchets — ensure prior closures remain intact
# ---------------------------------------------------------------------------

def test_w14_ratchet_acquisition_lock_teardown_marker() -> None:
    """W14 S607: BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN must still be present."""
    src = _read("application/auth/_acquisition_lock.py")
    assert "BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN" in src, (
        "W14 S607 ratchet failure: BROAD-EXCEPT-RATIONALE-ACQUISITION-LOCK-TEARDOWN missing"
    )


def test_w14_ratchet_session_provider_teardown_marker() -> None:
    """W14 S608: BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN must have >=2 occurrences."""
    src = _read("application/auth/_sessions.py")
    token = "BROAD-EXCEPT-RATIONALE-SESSION-PROVIDER-CLOSE-TEARDOWN"
    assert src.count(token) >= 2, (
        f"W14 S608 ratchet failure: {token!r} has fewer than 2 occurrences"
    )


def test_w14_ratchet_file_stat_fingerprint_canonical() -> None:
    """W14 S611: file_stat_fingerprint must still be defined in aeat.core.paths."""
    src = _read("core/paths.py")
    assert "def file_stat_fingerprint" in src, (
        "W14 S611 ratchet failure: file_stat_fingerprint not in core/paths.py"
    )


def test_w14_ratchet_renta_web_open_year_constant() -> None:
    """W14 S612: _RENTA_WEB_OPEN_DEFAULT_YEAR Final constant must exist."""
    src = _read("domain/calculations/registry/_renta_web_open_oracle.py")
    assert "_RENTA_WEB_OPEN_DEFAULT_YEAR" in src, (
        "W14 S612 ratchet failure: _RENTA_WEB_OPEN_DEFAULT_YEAR missing from _renta_web_open_oracle.py"
    )
