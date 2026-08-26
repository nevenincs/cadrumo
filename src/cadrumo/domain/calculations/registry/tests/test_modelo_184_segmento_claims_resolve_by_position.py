"""Modelo 184's segmento assignments are proven against the design, by POSITION.

:mod:`test_diseno_pair_evidence_tolerance` records that the completeness refusal
matches a segmento against a design SHEET NAME, that modelo 184's segmentos name
no sheet in its own design, and that the refusal is therefore suppressed by an
empty-tag tolerance standing in front of an unverified claim. This module supplies
the verification the tolerance was standing in for, on the axis the manifest
actually uses.

THE MANIFEST DOES NOT KEY ON BOX NUMBERS. Modelo 184's designs print no bracketed
casilla tags at all -- that is the premise the tolerance rests on and the sibling
module proves. Its completeness manifest keys each casilla by ``number`` values
that are DESIGN POSITIONS: ``"77"``, ``"78-79"``, ``"177-190"``. So the question
"does the diseño carry this casilla under this segmento" is answerable without any
tag: read the record and see what occupies the claimed span.

WHY THE ANSWER DISCRIMINATES. Modelo 184 has TWO Tipo 2 records -- the entidad's
rentas register and the socio/heredero register -- and they carry entirely
different fields at the same positions. Position 77 is CLAVE on one and the first
byte of CÓDIGO PROVINCIA on the other; 177-190 is RENTA ATRIBUIBLE on one and falls
inside REFERENCIA CATASTRAL on the other. A position match therefore picks exactly
one record, which is what makes it evidence rather than a coincidence.

NO SHEET NAME IS COMPARED. The expected record is derived as the one record whose
fields satisfy every claim exactly, and the assignment is confirmed by requiring
the sibling record to satisfy none of them. Naming the sheet instead would pin this
module to a parser-derived truncation of AEAT's heading, which is the thing the
sibling module declined to do.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.record_design import extract_record_design

from .....core.resources import bundled_path
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The design each revision's completeness manifest cites, by the file AEAT publishes.
#: Both editions are read: the 2025 orden modified the record, so agreeing on these
#: spans across both is a stronger statement than checking either alone.
_MODELO_184_DESIGNS = (
    "02-184-orden-hap-2250-2015-actualizado-por-orden-hfp-1284-2023-de-28-de-noviembre-263-kb-pdf.pdf",
    "01-184-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1430-2025-de-3-de-diciembre-365-kb.pdf",
)


def _claimed_spans() -> dict[str, tuple[int, int]]:
    """``casilla_id -> (first position, last position)`` for every segmento-bearing claim.

    Read from the committed manifests rather than restated here, so a claim added,
    removed or re-pinned is measured on its next run instead of silently diverging
    from a copy.
    """
    modelos, _catalogues = _committed_registry_tree()
    modelo = next(candidate for candidate in modelos if candidate.id == "184")

    spans: dict[str, tuple[int, int]] = {}
    for revision in modelo.revisions.values():
        manifest = revision.completeness_manifest
        if manifest is None:
            continue
        for entry in manifest.casillas:
            if not entry.segmento:
                continue
            number = str(entry.number)
            first, _, last = number.partition("-")
            if not first.isdigit():
                continue
            spans[entry.casilla_id] = (int(first), int(last) if last.isdigit() else int(first))
    return spans


def _records(design_name: str) -> dict[str, set[tuple[int, int]]]:
    """``record name -> the exact spans its fields occupy`` for one design."""
    extraction = extract_record_design(
        bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_184", "files", design_name),
    )
    records: dict[str, set[tuple[int, int]]] = {}
    for sheet in extraction.sheets:
        spans = {
            (field.offset, field.offset + (field.length or 1) - 1) for field in sheet.fields if field.offset is not None
        }
        if spans:
            records[sheet.name] = spans
    return records


@pytest.mark.parametrize("design_name", _MODELO_184_DESIGNS)
def test_every_segmento_claim_lands_on_exactly_one_record(design_name: str) -> None:
    """Each claimed span is a real field of one record, and of one record only.

    Both halves matter. Landing on a field is what makes the claim true; landing on
    only ONE record is what makes the segmento meaningful -- a span every record
    happened to share would confirm the assignment no more than an empty design does.
    """
    claims = _claimed_spans()
    assert claims, "modelo 184 declares no positional segmento claims, so this module tests nothing"

    records = _records(design_name)
    assert len(records) > 1, f"only one record was read from {design_name}; the claims cannot discriminate"

    satisfying = {name: sorted(c for c, span in claims.items() if span in spans) for name, spans in records.items()}
    complete = sorted(name for name, matched in satisfying.items() if len(matched) == len(claims))

    assert len(complete) == 1, (
        "exactly one record must carry every claimed span, or the segmento assignment is not "
        f"determined by the design: {[(name, satisfying[name]) for name in sorted(satisfying)]}"
    )

    others = {name: matched for name, matched in satisfying.items() if name != complete[0] and matched}
    assert not others, (
        "another record also carries a claimed span exactly, so the position match does not "
        f"discriminate between modelo 184's two Tipo 2 records: {others}"
    )


def test_the_sibling_record_carries_different_fields_at_the_same_positions() -> None:
    """The control: the discrimination above is a fact about the design, not about the claims.

    If the two records simply had different field BOUNDARIES everywhere, an exact-span
    match would separate them for uninteresting reasons. What actually separates them is
    content: the same byte positions carry different fields. Asserted on the claimed spans
    themselves, so a future edition that aligned the two records would fail here first and
    explain why the assignment stopped being provable.
    """
    claims = _claimed_spans()
    records = _records(_MODELO_184_DESIGNS[0])

    covering_records = {
        name
        for name, spans in records.items()
        for span in claims.values()
        if any(start <= span[1] and end >= span[0] for start, end in spans)
    }

    assert len(covering_records) > 1, (
        "only one record has any field overlapping the claimed positions, so the exact-span match "
        "is separating records that never competed and proves less than it appears to"
    )
