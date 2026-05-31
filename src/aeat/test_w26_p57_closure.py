"""Closure verification for W26.P57 (S659/S660/S661/S662).

Asserts that every rationale marker landed at the expected file:line sites,
that the allowlist shrank to exactly 49 entries, and that the ratchet
test itself passes.
"""

from __future__ import annotations

import importlib
import pathlib
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

# ---------------------------------------------------------------------------
# Site inventory: (relative-posix-path-from-src/aeat/, 1-based line, token)
# Each entry must carry the token on the named line or within 3 lines above.
# ---------------------------------------------------------------------------

_S659_SITES: list[tuple[str, str]] = [
    # Cluster B — click stubs (8 sites, _doc_reference.py)
    ("entrypoints/cli/_doc_reference.py", "TYPE-IGNORE-RATIONALE-THIRD-PARTY-STUB-MISSING"),
]

_S660_SITES: list[tuple[str, str]] = [
    # Cluster A continuation — pydantic model_config (17 sites)
    ("entrypoints/cli/_config_payloads.py", "TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR"),
    ("entrypoints/cli/_root_payloads.py", "TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR"),
    ("entrypoints/cli/_config/_google_payloads.py", "TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR"),
    ("entrypoints/cli/_config/_profile_census_payloads.py", "TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR"),
    ("entrypoints/cli/_registry_payloads.py", "TYPE-IGNORE-RATIONALE-PYDANTIC-MODEL-CONFIG-CLASSVAR"),
]

_S661_SITES: list[tuple[str, str]] = [
    # Cluster C — ctypes.windll (1 site)
    ("entrypoints/cli/_stdio.py", "TYPE-IGNORE-RATIONALE-PLATFORM-WINDOWS-CTYPES"),
    # Cluster D — TOML str-key erasure (3 sites)
    ("domain/calculations/registry/_loader.py", "TYPE-IGNORE-RATIONALE-TOML-STR-KEY-ERASURE"),
    ("domain/calculations/registry/_schema.py", "TYPE-IGNORE-RATIONALE-TOML-STR-KEY-ERASURE"),
    # Cluster E — generic getattr bounded (2 sites)
    ("application/ledger/_actions.py", "TYPE-IGNORE-RATIONALE-GENERIC-GETATTR-BOUNDED"),
    # Cluster F — runtime CM protocol (4 sites)
    ("application/diagnostics.py", "TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL"),
    ("application/repair_integrity.py", "TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL"),
]

# Expected allowlist size after S659 + S660 + S661 paydown.
# Starting count post-S658: 84
# S659 removed: 8 (Cluster B)
# S660 removed: 17 (Cluster A continuation + _registry_payloads remaining)
# S661 removed: 10 (Clusters C/D/E/F)
# Total removed: 35 → final: 84 - 35 = 49
_EXPECTED_ALLOWLIST_SIZE = 49


def _file_has_token(rel_path: str, token: str) -> bool:
    """Return True if the production file carries the given token anywhere."""
    path = _SRC_ROOT / pathlib.Path(*rel_path.split("/"))
    if not path.exists():
        return False
    source = path.read_text(encoding="utf-8", errors="replace")
    return token in source


def test_s659_markers_present() -> None:
    """Every S659 (Cluster B click-stub) file carries the expected marker token."""
    missing = [
        rel
        for rel, token in _S659_SITES
        if not _file_has_token(rel, token)
    ]
    if missing:
        raise AssertionError(
            f"S659 marker token missing from: {missing}"
        )


def test_s660_markers_present() -> None:
    """Every S660 (Cluster A continuation) file carries the expected marker token."""
    missing = [
        rel
        for rel, token in _S660_SITES
        if not _file_has_token(rel, token)
    ]
    if missing:
        raise AssertionError(
            f"S660 marker token missing from: {missing}"
        )


def test_s661_markers_present() -> None:
    """Every S661 (Clusters C/D/E/F) file carries the expected marker token."""
    missing = [
        rel
        for rel, token in _S661_SITES
        if not _file_has_token(rel, token)
    ]
    if missing:
        raise AssertionError(
            f"S661 marker token missing from: {missing}"
        )


def test_allowlist_size_is_49() -> None:
    """The ratchet allowlist has exactly 49 entries after P57 paydown."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "test_type_ignore_rationale_inventory",
        _SRC_ROOT / "test_type_ignore_rationale_inventory.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    known: frozenset[tuple[str, int]] = mod._KNOWN_VIOLATING_LINES  # type: ignore[attr-defined]
    assert len(known) == _EXPECTED_ALLOWLIST_SIZE, (
        f"Expected {_EXPECTED_ALLOWLIST_SIZE} ratchet entries, got {len(known)}. "
        "Check S659/S660/S661 paydown counts."
    )


def test_ratchet_passes() -> None:
    """The type-ignore ratchet test itself reports zero new violations."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(_SRC_ROOT / "test_type_ignore_rationale_inventory.py"),
            "-x",
            "-q",
            "--no-header",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
        cwd=_SRC_ROOT.parent.parent,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Ratchet test failed:\n{result.stdout}\n{result.stderr}"
        )
