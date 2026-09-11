"""Modelo 151's design-less casillas are the calculation surface, and they belong here.

Modelo 151 declares two kinds of casilla side by side. Most are DESIGN SLOTS:
they carry an offset-range number (``808-824``), sit under a record segmento
(``M15108000``), and cite the revision's AEAT Diseño. A handful are not slots at
all -- ``impatriado.cuota-diferencial``, ``decl.ejercicio`` -- carrying a
symbolic number, no segmento, and citing the procedure and BOE layout instead.

The second kind reads like drift, and was raised as such: casillas the
revision's rendered export tree does not address. They are not drift. They are
the régimen de impatriados calculation surface of Ley 35/2006 art. 93 plus the
declaration-scope identifiers, and the export tree does not address them
because they are not positions in AEAT's fixed-width record.

WHAT THIS PINS, AND WHY AS A PROPERTY. Not the six ids, which would freeze a
tally and teach the next author to update a constant. The property: a modelo 151
casilla that cites no record design must be design-less in every other respect
too -- no segmento, a symbolic rather than an offset-range number -- and must
still be legally grounded. A stray casilla fails that shape; a real calculation
node satisfies it. The shape is checked on both revisions, so it also holds the
2025 tree, whose surface is the same set plus the ahorro pair.
"""

from __future__ import annotations

import re

import pytest

from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A design slot's number is the byte range AEAT gives it in the fixed-width record.
_OFFSET_RANGE = re.compile(r"^\d+-\d+$")


def _modelo_151():
    modelos, catalogues = _committed_registry_tree()
    return next(modelo for modelo in modelos if modelo.id == "151"), catalogues


def _cites_a_record_design(casilla, catalogues) -> bool:
    return any(
        str(ref) in catalogues.sources and catalogues.sources[str(ref)].kind == "record_design"
        for ref in (getattr(casilla, "source_refs", ()) or ())
    )


def test_both_kinds_of_casilla_are_present_so_the_property_has_something_to_separate() -> None:
    """Without this, every assertion below could pass on an empty or uniform set."""
    modelo, catalogues = _modelo_151()

    for revision_id, revision in modelo.revisions.items():
        design_backed = [c for c in revision.casillas if _cites_a_record_design(c, catalogues)]
        design_less = [c for c in revision.casillas if not _cites_a_record_design(c, catalogues)]

        assert design_backed, f"151/{revision_id} declares no design-backed casillas"
        assert design_less, f"151/{revision_id} declares no calculation-surface casillas"


def test_a_casilla_citing_no_record_design_is_design_less_throughout() -> None:
    """The shape that separates a calculation node from a stray declaration.

    A casilla with no design citation must also carry no segmento and no
    offset-range number. One of the three without the others is the drift this
    would otherwise be mistaken for.
    """
    modelo, catalogues = _modelo_151()

    for revision_id, revision in modelo.revisions.items():
        for casilla in revision.casillas:
            if _cites_a_record_design(casilla, catalogues):
                continue
            assert casilla.segmento is None, (
                f"151/{revision_id} casilla {casilla.id} cites no record design yet claims "
                f"segmento {casilla.segmento!r}, so it is addressed as a record slot without one"
            )
            assert not _OFFSET_RANGE.match(casilla.number or ""), (
                f"151/{revision_id} casilla {casilla.id} cites no record design yet numbers "
                f"itself {casilla.number!r}, which is a fixed-width byte range"
            )


def test_every_design_backed_casilla_is_addressed_as_a_record_slot() -> None:
    """The converse, so the property above cannot pass by nothing being design-backed."""
    modelo, catalogues = _modelo_151()

    for revision_id, revision in modelo.revisions.items():
        for casilla in revision.casillas:
            if not _cites_a_record_design(casilla, catalogues):
                continue
            assert casilla.segmento is not None, (
                f"151/{revision_id} casilla {casilla.id} cites a record design but claims no segmento"
            )


def test_the_calculation_surface_stays_legally_grounded() -> None:
    """Being absent from the record is not a reason to be absent from the law.

    These casillas carry the whole regulatory claim the modelo makes about the
    régimen especial, so a design-less casilla with no ``legal_refs`` would be a
    computed value with nothing behind it.
    """
    modelo, catalogues = _modelo_151()

    for revision_id, revision in modelo.revisions.items():
        for casilla in revision.casillas:
            if _cites_a_record_design(casilla, catalogues):
                continue
            assert getattr(casilla, "legal_refs", ()), (
                f"151/{revision_id} casilla {casilla.id} is a calculation-surface casilla with no legal grounding"
            )
