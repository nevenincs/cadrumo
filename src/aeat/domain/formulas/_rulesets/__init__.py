"""Concrete rulesets shipped with :mod:`aeat.domain.formulas`.

**Ruleset ID grammar.**

All ruleset IDs follow ``modelo_{code}[.{variant}].{year}``, where the
optional ``{variant}`` disambiguates a partial or alternate encoding of
a modelo that also has a canonical full ruleset:

- ``modelo_130.2024`` — canonical, full-year Modelo 130 for 2024.
- ``modelo_130.2025`` — canonical, full-year Modelo 130 for 2025.
- ``modelo_100.summary.2025`` — summary-block partial of Modelo 100
  (Renta); a future ``modelo_100.2025`` carries the full tarifa
  progresiva + deducciones chain.

Formula IDs follow ``{ruleset_id}.{reason}`` where ``{reason}`` is a
``snake_case`` identifier of the derivation (e.g.
``modelo_130.2025.rendimiento_neto``).

**Coverage scope.**

Modelo 130 and Modelo 303 ship both a 2024 and a 2025 ruleset so
pre-2025 quarters remain self-auditable in case a complementaria is
needed. Most other modelos ship the 2024-2026 trail; resolving a
pre-coverage period raises
:exc:`aeat.core.errors.MissingRulesetError` from
:func:`aeat.domain.formulas.get_registry`.

The per-modelo trail for Modelo 130 (RIRPF art. 110), Modelo 115 (RIRPF
art. 100, the 19 % retention rate on arrendamientos urbanos fixed since
2016), and Modelo 123 (LIRPF art. 101.4 and RIRPF art. 90 keeping the
ordinary IRPF capital-income retention rate at 19 %) is unchanged across
2024 → 2025 → 2026, so the year-scoped rulesets are structural clones of
the 2024 master with their own ``effective_from`` / ``effective_to``
windows.

Modelo 390 ships year-scoped 2024 / 2025 / 2026 rulesets. LIVA arts. 90 /
91 / 92 / 102 / 107 / 164 and RIVA art. 71.7 are unchanged across the
three years. Modelo 390 is structurally an annual aggregator of the four
quarterly Modelo 303 filings: the cumulated casillas (95, 96, 100, 101,
108, 109, 662) remain user-supplied and the ruleset only encodes the
algebraic chain (104 = 100+101, 105 = 96-104, 190 = 105+108+109, 191 =
190-662, 192 = clamp_pos(191), 193 = clamp_pos(0-191)). Cumulation is
asserted at the test level, mirroring the Modelo 180 pattern.

Modelo 100 (RENTA) ships full-form 2024 / 2025 / 2026 rulesets at the
default variant slot ``modelo_100.<año>`` alongside the
``modelo_100.summary.2025`` variant. The full-form rulesets aggregate
per-anexo per-año modules from the ``modelo_100/`` sub-package — the
only sub-package within ``_rulesets/``, justified by the 5-10x scale
relative to sibling modelos.
"""

from __future__ import annotations

from .._ruleset import Ruleset
from .modelo_100_2024 import RULESET as MODELO_100_2024
from .modelo_100_2025 import RULESET as MODELO_100_2025
from .modelo_100_2026 import RULESET as MODELO_100_2026
from .modelo_100_summary_2025 import RULESET as MODELO_100_SUMMARY_2025
from .modelo_111_2024 import RULESET as MODELO_111_2024
from .modelo_111_2025 import RULESET as MODELO_111_2025
from .modelo_111_2026 import RULESET as MODELO_111_2026
from .modelo_115_2024 import RULESET as MODELO_115_2024
from .modelo_115_2025 import RULESET as MODELO_115_2025
from .modelo_115_2026 import RULESET as MODELO_115_2026
from .modelo_123_2024 import RULESET as MODELO_123_2024
from .modelo_123_2025 import RULESET as MODELO_123_2025
from .modelo_123_2026 import RULESET as MODELO_123_2026
from .modelo_130_2024 import RULESET as MODELO_130_2024
from .modelo_130_2025 import RULESET as MODELO_130_2025
from .modelo_130_2026 import RULESET as MODELO_130_2026
from .modelo_131_2024 import RULESET as MODELO_131_2024
from .modelo_131_2025 import RULESET as MODELO_131_2025
from .modelo_131_2026 import RULESET as MODELO_131_2026
from .modelo_180_2024 import RULESET as MODELO_180_2024
from .modelo_180_2025 import RULESET as MODELO_180_2025
from .modelo_180_2026 import RULESET as MODELO_180_2026
from .modelo_200_2024 import RULESET as MODELO_200_2024
from .modelo_200_2025 import RULESET as MODELO_200_2025
from .modelo_200_2026 import RULESET as MODELO_200_2026
from .modelo_202_2025 import RULESET as MODELO_202_2025
from .modelo_303_2024 import RULESET as MODELO_303_2024
from .modelo_303_2025 import RULESET as MODELO_303_2025
from .modelo_303_2026 import RULESET as MODELO_303_2026
from .modelo_390_2024 import RULESET as MODELO_390_2024
from .modelo_390_2025 import RULESET as MODELO_390_2025
from .modelo_390_2026 import RULESET as MODELO_390_2026

# Numerically-ascending by modelo code; within a modelo, ascending by
# effective-from year.
ALL_RULESETS: tuple[Ruleset, ...] = (
    MODELO_100_2024,
    MODELO_100_2025,
    MODELO_100_2026,
    MODELO_100_SUMMARY_2025,
    MODELO_111_2024,
    MODELO_111_2025,
    MODELO_111_2026,
    MODELO_115_2024,
    MODELO_115_2025,
    MODELO_115_2026,
    MODELO_123_2024,
    MODELO_123_2025,
    MODELO_123_2026,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_131_2024,
    MODELO_131_2025,
    MODELO_131_2026,
    MODELO_180_2024,
    MODELO_180_2025,
    MODELO_180_2026,
    MODELO_200_2024,
    MODELO_200_2025,
    MODELO_200_2026,
    MODELO_202_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2024,
    MODELO_390_2025,
    MODELO_390_2026,
)

__all__ = [
    "ALL_RULESETS",
    "MODELO_100_2024",
    "MODELO_100_2025",
    "MODELO_100_2026",
    "MODELO_100_SUMMARY_2025",
    "MODELO_111_2024",
    "MODELO_111_2025",
    "MODELO_111_2026",
    "MODELO_115_2024",
    "MODELO_115_2025",
    "MODELO_115_2026",
    "MODELO_123_2024",
    "MODELO_123_2025",
    "MODELO_123_2026",
    "MODELO_130_2024",
    "MODELO_130_2025",
    "MODELO_130_2026",
    "MODELO_131_2024",
    "MODELO_131_2025",
    "MODELO_131_2026",
    "MODELO_180_2024",
    "MODELO_180_2025",
    "MODELO_180_2026",
    "MODELO_200_2024",
    "MODELO_200_2025",
    "MODELO_200_2026",
    "MODELO_202_2025",
    "MODELO_303_2024",
    "MODELO_303_2025",
    "MODELO_303_2026",
    "MODELO_390_2024",
    "MODELO_390_2025",
    "MODELO_390_2026",
]
