"""Grounding gate for the IRPF art. 20 work-income reduction casilla (0023).

Casilla 0023 ("Cuantía aplicable con carácter general") of Modelo 100 is the
*reducción por obtención de rendimientos del trabajo* of Ley 35/2006 art. 20 —
it minora the rendimiento neto del trabajo (casilla 0022) to obtain the
rendimiento neto reducido (casilla 0025, formula ``0022 - 0057 - 0023``). Its
binding provision is therefore art. 20, NOT art. 17 (rendimientos íntegros).

The 2021-2024 revisions had drifted to ``legal_refs = ["ley-35-2006:art-17"]``
— citing the wrong article for the reduction — while 2020 and 2025 already
carried ``ley-35-2006:art-20``. This gate pins the binding-provision citation on
casilla 0023 across every live ejercicio so the grounding cannot regress.

Authority: the bundled consolidated LIRPF ``ley-35-2006.html#a20`` (art. 20,
"Reducción por obtención de rendimientos del trabajo"), modified for 2024 by
RDL 4/2024 art. 3.1 (BOE-A-2024-12944) to the 7.302 € / 19.747,5 € schedule.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree
from .._temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _m100_revision(filing_year: int):
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    modelos_by_id = {m.id: m for m in modelos}
    return select_revision(modelos_by_id["100"], filing_year=filing_year, period="0A")


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
def test_casilla_0023_cites_art20_reduction(year: int) -> None:
    """Casilla 0023 (the art. 20 work-income reduction) must cite ley-35-2006:art-20."""
    rev = _m100_revision(year)
    casillas_by_id = {c.id: c for c in rev.casillas}
    casilla = casillas_by_id.get("0023")
    assert casilla is not None, f"M100 {year} must declare casilla 0023"
    assert "ley-35-2006:art-20" in casilla.legal_refs, (
        f"casilla 0023 ({year}) is the art. 20 reduction; its legal_refs must cite "
        f"ley-35-2006:art-20, not {list(casilla.legal_refs)}"
    )


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024])
def test_casilla_0023_does_not_misground_to_art17(year: int) -> None:
    """The corrected years must not retain the art-17 misgrounding (art. 17 is
    rendimientos íntegros, not the reduction the casilla holds)."""
    rev = _m100_revision(year)
    casillas_by_id = {c.id: c for c in rev.casillas}
    casilla = casillas_by_id.get("0023")
    assert casilla is not None
    assert "ley-35-2006:art-17" not in casilla.legal_refs, (
        f"casilla 0023 ({year}) must not cite art-17 (rendimientos íntegros) for the "
        f"art. 20 reduction; found {list(casilla.legal_refs)}"
    )
