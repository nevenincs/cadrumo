"""Grounding gate for the M100 rendimiento-del-capital-inmobiliario chain.

The capital-inmobiliario rendimiento computation (arts. 22 íntegros / 23 gastos
y reducciones / 24 rendimiento mínimo en parentesco, + art. 85 for the imputación
de rentas inmobiliarias) had drifted in 2021-2024 to the actividades económicas
chapter (arts. 27/28/30/31/32) — part of the same cross-section copy-paste defect
fixed for capital mobiliario and retenciones. This gate pins the rendimiento-chain
boxes to their own provisions and bars the actividades chapter.

Scope note: ONLY the rendimiento-computation chain is covered here. The wider
`inmueble` section also carries ganancias-patrimoniales-por-transmisión boxes
(arts. 33-39) and structural data-entry fields, which are deliberately NOT in this
set — re-grounding those is a separate ganancias pass (see the V11 audit note).
"""

from __future__ import annotations

import pytest

from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ACTIVIDADES_CHAPTER = frozenset({f"ley-35-2006:art-{n}" for n in (27, 28, 30, 31, 32)})

# box id -> the exact capital-inmobiliario articles that govern it (verified
# against the canonical 2025 grounding and the box's own AEAT label).
_CHAIN_GROUNDING: dict[str, frozenset[str]] = {
    "0089": frozenset({"ley-35-2006:art-22", "ley-35-2006:art-85"}),  # renta imputada
    "0102": frozenset({"ley-35-2006:art-22"}),  # ingresos íntegros
    "0104": frozenset({"ley-35-2006:art-23"}),
    "0107": frozenset({"ley-35-2006:art-23"}),
    "0109": frozenset({"ley-35-2006:art-23"}),
    "0110": frozenset({"ley-35-2006:art-23"}),
    "0111": frozenset({"ley-35-2006:art-23"}),
    "0112": frozenset({"ley-35-2006:art-23"}),
    "0113": frozenset({"ley-35-2006:art-23"}),
    "0114": frozenset({"ley-35-2006:art-23"}),
    "0115": frozenset({"ley-35-2006:art-23"}),
    "0116": frozenset({"ley-35-2006:art-23"}),
    "0117": frozenset({"ley-35-2006:art-23"}),
    "0131": frozenset({"ley-35-2006:art-23"}),
    "0132": frozenset({"ley-35-2006:art-23"}),
    "0146": frozenset({"ley-35-2006:art-23"}),
    "0147": frozenset({"ley-35-2006:art-23"}),
    "0148": frozenset({"ley-35-2006:art-23"}),
    "0149": frozenset({"ley-35-2006:art-22", "ley-35-2006:art-23"}),  # rendimiento neto
    "0150": frozenset({"ley-35-2006:art-23"}),
    "0151": frozenset({"ley-35-2006:art-23"}),
    "0152": frozenset({"ley-35-2006:art-24"}),  # rendimiento mínimo parentesco
    "0154": frozenset({"ley-35-2006:art-22", "ley-35-2006:art-23", "ley-35-2006:art-24"}),
    "0155": frozenset({"ley-35-2006:art-22", "ley-35-2006:art-85"}),  # suma imputadas
    "0156": frozenset({"ley-35-2006:art-22", "ley-35-2006:art-23", "ley-35-2006:art-24"}),
}


def _m100_casillas_by_id(filing_year: int):
    modelo, _ = _committed_modelo("100")
    rev = select_revision(modelo, filing_year=filing_year, period="0A")
    return {c.id: c for c in rev.casillas}


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024])
@pytest.mark.parametrize(("cid", "expected"), sorted(_CHAIN_GROUNDING.items()))
def test_inmueble_chain_box_grounds_in_its_own_provision(year: int, cid: str, expected: frozenset[str]) -> None:
    """Each rendimiento-chain box cites its capital-inmobiliario article(s) and
    never the actividades chapter."""
    casilla = _m100_casillas_by_id(year).get(cid)
    assert casilla is not None, f"M100 {year} must declare casilla {cid}"
    refs = set(casilla.legal_refs)
    assert not (_ACTIVIDADES_CHAPTER & refs), (
        f"casilla {cid} ({year}) must not cite the actividades chapter: {sorted(refs)}"
    )
    assert expected <= refs, f"casilla {cid} ({year}) must ground in {sorted(expected)}; found {sorted(refs)}"


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024])
def test_capital_inmobiliario_range_never_cites_actividades(year: int) -> None:
    """No capital-inmobiliario casilla (the inmueble-section computation block, ids
    100-156 — capital inmobiliario; ganancia boxes are >=1226) may cite the
    actividades económicas chapter. Covers the rental-property gastos/amortización-base
    sub-block (art. 23) and the retención box 0153 (art. 99) regrounded from the
    cross-section copy-paste defect."""
    offenders = []
    for c in _m100_casillas_by_id(year).values():
        if not c.id.isdigit() or not (100 <= int(c.id) <= 156):
            continue
        if "inmueble" not in tuple(c.section):
            continue
        if _ACTIVIDADES_CHAPTER & set(c.legal_refs):
            offenders.append((c.id, sorted(c.legal_refs)))
    assert not offenders, f"M100 {year}: capital-inmobiliario casillas still cite the actividades chapter: {offenders}"
