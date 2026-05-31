"""Art. 81 LIRPF deducción maternidad computation helpers.

Pure-domain arithmetic; no entrypoint or CLI dependencies.
"""

from __future__ import annotations


def compute_deduccion_maternidad_0611(meses_por_hijo: list[tuple[str, int]]) -> int:
    """Compute Art. 81 LIRPF deducción maternidad from per-hijo meses pairs.

    Formula: ``sum(min(meses × 100, 1_200))`` for each ``(hijo_id, meses)`` pair.
    Returns an integer euros amount.
    """
    return sum(min(meses * 100, 1200) for _, meses in meses_por_hijo)
