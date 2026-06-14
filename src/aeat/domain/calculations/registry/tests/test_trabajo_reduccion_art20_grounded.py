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


# Sibling gasto casillas of the same drift cluster: 0019 (otros gastos deducibles),
# 0020 (incremento por movilidad geográfica), 0021 (incremento trabajadores activos
# con discapacidad) are all art. 19.2.f gastos deducibles — their binding provision
# is art. 19, NOT art. 17 (rendimientos íntegros). 2021-2024 had drifted to art-17;
# 2020 and 2025 already carried art-19.
_GASTO_CASILLAS = ("0019", "0020", "0021")


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
@pytest.mark.parametrize("casilla_id", _GASTO_CASILLAS)
def test_gasto_casillas_cite_art19(year: int, casilla_id: str) -> None:
    """The art. 19.2.f gasto casillas (0019/0020/0021) must cite ley-35-2006:art-19."""
    rev = _m100_revision(year)
    casillas_by_id = {c.id: c for c in rev.casillas}
    casilla = casillas_by_id.get(casilla_id)
    assert casilla is not None, f"M100 {year} must declare casilla {casilla_id}"
    assert "ley-35-2006:art-19" in casilla.legal_refs, (
        f"casilla {casilla_id} ({year}) is an art. 19.2.f gasto deducible; its legal_refs "
        f"must cite ley-35-2006:art-19, not {list(casilla.legal_refs)}"
    )


# The wider trabajo-section grounding cluster, all formerly drifted to art-17 in
# 2021-2024 and canonically grounded in 2025: casilla -> the binding article that
# governs it. 0011 is the art. 18 reduction por irregularidad; 0013 (cotizaciones
# SS, art. 19.2.a), 0014/0015 (cuotas sindicato/colegio, art. 19.2.d), 0016 (defensa
# jurídica, art. 19.2.e), 0017 (rendimiento neto previo) are art. 19.
_TRABAJO_SECTION_GROUNDING: dict[str, str] = {
    "0011": "ley-35-2006:art-18",
    "0013": "ley-35-2006:art-19",
    "0014": "ley-35-2006:art-19",
    "0015": "ley-35-2006:art-19",
    "0016": "ley-35-2006:art-19",
    "0017": "ley-35-2006:art-19",
    "0018": "ley-35-2006:art-19",  # suma rendimientos netos previos
    "0022": "ley-35-2006:art-19",  # rendimiento neto
}


@pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
@pytest.mark.parametrize(("casilla_id", "expected_ref"), sorted(_TRABAJO_SECTION_GROUNDING.items()))
def test_trabajo_section_casillas_cite_binding_article(year: int, casilla_id: str, expected_ref: str) -> None:
    """Each trabajo-section casilla cites its binding article (art. 18 / art. 19),
    not the art. 17 rendimientos-íntegros chapter it had drifted to."""
    rev = _m100_revision(year)
    casillas_by_id = {c.id: c for c in rev.casillas}
    casilla = casillas_by_id.get(casilla_id)
    assert casilla is not None, f"M100 {year} must declare casilla {casilla_id}"
    assert expected_ref in casilla.legal_refs, (
        f"casilla {casilla_id} ({year}) must cite {expected_ref}; found {list(casilla.legal_refs)}"
    )


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024, 2025])
def test_casilla_0025_neto_reducido_cites_full_reduction_chain(year: int) -> None:
    """Casilla 0025 (rendimiento neto reducido) is governed by the reduction chain
    arts. 18 (irregularidad), 19 (gastos) and 20 (reducción trabajo) — not art-17."""
    rev = _m100_revision(year)
    casillas_by_id = {c.id: c for c in rev.casillas}
    casilla = casillas_by_id.get("0025")
    assert casilla is not None, f"M100 {year} must declare casilla 0025"
    for ref in ("ley-35-2006:art-18", "ley-35-2006:art-19", "ley-35-2006:art-20"):
        assert ref in casilla.legal_refs, f"casilla 0025 ({year}) must cite {ref}; found {list(casilla.legal_refs)}"
