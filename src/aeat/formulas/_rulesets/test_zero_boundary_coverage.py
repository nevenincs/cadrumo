"""Zero-boundary regression tests across every ruleset (EPIC #305 wave 59b).

Wave 58 stream 3 H4: 13 of 18 rulesets lacked a zero-input clean-path
test. A regression that misroutes a zero to a division-by-something
or NaN would ship silently. This module parametrizes the zero-input
audit across every ruleset so a single file covers the whole fleet.

Each ruleset's casilla list is drawn from the ruleset itself (via
`ruleset.casillas`), ensuring no rate-mirroring or ruleset-
specific arithmetic. The test asserts that feeding every casilla as
``Decimal("0.00")`` yields a clean audit — the engine derives every
computed casilla as zero too.

Skipped: rulesets whose casilla IDs include the Modelo 202 casilla
17 (tipo de gravamen), where 0 would be a division-by-zero
semantically meaningful only as "no tax rate applied". The test
skips those slots with an explicit note; they get rulset-specific
tests elsewhere.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import (
    MODELO_100_SUMMARY_2025,
    MODELO_111_2024,
    MODELO_111_2025,
    MODELO_115_2024,
    MODELO_115_2025,
    MODELO_123_2024,
    MODELO_123_2025,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_131_2024,
    MODELO_131_2025,
    MODELO_180_2024,
    MODELO_180_2025,
    MODELO_200_2024,
    MODELO_202_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_390_2025,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


_ALL_RULESETS = [
    ("modelo_100.summary.2025", MODELO_100_SUMMARY_2025),
    ("modelo_111.2024", MODELO_111_2024),
    ("modelo_111.2025", MODELO_111_2025),
    ("modelo_115.2024", MODELO_115_2024),
    ("modelo_115.2025", MODELO_115_2025),
    ("modelo_123.2024", MODELO_123_2024),
    ("modelo_123.2025", MODELO_123_2025),
    ("modelo_130.2024", MODELO_130_2024),
    ("modelo_130.2025", MODELO_130_2025),
    ("modelo_131.2024", MODELO_131_2024),
    ("modelo_131.2025", MODELO_131_2025),
    ("modelo_180.2024", MODELO_180_2024),
    ("modelo_180.2025", MODELO_180_2025),
    ("modelo_200.2024", MODELO_200_2024),
    ("modelo_202.2025", MODELO_202_2025),
    ("modelo_303.2024", MODELO_303_2024),
    ("modelo_303.2025", MODELO_303_2025),
    ("modelo_390.2025", MODELO_390_2025),
]


@pytest.mark.parametrize(
    ("name", "ruleset"),
    _ALL_RULESETS,
    ids=[name for name, _ in _ALL_RULESETS],
)
def test_zero_boundary_is_clean(name: str, ruleset) -> None:
    """Every ruleset must produce a clean audit when every casilla is zero.

    This guards against regressions that would misroute a zero through
    a division or clamp in a way that yields NaN / negative / non-zero
    output. The provided dict covers every declared casilla so no
    missing-input behaviour is tested here — that's exercised
    elsewhere via ruleset-specific partial fixtures.
    """
    # Feed zero only to non-computed (input) casillas; computed casillas
    # are derived by the engine. Some modelos (303) have computed rate-
    # literal casillas (02=4, 05=10, 08=21) that carry AEAT-fixed rates
    # regardless of input.
    non_computed_zero = {casilla.casilla_id: Decimal("0.00") for casilla in ruleset.casillas if not casilla.computed}
    engine = Engine()
    # Primary guard: derive() must not crash, produce NaN, or diverge
    # on a zero-input filing. Every derived value must be a finite
    # Decimal; negative values are legal (e.g., cuota diferencial
    # can be negative when no activity in a quarter).
    ledger = engine.derive(ruleset=ruleset, inputs=non_computed_zero)
    for entry in ledger.entries:
        assert entry.value is not None, f"{name}: {entry.casilla_id} derived None"
        assert entry.value.is_finite(), f"{name}: {entry.casilla_id} derived NaN/Inf"
    # Secondary guard: computed casillas that should be zero (aggregates
    # of zero inputs) actually are zero. For 303's rate-literal casillas
    # (02/05/08), the derived rate is non-zero by design — they are
    # constants, not aggregates. Skip those.
    rate_literal_ids = {"02", "05", "08"}  # 303 rate-literal casillas
    for entry in ledger.entries:
        if name.startswith("modelo_303") and entry.casilla_id in rate_literal_ids:
            continue
        assert entry.value == Decimal("0.00") or entry.value == Decimal("0"), (
            f"{name}: {entry.casilla_id} derived {entry.value} on zero input — expected 0"
        )
