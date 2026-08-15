"""An authored fixed-width layout must be able to write its official design.

The sibling exemption gate refuses a revision declaring NO export layout. It
cannot tell a complete layout from a tenth of one, and Modelo 714 is the proof:
five revisions declaring 127 fields across 10 records against a bundled AEAT
design carrying 1,200+ positions across 12 records, two of them unauthored
entirely -- including the record that carries forma de pago, IBAN and importe
del ingreso. Every one of them loaded clean.

These tests run against the BUNDLED registry and the BUNDLED official designs
rather than a hand-built fixture, because the property under test is about the
shipped corpus: a synthetic revision could satisfy every assertion here while
the real tree shipped a layout that writes a tenth of its form.

**No test here asserts a count.** A tally encodes the day it was written and
then detects nothing; every assertion below pins an IMPLICATION whose two sides
are computed live -- a gap independently derived from the official design on one
side, the gate's own verdict on the other.

The independent derivation is deliberately NARROWER than the production rule.
The gate treats every design position as required unless the design itself
declares it omissible; these tests re-derive only the positions AEAT explicitly
marks ``OBLIGATORIO`` in its own obligatoriness column, and only ask whether ANY
record of the layout writes the coordinate. Both narrowings make the test's set
a strict subset of the gate's, so a disagreement can only mean the gate missed
something -- never that the test and the gate merely restate one rule twice.
"""

from __future__ import annotations

import re

import pytest

from .....core import ExportLayoutFormat
from .._export import derive_export_layouts_from_bindings
from .._record_design import extract_record_design
from .._record_design_schema import RecordDesignExtraction, RecordDesignSheet, RecordDesignSkippedSheet
from .._schema import ExportLayoutDefinition, ModeloDefinition, ModeloRevision, RegistryCatalogues, SourceReference
from .._validate_export_layout_coverage import (
    _design_sources,
    _omissible_reason,
    _read_design_sheets,
    _required_positions,
    validate_export_layout_record_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: AEAT's own explicit obligatoriness marking. Re-declared here rather than
#: imported from the module under test: a test that borrows the production
#: predicate cannot disagree with it, and disagreement is the whole signal.
_OBLIGATORIO = re.compile(r"\bOBLIGATORI[OA]\b", re.IGNORECASE)

#: One ``@offset+length`` coordinate as the refusal enumerates it.
_ENUMERATED_COORDINATE = re.compile(r"@(\d+)\+(\d+)")

#: A real bundled layout this gate must refuse. Anchored by name so the module
#: cannot pass vacuously, and re-derived by
#: ``test_the_fixture_anchor_still_names_an_incomplete_layout`` so a rename or a
#: repair turns into a failed anchor rather than a silently skipped test.
_INCOMPLETE_ANCHOR = ("714", "2021", "modelo-714-fichero-aeat")


def _fixed_width_layouts(revision: ModeloRevision) -> tuple[ExportLayoutDefinition, ...]:
    """Resolve layouts the way snapshot build -- and the gate -- resolve them.

    Through ``derive_export_layouts_from_bindings`` rather than off
    ``revision.export_layouts`` directly, so a record assembled from
    ``binding_record`` selectors carries its materialised fields here too.
    Reading the raw tuple would make Modelo 720's records look empty and hand
    this test a gap the gate correctly does not see.
    """
    return tuple(
        layout
        for layout in derive_export_layouts_from_bindings(revision)
        if layout.format is ExportLayoutFormat.FIXED_WIDTH
    )


def _revisions_with_fixed_width_layouts(
    modelos: tuple[ModeloDefinition, ...],
) -> list[tuple[str, str, ModeloRevision]]:
    return [
        (modelo.id, revision_id, revision)
        for modelo in modelos
        for revision_id, revision in modelo.revisions.items()
        if _fixed_width_layouts(revision)
    ]


def _design_sheets(
    layout: ExportLayoutDefinition,
    catalogues: RegistryCatalogues,
) -> tuple[RecordDesignSheet, ...]:
    """Read every official design sheet backing ``layout``, refusing a partial read."""
    sheets: list[RecordDesignSheet] = []
    for source in _design_sources(layout, catalogues.sources):
        read = _read_design_sheets(source)
        assert not isinstance(read, str), f"bundled design for {layout.id!r} unreadable: {read}"
        sheets.extend(read)
    return tuple(sheets)


def _written_coordinates(layout: ExportLayoutDefinition) -> set[tuple[int, int]]:
    """Every ``(offset, length)`` slot ANY record of the layout declares."""
    return {
        (field.offset, field.length)
        for record in layout.records
        for field in record.fields
        if field.offset is not None and field.length is not None
    }


def _obligatorio_gap(
    layout: ExportLayoutDefinition,
    catalogues: RegistryCatalogues,
) -> set[tuple[str, int, int]]:
    """Return AEAT-marked-obligatorio positions no record of ``layout`` can write.

    A strict subset of what the gate itself demands, on two axes: only positions
    AEAT explicitly marks obligatorio, and only a coordinate no record at all
    declares. A non-empty result is therefore an unarguable gap.
    """
    written = _written_coordinates(layout)
    return {
        (sheet.name, field.offset, field.length)
        for sheet in _design_sheets(layout, catalogues)
        for field in sheet.fields
        if _OBLIGATORIO.search(field.validation or "") and (field.offset, field.length) not in written
    }


def _gate(revision: ModeloRevision, catalogues: RegistryCatalogues) -> list[str]:
    return validate_export_layout_record_coverage(
        prefix="modelo T revision R", revision=revision, source_refs=catalogues.sources
    )


def test_the_gate_examines_real_bundled_designs(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Anti-vacuity: the bundled tree really does reach this gate with a real design.

    Every other test here is conditional on a bundled fixed-width layout whose
    official design reads completely. If that population were empty the whole
    module would pass while asserting nothing, which is the failure shape this
    gate exists to remove -- so it is asserted directly rather than assumed.
    """
    modelos, catalogues = registry_tree
    examined = [
        (modelo_id, revision_id, layout.id)
        for modelo_id, revision_id, revision in _revisions_with_fixed_width_layouts(modelos)
        for layout in _fixed_width_layouts(revision)
        if _design_sources(layout, catalogues.sources) and _design_sheets(layout, catalogues)
    ]
    assert examined, "no bundled fixed-width layout resolves a readable official record design"


def test_the_fixture_anchor_still_names_an_incomplete_layout(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Re-derive the anchor's property so a rename cannot make this module vacuous.

    The anchor names a layout by id. If it were repaired, renamed or retired,
    every assertion keyed on it would start passing for the wrong reason; so the
    property it is named for -- that it leaves AEAT-obligatorio positions
    unwritable -- is recomputed from the official design here.
    """
    modelo_id, revision_id, layout_id = _INCOMPLETE_ANCHOR
    modelos, catalogues = registry_tree
    modelo = next((candidate for candidate in modelos if candidate.id == modelo_id), None)
    assert modelo is not None, f"anchor modelo {modelo_id!r} is no longer in the bundled registry"
    revision = modelo.revisions.get(revision_id)
    assert revision is not None, f"anchor revision {revision_id!r} is no longer declared by modelo {modelo_id!r}"
    layout = next((candidate for candidate in _fixed_width_layouts(revision) if candidate.id == layout_id), None)
    assert layout is not None, f"anchor layout {layout_id!r} is no longer a fixed-width layout on this revision"

    gap = _obligatorio_gap(layout, catalogues)
    assert gap, (
        f"anchor layout {layout_id!r} no longer leaves any AEAT-obligatorio position unwritten. If it was "
        f"genuinely completed, move this anchor to another incomplete layout rather than deleting it"
    )
    assert _gate(revision, catalogues), f"the gate accepts anchor layout {layout_id!r} despite the gap {sorted(gap)}"


def test_an_unwritable_obligatorio_position_forces_a_refusal(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Implication, both sides live: an independently derived gap must red the gate.

    Runs over every bundled fixed-width revision rather than a chosen one, so a
    layout that starts under-writing its design is caught wherever it appears.
    """
    modelos, catalogues = registry_tree
    unreported: list[str] = []
    for modelo_id, revision_id, revision in _revisions_with_fixed_width_layouts(modelos):
        gaps = {layout.id: _obligatorio_gap(layout, catalogues) for layout in _fixed_width_layouts(revision)}
        if not any(gaps.values()):
            continue
        if not _gate(revision, catalogues):
            unreported.append(f"modelo {modelo_id} revision {revision_id}: {gaps}")
    assert not unreported, "layouts with unwritable AEAT-obligatorio positions the gate did not refuse: " + "; ".join(
        unreported
    )


def test_every_enumerated_coordinate_is_a_real_unwritten_design_position(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Soundness: the worklist a refusal prints must be true of the official design.

    The refusal is meant to BE the authoring worklist, so a coordinate it names
    that is not a real position of that design record would send an author to
    write bytes AEAT does not declare -- a worse outcome than the silence this
    gate replaces.
    """
    modelos, catalogues = registry_tree
    for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos):
        for layout in _fixed_width_layouts(revision):
            declared = {
                (field.offset, field.length) for sheet in _design_sheets(layout, catalogues) for field in sheet.fields
            }
            if not declared:
                continue
            written = _written_coordinates(layout)
            for failure in _gate(revision, catalogues):
                if repr(layout.id) not in failure:
                    continue
                for offset, length in _ENUMERATED_COORDINATE.findall(failure):
                    coordinate = (int(offset), int(length))
                    assert coordinate in declared, (
                        f"layout {layout.id!r} refusal names {coordinate}, which its official record "
                        f"design does not declare at all"
                    )
                    if coordinate in written:
                        # Legitimate only when the coordinate is written by a
                        # DIFFERENT record than the one the design record joined
                        # to; a coordinate written by the joined record must
                        # never be reported.
                        assert any(
                            all(
                                (field.offset, field.length) != coordinate
                                for field in record.fields
                                if field.offset is not None
                            )
                            for record in layout.records
                        ), f"layout {layout.id!r} reports {coordinate} which every record writes"


def test_deleting_one_required_slot_reds_an_accepted_layout(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The gate is unproven until it bites: break an ACCEPTED layout and watch it red.

    Mutates a ``model_copy`` of the real loaded revision, never a fixture stub,
    so the production validator runs against production data. The original
    objects are untouched and are re-checked afterwards.
    """
    modelos, catalogues = registry_tree
    accepted = [
        (revision, layout)
        for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos)
        for layout in _fixed_width_layouts(revision)
        if not _gate(revision, catalogues)
    ]
    if not accepted:
        pytest.fail(
            "no bundled fixed-width layout is currently accepted, so the accepting direction of this "
            "gate is unexercised. Do not delete this test: a gate that only ever refuses proves nothing"
        )
    revision, layout = accepted[0]
    # The victim is CHOSEN through the production requiredness derivation, not
    # asserted by it: the claim under test is that deleting a slot the gate
    # calls required makes the gate red, so the gate's own notion of required is
    # the right selector. The two accepted layouts back designs AEAT publishes
    # with no obligatoriness column at all, so the narrower marking this module
    # derives gaps from selects nothing here.
    declared = {
        (position.offset, position.length)
        for sheet in _design_sheets(layout, catalogues)
        for position in _required_positions(sheet)
    }
    victim_record, victim = next(
        (record, field)
        for record in layout.records
        for field in record.fields
        if (field.offset, field.length) in declared
    )
    broken_record = victim_record.model_copy(
        update={"fields": tuple(field for field in victim_record.fields if field is not victim)}
    )
    broken_layout = layout.model_copy(
        update={"records": tuple(broken_record if r.id == victim_record.id else r for r in layout.records)}
    )
    # Substituted BY ID, not by identity: the layout under test came out of
    # ``derive_export_layouts_from_bindings``, which may hand back a
    # materialised copy rather than the object the revision holds, and an
    # identity swap would then silently substitute nothing and prove nothing.
    broken_revision = revision.model_copy(
        update={
            "export_layouts": tuple(
                broken_layout if candidate.id == layout.id else candidate for candidate in revision.export_layouts
            )
        }
    )
    failures = _gate(broken_revision, catalogues)
    assert failures, "deleting a required export slot left the gate green"
    assert f"@{victim.offset}+{victim.length}" in " ".join(failures), (
        "the refusal did not name the coordinate whose slot was deleted, so its worklist is not usable"
    )
    assert not _gate(revision, catalogues), "the untouched revision did not stay accepted"


def test_a_partial_design_read_refuses_instead_of_reporting_coverage(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A design whose records were dropped must never yield a coverage verdict.

    Coverage derived from a partly-read design is inflated by exactly the
    records that went missing, and nothing downstream can tell that from real
    coverage -- so partiality has to refuse rather than measure. Built from a
    REAL bundled extraction with one sheet moved into ``skipped``, so the
    refusal comes from the shipped completeness contract, not from a stub.
    """
    modelos, catalogues = registry_tree
    layout = next(
        layout
        for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos)
        for layout in _fixed_width_layouts(revision)
        if _design_sources(layout, catalogues.sources)
    )
    source = _design_sources(layout, catalogues.sources)[0]
    whole = extract_record_design(_bundled_design_path(source))
    assert whole.is_complete, "pick a design that reads completely, so partiality is the only difference"
    partial = RecordDesignExtraction(
        source=whole.source,
        sheets=whole.sheets[:-1],
        skipped=(RecordDesignSkippedSheet(name=whole.sheets[-1].name, reason="dropped for this test"),),
    )
    with pytest.raises(Exception, match="PARTIAL design"):
        partial.require_complete()


def test_an_unreachable_design_refuses_instead_of_passing(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A design nobody could read must never be reported as covered.

    Uses a real :class:`SourceReference` copied onto a path that does not exist,
    so the unreachable branch is exercised through the production resolver
    rather than by patching it away.
    """
    _modelos, catalogues = registry_tree
    real = next(source for source in catalogues.sources.values() if source.kind == "record_design")
    missing = real.model_copy(update={"corpus_path": "corpus/aeat_official/disenos_registro/does/not/exist.xls"})
    read = _read_design_sheets(missing)
    assert isinstance(read, str), "an unreachable official design was read as sheets"
    assert "not reachable" in read


def _bundled_design_path(source: SourceReference):
    from .....core.resources import resolve_corpus_binary

    path = resolve_corpus_binary(*source.corpus_path.split("/"))
    assert path is not None, f"bundled design {source.id!r} is not resolvable"
    return path


def _component_parents(
    modelos: tuple[ModeloDefinition, ...],
    catalogues: RegistryCatalogues,
) -> list[tuple[RecordDesignSheet, object]]:
    """Every design field AEAT desglosa into sub-fields, across the bundled tree."""
    return [
        (sheet, field)
        for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos)
        for layout in _fixed_width_layouts(revision)
        for sheet in _design_sheets(layout, catalogues)
        for field in sheet.fields
        if field.components
    ]


def test_a_desglosado_field_requires_its_sub_fields_and_not_its_parent_span(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Where AEAT desglosa a field, the sub-fields are the positions.

    The parent's printed span is a grouping, not a slot: a layout writing it as
    one field writes taxpayer data straight across whatever the design reserves
    inside it. Both directions are pinned here -- the parent coordinate must NOT
    be demanded, and every non-omissible sub-field must be -- so the rule cannot
    be satisfied by dropping the parent alone.

    Anti-vacuity is explicit: the population is asserted non-empty first, so a
    corpus that stopped carrying a desglosado field fails here rather than
    passing this test by examining nothing.
    """
    modelos, catalogues = registry_tree
    parents = _component_parents(modelos, catalogues)
    assert parents, "no bundled design declares a desglosado field, so this rule is untested"
    for sheet, parent in parents:
        required = {(position.offset, position.length) for position in _required_positions(sheet)}
        assert (parent.offset, parent.length) not in required, (
            f"{sheet.name!r} still demands the desglosado parent span "
            f"@{parent.offset}+{parent.length} as a single position; a layout can only satisfy that "
            f"by writing one blob across its sub-fields"
        )
        for component in parent.components:
            coordinate = (component.offset, component.length)
            if _omissible_reason(component) is not None:
                assert coordinate not in required, (
                    f"{sheet.name!r} demands sub-field @{component.offset}+{component.length}, which "
                    f"the design itself declares omissible ({component.description!r})"
                )
                continue
            assert coordinate in required, (
                f"{sheet.name!r} does not demand sub-field @{component.offset}+{component.length} "
                f"({component.description!r}), so a layout omitting a real datum reads as complete"
            )


def test_writing_a_desglosado_parent_as_one_blob_is_refused(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The bite proof: the shape that corrupts the filing must not satisfy the gate.

    Replaces the faithful sub-field slots of a REAL bundled layout with the
    single parent-span field the old rule rewarded, in memory only, and asserts
    the gate refuses and names the sub-fields it can no longer write. Nothing on
    disk is touched, so a peer sweep cannot capture the mutation and a crashed
    run leaves no residue.
    """
    modelos, catalogues = registry_tree
    subject = next(
        (
            (revision, layout, sheet, parent)
            for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos)
            for layout in _fixed_width_layouts(revision)
            for sheet in _design_sheets(layout, catalogues)
            for parent in sheet.fields
            if parent.components
        ),
        None,
    )
    assert subject is not None, "no bundled layout is backed by a design declaring a desglosado field"
    revision, layout, _sheet, parent = subject
    span = range(parent.offset, parent.offset + parent.length)
    expected = [
        component
        for component in parent.components
        if _omissible_reason(component) is None and component.offset in span
    ]
    assert expected, "the desglosado parent carries no required sub-field, so this proof would be vacuous"

    def _blobbed(record):
        outside = tuple(field for field in record.fields if field.offset not in span)
        if len(outside) == len(record.fields):
            return record
        donor = next(field for field in record.fields if field.offset in span)
        blob = donor.model_copy(update={"offset": parent.offset, "length": parent.length})
        return record.model_copy(update={"fields": (*outside, blob)})

    blobbed_layout = layout.model_copy(update={"records": tuple(_blobbed(r) for r in layout.records)})
    blobbed_revision = revision.model_copy(
        update={
            "export_layouts": tuple(
                blobbed_layout if candidate.id == layout.id else candidate for candidate in revision.export_layouts
            )
        }
    )
    failures = _gate(blobbed_revision, catalogues)
    assert failures, "collapsing a desglosado field into its parent span left the gate green"
    reported = " ".join(failures)
    for component in expected:
        assert f"@{component.offset}+{component.length}" in reported, (
            f"the refusal did not name sub-field @{component.offset}+{component.length}, so an author "
            f"cannot tell which datum the blob swallowed"
        )
