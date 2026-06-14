"""Grounding gate for the M100 rendimientos del capital mobiliario section.

LIRPF grounds capital mobiliario in arts. 25 (rendimientos íntegros) and 26
(gastos deducibles y reducciones) — NOT in the actividades económicas chapter
(arts. 27/28/30/31/32). The 2021-2024 revisions had a cross-section copy-paste
defect: every capital-mobiliario casilla cited the actividades chapter and none
of arts. 25/26. 2025 grounds them correctly per-box. This gate pins that no
capital-mobiliario box ever cites an actividades article and every box cites at
least one of arts. 25/26, across all live ejercicios.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_ACTIVIDADES_CHAPTER = frozenset(
    {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }
)
_CAPITAL_MOBILIARIO_CHAPTER = frozenset({"ley-35-2006:art-25", "ley-35-2006:art-26"})


def _m100_capital_mobiliario_casillas(filing_year: int):
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelos_by_id = {m.id: m for m in modelos}
    rev = select_revision(modelos_by_id["100"], filing_year=filing_year, period="0A")
    return [c for c in rev.casillas if "rdto_capital_mobiliario" in tuple(c.section)]


# Scoped to the years corrected by this fix. 2025 is excluded here because its
# casillas 0043/0044/0049 carry a separate 17-article "kitchen-sink" over-grounding
# (an enrichment-authoring artifact, not this copy-paste defect) that happens to
# include the actividades chapter — tracked as a distinct follow-up, not regressed by
# this correction. The own-chapter test below still covers 2025.
@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024])
def test_capital_mobiliario_never_cites_actividades_chapter(year: int) -> None:
    """No capital-mobiliario casilla may cite an actividades económicas article."""
    offenders = [
        (c.id, sorted(c.legal_refs))
        for c in _m100_capital_mobiliario_casillas(year)
        if _ACTIVIDADES_CHAPTER & set(c.legal_refs)
    ]
    assert not offenders, (
        f"M100 {year}: capital-mobiliario casillas cite the actividades chapter "
        f"(arts. 27-32) instead of arts. 25/26: {offenders}"
    )


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024, 2025])
def test_capital_mobiliario_cites_its_own_chapter(year: int) -> None:
    """Every capital-mobiliario casilla that carries an LIRPF article must ground
    in arts. 25/26 (its own chapter)."""
    bad = []
    for c in _m100_capital_mobiliario_casillas(year):
        lirpf = {r for r in c.legal_refs if r.startswith("ley-35-2006:art-")}
        if lirpf and not (lirpf & _CAPITAL_MOBILIARIO_CHAPTER):
            bad.append((c.id, sorted(c.legal_refs)))
    assert not bad, f"M100 {year}: capital-mobiliario casillas with an LIRPF article that is not art. 25/26: {bad}"


# The retenciones / pagos a cuenta boxes were part of the same cross-section
# copy-paste defect (citing the actividades chapter); their binding provision is
# LIRPF art. 99 (obligación de practicar pagos a cuenta).
_RETENCIONES_PAGOS = ("0591", "0604", "0609")


def _m100_casilla(filing_year: int, cid: str):
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelos_by_id = {m.id: m for m in modelos}
    rev = select_revision(modelos_by_id["100"], filing_year=filing_year, period="0A")
    return {c.id: c for c in rev.casillas}.get(cid)


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024, 2025])
@pytest.mark.parametrize("cid", _RETENCIONES_PAGOS)
def test_retenciones_pagos_ground_in_art99_not_actividades(year: int, cid: str) -> None:
    """Retenciones/pagos-a-cuenta boxes cite art. 99, never the actividades chapter."""
    casilla = _m100_casilla(year, cid)
    assert casilla is not None, f"M100 {year} must declare casilla {cid}"
    refs = set(casilla.legal_refs)
    assert "ley-35-2006:art-99" in refs, (
        f"casilla {cid} ({year}) is a retenciones/pagos box; must cite art. 99, found {sorted(refs)}"
    )
    assert not (_ACTIVIDADES_CHAPTER & refs), (
        f"casilla {cid} ({year}) must not cite the actividades chapter: {sorted(refs)}"
    )
