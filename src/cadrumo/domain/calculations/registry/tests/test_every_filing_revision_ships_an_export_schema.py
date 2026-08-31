"""Every filing-grade revision ships an export schema, and it is a schema that carries something.

This is the export axis of the registry's completion criterion, stated so it cannot
quietly regress. A revision the registry marks ``filing`` claims it can produce a
return; a filing revision with no export schema, or with an empty one, claims that
while carrying nothing that could be filed.

GRADE IS THE POPULATION, AND READING IT IS THE WHOLE MEASUREMENT. Roughly a third of
the revisions in the tree are ``applicability`` grade: they exist to answer whether a
taxpayer has an obligation for a period, not how to file it. Modelo 390's 2021 revision
says so in its own reviewer note -- "filing layout authority is not claimed" -- and
carries ten casillas and no records on purpose. Counting export records without reading
``authority_grade`` reports twenty revisions as gaps when six are a different question
and fourteen are not gaps at all.

TWO FORMATS SHIP, AND THEY ARE EMPTY IN DIFFERENT WAYS. A ``fixed_width`` layout is
empty when it declares no record, or a record with no field. An ``xml_dictionary``
layout -- modelo 100's six ejercicios, which is why they carry no records and are not a
gap -- is empty when its ``dictionary_source_ref`` names nothing the catalogue holds.
Asserting "has a layout" alone would pass a layout that ships neither.

NO COUNT IS PINNED. Not the sixty-seven filing revisions, not the sixty-one fixed-width
layouts, not the six dictionaries. A modelo enrolled or retired tomorrow moves all three
and none of them is the property. What is asserted is that the filing population is
non-empty, that both formats are represented so neither branch is vacuous, and that
every member carries a schema with content in it.
"""

from __future__ import annotations

import pytest

from .....core.export_layout_format import ExportLayoutFormat
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_GRADE = "filing"


def _filing_revisions():
    """``(modelo id, revision id, revision)`` for every revision claiming filing authority."""
    modelos, catalogues = _committed_registry_tree()
    rows = [
        (modelo.id, revision_id, revision)
        for modelo in sorted(modelos, key=lambda candidate: candidate.id)
        for revision_id, revision in sorted(modelo.revisions.items())
        if str(getattr(revision, "authority_grade", "") or "").lower() == _FILING_GRADE
    ]
    return rows, catalogues


def test_the_population_splits_by_grade_so_this_module_is_not_measuring_everything() -> None:
    """Both grades must exist, or reading ``authority_grade`` decides nothing.

    If every revision were filing grade this module would silently become a
    whole-tree assertion, and the applicability revisions that legitimately ship no
    filing schema would start failing it. If none were, it would assert nothing at all.
    """
    modelos, _catalogues = _committed_registry_tree()
    grades = {
        str(getattr(revision, "authority_grade", "") or "").lower()
        for modelo in modelos
        for revision in modelo.revisions.values()
    }

    assert _FILING_GRADE in grades, "no revision claims filing authority, so this module tests nothing"
    assert grades - {_FILING_GRADE}, (
        "every revision is filing grade, so this module has become a whole-tree assertion and the "
        f"grade distinction it relies on has stopped existing: {sorted(grades)}"
    )


def test_every_filing_revision_declares_an_export_layout() -> None:
    """A revision that claims it can produce a return must carry the schema to produce one."""
    rows, _catalogues = _filing_revisions()
    assert rows, "no filing-grade revision was found, so this assertion would be vacuous"

    missing = [f"{modelo_id}/{revision_id}" for modelo_id, revision_id, revision in rows if not revision.export_layouts]
    assert not missing, (
        "these revisions claim filing authority but declare no export layout, so the registry says "
        f"they can produce a return while carrying nothing that could be filed: {missing}"
    )


def test_both_export_formats_are_represented_among_filing_revisions() -> None:
    """Neither branch of the emptiness check below may be vacuous.

    Kept separate from the check itself so that a tree which lost every dictionary
    layout fails HERE, naming the cause, rather than passing an assertion that no
    longer examines dictionaries at all.
    """
    rows, _catalogues = _filing_revisions()
    formats = {layout.format for _modelo_id, _revision_id, revision in rows for layout in revision.export_layouts}

    assert ExportLayoutFormat.FIXED_WIDTH in formats, f"no filing revision ships a fixed-width layout: {formats}"
    assert ExportLayoutFormat.XML_DICTIONARY in formats, f"no filing revision ships a dictionary layout: {formats}"


def test_no_filing_export_schema_is_empty() -> None:
    """Each format is judged empty on its own terms, because they carry different things."""
    rows, catalogues = _filing_revisions()

    empty: list[str] = []
    for modelo_id, revision_id, revision in rows:
        for layout in revision.export_layouts:
            where = f"{modelo_id}/{revision_id} {layout.id}"

            if layout.format is ExportLayoutFormat.FIXED_WIDTH:
                if not layout.records:
                    empty.append(f"{where}: fixed-width layout declaring no record")
                    continue
                hollow = [record.id for record in layout.records if not record.fields]
                if hollow:
                    empty.append(f"{where}: record(s) declaring no field: {hollow}")
                continue

            if layout.format is ExportLayoutFormat.XML_DICTIONARY:
                ref = getattr(layout, "dictionary_source_ref", None)
                if not ref:
                    empty.append(f"{where}: dictionary layout naming no dictionary source")
                elif str(ref) not in catalogues.sources:
                    empty.append(f"{where}: dictionary source {str(ref)!r} is not in the catalogue")
                continue

            empty.append(f"{where}: unhandled export format {layout.format!r}, so it is unjudged here")

    assert not empty, "these filing-grade export schemas carry nothing that could be filed:\n  " + "\n  ".join(empty)
