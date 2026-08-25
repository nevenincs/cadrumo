"""The operator numeric value-oracle is grounded in real AEAT figures.

The operator relays computed casilla values; whether those values are correct is
reconciled against an authoritative external oracle, never hand-computed from the
registry formula under test (``aeat-quality-gates``). For Modelo
100 that oracle already exists and is bundled: JSON payloads captured from AEAT's
official Renta WEB Open simulator carry ``expected_by_casilla_id`` - AEAT's own
computed casilla figures. This test asserts that oracle is real and consumable:
every captured AEAT figure is a well-formed money value for a Modelo 100 casilla
the registry declares ``input_kind == "computed"`` with legal/source grounding, so
the operator's numeric dimension has a genuine AEAT reconciliation target. The
value-level registry-vs-AEAT parity comparison itself is the calc engine's Renta
WEB Open parity mechanism; this is its operator-eval-surface counterpart.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources import bundled_path, resources

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_REPLAY_DIR = bundled_path("corpus", "parity_replays", "renta_web_open")


def _oracle_payloads() -> list[Path]:
    return list(scan_directory(_REPLAY_DIR, pattern="modelo-100-*.json"))


def _m100_computed_grounded_ids() -> dict[str, bool]:
    rev = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A").revision
    casillas = list(rev.casillas.values()) if isinstance(rev.casillas, dict) else list(rev.casillas)
    result: dict[str, bool] = {}
    for casilla in casillas:
        for key in (getattr(casilla, "number", None), getattr(casilla, "id", None)):
            if key is None:
                continue
            computed = getattr(casilla, "input_kind", None) == "computed"
            grounded = bool(getattr(casilla, "legal_refs", ()) and getattr(casilla, "source_refs", ()))
            result[str(key)] = computed and grounded
    return result


def test_renta_web_open_oracle_payloads_are_bundled() -> None:
    payloads = _oracle_payloads()
    assert payloads, "no Renta WEB Open (Modelo 100) AEAT oracle payloads are bundled"


def test_every_aeat_oracle_figure_is_a_grounded_computed_m100_casilla() -> None:
    computed_grounded = _m100_computed_grounded_ids()
    failures: list[str] = []
    checked = 0
    for payload_path in _oracle_payloads():
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        expected = payload.get("expected_by_casilla_id", {})
        for casilla_id, figure in expected.items():
            checked += 1
            # The AEAT figure is a well-formed money value (the external oracle).
            try:
                Decimal(str(figure))
            except (ArithmeticError, ValueError):
                failures.append(f"{payload_path.name}: casilla {casilla_id} AEAT figure {figure!r} is not a number")
                continue
            # ...for a casilla the registry declares computed AND grounded, so the
            # operator's relayed value has a real AEAT reconciliation target.
            if not computed_grounded.get(str(casilla_id), False):
                failures.append(
                    f"{payload_path.name}: AEAT oracle casilla {casilla_id} is not a grounded computed M100 casilla",
                )
    assert checked, "no AEAT oracle figures were checked"
    assert not failures, "operator numeric oracle is not grounded:\n" + "\n".join(failures)
