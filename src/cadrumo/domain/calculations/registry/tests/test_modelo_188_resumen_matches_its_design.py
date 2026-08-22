"""Modelo 188's hoja-resumen casillas agree with the record design they cite.

Modelo 188 declares five ``resumen`` casillas and no export layout, so it sits
on the filing-capability worklist. Authoring that layout means binding each
summary box to a byte range in the bundled diseño, and the registry already
states which ranges: casilla 04's own reason field says the two perceptor counts
are carried "at offsets 136 and 175".

That claim is prose. Nothing checked it against the design, so the casilla set
and the diseño could disagree -- and the layout would then be authored onto the
disagreement. This module checks the claim while it is still cheap to correct.

WHAT IS AND IS NOT ASSERTED. The design's own offsets are not compared to
themselves; that would be tautological. What is compared is the REGISTRY's
declared casilla set against the DESIGN's summary block: the count of boxes, and
the integer/money split, must match the widths AEAT prints. AEAT gives the two
perceptor counts 9 characters and the three amounts 15, so a registry that
declared four amounts and one count, or six boxes, would fail here even though
every individual file still parsed.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import bundled_authority, extract_record_design

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The diseño this revision cites, and the record carrying the hoja-resumen.
_DESIGN = "01-188-diseno-de-registro-actualizado-en-2023.pdf"
_SUMMARY_SHEET = "PDF record design"
#: AEAT's widths for the summary block: a perceptor COUNT is 9 characters and a
#: monetary total is 15. The block begins after the declarante identity fields.
_COUNT_WIDTH, _AMOUNT_WIDTH = 9, 15
_SUMMARY_FIRST_OFFSET = 136


def _summary_fields():
    design = bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_188", "files", _DESIGN)
    extraction = extract_record_design(design)
    sheet = next(s for s in extraction.sheets if s.name == _SUMMARY_SHEET)
    return tuple(
        field
        for field in sheet.fields
        if field.offset >= _SUMMARY_FIRST_OFFSET
        and field.length in {_COUNT_WIDTH, _AMOUNT_WIDTH}
        and "BLANCOS" not in (field.description or "").upper()
    )


def _resumen_casillas():
    modelo = next(m for m in bundled_authority().modelos if str(m.id) == "188")
    revision = modelo.revisions["2019-y-siguientes"]
    return tuple(c for c in revision.casillas if "resumen" in tuple(c.section or ()))


def test_the_design_carries_one_summary_field_per_declared_resumen_casilla() -> None:
    fields = _summary_fields()
    casillas = _resumen_casillas()

    assert casillas, "modelo 188 declares no resumen casillas"
    assert len(fields) == len(casillas), (
        f"the diseño carries {len(fields)} hoja-resumen field(s) but the registry declares "
        f"{len(casillas)} resumen casilla(s); the export layout cannot bind them one to one"
    )


def test_the_integer_and_money_split_matches_the_widths_aeat_prints() -> None:
    """A count is 9 characters and an amount 15; the registry must agree."""
    fields = _summary_fields()
    casillas = _resumen_casillas()

    design_counts = sum(1 for field in fields if field.length == _COUNT_WIDTH)
    design_amounts = sum(1 for field in fields if field.length == _AMOUNT_WIDTH)
    declared_counts = sum(1 for casilla in casillas if str(casilla.data_type) == "integer")
    declared_amounts = sum(1 for casilla in casillas if str(casilla.data_type) == "money")

    assert (declared_counts, declared_amounts) == (design_counts, design_amounts), (
        f"the diseño prints {design_counts} count(s) and {design_amounts} amount(s) in the "
        f"hoja-resumen, but the registry declares {declared_counts} integer and "
        f"{declared_amounts} money casilla(s)"
    )


def test_the_two_perceptor_counts_sit_where_the_registry_says_they_do() -> None:
    """Casilla 04's reason field names offsets 136 and 175; the design must carry them."""
    counts = tuple(field.offset for field in _summary_fields() if field.length == _COUNT_WIDTH)

    assert counts == (136, 175), (
        f"the registry documents the two perceptor counts at offsets 136 and 175; the diseño carries counts at {counts}"
    )
