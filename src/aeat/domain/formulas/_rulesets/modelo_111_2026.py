"""Modelo 111 ruleset covering the full 2026 fiscal year.

Structural clone of :mod:`modelo_111_2025`. The 19 % retention rates
on premios en metálico (LIRPF art. 101.7 implemented via RIRPF art.
99) and on rendimientos del arrendamiento / ganancias gravadas (LIRPF
art. 101.2 implemented via RIRPF art. 100.1) are unchanged across the
2024 → 2025 → 2026 trail. RD 253/2025 — the only 2025 modification of
the RIRPF — touched art. 69 (information obligations), not arts.
99-100. The RIRPF consolidated text (last update 2026-02-28) and the
LIRPF consolidated text (last update 2026-03-21) carry no 2025 / 2026
amendment notice that touches the rate-bearing articles.

The separate ruleset file simplifies future divergence (e.g., if a
later RD introduces a per-rubro rate change) without disturbing the
2024 / 2025 surfaces. The rule-delta manifest at
``.vault/reference/2026-111-rule-delta.md`` documents the 2024 →
2025 → 2026 trail with BOE citations.

Issue `#318` (per-modelo Tier-L bar for Modelo 111). Mirrors the M130
reference implementation under issue `#321`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...modelos import ModeloCode
from .._ruleset import ParameterTable, ParameterValue, Ruleset
from .modelo_111_2025 import (
    _CASILLAS as _CASILLAS_2025,
)
from .modelo_111_2025 import (
    _CITATIONS as _CITATIONS_2025,
)
from .modelo_111_2025 import (
    _FORMULAS as _FORMULAS_2025,
)

_EFFECTIVE_FROM = date(2026, 1, 1)
_EFFECTIVE_TO = date(2026, 12, 31)


_PARAMETERS = ParameterTable(
    entries={
        "irpf.premios_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.19"),
            ),
        ),
        "irpf.ganancias_arrendamiento_rate": (
            ParameterValue(
                effective_from=_EFFECTIVE_FROM,
                effective_to=_EFFECTIVE_TO,
                value=Decimal("0.19"),
            ),
        ),
    }
)


RULESET: Ruleset = Ruleset(
    ruleset_id="modelo_111.2026",
    modelo=ModeloCode.MODELO_111,
    effective_from=_EFFECTIVE_FROM,
    effective_to=_EFFECTIVE_TO,
    casillas=_CASILLAS_2025,
    formulas=_FORMULAS_2025,
    parameters=_PARAMETERS,
    legal_citations=_CITATIONS_2025,
)
