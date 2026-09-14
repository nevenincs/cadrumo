from __future__ import annotations

from datetime import date

from dev.registry.compiler.authority import compiled_bundled_authority


def modelo_130_2025_1t_snapshot():
    return compiled_bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
