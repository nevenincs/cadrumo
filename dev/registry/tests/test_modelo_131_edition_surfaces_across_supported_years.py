"""Modelo 131 edition surfaces that must follow each supported year's own evidence.

Two surfaces change between consecutive editions while the rest of the payload
is shared: the art. 68.4 LIRPF territorial deduction fields, whose scope the
record design of each year words differently, and the corrective-index labels,
which cite the annual Orden de módulos that governs the year. An edition stored
against an earlier one inherits both unless it states the difference, so each
year's expectation is read from the record design and the Orden its own
edition cites rather than restated here.
"""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "131"
_PERIOD = "1T"
# The record-design wording of the art. 68.4 deduction fields on page 1 and in DPA00.
_TERRITORIAL_FIELD_MARKERS = ("Deducción por rentas obtenidas en Ceuta", "RENTAS OBTENIDAS EN CEUTA")
_TERRITORIAL_BINDING_MARKER = "ceuta-melilla"
_LA_PALMA_SUFFIX = "-la-palma"
_MODULOS_ORDEN_ARTICLE = ":art-4"
# Corrective-index inputs and incompatibility flags whose labels cite the governing Orden.
_ORDEN_CITING_CASILLAS = (
    "modulos-indice-pequena-dimension",
    "modulos-indice-temporada",
    "modulos-indice-inicio-actividad",
    "modulos-pequena-dimension-ignorado-flag",
    "modulos-temporada-inicio-actividad-conflicto-flag",
)


@cache
def _supported_years() -> tuple[int, ...]:
    support = load_shared_catalogues(bundled_path("registry", "aeat")).supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return support.years


@cache
def _edition(year: int) -> ModeloRevision:
    return compiled_bundled_authority().snapshot(_MODELO, filing_year=year, period=_PERIOD).revision


def _record_design_lines(revision: ModeloRevision) -> list[str]:
    """Return the extracted lines of the record design the edition's export layout cites."""
    sources = compiled_bundled_authority().catalogues.sources
    designs = {
        ref for layout in revision.export_layouts for ref in layout.source_refs if sources[ref].kind == "record_design"
    }
    assert len(designs) == 1, f"edition {revision.id} cites record designs {sorted(designs)}"
    (design,) = designs
    corpus_path = bundled_path() / sources[design].corpus_path
    return corpus_path.with_name(f"{corpus_path.name}.extracted.md").read_text(encoding="utf-8").splitlines()


def _modulos_orden_title(revision: ModeloRevision, year: int) -> str | None:
    """Return the printed title of the annual Orden de módulos the edition cites for ``year``, if it cites one.

    An edition spanning several years cites each year's Orden; the one governing
    ``year`` is the cited Orden whose catalogue window covers that year.
    """
    legal = compiled_bundled_authority().catalogues.legal

    def governs(ref: str) -> bool:
        effective_to = legal[ref].effective_to
        return legal[ref].effective_from.year <= year and (effective_to is None or effective_to.year >= year)

    ordenes = [
        str(ref).removesuffix(_MODULOS_ORDEN_ARTICLE)
        for ref in revision.legal_refs
        if str(ref).endswith(_MODULOS_ORDEN_ARTICLE) and governs(ref)
    ]
    if not ordenes:
        return None
    assert len(ordenes) == 1, f"edition {revision.id} cites Ordenes de módulos {ordenes} for {year}"
    _, ministry, number, approved = ordenes[0].split("-")
    return f"Orden {ministry.upper()}/{number}/{approved}"


@pytest.mark.parametrize("year", _supported_years())
def test_territorial_deduction_bindings_follow_each_years_record_design(year: int) -> None:
    revision = _edition(year)
    design_fields = [
        line for line in _record_design_lines(revision) if any(marker in line for marker in _TERRITORIAL_FIELD_MARKERS)
    ]
    bound = sorted(str(binding.id) for binding in revision.bindings if _TERRITORIAL_BINDING_MARKER in str(binding.id))

    if not design_fields:
        assert bound == [], f"{year}: the record design lays out no art. 68.4 field, yet the edition binds {bound}"
        return
    names_la_palma = any("la palma" in line.lower() for line in design_fields)
    assert bound, f"{year}: the record design lays out art. 68.4 fields {design_fields}, yet the edition binds none"
    wrong_scope = [binding for binding in bound if binding.endswith(_LA_PALMA_SUFFIX) is not names_la_palma]
    assert wrong_scope == [], (
        f"{year}: the record design {'names' if names_la_palma else 'does not name'} La Palma, "
        f"but these bindings carry the other scope: {wrong_scope}"
    )


@pytest.mark.parametrize("year", _supported_years())
def test_corrective_index_labels_cite_the_years_orden_de_modulos(year: int) -> None:
    revision = _edition(year)
    casillas = {str(casilla.id): casilla for casilla in revision.casillas}
    present = [casilla_id for casilla_id in _ORDEN_CITING_CASILLAS if casilla_id in casillas]
    if not present:
        return
    orden = _modulos_orden_title(revision, year)
    assert orden is not None, f"{year}: edition {revision.id} computes módulos without an Orden de módulos"
    stale = {casilla_id: casillas[casilla_id].get_label("es") for casilla_id in present}
    stale = {casilla_id: label for casilla_id, label in stale.items() if orden not in label}
    assert stale == {}, f"{year}: labels do not cite {orden}: {stale}"
