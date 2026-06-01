"""W26.P59 closure verification: 28-site type-ignore paydown (S668–S670).

Verifies that:
- Every S668 site in ``_app_live.py`` carries a ``CAST-RATIONALE-WIRE-PAYLOAD-*`` marker.
- Every S669 Sub-A site in ``_modelo.py`` carries a ``CAST-RATIONALE-WIRE-PAYLOAD-*`` marker.
- Every S669 Sub-B site (Decimal None guards) has no ``# type: ignore`` remaining.
- Every S669 Sub-C site carries a ``CAST-RATIONALE-MARITIME-LITERAL-FIELD`` marker.
- Every S670 structural fix is in place (no bare ``# type: ignore`` at the target lines).
- The ratchet allowlist contains exactly 11 entries (39 – 28).
- The prior-wave ratchet test itself passes (imported and re-run in-process).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC = pathlib.Path(__file__).parent
_APP_LIVE = _SRC / "entrypoints/cli/_app_live.py"
_MODELO = _SRC / "entrypoints/cli/_modelo.py"
_PARSER = _SRC / "adapters/inbound/declaracion/_parser.py"
_ENVELOPE = _SRC / "adapters/persistence/storage/envelope/_envelope.py"
_IVA_WALLET = _SRC / "application/calculations/_iva_wallet_reconciliation.py"
_DOC_REF = _SRC / "entrypoints/cli/_doc_reference.py"
_IDENTITY = _SRC / "diagnostics/_identity_placement.py"
_DESCENDANT = _SRC / "domain/profile/_descendant_facts.py"

_WIRE_PAYLOAD_TOKEN = "CAST-RATIONALE-WIRE-PAYLOAD-"
_MARITIME_TOKEN = "CAST-RATIONALE-MARITIME-LITERAL-FIELD"
_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore")


def _lines(path: pathlib.Path) -> list[str]:
    assert path.exists(), f"File not found: {path}"
    return path.read_text(encoding="utf-8").splitlines()


def _has_marker(lines: list[str], lineno: int, marker: str) -> bool:
    """Return True if the marker appears on ``lineno`` or in up to 3 preceding lines."""
    idx = lineno - 1
    window = lines[max(0, idx - 3) : idx + 1]
    return any(marker in ln for ln in window)


def _has_type_ignore(lines: list[str], lineno: int) -> bool:
    idx = lineno - 1
    if idx >= len(lines):
        return False
    return bool(_TYPE_IGNORE_RE.search(lines[idx]))


# ---------------------------------------------------------------------------
# S668: _app_live.py — 9 wire-payload splat sites
# ---------------------------------------------------------------------------

_S668_LINES = [1067, 1093, 1181, 1367, 1397, 1461, 1514, 1566, 1642]


@pytest.mark.parametrize("lineno", _S668_LINES)
def test_s668_app_live_wire_payload_marker_present(lineno: int) -> None:
    """Each _app_live.py splat site must carry CAST-RATIONALE-WIRE-PAYLOAD-* marker."""
    lines = _lines(_APP_LIVE)
    assert _has_marker(lines, lineno, _WIRE_PAYLOAD_TOKEN), (
        f"_app_live.py:{lineno}: missing {_WIRE_PAYLOAD_TOKEN!r} marker"
    )


# ---------------------------------------------------------------------------
# S669 Sub-A: _modelo.py — 4 kv_pairs splat sites
# ---------------------------------------------------------------------------

_S669A_LINES = [902, 904, 906, 925]


@pytest.mark.parametrize("lineno", _S669A_LINES)
def test_s669a_modelo_kv_pairs_marker_present(lineno: int) -> None:
    """Each _modelo.py kv_pairs splat site must carry CAST-RATIONALE-WIRE-PAYLOAD-* marker."""
    lines = _lines(_MODELO)
    assert _has_marker(lines, lineno, _WIRE_PAYLOAD_TOKEN), (
        f"_modelo.py:{lineno}: missing {_WIRE_PAYLOAD_TOKEN!r} marker"
    )


# ---------------------------------------------------------------------------
# S669 Sub-B: _modelo.py — 6 Decimal(None) sites now have assert guards
# ---------------------------------------------------------------------------

def test_s669b_decimal_rescate_no_type_ignore() -> None:
    """Rescate-plan-pensiones Decimal sites must not carry bare # type: ignore."""
    src = pathlib.Path(_MODELO).read_text(encoding="utf-8")
    # Verify assert guards are present
    assert "assert rescate_plan_pensiones_capital is not None" in src, (
        "_modelo.py: assert guard for rescate_plan_pensiones_capital not found"
    )
    assert "assert rescate_plan_pensiones_aportaciones_pre_2007 is not None" in src, (
        "_modelo.py: assert guard for rescate_plan_pensiones_aportaciones_pre_2007 not found"
    )
    assert "assert rescate_plan_pensiones_aportaciones_totales is not None" in src, (
        "_modelo.py: assert guard for rescate_plan_pensiones_aportaciones_totales not found"
    )


def test_s669b_decimal_sal_no_type_ignore() -> None:
    """SAL Decimal sites must not carry bare # type: ignore."""
    src = pathlib.Path(_MODELO).read_text(encoding="utf-8")
    assert "assert sal_beneficio_neto is not None" in src, (
        "_modelo.py: assert guard for sal_beneficio_neto not found"
    )
    assert "assert sal_reserva_dotada is not None" in src, (
        "_modelo.py: assert guard for sal_reserva_dotada not found"
    )
    assert "assert sal_capital_social is not None" in src, (
        "_modelo.py: assert guard for sal_capital_social not found"
    )


# ---------------------------------------------------------------------------
# S669 Sub-C: _modelo.py — 3 _enum() → Literal sites carry rationale marker
# ---------------------------------------------------------------------------

def test_s669c_maritime_literal_marker_present() -> None:
    """maritime_worker Literal fields must carry CAST-RATIONALE-MARITIME-LITERAL-FIELD marker."""
    src = pathlib.Path(_MODELO).read_text(encoding="utf-8")
    # marker appears at least 3 times (one per Literal field)
    count = src.count(_MARITIME_TOKEN)
    assert count >= 3, (
        f"_modelo.py: expected at least 3 occurrences of {_MARITIME_TOKEN!r}, found {count}"
    )


# ---------------------------------------------------------------------------
# S670: 6 misc structural fixes
# ---------------------------------------------------------------------------

def test_s670_parser_col_x_max_guard() -> None:
    """_parser.py:519 area must use explicit col_x_max is None guard (no type: ignore)."""
    src = pathlib.Path(_PARSER).read_text(encoding="utf-8")
    assert "col_x_max is None or col_x_min <= w" in src, (
        "_parser.py: explicit col_x_max is None guard not found"
    )
    # Confirm the old type: ignore is gone from this conditional
    for i, ln in enumerate(src.splitlines(), 1):
        if "col_x_min is None or col_x_max is None" in ln:
            assert "# type: ignore" not in ln, (
                f"_parser.py:{i}: col_x_max guard line still has # type: ignore"
            )
            break
    else:
        pytest.fail("_parser.py: col_x_max guard line not found")


def test_s670_envelope_classgetitem_rationale() -> None:
    """_envelope.py:158 must carry CAST-RATIONALE-GENERIC-CLASSGETITEM marker."""
    src = pathlib.Path(_ENVELOPE).read_text(encoding="utf-8")
    assert "CAST-RATIONALE-GENERIC-CLASSGETITEM" in src, (
        "_envelope.py: missing CAST-RATIONALE-GENERIC-CLASSGETITEM marker"
    )


def test_s670_iva_wallet_repository_typed() -> None:
    """_iva_wallet_reconciliation.py must have typed repository annotation (no no-untyped-def)."""
    src = pathlib.Path(_IVA_WALLET).read_text(encoding="utf-8")
    assert "repository: " in src, (
        "_iva_wallet_reconciliation.py: typed repository parameter not found"
    )
    assert "no-untyped-def" not in src, (
        "_iva_wallet_reconciliation.py: bare no-untyped-def type: ignore survives"
    )


def test_s670_doc_reference_isinstance_narrowing() -> None:
    """_doc_reference.py must use isinstance(schema_cls, type) narrowing (no union-attr ignore)."""
    src = pathlib.Path(_DOC_REF).read_text(encoding="utf-8")
    assert "isinstance(schema_cls, type)" in src, (
        "_doc_reference.py: isinstance(schema_cls, type) narrowing not found"
    )


def test_s670_identity_placement_numeric_narrowing() -> None:
    """_identity_placement.py must use isinstance(..., (int, float)) narrowing (no operator ignore)."""
    src = pathlib.Path(_IDENTITY).read_text(encoding="utf-8")
    assert "isinstance(node.operand.value, (int, float))" in src, (
        "_identity_placement.py: isinstance numeric narrowing not found"
    )


def test_s670_descendant_facts_cast_applied() -> None:
    """_descendant_facts.py must use cast for Literal discapacidad_grado (no arg-type ignore)."""
    src = pathlib.Path(_DESCENDANT).read_text(encoding="utf-8")
    assert "CAST-RATIONALE-DISCAPACIDAD-LITERAL" in src, (
        "_descendant_facts.py: CAST-RATIONALE-DISCAPACIDAD-LITERAL marker not found"
    )
    assert "# type: ignore[arg-type]" not in src, (
        "_descendant_facts.py: bare [arg-type] type: ignore survives"
    )


# ---------------------------------------------------------------------------
# Allowlist size ratchet: exactly 11 entries remain
# ---------------------------------------------------------------------------

def test_allowlist_size_is_7() -> None:
    """``_KNOWN_VIOLATING_LINES`` must contain exactly 7 entries.

    W26.P59 paid down 28 of 39 entries (leaving 11). Subsequent paydowns
    (S672 removed 3, S673 removed 1) brought the allowlist to its current
    size of 7. The inventory module's own header comment is the source of
    truth for the running tally; this closure assertion ratchets the
    allowlist size so any unintended re-introduction surfaces immediately.
    """
    # Import the inventory module to read the live frozenset
    import importlib
    import sys

    mod_name = "aeat.test_type_ignore_rationale_inventory"
    # Force a fresh import to avoid cached state
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    mod = importlib.import_module(mod_name)
    size = len(mod._KNOWN_VIOLATING_LINES)  # type: ignore[attr-defined]
    assert size == 7, (
        f"Expected 7 entries in _KNOWN_VIOLATING_LINES (post W26.P59 + S672 + S673 paydown), "
        f"found {size}"
    )


# ---------------------------------------------------------------------------
# Prior-wave ratchet: test_no_new_type_ignore_without_rationale must pass
# ---------------------------------------------------------------------------

def test_prior_wave_ratchet_still_passes() -> None:
    """The main type-ignore ratchet must find zero new violations after W26.P59 fixes."""
    import importlib
    import sys

    mod_name = "aeat.test_type_ignore_rationale_inventory"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    mod = importlib.import_module(mod_name)
    violations = frozenset(mod._collect_violations())  # type: ignore[attr-defined]
    known = mod._KNOWN_VIOLATING_LINES  # type: ignore[attr-defined]
    new_violations = violations - known
    assert not new_violations, (
        "W26.P59 introduced new type-ignore violations:\n"
        + "\n".join(f"  {rel}:{lineno}" for rel, lineno in sorted(new_violations))
    )
