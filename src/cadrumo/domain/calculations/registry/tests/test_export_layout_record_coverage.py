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

from .....core.export_layout_format import ExportLayoutFormat
from .._validate_export_layout_coverage import (
    _administration_reserved,
    _belongs_to_layout,
    _covers,
    _design_sources,
    _missing_report,
    _omissible_reason,
    _read_design_sheets,
    _required_positions,
    _sheet_constants,
    validate_export_layout_record_coverage,
)
from ..errors import RegistryValidationError
from ..export import derive_export_layouts_from_bindings
from ..record_design import extract_record_design
from ..record_design_schema import (
    RecordDesignExtraction,
    RecordDesignField,
    RecordDesignNote,
    RecordDesignSheet,
    RecordDesignSkippedSheet,
)
from ..schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ..schema_exports import (
    AuxiliaryEnvelopeHeaderDefinition,
    ExportLayoutDefinition,
    FilingEnvelopePrefixFieldDeclaration,
    FilingEnvelopePrefixRole,
)
from ..schema_references import SourceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: AEAT's own explicit obligatoriness marking. Re-declared here rather than
#: imported from the module under test: a test that borrows the production
#: predicate cannot disagree with it, and disagreement is the whole signal.
_OBLIGATORIO = re.compile(r"\bOBLIGATORI[OA]\b", re.IGNORECASE)

#: One ``@offset+length`` coordinate as the refusal enumerates it.
_ENUMERATED_COORDINATE = re.compile(r"@(\d+)\+(\d+)")

#: AEAT's "this position holds a fixed value" marking, and the quoted value
#: itself. Re-declared here rather than imported, for the same reason
#: ``_OBLIGATORIO`` is: a test borrowing the production predicates cannot
#: disagree with them, and disagreement is the signal.
_CONSTANT_WORD = re.compile(r"[Cc]onstante")
_QUOTED_TEXT = re.compile("[\"'«“‘][^\"'»«”’‘“]{1,40}[\"'»”’]")

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
    """Return the official design sheets backing ``layout`` that could be read.

    An unreadable source is SKIPPED rather than asserted on, because
    "unreadable" is a real and correct state the gate itself reports: a sheet
    whose rows leave holes in its declared extent is recorded as skipped, so
    ``require_complete`` refuses it. Asserting here would turn the gate's own
    honest refusal into a test error.

    Skipped per SOURCE, never per layout. Zeroing every sheet because one of a
    layout's sources went unreadable throws away the readable ones too, which
    silently emptied a sibling test's whole population and made its
    anti-vacuity assertion -- correctly -- fire.
    """
    sheets: list[RecordDesignSheet] = []
    for source in _design_sources(layout, catalogues.sources):
        read = _read_design_sheets(source)
        if isinstance(read, str):
            continue
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

    ``layout`` MUST be one resolved through ``derive_export_layouts_from_bindings``
    -- as ``_fixed_width_layouts`` returns and the gate itself uses -- because
    ``_written_coordinates`` reads ``layout.records[].fields`` directly. Passing
    a raw ``revision.export_layouts`` entry would report every binding-derived
    position as an unwritable gap: Modelo 369's union layout carries 58 authored
    fields that derive to 883.

    Sheets belonging to ANOTHER schema in the same shared workbook are excluded,
    exactly as the gate excludes them. Modelo 369's three schemas cite one
    workbook, so without this every schema was measured against the other two's
    sheets and reported gaps for records it is not supposed to write at all.
    """
    written = _written_coordinates(layout)
    return {
        (sheet.name, field.offset, field.length)
        for sheet in _design_sheets(layout, catalogues)
        if _belongs_to_layout(sheet, layout.records)
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
    cohort = {
        (candidate_modelo, candidate_revision, layout.id): gap
        for candidate_modelo, candidate_revision, revision in _revisions_with_fixed_width_layouts(modelos)
        for layout in _fixed_width_layouts(revision)
        if (gap := _obligatorio_gap(layout, catalogues))
    }
    if not cohort:
        # The cohort emptied: every AEAT-obligatorio position in the bundled
        # tree is now writable. That is the campaign's goal reached on this
        # narrow axis, not a reason to delete the anchor -- so the assertion
        # becomes the positive statement of the same fact, and re-engages by
        # itself the moment any layout stops writing an obligatorio position.
        # The gate's own broader rule (every non-omissible position, not only
        # the obligatorio-marked ones) still refuses layouts today; those are
        # covered by the live-derived tests below, which need no anchor.
        assert not _obligatorio_gap_anywhere(modelos, catalogues), "cohort recomputed non-empty within one test"
        return

    assert (modelo_id, revision_id, layout_id) in cohort, (
        f"anchor layout {layout_id!r} no longer leaves any AEAT-obligatorio position unwritten, but "
        f"{sorted(cohort)} still do. Move the anchor to one of them rather than deleting it"
    )
    modelo = next(candidate for candidate in modelos if candidate.id == modelo_id)
    revision = modelo.revisions[revision_id]
    assert _gate(revision, catalogues), (
        f"the gate accepts anchor layout {layout_id!r} despite the gap {sorted(cohort[(modelo_id, revision_id, layout_id)])}"
    )


def _obligatorio_gap_anywhere(
    modelos: tuple[ModeloDefinition, ...],
    catalogues: RegistryCatalogues,
) -> set[tuple[str, int, int]]:
    """Every AEAT-obligatorio position unwritable by its own layout, tree-wide."""
    found: set[tuple[str, int, int]] = set()
    for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos):
        for layout in _fixed_width_layouts(revision):
            found |= _obligatorio_gap(layout, catalogues)
    return found


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
            # Sub-fields count as declared: where AEAT desglosa a field the gate
            # enumerates the SUB-FIELD coordinates, which live under
            # ``components`` and never appear in ``sheet.fields``. Reading only
            # the top level would call a correctly-reported sub-field a
            # fabricated coordinate.
            declared = {
                (candidate.offset, candidate.length)
                for sheet in _design_sheets(layout, catalogues)
                for field in sheet.fields
                for candidate in (field, *field.components)
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
                    if "auxiliary envelope header" in failure:
                        # An auxiliary header joins to NO authored record, so the
                        # "written by a different record" reasoning below does not
                        # apply to it. Its own opening tag sits at the same low
                        # offsets the numbered records use for theirs, and another
                        # record writing (1, 2) does not emit the HEADER's two
                        # bytes. The declared-position assertion above still runs,
                        # so a fabricated coordinate is still caught here.
                        continue
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
    with pytest.raises(RegistryValidationError, match="PARTIAL design"):
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
) -> list[tuple[RecordDesignSheet, RecordDesignField]]:
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
            if parent.components and any(_omissible_reason(component) is not None for component in parent.components)
        ),
        None,
    )
    # The subject must RESERVE one of its sub-fields, and selecting on that is
    # the discipline. Byte-extent coverage cannot object to a blob laid over
    # sub-fields that are all real data -- the blob's bytes cover every one of
    # them -- so what makes the shape refusable is precisely that it writes
    # AEAT's own bytes. Selecting merely on ``parent.components`` was
    # accidentally correct while Modelo 576 was the only bundled design
    # carrying any; as soon as another design declared components, this picked
    # a parent reserving nothing and the proof went green against a gate that
    # had not changed. The vacuity assertion further down states this same
    # requirement, so pinning it in the selection is that claim moved to where
    # it can bite instead of reporting the weaker "left the gate green".
    assert subject is not None, (
        "no bundled layout is backed by a design declaring a desglosado field that reserves a sub-field"
    )
    revision, layout, _sheet, parent = subject
    span = range(parent.offset, parent.offset + parent.length)

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

    # Byte-extent coverage alone cannot catch this: the blob's bytes DO cover
    # every sub-field's span. What makes it a defect is that the same field
    # claims the bytes AEAT reserves for itself, so that is what the refusal
    # must name -- the intruding field and the reserved range it swallowed.
    reserved = [
        component
        for component in parent.components
        if _omissible_reason(component) is not None and component.offset in span
    ]
    assert reserved, "the desglosado parent reserves no sub-field, so this proof would be vacuous"
    assert f"@{parent.offset}+{parent.length}" in reported, (
        f"the refusal did not name the offending field @{parent.offset}+{parent.length}, so an author "
        f"cannot tell which field to split"
    )
    for component in reserved:
        last = component.offset + component.length - 1
        assert f"@{component.offset}..{last}" in reported, (
            f"the refusal did not name the reserved bytes @{component.offset}..{last} the blob wrote "
            f"over, so an author cannot tell what makes the shape wrong"
        )


def _split_constant_rows(
    modelos: tuple[ModeloDefinition, ...],
    catalogues: RegistryCatalogues,
) -> list[tuple[RecordDesignSheet, RecordDesignField]]:
    """Design rows declaring ``Constante`` in one cell and quoting the value in another."""
    rows = []
    for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos):
        for layout in _fixed_width_layouts(revision):
            for sheet in _design_sheets(layout, catalogues):
                for field in sheet.fields:
                    together = any(
                        text and _CONSTANT_WORD.search(text) and _QUOTED_TEXT.search(text)
                        for text in (field.content, field.description)
                    )
                    word = any(text and _CONSTANT_WORD.search(text) for text in (field.content, field.description))
                    quoted = any(text and _QUOTED_TEXT.search(text) for text in (field.content, field.description))
                    if word and quoted and not together:
                        rows.append((sheet, field))
    return rows


def test_a_constant_split_across_cells_is_still_read(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """AEAT splits ``Constante`` from its value as readily as it keeps them together.

    Modelo 111 writes ``Constante.`` in Descripción and ``"<T"`` in Contenido;
    Modelo 714's ``714-00`` envelope does the same. Requiring the two adjacent
    emptied the constant set for those sheets, and a sheet with no constants
    cannot be joined to its authored record at all -- so the check silently
    degraded to the weaker layout-wide question with nothing announcing it.

    Pins the implication rather than a tally: every split row must yield a
    constant at its own coordinate, and the population is asserted non-empty so
    a corpus that stopped carrying the split shape fails here instead of
    passing by examining nothing.
    """
    modelos, catalogues = registry_tree
    rows = _split_constant_rows(modelos, catalogues)
    assert rows, "no bundled design splits a Constante declaration across cells, so this rule is untested"
    for sheet, field in rows:
        constants = _sheet_constants(sheet)
        assert (field.offset, field.length) in constants, (
            f"{sheet.name!r} @{field.offset}+{field.length} declares a constant across two cells "
            f"({field.description!r} / {field.content!r}) but no constant was read, so this sheet "
            f"cannot be joined to its authored record"
        )


def test_a_row_aeat_does_not_mark_constante_yields_no_constant(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The declaration word stays required, so an enumeration is never mistaken for a constant.

    Reading a quoted value out of any row would take Modelo 111's período cell
    (``"01" ... "12" o "1T" … "4T"``) as the constant ``01`` and join the sheet
    to the WRONG record -- a confident wrong answer, which is worse than the
    missing one this fix removes. Every constant must come from a row AEAT
    itself marks ``Constante`` -- or from the identifier-block rows whose
    vocabulary ("identificador de modelo y página", "fin de registro") names
    the fixed ``<T`` delimiters directly, which is how Modelo 360's design
    declares them without the word.
    """
    from .._validate_export_layout_coverage import _IDENTIFIER_VOCABULARY

    modelos, catalogues = registry_tree
    checked = 0
    for _modelo_id, _revision_id, revision in _revisions_with_fixed_width_layouts(modelos):
        for layout in _fixed_width_layouts(revision):
            for sheet in _design_sheets(layout, catalogues):
                constants = _sheet_constants(sheet)
                for field in sheet.fields:
                    if any(text and _CONSTANT_WORD.search(text) for text in (field.content, field.description)):
                        continue
                    if any(text and _IDENTIFIER_VOCABULARY.search(text) for text in (field.content, field.description)):
                        continue
                    checked += 1
                    assert (field.offset, field.length) not in constants, (
                        f"{sheet.name!r} @{field.offset}+{field.length} yielded a constant although AEAT "
                        f"does not mark it Constante ({field.description!r} / {field.content!r})"
                    )
    assert checked, "no unmarked design row was examined, so this guard proved nothing"


def _every_declared_design_sheet(
    catalogues: RegistryCatalogues,
) -> list[RecordDesignSheet]:
    """Every sheet of every record design the registry declares.

    Broader than the designs a layout happens to cite, because the properties
    tested through it are readings of AEAT's own vocabulary rather than
    properties of one modelo.

    Deliberately tolerant of a PARTIAL read, unlike ``_read_design_sheets``.
    Completeness guards coverage ARITHMETIC -- a ratio derived from a half-read
    design is inflated by exactly the records that were dropped -- whereas
    classifying one row needs only that row. Requiring completeness here
    silently emptied the bare-label population instead: all sixty of those rows
    live in Modelo 840, whose design is one of the seventeen the reader cannot
    finish, so the fallback assertion passed its own emptiness check and then
    proved nothing.
    """
    from .....core.resources import resolve_corpus_binary

    sheets: list[RecordDesignSheet] = []
    for source in (
        source
        for source in catalogues.sources.values()
        if source.kind == "record_design" and source.design_authority == "authoritative"
    ):
        path = resolve_corpus_binary(*source.corpus_path.split("/"))
        if path is None:
            continue
        sheets.extend(extract_record_design(path).sheets)
    return sheets


def _every_declared_design_row(
    catalogues: RegistryCatalogues,
) -> list[RecordDesignField]:
    """Every row of every declared record design, sub-fields included."""
    return [
        candidate
        for sheet in _every_declared_design_sheet(catalogues)
        for field in sheet.fields
        for candidate in (field, *field.components)
    ]


def test_a_reservado_row_naming_the_aeat_as_owner_stays_reserved(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """AEAT naming itself as the owner settles the row, whatever its contenido says.

    Anchored on AEAT's literal wording rather than on the production predicate,
    so this can disagree with it. Modelo 131 ``@627+1`` and Modelo 303
    ``@840+1``/``@841+1`` read ``RESERVADO PARA LA A.E.A.T.`` and yet declare
    ``"0" o blanco`` -- a value set on a row that is unambiguously the
    administración's, where ``"0"`` is an AEAT-side marker and not a filer tick.
    A rule led by the contenido would hand all three to the filer, so the owner
    signal has to be read first.
    """
    _modelos, catalogues = registry_tree
    owned = [
        field
        for field in _every_declared_design_row(catalogues)
        if "RESERVADO PARA LA A.E.A.T." in (field.description or "").upper()
        or "RESERVADO PARA LA AEAT" in (field.description or "").upper()
    ]
    assert owned, "no design row names the A.E.A.T. as owner, so this proved nothing"
    assert any((field.content or "").strip() for field in owned), (
        "no owner-named row carries a contenido, so the ordering this test guards is unexercised"
    )
    for field in owned:
        assert _administration_reserved(field), (
            f"@{field.offset}+{field.length} names the A.E.A.T. as owner "
            f"({field.description!r}, contenido {field.content!r}) but was classified as filer data"
        )


def test_the_colegio_concertado_row_is_filer_data_not_reserved_space(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """Modelo 111 ``@552+1`` carries a mark the presenter writes, despite its label.

    AEAT describes it ``Reservado. Administración presentando declaración de
    Colegio Concertado (CC)`` and gives it contenido ``"X" o blanco`` -- the same
    filer-tick spelling it uses for ``Declaración complementaria`` three rows
    earlier. It marks Spain's *pago delegado* case, where an education
    Administración presents the Modelo 111 for a state-subsidised school: a fact
    only the presenter holds, and an input TO the AEAT rather than a byte it owns.

    Reading the ``Reservado`` label alone excused a real datum from coverage AND
    made the layout that correctly writes it look like a trespass into reserved
    bytes -- the tree was internally inconsistent because the predicate was.
    """
    _modelos, catalogues = registry_tree
    tagged = [
        field for field in _every_declared_design_row(catalogues) if "Colegio Concertado" in (field.description or "")
    ]
    assert tagged, "the Colegio Concertado row is no longer in the bundled corpus; re-anchor this test"
    for field in tagged:
        # The tick is read from whichever cell the edition prints it in. The two
        # xlsx designs declare it in Contenido; the 2012 PDF is recovered from
        # chart geometry and has no content column, so the identical declaration
        # arrives merged into the description. Demanding the content cell made
        # this row's premise depend on the extraction shape rather than on what
        # AEAT states, which is the axis the production rule now also spans.
        assert '"X"' in f"{field.content or ''} {field.description or ''}", (
            f"@{field.offset}+{field.length} no longer declares AEAT's filer tick "
            f"(contenido {field.content!r}, description {field.description!r}); "
            "the premise of this test has changed"
        )
        assert not _administration_reserved(field), (
            f"@{field.offset}+{field.length} carries a filer mark but was excused as reserved"
        )
        assert _omissible_reason(field) is None, (
            f"@{field.offset}+{field.length} carries a filer datum yet the production rule "
            f"still excuses it: {_omissible_reason(field)!r}"
        )


def test_a_bare_reservado_label_with_no_contenido_stays_reserved(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The fallback keeps the label-then-clause population reserved.

    Modelo 840 carries around forty rows shaped ``Reservado. Apart. VII: Cuota
    [103]`` -- the same label-then-clause form as the Modelo 111 row above, and
    with no contenido at all. Nothing there says a filer writes them, so the
    absence of a tick has to leave them reserved.

    This is why the predicate could not be narrowed on WORDING alone: keying on
    the ``para``-less shape would have required every one of these.

    The population is selected on declaring no tick ANYWHERE, which is the
    sentence this test actually asserts. An empty contenido used to stand in for
    that, and the two stopped being equivalent once a geometry-recovered design
    -- which has no contenido column at all -- was found stating its tick in the
    description instead. Selecting on the proxy would put the Modelo 111 row of
    the sibling test into this one's population and demand the opposite verdict
    of the same field.
    """
    _modelos, catalogues = registry_tree
    bare = [
        field
        for field in _every_declared_design_row(catalogues)
        if (field.description or "").strip().startswith("Reservado.")
        and not (field.content or "").strip()
        and '"X"' not in (field.description or "")
    ]
    assert bare, "no bare-label Reservado row was examined, so the fallback proved nothing"
    assert len(bare) > 20, (
        f"only {len(bare)} bare-label rows remain; the Modelo 840 population this "
        "fallback rests on has thinned out and the exclusion needs re-checking"
    )
    for field in bare:
        assert _administration_reserved(field), (
            f"@{field.offset}+{field.length} ({field.description!r}) lost its reservation "
            f"although AEAT names no owner and declares no filer tick"
        )


def test_an_obligatory_blank_is_required_and_satisfied_by_a_filler(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """AEAT can demand a position AND declare its content blank; both bind.

    Thirty-four positions across Modelos 369, 322, 036, 210 and 353 are marked
    obligatorio while their own ``Contenido`` cell reads ``Blancos`` / ``blanco``
    / ``En blanco``. Neither statement overrides the other: the field must be
    emitted so the fixed-width record stays contiguous, and what it emits is
    blanks.

    Demanding real data there made every one of them UNSATISFIABLE -- a filler
    did not cover them, and a value-carrying field would contradict the
    Contenido cell and trip the reserved-span rule for claiming reserved bytes.
    So the assertion is two-sided: a filler must satisfy such a position, and
    writing NOTHING must still fail it, or the rule would be a blanket pass.
    """
    _modelos, catalogues = registry_tree
    blanks = [
        position
        for sheet in _every_declared_design_sheet(catalogues)
        for position in _required_positions(sheet)
        if position.declared_blank
    ]
    assert blanks, "no obligatory-blank position was examined, so this proved nothing"
    assert any(
        position.offset == 12 and "Indicador de página complementaria" in position.description for position in blanks
    ), "a terminal 'En blanco' description sentence must retain its obligatory filler position"
    for position in blanks:
        span = set(range(position.offset, position.offset + position.length))
        assert _covers(position, set(), span), (
            f"{position.sheet!r} @{position.offset}+{position.length} "
            f"({position.description!r}) is an obligatory blank a filler must satisfy"
        )
        assert not _covers(position, set(), set()), (
            f"{position.sheet!r} @{position.offset}+{position.length} passed while the layout "
            f"emits nothing there, so the obligatory-blank allowance is a blanket pass"
        )


def test_a_required_position_that_is_not_a_declared_blank_still_needs_real_data(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The obligatory-blank allowance must not leak to ordinary data positions.

    A filler over a position AEAT expects a datum in is the silent
    under-declaration this gate exists to refuse -- Modelo 190 read 96.2% against
    a real data coverage of 32% while blanking its way there. The allowance is
    keyed strictly on AEAT's own Contenido cell, so every other required
    position must still reject a filler.
    """
    _modelos, catalogues = registry_tree
    ordinary = [
        position
        for sheet in _every_declared_design_sheet(catalogues)
        for position in _required_positions(sheet)
        if not position.declared_blank
    ]
    assert ordinary, "no ordinary required position was examined, so this proved nothing"
    for position in ordinary[:2000]:
        span = set(range(position.offset, position.offset + position.length))
        assert not _covers(position, set(), span), (
            f"{position.sheet!r} @{position.offset}+{position.length} "
            f"({position.description!r}) was satisfied by fill alone"
        )
        assert _covers(position, span, span)


def test_a_position_two_cited_editions_share_is_counted_once(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A layout citing several design editions must not count shared positions twice.

    Modelo 190's 2024 and 2025 Diseños de Registro repeat every sheet they
    share. Counting each citation separately inflated BOTH sides of the ratio --
    it reported 102/106 where the union of its editions declares 53 positions,
    51 of them duplicated. The layout has to write each position ONCE however
    many editions declare it, so a later edition contributes only what it adds.

    The live registry no longer ships a multi-edition layout -- the 190 revision
    split scopes each revision to its own edition -- so the fixture synthesises
    the historic dual citation over the real 2024 and 2025 designs and the real
    perceptor record, and pins the implication rather than the tally: the gate's
    own required count must equal the number of DISTINCT (design record,
    coordinate) pairs the two editions declare between them.
    """
    modelos, catalogues = registry_tree
    m190 = next(m for m in modelos if m.id == "190")
    revision = m190.revisions["2025-y-siguientes"]
    perceptor_record = next(r for r in revision.export_layouts[0].records if r.record_type == "perceptor")
    layout = ExportLayoutDefinition(
        id="synthetic-190-dual-edition",
        format=ExportLayoutFormat.FIXED_WIDTH,
        source_refs=("aeat-dr-190-2024", "aeat-dr-190-2025"),
        legal_refs=("orden-eha-3127-2009:art-1",),
        records=(perceptor_record,),
    )
    sheets = _design_sheets(layout, catalogues)
    assert len(sheets) >= 2, "the fixture must cite both 190 design editions"
    distinct = {
        (sheet.name, position.offset, position.length)
        for sheet in sheets
        if _belongs_to_layout(sheet, layout.records)
        for position in _required_positions(sheet)
    }
    raw = sum(len(_required_positions(sheet)) for sheet in sheets if _belongs_to_layout(sheet, layout.records))
    assert raw > len(distinct), (
        "the synthetic dual-citation fixture must share positions across its two "
        f"editions to be meaningful, but raw={raw} equals distinct={len(distinct)}"
    )
    required, _missing, _lines = _missing_report(sheets, layout.records)
    assert required == len(distinct), (
        f"the dual-citation layout counts {required} required positions where its cited "
        f"editions declare {len(distinct)} distinct ones ({raw - len(distinct)} duplicated); "
        "a shared position must be satisfied once, not once per citation"
    )


def test_an_eedd_delegated_position_is_excused_only_with_its_note_body(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """A position the design delegates to the software house is not the filer's to write.

    AEAT prints "Nota 1: A cumplimentar por las entidades desarrolladoras
    (EEDD)" beneath the M111 field table, and two positions cite it. They
    identify the software house that produced the file; this application holds
    no EEDD registration, so any value would be invented and a blank would
    assert an empty EEDD rather than an absent one.

    Both halves are asserted, because a citation alone must never excuse
    anything: one design's Nota 1 delegates, another's says something else
    entirely. Swapping in a non-delegating body, and removing the definition,
    each restore the requirement.
    """
    _modelos, catalogues = registry_tree
    design = extract_record_design(
        _bundled_design_path(catalogues.sources["aeat-dr-111-2019-v18"]),
    )
    sheet = next(s for s in design.sheets if s.name == "M11100")
    delegated = {
        (field.offset, field.length)
        for field in sheet.fields
        if _omissible_reason(field, sheet) == "delegated to the entidad desarrolladora by the design's own footnote"
    }

    assert delegated == {(93, 4), (101, 9)}, (
        "the EEDD-delegated positions moved; re-derive them from the design rather than "
        f"trusting this pin: {sorted(delegated)}"
    )

    cited = next(field for field in sheet.fields if field.offset == 93)

    non_delegating_sheet = RecordDesignSheet(
        name=sheet.name,
        fields=(),
        notes=(
            RecordDesignNote(
                ordinal="1",
                body="Consignar el importe total de las retenciones practicadas",
            ),
        ),
    )
    undefined_sheet = RecordDesignSheet(name=sheet.name, fields=(), notes=())

    assert _omissible_reason(cited, non_delegating_sheet) is None, (
        "a note body that does not delegate to the EEDD must leave the position required"
    )
    assert _omissible_reason(cited, undefined_sheet) is None, (
        "a citation whose note the sheet never defined must leave the position required"
    )


class TestAeatProgramSealedPositions:
    """AEAT's own electronic-seal slot is omissible, and only on two signals.

    These designs name the field ``SELLO ELECTRÓNICO`` in the cell that NAMES it
    and delegate completion to AEAT's own programs in the cell that describes its
    CONTENT. Neither cell alone settles the row, which is why
    :func:`_administration_reserved` -- which reads the description only, and
    deliberately so -- leaves them required.
    """

    @staticmethod
    def _sealed_rows(catalogues: RegistryCatalogues) -> list[RecordDesignField]:
        return [
            field
            for field in _every_declared_design_row(catalogues)
            if "SELLO ELECTR" in (field.description or "").upper()
            and re.search(
                r"cumplimentad[oa]\s+(?:[^.;]{0,30}?\s+)?por\s+(?:los\s+)?programas[^.;]{0,40}?a\.?e\.?a\.?t\.?",
                field.content or "",
                re.IGNORECASE,
            )
        ]

    def test_the_bundled_seal_rows_are_omissible(self, registry_tree) -> None:
        """Real corpus rows, not a synthetic one: they must stop being demanded."""
        _modelos, catalogues = registry_tree
        sealed = self._sealed_rows(catalogues)

        assert sealed, "no bundled row pairs a sello name with an AEAT-programs delegation"
        for field in sealed:
            assert _omissible_reason(field) is not None, (
                f"@{field.offset}+{field.length} {field.description!r} is AEAT's own seal slot but is "
                f"still demanded of the filer"
            )

    def test_the_description_alone_does_not_excuse_a_seal_row(self, registry_tree) -> None:
        """The control: naming the sello without the delegation stays required.

        Modelo 347's 2008 design is the live case -- it names ``SELLO
        ELECTRÓNICO`` but carries a chart-geometry placeholder where the
        delegation would be, so nothing states whose bytes these are.
        """
        _modelos, catalogues = registry_tree
        named_without_delegation = [
            field
            for field in _every_declared_design_row(catalogues)
            if "SELLO ELECTR" in (field.description or "").upper()
            and field not in self._sealed_rows(catalogues)
            and _administration_reserved(field) is False
        ]

        assert named_without_delegation, "every sello row carries a delegation, so this control is vacuous"
        for field in named_without_delegation:
            assert _omissible_reason(field) is None, (
                f"@{field.offset}+{field.length} was excused on its NAME alone, which would let any row "
                f"mentioning a seal drop out of coverage"
            )

    def test_a_delegation_without_the_seal_name_does_not_excuse_a_row(self) -> None:
        """The other control: the delegation clause alone must not excuse a datum."""
        datum = RecordDesignField(
            sheet="Tipo 1",
            row=9,
            ordinal="9",
            offset=1,
            length=9,
            type_code="Alfanumérico",
            description="NIF DEL DECLARANTE",
            content="Se cumplimentará por los programas de la A.E.A.T. en presentaciones telemáticas.",
        )

        assert _omissible_reason(datum) is None


def test_auxiliary_header_declaration_covers_the_header_and_its_absence_still_refuses(
    registry_tree: tuple[tuple[ModeloDefinition, ...], RegistryCatalogues],
) -> None:
    """The DR23200 header is covered exactly when its declaration is present.

    Implication, both sides live: the declared prefix extent covers every
    required header position, and the same sheets without the declaration
    report the header as unemitted -- the message that was the authoring
    worklist for both Modelo 232 revisions. The declaration is derived from
    the sheet's own parser-owned header, never from a hand-authored constant.
    """
    modelos, catalogues = registry_tree
    modelo = next(candidate for candidate in modelos if candidate.id == "232")
    for revision_id, revision in modelo.revisions.items():
        layout = _fixed_width_layouts(revision)[0]
        sheets = _design_sheets(layout, catalogues)
        header_sheets = [sheet for sheet in sheets if sheet.auxiliary_envelope_header is not None]
        assert len(header_sheets) == 1, f"{revision_id}: expected exactly one auxiliary header sheet"
        header = header_sheets[0].auxiliary_envelope_header
        assert header is not None
        source_ref = next(source_ref for source_ref in layout.source_refs if source_ref.startswith("aeat-dr-232"))
        roles = tuple(
            role for role in FilingEnvelopePrefixRole if role is not FilingEnvelopePrefixRole.COMPOSED_OPENING_TAG
        )
        declaration = AuxiliaryEnvelopeHeaderDefinition(
            source_ref=source_ref,
            source_sha256=catalogues.sources[source_ref].sha256,
            record_identity=header.record_identity,
            prefix_fields=tuple(
                FilingEnvelopePrefixFieldDeclaration(role=role, length=item.field.length)
                for role, item in zip(roles, header.fields, strict=True)
            ),
            prefix_extent=header.emitted_extent,
            product_identity_requirement="aeat-product-software-identity-v1",
        )
        _required, missing, lines = _missing_report(sheets, layout.records, auxiliary_header=declaration)
        assert missing == 0, f"{revision_id}: declared header still leaves required positions: {lines}"
        _required, missing, lines = _missing_report(sheets, layout.records, auxiliary_header=None)
        header_lines = [line for line in lines if f"auxiliary envelope header {header.record_identity!r}" in line]
        assert len(header_lines) == 1, f"{revision_id}: expected one header refusal, got {lines}"
        assert missing > 0
