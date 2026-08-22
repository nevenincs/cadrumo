"""An empty Diseño pair set is no evidence, and that premise is checked rather than assumed.

:func:`derive_calculation_completeness_casillas` refuses a casilla pinned to a
segmento the AEAT Diseño does not carry it under. That refusal is suppressed
when the design yields NO ``(sheet, number)`` pairs at all, because refusing
from an empty set asserts absence out of ignorance.

The suppression is sound only while its premise holds: that the design really
prints no bracketed casilla tags, rather than the parser having failed to read
the ones it prints. That premise is an implicit allowlist entry, and nothing
made it fail when it went stale. This module is that missing half.

Modelo 184 is the case the tolerance was written for. Its two designs read
WHOLE -- three sheets each, nothing skipped -- and still carry zero bracketed
tags, so the emptiness is a fact about AEAT's document and not about this
parser. If a future parser improvement starts recovering tags from these
designs, the tolerance stops applying to them, and the second test states what
then has to be confronted: modelo 184's segmentos are registry slugs that name
no sheet in its own design, so every declared casilla would refuse at once.
"""

from __future__ import annotations

import re

import pytest

from .....core.resources import bundled_path
from .. import extract_record_design
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO_184_DESIGNS = (
    "02-184-orden-hap-2250-2015-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-263-kb-pdf.pdf",
    "01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf",
)

_TAG = re.compile(r"\[(\d+)\]")


def _design(name: str):
    return extract_record_design(
        bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_184", "files", name),
    )


@pytest.mark.parametrize("name", _MODELO_184_DESIGNS)
def test_the_design_is_read_whole_yet_prints_no_casilla_tags(name: str) -> None:
    """The premise behind the tolerance, stated as two facts that must hold together.

    Read whole AND silent on tags. Either alone would be misleading: a design
    that yielded no tags because it could not be read would be a parser gap
    wearing the tolerance as a disguise.
    """
    extraction = _design(name)

    assert not extraction.skipped, [(sheet.name, sheet.reason) for sheet in extraction.skipped]
    assert extraction.sheets, "the design produced no sheets at all"

    tags = [
        number
        for sheet in extraction.sheets
        for field in sheet.fields
        for text in (field.description, field.validation, field.content)
        if text
        for number in _TAG.findall(text)
    ]

    assert tags == [], f"the design now prints casilla tags, so the evidence tolerance no longer applies: {tags[:8]}"


def test_this_modelo_s_segmentos_name_no_sheet_in_its_own_design() -> None:
    """What the tolerance is currently standing in front of.

    The refusal matches a segmento against a design SHEET NAME. Modelo 184's
    segmentos are registry slugs -- ``184-2-entidad`` -- while its design names
    the same record ``Tipo 2 - Registro De Rentas De La ...``. So the match
    would fail for every casilla, not just a misplaced one.

    Pinned as the current state rather than fixed here: the sheet names are
    parser-derived truncations of AEAT's headings, so making the slugs equal
    them would pin the registry to an extraction artefact. Recording it means
    the day tags appear, the failure is already explained.
    """
    modelos, _ = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "184")
    segmentos = {
        casilla.segmento for revision in modelo.revisions.values() for casilla in revision.casillas if casilla.segmento
    }
    assert segmentos, "modelo 184 declares no segmentos, so this module is testing nothing"

    sheet_names = {sheet.name for name in _MODELO_184_DESIGNS for sheet in _design(name).sheets}

    matched = {
        segmento
        for segmento in segmentos
        for sheet_name in sheet_names
        if segmento == sheet_name or sheet_name.startswith(f"{segmento} ")
    }

    assert matched == set(), (
        f"a segmento now names a design sheet, so the segmento-to-sheet match is live "
        f"for modelo 184 and this module's premise has changed: {sorted(matched)}"
    )
