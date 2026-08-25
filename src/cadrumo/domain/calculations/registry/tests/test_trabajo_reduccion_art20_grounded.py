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

from functools import lru_cache

import pytest

from .....core import CasillaId, validated_casilla_id
from ..temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ALL_LIVE_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
_DRIFT_CORRECTED_YEARS = (2021, 2022, 2023, 2024)
_NETO_REDUCIDO_CHAIN_YEARS = (2021, 2022, 2023, 2024, 2025)

_TRABAJO_REDUCCION_CASILLA = validated_casilla_id(
    "0023",
    surface="test_trabajo_reduccion_art20_grounded.trabajo_reduccion",
)
_TRABAJO_NETO_REDUCIDO_CASILLA = validated_casilla_id(
    "0025",
    surface="test_trabajo_reduccion_art20_grounded.trabajo_neto_reducido",
)


def _m100_revision(filing_year: int):
    modelo, _ = _committed_modelo("100")
    return select_revision(modelo, filing_year=filing_year, period="0A")


@lru_cache
def _m100_casillas_by_id(filing_year: int):
    rev = _m100_revision(filing_year)
    return {casilla.id: casilla for casilla in rev.casillas}


def test_casilla_0023_cites_art20_reduction() -> None:
    """Casilla 0023 (the art. 20 work-income reduction) must cite ley-35-2006:art-20."""
    for year in _ALL_LIVE_YEARS:
        casilla = _m100_casillas_by_id(year).get(_TRABAJO_REDUCCION_CASILLA)
        assert casilla is not None, f"M100 {year} must declare casilla 0023"
        assert "ley-35-2006:art-20" in casilla.legal_refs, (
            f"casilla 0023 ({year}) is the art. 20 reduction; its legal_refs must cite "
            f"ley-35-2006:art-20, not {list(casilla.legal_refs)}"
        )


def test_casilla_0023_does_not_misground_to_art17() -> None:
    """The corrected years must not retain the art-17 misgrounding (art. 17 is
    rendimientos íntegros, not the reduction the casilla holds)."""
    for year in _DRIFT_CORRECTED_YEARS:
        casilla = _m100_casillas_by_id(year).get(_TRABAJO_REDUCCION_CASILLA)
        assert casilla is not None, f"M100 {year} must declare casilla 0023"
        assert "ley-35-2006:art-17" not in casilla.legal_refs, (
            f"casilla 0023 ({year}) must not cite art-17 (rendimientos íntegros) for the "
            f"art. 20 reduction; found {list(casilla.legal_refs)}"
        )


# Sibling gasto casillas of the same drift cluster: 0019 (otros gastos deducibles),
# 0020 (incremento por movilidad geográfica), 0021 (incremento trabajadores activos
# con discapacidad) are all art. 19.2.f gastos deducibles — their binding provision
# is art. 19, NOT art. 17 (rendimientos íntegros). 2021-2024 had drifted to art-17;
# 2020 and 2025 already carried art-19.
_GASTO_CASILLAS: tuple[CasillaId, ...] = (
    validated_casilla_id("0019", surface="test_trabajo_reduccion_art20_grounded.gasto.0019"),
    validated_casilla_id("0020", surface="test_trabajo_reduccion_art20_grounded.gasto.0020"),
    validated_casilla_id("0021", surface="test_trabajo_reduccion_art20_grounded.gasto.0021"),
)


def test_gasto_casillas_cite_art19() -> None:
    """The art. 19.2.f gasto casillas (0019/0020/0021) must cite ley-35-2006:art-19."""
    for year in _ALL_LIVE_YEARS:
        casillas_by_id = _m100_casillas_by_id(year)
        for casilla_id in _GASTO_CASILLAS:
            casilla = casillas_by_id.get(casilla_id)
            assert casilla is not None, f"M100 {year} must declare casilla {casilla_id}"
            assert "ley-35-2006:art-19" in casilla.legal_refs, (
                f"casilla {casilla_id} ({year}) is an art. 19.2.f gasto deducible; "
                f"its legal_refs must cite ley-35-2006:art-19, not {list(casilla.legal_refs)}"
            )


# The wider trabajo-section grounding cluster, all formerly drifted to art-17 in
# 2021-2024 and canonically grounded in 2025: casilla -> the binding article that
# governs it. 0011 is the art. 18 reduction por irregularidad; 0013 (cotizaciones
# SS, art. 19.2.a), 0014/0015 (cuotas sindicato/colegio, art. 19.2.d), 0016 (defensa
# jurídica, art. 19.2.e), 0017 (rendimiento neto previo) are art. 19.
_TRABAJO_SECTION_GROUNDING: dict[CasillaId, str] = {
    validated_casilla_id("0011", surface="test_trabajo_reduccion_art20_grounded.trabajo.0011"): ("ley-35-2006:art-18"),
    validated_casilla_id("0013", surface="test_trabajo_reduccion_art20_grounded.trabajo.0013"): ("ley-35-2006:art-19"),
    validated_casilla_id("0014", surface="test_trabajo_reduccion_art20_grounded.trabajo.0014"): ("ley-35-2006:art-19"),
    validated_casilla_id("0015", surface="test_trabajo_reduccion_art20_grounded.trabajo.0015"): ("ley-35-2006:art-19"),
    validated_casilla_id("0016", surface="test_trabajo_reduccion_art20_grounded.trabajo.0016"): ("ley-35-2006:art-19"),
    validated_casilla_id("0017", surface="test_trabajo_reduccion_art20_grounded.trabajo.0017"): ("ley-35-2006:art-19"),
    validated_casilla_id("0018", surface="test_trabajo_reduccion_art20_grounded.trabajo.0018"): ("ley-35-2006:art-19"),
    validated_casilla_id("0022", surface="test_trabajo_reduccion_art20_grounded.trabajo.0022"): ("ley-35-2006:art-19"),
}


def test_trabajo_section_casillas_cite_binding_article() -> None:
    """Each trabajo-section casilla cites its binding article (art. 18 / art. 19),
    not the art. 17 rendimientos-íntegros chapter it had drifted to."""
    for year in _ALL_LIVE_YEARS:
        casillas_by_id = _m100_casillas_by_id(year)
        for casilla_id, expected_ref in sorted(_TRABAJO_SECTION_GROUNDING.items()):
            casilla = casillas_by_id.get(casilla_id)
            assert casilla is not None, f"M100 {year} must declare casilla {casilla_id}"
            assert expected_ref in casilla.legal_refs, (
                f"casilla {casilla_id} ({year}) must cite {expected_ref}; found {list(casilla.legal_refs)}"
            )


def test_casilla_0025_neto_reducido_cites_full_reduction_chain() -> None:
    """Casilla 0025 (rendimiento neto reducido) is governed by the reduction chain
    arts. 18 (irregularidad), 19 (gastos) and 20 (reducción trabajo) — not art-17."""
    for year in _NETO_REDUCIDO_CHAIN_YEARS:
        casilla = _m100_casillas_by_id(year).get(_TRABAJO_NETO_REDUCIDO_CASILLA)
        assert casilla is not None, f"M100 {year} must declare casilla 0025"
        for ref in ("ley-35-2006:art-18", "ley-35-2006:art-19", "ley-35-2006:art-20"):
            assert ref in casilla.legal_refs, f"casilla 0025 ({year}) must cite {ref}; found {list(casilla.legal_refs)}"
