"""Concrete rulesets shipped with :mod:`aeat.formulas`.

**Ruleset ID grammar.**

All ruleset IDs follow ``modelo_{code}[.{variant}].{year}``, where the
optional ``{variant}`` disambiguates a partial or alternate encoding
of a modelo that also has a canonical full ruleset:

- ``modelo_130.2024``  — canonical, full-year Modelo 130 for 2024.
- ``modelo_130.2025``  — canonical, full-year Modelo 130 for 2025.
- ``modelo_100.summary.2025`` — summary-block partial of Modelo 100
  (Renta); a future ``modelo_100.2025`` would carry the full tarifa
  progresiva + deducciones chain.

Formula IDs follow ``{ruleset_id}.{reason}`` where ``{reason}`` is a
``snake_case`` identifier of the derivation (e.g.
``modelo_130.2025.rendimiento_neto``).

**Coverage scope (wave 42 M1).**

Modelo 130 and Modelo 303 ship both a 2024 and a 2025 ruleset because
those are Kent's primary autónomo forms — pre-2025 quarters must be
self-auditable in case a complementaria is needed. Every other
ruleset currently ships only its 2025 (or 2024 for IS annual)
variant — pre-2025 periods for those modelos are deferred to the
per-modelo sub-EPIC until Kent demonstrates a need. Resolving a
pre-coverage period raises :class:`MissingRulesetError` from
``get_registry().resolve(...)``.

**Issue #321 (per-modelo Tier-L bar for Modelo 130).** Modelo 130
additionally ships a 2026 ruleset; the 2024 → 2025 → 2026 trail is
documented in ``.vault/reference/2026-130-rule-delta.md``. RIRPF
art. 110 is unchanged across the three years, so the 2026 ruleset is
a structural clone of the 2024 / 2025 ruleset with its own
``effective_from`` / ``effective_to`` window.

**Issue #319 (per-modelo Tier-L bar for Modelo 115).** Modelo 115
additionally ships a 2026 ruleset; the 2024 → 2025 → 2026 trail is
documented in ``.vault/reference/2026-115-rule-delta.md``. RIRPF
art. 100 is unchanged across the three years (the 19 % retention
rate on arrendamientos urbanos has been fixed since 2016), so the
2026 ruleset is a structural clone of the 2024 / 2025 ruleset with
its own ``effective_from`` / ``effective_to`` window.
"""

from __future__ import annotations

from .._ruleset import Ruleset
from .modelo_100_summary_2025 import RULESET as MODELO_100_SUMMARY_2025
from .modelo_111_2024 import RULESET as MODELO_111_2024
from .modelo_111_2025 import RULESET as MODELO_111_2025
from .modelo_115_2024 import RULESET as MODELO_115_2024
from .modelo_115_2025 import RULESET as MODELO_115_2025
from .modelo_115_2026 import RULESET as MODELO_115_2026
from .modelo_123_2024 import RULESET as MODELO_123_2024
from .modelo_123_2025 import RULESET as MODELO_123_2025
from .modelo_130_2024 import RULESET as MODELO_130_2024
from .modelo_130_2025 import RULESET as MODELO_130_2025
from .modelo_130_2026 import RULESET as MODELO_130_2026
from .modelo_131_2024 import RULESET as MODELO_131_2024
from .modelo_131_2025 import RULESET as MODELO_131_2025
from .modelo_180_2024 import RULESET as MODELO_180_2024
from .modelo_180_2025 import RULESET as MODELO_180_2025
from .modelo_200_2024 import RULESET as MODELO_200_2024
from .modelo_202_2025 import RULESET as MODELO_202_2025
from .modelo_303_2024 import RULESET as MODELO_303_2024
from .modelo_303_2025 import RULESET as MODELO_303_2025
from .modelo_303_2026 import RULESET as MODELO_303_2026
from .modelo_390_2025 import RULESET as MODELO_390_2025

# Numerically-ascending by modelo code; within a modelo, ascending by
# effective-from year. Wave 42 M3: prior ordering accidentally trailed
# MODELO_100_SUMMARY_2025 at the end, breaking the numeric sequence.
ALL_RULESETS: tuple[Ruleset, ...] = (
    MODELO_100_SUMMARY_2025,
    MODELO_111_2024,
    MODELO_111_2025,
    MODELO_115_2024,
    MODELO_115_2025,
    MODELO_115_2026,
    MODELO_123_2024,
    MODELO_123_2025,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_131_2024,
    MODELO_131_2025,
    MODELO_180_2024,
    MODELO_180_2025,
    MODELO_200_2024,
    MODELO_202_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2025,
)

__all__ = [
    "ALL_RULESETS",
    "MODELO_100_SUMMARY_2025",
    "MODELO_111_2024",
    "MODELO_111_2025",
    "MODELO_115_2024",
    "MODELO_115_2025",
    "MODELO_115_2026",
    "MODELO_123_2024",
    "MODELO_123_2025",
    "MODELO_130_2024",
    "MODELO_130_2025",
    "MODELO_130_2026",
    "MODELO_131_2024",
    "MODELO_131_2025",
    "MODELO_180_2024",
    "MODELO_180_2025",
    "MODELO_200_2024",
    "MODELO_202_2025",
    "MODELO_303_2024",
    "MODELO_303_2025",
    "MODELO_303_2026",
    "MODELO_390_2025",
]
