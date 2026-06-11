"""Real-behavior contract tests for browser timeout constants.

Asserts that ``_VISIBLE_PROBE_TIMEOUT_MS`` and ``_ELEMENT_WAIT_TIMEOUT_MS``
are named constants in ``_renta_web_open.py`` and that the bare integer
literals they replace (``2_000`` and ``10_000``) no longer appear as
argument-position literals in the functions that drove the extraction.
The tests parse the real source AST so they catch future regression
without live browser access.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_RENTA_MODULE = "aeat.adapters.outbound.aeat.sede._renta_web_open"
_SEDE_DIR = Path(__file__).parent.parent
_RENTA_SOURCE = (_SEDE_DIR / "_renta_web_open.py").read_text(encoding="utf-8")


def test_visible_probe_timeout_constant_value() -> None:
    """``_VISIBLE_PROBE_TIMEOUT_MS`` equals 2 000 ms (short fast-path probe)."""

    mod = importlib.import_module(_RENTA_MODULE)

    assert mod._VISIBLE_PROBE_TIMEOUT_MS == 2_000


def test_element_wait_timeout_constant_value() -> None:
    """``_ELEMENT_WAIT_TIMEOUT_MS`` equals 10 000 ms (standard form-interaction budget)."""

    mod = importlib.import_module(_RENTA_MODULE)

    assert mod._ELEMENT_WAIT_TIMEOUT_MS == 10_000


def _arg_int_literals(source: str) -> list[tuple[int, int]]:
    """Return ``(lineno, value)`` for every integer literal passed as a
    keyword-argument named ``timeout`` or ``timeout_ms`` in *source*."""

    tree = ast.parse(source)
    results: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg in ("timeout", "timeout_ms") and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, int):
                    results.append((keyword.value.lineno, keyword.value.value))
    return results


def test_no_bare_2000_timeout_literal_in_renta_web_open() -> None:
    """No ``timeout=2_000`` call-site literal remains in ``_renta_web_open.py``.

    Anti-tautology: the check scans the real AST; if someone re-introduces
    ``timeout=2_000`` the test fails immediately.
    """

    offenders = [
        f"_renta_web_open.py:{lineno}: bare timeout literal {value}"
        for lineno, value in _arg_int_literals(_RENTA_SOURCE)
        if value == 2_000
    ]
    assert offenders == [], "Bare 2_000 timeout literals found; use _VISIBLE_PROBE_TIMEOUT_MS instead:\n" + "\n".join(
        offenders,
    )


def test_no_bare_10000_timeout_literal_in_renta_web_open() -> None:
    """No ``timeout=10_000`` call-site literal remains in ``_renta_web_open.py``.

    Anti-tautology: the check scans the real AST; if someone re-introduces
    ``timeout=10_000`` the test fails immediately.
    """

    offenders = [
        f"_renta_web_open.py:{lineno}: bare timeout literal {value}"
        for lineno, value in _arg_int_literals(_RENTA_SOURCE)
        if value == 10_000
    ]
    assert offenders == [], "Bare 10_000 timeout literals found; use _ELEMENT_WAIT_TIMEOUT_MS instead:\n" + "\n".join(
        offenders,
    )
