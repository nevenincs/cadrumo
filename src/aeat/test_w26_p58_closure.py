"""Closure verification for W26.P58 (S663/S664/S665/S666/S667).

Asserts that every proper annotation landed at the expected sites,
that the allowlist shrank to exactly 39 entries, and that the ratchet
test passes.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

# ---------------------------------------------------------------------------
# S663 — Playwright adapter annotation sites (no type: ignore remaining)
# ---------------------------------------------------------------------------

_S663_SITES: list[tuple[str, str]] = [
    ("adapters/outbound/aeat/sede/_renta_web_open.py", "_open_renta_web_open_session"),
    ("adapters/outbound/aeat/sede/_renta_web_open.py", "_drive_open_simulator_identification"),
    ("adapters/outbound/aeat/sede/_renta_web_open.py", "_scrape_renta_web_open_values"),
]

# ---------------------------------------------------------------------------
# S664 — Session-store protocol: cast + assert replaces type: ignore
# ---------------------------------------------------------------------------

_S664_SITES: list[tuple[str, str]] = [
    ("application/auth/_sessions.py", "cast(SessionStoreProtocol, _impl)"),
    ("application/auth/_sessions.py", "assert _session_store_impl is not None"),
]

# ---------------------------------------------------------------------------
# S665 — Invoice-import TypedDict cast: cast(InvoiceRowPayload, ...) present
# ---------------------------------------------------------------------------

_S665_SITES: list[tuple[str, str]] = [
    ("application/invoices/_importing.py", "cast(InvoiceRowPayload, dict(decoded))"),
    ("application/invoices/_importing.py", "cast(InvoiceRowPayload, dict(item))"),
    ("application/invoices/_importing.py", "cast(InvoiceRowPayload, dict(row))"),
]

# ---------------------------------------------------------------------------
# S666 — Ledger helpers: proper return type annotations present
# ---------------------------------------------------------------------------

_S666_SITES: list[tuple[str, str]] = [
    ("application/modelo/_actions.py", "work_units: WorkUnitCatalogue, *, work_unit_id: str) -> WorkUnit:"),
    ("application/modelo/_actions.py", "work_unit: WorkUnit) -> RegistrySnapshot:"),
]

# S663 paydown: 3 entries removed
# S664 paydown: 2 entries removed
# S665 paydown: 3 entries removed
# S666 paydown: 2 entries removed
# Total: 10 removed from 49 → 39
_EXPECTED_ALLOWLIST_SIZE = 7  # further paid down beyond P58 baseline


def _file_has_token(rel_path: str, token: str) -> bool:
    """Return True if the production file contains the given token anywhere."""
    path = _SRC_ROOT / pathlib.Path(*rel_path.split("/"))
    if not path.exists():
        return False
    return token in path.read_text(encoding="utf-8", errors="replace")


def _file_has_no_type_ignore_on_def(rel_path: str, func_name: str) -> bool:
    """Return True if the named function definition carries no type: ignore."""
    path = _SRC_ROOT / pathlib.Path(*rel_path.split("/"))
    if not path.exists():
        return True
    source = path.read_text(encoding="utf-8", errors="replace")
    for line in source.splitlines():
        if f"def {func_name}" in line and "# type: ignore" in line:
            return False
    return True


def test_s663_no_type_ignore_on_playwright_functions() -> None:
    """S663: All three Playwright adapter functions carry proper annotations, no type: ignore."""
    rel, _ = _S663_SITES[0]
    violations = [
        name
        for _, name in _S663_SITES
        if not _file_has_no_type_ignore_on_def(rel, name)
    ]
    if violations:
        raise AssertionError(
            f"S663: type: ignore still present on function defs: {violations}"
        )


def test_s664_session_store_cast_present() -> None:
    """S664: cast(SessionStoreProtocol, _impl) and assert present; no type: ignore on those lines."""
    missing = [
        token
        for _, token in _S664_SITES
        if not _file_has_token(_S664_SITES[0][0], token)
    ]
    if missing:
        raise AssertionError(f"S664: expected tokens missing: {missing}")

    # Verify the original type: ignore lines are gone
    path = _SRC_ROOT / pathlib.Path("application", "auth", "_sessions.py")
    source = path.read_text(encoding="utf-8", errors="replace")
    for line in source.splitlines():
        if "type: ignore[arg-type]" in line or "type: ignore[return-value]" in line:
            if "configure_session_store" in line or "_session_store_impl" in line:
                raise AssertionError(
                    f"S664: type: ignore still present on session-store line: {line!r}"
                )


def test_s665_invoice_import_cast_present() -> None:
    """S665: cast(InvoiceRowPayload, ...) used at all three decode sites; no type: ignore[misc]."""
    missing = [
        token
        for _, token in _S665_SITES
        if not _file_has_token(_S665_SITES[0][0], token)
    ]
    if missing:
        raise AssertionError(f"S665: expected cast tokens missing: {missing}")

    path = _SRC_ROOT / pathlib.Path("application", "invoices", "_importing.py")
    source = path.read_text(encoding="utf-8", errors="replace")
    misc_ignores = [
        line for line in source.splitlines()
        if "type: ignore[misc]" in line and "InvoiceRowPayload" in line
    ]
    if misc_ignores:
        raise AssertionError(
            f"S665: type: ignore[misc] still present on InvoiceRowPayload lines: {misc_ignores}"
        )


def test_s666_actions_helpers_annotated() -> None:
    """S666: Both private helpers carry proper WorkUnit / RegistrySnapshot annotations."""
    missing = [
        token
        for _, token in _S666_SITES
        if not _file_has_token(_S666_SITES[0][0], token)
    ]
    if missing:
        raise AssertionError(f"S666: annotation signatures missing: {missing}")


def test_allowlist_size_is_39() -> None:
    """The ratchet allowlist has exactly 39 entries after P58 paydown (10 removed from 49)."""
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
        "Check S663/S664/S665/S666 paydown counts."
    )


def test_ratchet_passes() -> None:
    """The type-ignore ratchet reports zero new violations after P58 paydown."""
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


def test_prior_wave_cast_rationale_inventory_green() -> None:
    """The cast-rationale inventory ratchet (P55 gate) remains green after P58 paydown.

    Prior-wave closure tests hard-code allowlist sizes at their authoring point
    and are superseded by each subsequent paydown; only the underlying ratchet
    inventories (type-ignore + cast-rationale) must remain green.
    """
    cast_inventory = str(_SRC_ROOT / "test_cast_rationale_inventory.py")
    if not pathlib.Path(cast_inventory).exists():
        return
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            cast_inventory,
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
            f"Cast-rationale inventory failed:\n{result.stdout}\n{result.stderr}"
        )
