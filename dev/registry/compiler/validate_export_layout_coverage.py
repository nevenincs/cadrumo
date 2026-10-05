"""Registry-build gate: an authored fixed-width layout must cover its official design.

:func:`~._validate_export_exemption.validate_export_exemption_declarations`
refuses a revision that declares NO export layout. It cannot tell a complete
layout from a tenth of one, because it never reads the official record design:
it asks only whether the registry declared *something*. Modelo 714 is the worked
case -- five revisions each declaring 127 fields across 10 records against a
bundled AEAT design carrying 1,200+ positions across 12 records, two of which
(the ``714-00`` file envelope and ``714-Ingreso o Devolución``, which carries
forma de pago, IBAN and importe del ingreso) are not authored at all. It passed.
A filing generated from it would carry a blank NIF, a blank name, a blank IBAN
and a blank resumen block behind a perfectly valid digest.

This module closes that. For every revision declaring a fixed-width export
layout, it reads the official bundled design that layout itself cites and
refuses when a position the design requires has no authored slot.

What counts as required, and why it is read from the design
-----------------------------------------------------------

A fixed-width record is CONTIGUOUS: AEAT declares its whole byte extent and the
file carries every byte of it. So a position the layout does not declare is not
"optional", it is a datum the application can never write -- the slot emits fill
and the operator gets a structurally thin record behind a valid digest. The
default is therefore that every position is required, and omissibility must be
something the DESIGN says, never something a per-modelo allowlist asserts:

* a position AEAT marks ``OBLIGATORIO`` in its own obligatoriness column is
  required, and that marking overrides every omissibility signal below;
* a position AEAT reserves for itself ("Reservado para la Administración",
  "RESERVADO PARA LA A.E.A.T.") is omissible -- the filer must not write it;
* a position AEAT declares as fill ("BLANCOS", "Sin contenido", a blank
  constant) is omissible -- there is no datum there.

Where AEAT *desglosa* a printed field into sub-fields, the SUB-FIELDS are the
positions and the parent's span is not one; each sub-field is judged for
omissibility on its own. See :func:`_required_positions` for why requiring the
parent inverted the incentive on Modelo 576.

Everything else is required. Measured over the eighteen bundled designs backing
a fixed-width layout: 570 positions marked obligatorio, 266 administration-
reserved, 29 declared fill, 8,297 ordinary data positions.

What counts as written: bytes, carrying data
--------------------------------------------

Coverage is measured by BYTE EXTENT, not by ``(offset, length)`` identity. The
design's grouping of bytes into rows and the layout's grouping of the same bytes
into fields are independent, and both are legitimate; demanding they agree made
three design sheets literally unsatisfiable. And a ``filler`` never covers a
required position: it emits blanks, so counting it hid 185 positions the
operator's filing leaves empty -- including modelos the gate reported COMPLETE.
:func:`_covers` carries the evidence for both halves.

Joining an authored record to its design sheet
----------------------------------------------

The registry declares no link between an authored ``ExportRecordDefinition`` and
the design sheet it renders, and the two vocabularies do not correspond: Modelo
714 writes ``record_type = "714-01"`` against a sheet named
``714-01 Patrimonio``, Modelo 390 writes ``page_01`` against ``Pág. 1``, Modelo
145 writes ``communication`` against ``PDF record design``, and Modelo 720's
records carry no discriminating name at all. **Matching those by name would be
inventing a mapping**, and a wrong mapping produces confident refusals against
positions the layout does write.

So the join is made on CONTENT, which is where a fixed-width record's identity
actually lives: AEAT declares each record's discriminating constants ("Constante
``<T``", "Constante ``714``", "Constante ``01000``") at exact offsets, and the
authored record declares the same bytes as ``literal`` fields. A record joins a
sheet when their declared constants agree at shared coordinates and contradict
at none, and the sheet takes the record whose agreement count is a unique
maximum.

**Where a multi-record join cannot be established the check does not guess or
pass.** It reports the layout-wide byte count as a lower bound and separately
refuses the unresolved record identity. Reserved-byte checks use only a joined
record or a source-matched envelope prefix; fields from another page cannot be
blamed on the unjoined sheet. A one-record layout can still use its sole record
for byte coverage without choosing between competing records.

A partial read never produces a pass
------------------------------------

:func:`~._record_design.extract_record_design` returns what it could read
alongside what it could not, and
:meth:`~.record_design_schema.RecordDesignExtraction.accept_partial` tolerates
the difference. The off-load-path coverage inventory in
``record_design_coverage`` deliberately takes that tolerance, and its own
docstring records why: tightening it would make Modelo 232's legitimately
skipped ``TABLAS`` lookup tab refuse the whole modelo.

**This gate does not share that tolerance and does not need to.** It calls
:meth:`~.record_design_schema.RecordDesignExtraction.require_complete` and
converts the refusal into its own diagnostic, because a design whose record body
was skipped understates the modelo and would hand back an inflated coverage
figure that nothing downstream could tell from a real one -- the exact false
green this gate exists to remove. A non-record tab must be explicitly classified
by the parser's source policy before a fixed-width layout can pass this gate.

An unreachable design binary is likewise a refusal, not a skip. The corpus
binaries live in the mandatory ``cadrumo_data`` companion namespace, so
"unreadable" is a broken installation rather than a supported configuration, and
reporting completeness over a file nobody read is the one outcome this module
must never produce.

See Also:
    :func:`~._validate_export_exemption.validate_export_exemption_declarations`
        The sibling that refuses a revision declaring no layout at all.
    :func:`~._record_design.extract_record_design`
        The official-design reader, and the completeness contract it returns.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    AuxiliaryEnvelopeHeaderDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    FilingEnvelopeDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from dev.registry.compiler.record_design_schema import (
    AUXILIARY_ENVELOPE_HEADER_LENGTHS,
    RecordDesignField,
    RecordDesignSheet,
    RecordDesignVariableEnvelope,
    validate_auxiliary_envelope_header_contents,
)
from dev.registry.pipeline.variable_envelope import AUXILIARY_TO_PREFIX_ROLE

from . import export_layout_record_join as record_join
from . import export_layout_required_positions as required_positions

#: How many missing positions one sheet enumerates before the message says how
#: many more there are. The bundled design is the exhaustive worklist; this
#: message is the entry point into it, and a refusal listing a thousand
#: coordinates is one nobody reads.
_ENUMERATED_PER_RECORD: Final = 8


@dataclass(frozen=True, slots=True)
class _CoverageInputs:
    """The fields, bytes, and diagnostic scope for one design sheet."""

    consulted: tuple[ExportFieldDefinition, ...]
    written: set[int]
    emitted: set[int]
    scope: str
    unresolved_record: bool = False


def _layout_write_sets(
    records: Sequence[ExportRecordDefinition],
    envelope: FilingEnvelopeDefinition | None,
) -> tuple[set[int], set[int]]:
    """Collect layout-wide data and emitted byte extents for fallback coverage."""
    written: set[int] = set()
    emitted: set[int] = set()
    for record in records:
        written |= record_join._written_bytes(record.fields, data_only=True)
        emitted |= record_join._written_bytes(record.fields, data_only=False)
    if envelope is not None:
        envelope_bytes = record_join._envelope_written_bytes(envelope)
        written |= envelope_bytes
        emitted |= envelope_bytes
    return written, emitted


def _uncounted_required_positions(
    sheet: RecordDesignSheet,
    counted: set[tuple[str, int, int]],
) -> tuple[required_positions._RequiredPosition, ...]:
    """Return this sheet's required positions not counted by another edition."""
    return tuple(
        position
        for position in required_positions._required_positions(sheet)
        if (sheet.name, position.offset, position.length) not in counted
    )


def _sheet_coverage_inputs(
    sheet: RecordDesignSheet,
    records: Sequence[ExportRecordDefinition],
    *,
    source: SourceReference,
    envelope: FilingEnvelopeDefinition | None,
    auxiliary_header: AuxiliaryEnvelopeHeaderDefinition | None,
    layout_written: set[int],
    layout_emitted: set[int],
    constants_by_binding: Mapping[str, str] | None,
) -> _CoverageInputs:
    """Resolve the authoritative byte source and scope for one design sheet."""
    is_envelope_sheet = envelope is not None and sheet.name == envelope.record_identity
    if is_envelope_sheet:
        written = record_join._envelope_written_bytes(envelope)
        return _CoverageInputs((), written, written, f"filing envelope {sheet.name!r}")

    if sheet.auxiliary_envelope_header is not None or sheet.variable_envelope is not None:
        joined_header = record_join._join_record(sheet, records, constants_by_binding, source=source)
        if joined_header is not None:
            return _joined_variable_header_coverage_inputs(sheet, joined_header)
        return _auxiliary_header_coverage_inputs(sheet, source, auxiliary_header)

    joined = record_join._join_record(sheet, records, constants_by_binding, source=source)
    if joined is not None:
        consulted = tuple(joined.fields)
        return _CoverageInputs(
            consulted,
            record_join._written_bytes(consulted, data_only=True),
            record_join._written_bytes(consulted, data_only=False),
            f"authored record {joined.id!r} (record_type {joined.record_type!r})",
        )

    if len(records) == 1:
        consulted = tuple(records[0].fields)
        return _CoverageInputs(
            consulted,
            record_join._written_bytes(consulted, data_only=True),
            record_join._written_bytes(consulted, data_only=False),
            f"sole authored record {records[0].id!r} (source identity unjoined)",
        )

    return _CoverageInputs(
        (),
        layout_written,
        layout_emitted,
        "NO authored record could be identified for this design record, so the check fell "
        "back to asking whether any record of the layout writes the coordinate -- a weaker "
        "question, so this count is a floor, not the whole gap",
        unresolved_record=len(records) > 1,
    )


def _joined_variable_header_coverage_inputs(
    sheet: RecordDesignSheet,
    record: ExportRecordDefinition,
) -> _CoverageInputs:
    """Verify a uniquely joined fixed record emits the source's exact prefix.

    Historical manual layouts model the variable opening as a real fixed
    record, whereas generated layouts carry an auxiliary declaration. Neither
    representation proves the variable body or relative closer here.
    """
    source_fields, source_extent = _variable_header_source_shape(sheet)
    fields = tuple(record.fields)
    ordered_fields = tuple(sorted(fields, key=lambda field: field.offset if field.offset is not None else -1))
    shape_matches = _variable_header_geometry_matches(sheet, source_fields, source_extent, ordered_fields)
    if shape_matches:
        shape_matches = _variable_header_values_match(ordered_fields, source_fields)
    if not shape_matches:
        raise RegistryValidationError(
            f"design record {sheet.name!r} uniquely joins authored header {record.id!r}, "
            "but its prefix roles, constants, fillers or byte geometry contradict the source"
        )
    return _CoverageInputs(
        fields,
        record_join._written_bytes(fields, data_only=True),
        record_join._written_bytes(fields, data_only=False),
        f"source-joined fixed header prefix {record.id!r}",
    )


def _variable_header_source_shape(
    sheet: RecordDesignSheet,
) -> tuple[tuple[RecordDesignField, ...], int]:
    source_fields = (
        sheet.variable_envelope.prefix_fields
        if sheet.variable_envelope is not None
        else sheet.auxiliary_envelope_header.source_fields
        if sheet.auxiliary_envelope_header is not None
        else ()
    )
    source_extent = (
        sheet.variable_envelope.prefix_extent
        if sheet.variable_envelope is not None
        else sheet.auxiliary_envelope_header.emitted_extent
        if sheet.auxiliary_envelope_header is not None
        else 0
    )
    return source_fields, source_extent


def _variable_header_geometry_matches(
    sheet: RecordDesignSheet,
    source_fields: tuple[RecordDesignField, ...],
    source_extent: int,
    fields: tuple[ExportFieldDefinition, ...],
) -> bool:
    return (
        _source_header_matches_sheet(sheet, source_fields, source_extent)
        and _source_header_is_contiguous(source_fields)
        and _authored_header_matches_source(fields, source_fields)
    )


def _source_header_matches_sheet(
    sheet: RecordDesignSheet,
    source_fields: tuple[RecordDesignField, ...],
    source_extent: int,
) -> bool:
    return (
        source_fields == sheet.fields
        and bool(source_fields)
        and source_extent == sum(field.length for field in source_fields)
        and source_fields[0].offset == 1
    )


def _source_header_is_contiguous(source_fields: tuple[RecordDesignField, ...]) -> bool:
    return all(left.offset + left.length == right.offset for left, right in pairwise(source_fields))


def _authored_header_matches_source(
    fields: tuple[ExportFieldDefinition, ...],
    source_fields: tuple[RecordDesignField, ...],
) -> bool:
    return len(fields) == len(source_fields) and all(
        field.offset == source_field.offset and field.length == source_field.length
        for field, source_field in zip(fields, source_fields, strict=True)
    )


def _variable_header_values_match(
    fields: tuple[ExportFieldDefinition, ...],
    source_fields: tuple[RecordDesignField, ...],
) -> bool:
    for field, source_field in zip(fields, source_fields, strict=True):
        constant = record_join._field_constant(source_field)
        if constant is not None and (field.kind is not CasillaFieldKind.LITERAL or field.literal != constant):
            return False
        if record_join._field_is_filler(source_field) and field.kind is not CasillaFieldKind.FILLER:
            return False
    return True


def _auxiliary_header_coverage_inputs(
    sheet: RecordDesignSheet,
    source: SourceReference,
    auxiliary_header: AuxiliaryEnvelopeHeaderDefinition | None,
) -> _CoverageInputs:
    """Attribute only source-matched prefix bytes to the auxiliary-header declaration.

    A variable source also declares a body and relative closer. This static
    auxiliary header covers neither; its 328-byte proof is prefix-only.
    """
    if sheet.auxiliary_envelope_header is None and sheet.variable_envelope is None:
        raise RegistryValidationError(f"design record {sheet.name!r} has no envelope prefix to cover")
    if auxiliary_header is None:
        return _unemitted_auxiliary_header_coverage(sheet)

    source_extent, source_lengths, source_roles = _source_prefix_shape(sheet)
    if not _auxiliary_header_matches_source(
        sheet,
        source,
        auxiliary_header,
        source_extent,
        source_lengths,
        source_roles,
    ):
        written: set[int] = set()
        scope = f"auxiliary envelope header {sheet.name!r} with mismatched source, identity, roles or extent"
    else:
        written = set(range(1, auxiliary_header.prefix_extent + 1))
        scope = f"source-matched auxiliary envelope header prefix {sheet.name!r}"
    return _CoverageInputs((), written, written, scope)


def _unemitted_auxiliary_header_coverage(sheet: RecordDesignSheet) -> _CoverageInputs:
    written: set[int] = set()
    scope = (
        f"auxiliary envelope header {sheet.name!r}, which this layout does not emit: the "
        "source-proved prefix needs its own emission contract rather than an authored fixed record"
    )
    return _CoverageInputs((), written, written, scope)


def _source_prefix_shape(
    sheet: RecordDesignSheet,
) -> tuple[int, tuple[int, ...], tuple[object, ...]]:
    source_header = sheet.auxiliary_envelope_header
    if source_header is not None:
        source_lengths = tuple(field.field.length for field in source_header.fields)
        source_roles = tuple(AUXILIARY_TO_PREFIX_ROLE[field.role] for field in source_header.fields)
        return source_header.emitted_extent, source_lengths, source_roles

    variable_envelope = sheet.variable_envelope
    if variable_envelope is None:
        raise RegistryValidationError(f"design record {sheet.name!r} has no envelope prefix")
    source_lengths, source_roles = _variable_prefix_dimensions(sheet, variable_envelope)
    return variable_envelope.prefix_extent, source_lengths, source_roles


def _variable_prefix_dimensions(
    sheet: RecordDesignSheet,
    variable_envelope: RecordDesignVariableEnvelope,
) -> tuple[tuple[int, ...], tuple[object, ...]]:
    source_fields = variable_envelope.prefix_fields
    try:
        validate_auxiliary_envelope_header_contents(tuple(field.content for field in source_fields))
    except ValueError:
        return (), ()
    if not _variable_prefix_matches_sheet(sheet, variable_envelope, source_fields):
        return (), ()
    return (
        tuple(field.length for field in source_fields),
        tuple(AUXILIARY_TO_PREFIX_ROLE.values()),
    )


def _variable_prefix_matches_sheet(
    sheet: RecordDesignSheet,
    variable_envelope: RecordDesignVariableEnvelope,
    source_fields: Sequence[RecordDesignField],
) -> bool:
    return (
        source_fields == sheet.fields
        and tuple(field.length for field in source_fields) == AUXILIARY_ENVELOPE_HEADER_LENGTHS
        and variable_envelope.name == sheet.name
    )


def _auxiliary_header_matches_source(
    sheet: RecordDesignSheet,
    source: SourceReference,
    auxiliary_header: AuxiliaryEnvelopeHeaderDefinition,
    source_extent: int,
    source_lengths: tuple[int, ...],
    source_roles: tuple[object, ...],
) -> bool:
    declared_lengths = tuple(field.length for field in auxiliary_header.prefix_fields)
    declared_roles = tuple(field.role for field in auxiliary_header.prefix_fields)
    return (
        auxiliary_header.record_identity == sheet.name
        and str(auxiliary_header.source_ref) == str(source.id)
        and str(auxiliary_header.source_sha256) == source.sha256
        and auxiliary_header.prefix_extent == source_extent
        and declared_lengths == source_lengths
        and declared_roles == source_roles
    )


def _sheet_missing_positions(
    required: Sequence[required_positions._RequiredPosition],
    coverage: _CoverageInputs,
) -> tuple[required_positions._RequiredPosition, ...]:
    """Find required positions whose bytes are not emitted by the resolved source."""
    return tuple(
        position for position in required if not record_join._covers(position, coverage.written, coverage.emitted)
    )


def _missing_positions_line(
    sheet: RecordDesignSheet,
    required: Sequence[required_positions._RequiredPosition],
    missing: Sequence[required_positions._RequiredPosition],
    scope: str,
) -> str:
    """Render the bounded diagnostic worklist for one sheet's missing positions."""
    shown = ", ".join(
        f"@{position.offset}+{position.length} "
        f"{'[OBLIGATORIO] ' if position.obligatorio else ''}{position.description!r}"
        for position in missing[:_ENUMERATED_PER_RECORD]
    )
    remainder = f" and {len(missing) - _ENUMERATED_PER_RECORD} more" if len(missing) > _ENUMERATED_PER_RECORD else ""
    return (
        f"design record {sheet.name!r}: {len(missing)} of {len(required)} required positions "
        f"unwritten by {scope}; {shown}{remainder}"
    )


def _sheet_coverage_result(
    sheet: RecordDesignSheet,
    required: Sequence[required_positions._RequiredPosition],
    coverage: _CoverageInputs,
    *,
    source: SourceReference,
) -> tuple[int, int, list[str]]:
    """Return missing positions, unresolved joins and diagnostics for one sheet."""
    missing = _sheet_missing_positions(required, coverage)
    intrusions = record_join._reserved_write_failures(sheet, coverage.consulted, source=source)
    lines: list[str] = [f"design record {sheet.name!r}: {'; '.join(intrusions)}"] if intrusions else []
    if missing:
        lines.append(_missing_positions_line(sheet, required, missing, coverage.scope))
    unresolved = int(coverage.unresolved_record)
    if unresolved:
        lines.append(
            f"design record {sheet.name!r}: no unique authored record joins its source constants; "
            "layout-wide byte coverage cannot verify this record"
        )
    return len(missing) + len(intrusions), unresolved, lines


def _missing_report(
    sheets: Sequence[tuple[RecordDesignSheet, SourceReference]],
    records: Sequence[ExportRecordDefinition],
    *,
    envelope: FilingEnvelopeDefinition | None = None,
    auxiliary_header: AuxiliaryEnvelopeHeaderDefinition | None = None,
    constants_by_binding: Mapping[str, str] | None = None,
) -> tuple[int, int, int, list[str]]:
    """Return required, missing, unresolved joins and diagnostics for a layout."""
    layout_written, layout_emitted = _layout_write_sets(records, envelope)
    required_total = 0
    missing_total = 0
    unresolved_total = 0
    lines: list[str] = []
    #: Positions already counted, keyed by (design record, coordinate). A layout
    #: may cite SEVERAL editions of one modelo's design -- Modelo 190 cites its
    #: 2024 and 2025 Diseños de Registro together -- and the editions repeat the
    #: sheets they share. Counting them once per citation double-counts every
    #: shared position in BOTH numerator and denominator: Modelo 190 reported
    #: 102/106 where the union of its editions declares 100/104. The layout has
    #: to satisfy each position ONCE, however many editions declare it, so the
    #: later edition contributes only what it adds -- which is exactly the
    #: (389, 1) and (390, 5) rows 2025 introduces.
    counted: set[tuple[str, int, int]] = set()
    for sheet, source in sheets:
        if not record_join._belongs_to_layout(sheet, records, constants_by_binding, source=source):
            continue
        required = _uncounted_required_positions(sheet, counted)
        counted.update((sheet.name, position.offset, position.length) for position in required)
        required_total += len(required)
        coverage = _sheet_coverage_inputs(
            sheet,
            records,
            source=source,
            envelope=envelope,
            auxiliary_header=auxiliary_header,
            layout_written=layout_written,
            layout_emitted=layout_emitted,
            constants_by_binding=constants_by_binding,
        )
        sheet_missing, unresolved, sheet_lines = _sheet_coverage_result(sheet, required, coverage, source=source)
        missing_total += sheet_missing
        unresolved_total += unresolved
        lines.extend(sheet_lines)
    return required_total, missing_total, unresolved_total, lines


def _layout_failure(
    *,
    prefix: str,
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
    constants_by_binding: Mapping[str, str] | None = None,
) -> str | None:
    design_sources = record_join._design_sources(layout, source_refs)
    if not design_sources:
        return _missing_design_source_failure(prefix, layout)
    sheets = _read_layout_design_sheets(prefix, layout, design_sources)
    if isinstance(sheets, str):
        return sheets
    report = _layout_coverage_report(prefix, layout, sheets, constants_by_binding)
    if isinstance(report, str):
        return report
    required, missing, unresolved, details = report
    return _layout_coverage_failure_message(prefix, layout, design_sources, required, missing, unresolved, details)


def _missing_design_source_failure(prefix: str, layout: ExportLayoutDefinition) -> str:
    return (
        f"{prefix}: fixed-width export layout {layout.id!r} cites no official record-design "
        f"source, so nothing states what a complete layout for it would contain and its "
        f"completeness cannot be verified. Cite the modelo's bundled Diseño de Registros in the "
        f"layout's source_refs"
    )


def _read_layout_design_sheets(
    prefix: str,
    layout: ExportLayoutDefinition,
    design_sources: Sequence[SourceReference],
) -> tuple[tuple[RecordDesignSheet, SourceReference], ...] | str:
    sheets: list[tuple[RecordDesignSheet, SourceReference]] = []
    for source in design_sources:
        read = record_join._read_design_sheets(source)
        if isinstance(read, str):
            return f"{prefix}: fixed-width export layout {layout.id!r} cannot be checked because {read}"
        try:
            record_join._require_adjudicated_source_sheets(source, read)
        except RegistryValidationError as exc:
            return f"{prefix}: fixed-width export layout {layout.id!r} cannot verify source-pinned coverage: {exc}"
        sheets.extend((sheet, source) for sheet in read)
    return tuple(sheets)


def _layout_coverage_report(
    prefix: str,
    layout: ExportLayoutDefinition,
    sheets: Sequence[tuple[RecordDesignSheet, SourceReference]],
    constants_by_binding: Mapping[str, str] | None,
) -> tuple[int, int, int, list[str]] | str:
    try:
        return _missing_report(
            sheets,
            layout.records,
            envelope=layout.filing_envelope,
            auxiliary_header=layout.auxiliary_envelope_header,
            constants_by_binding=constants_by_binding,
        )
    except RegistryValidationError as exc:
        return f"{prefix}: fixed-width export layout {layout.id!r} cannot verify source-pinned coverage: {exc}"


def _layout_coverage_failure_message(
    prefix: str,
    layout: ExportLayoutDefinition,
    design_sources: Sequence[SourceReference],
    required: int,
    missing: int,
    unresolved: int,
    details: Sequence[str],
) -> str | None:
    if not missing and not unresolved:
        return None
    if not missing:
        return (
            f"{prefix}: fixed-width export layout {layout.id!r} has {unresolved} design record(s) "
            "without a unique source-to-record join, so per-record coverage is unverified. " + " | ".join(details)
        )
    coverage = 100.0 * (required - missing) / required if required else 0.0
    return (
        f"{prefix}: fixed-width export layout {layout.id!r} writes only {required - missing} of the "
        f"{required} positions its official record design requires ({coverage:.1f}% coverage), so a "
        f"filing generated from it would carry fill where AEAT expects data -- behind a digest that "
        f"is valid, because a digest locks bytes and asserts nothing about completeness. Required "
        f"means every position of the official design except the ones the design ITSELF declares "
        f"omissible (reserved for the Administración, or declared fill); a position AEAT marks "
        f"OBLIGATORIO is required regardless. There is no percentage floor and no exemption: author "
        f"the missing positions from the design at "
        f"{', '.join(repr(source.corpus_path) for source in design_sources)}. " + " | ".join(details)
    )


def validate_export_layout_record_coverage(
    *,
    prefix: str,
    revision: ModeloRevision,
    source_refs: Mapping[str, SourceReference],
) -> list[str]:
    """Refuse every fixed-width layout that cannot write its official design.

    Resolves the revision's layouts the way snapshot build does -- through
    :func:`derive_export_layouts_from_bindings`, so binding-derived record fields
    count as written -- and checks each fixed-width one against the bundled AEAT
    record design it cites.

    A revision declaring no fixed-width layout yields nothing here. Modelo 100
    and Modelo 390's XML-dictionary siblings file through a dictionary and have
    no positional design to be measured against, and Modelo 720 assembles its
    records from ``binding_record`` selectors that
    :func:`derive_export_layouts_from_bindings` materialises before this runs.
    The revision that declares NO layout at all is the sibling gate's subject,
    not this one's: reporting it here too would put a second count into
    circulation for one defect.

    Failures accumulate rather than raising, so one load reports every
    incomplete layout instead of the first, and one failure covers one layout so
    the enumeration stays a worklist rather than a wall.

    Args:
        prefix: Caller-supplied ``modelo N revision R`` diagnostic prefix.
        revision: The :class:`ModeloRevision` under validation.
        source_refs: The registry source catalogue, keyed by source ID, used to
            resolve each layout's cited record-design binary.

    Returns:
        Accumulated diagnostics; empty when every fixed-width layout writes
        every position its official design requires.
    """
    failures: list[str] = []
    constants_by_binding = record_join._design_constant_values(revision)
    for layout in derive_export_layouts_from_bindings(revision):
        if layout.format is not ExportLayoutFormat.FIXED_WIDTH:
            continue
        failure = _layout_failure(
            prefix=prefix,
            layout=layout,
            source_refs=source_refs,
            constants_by_binding=constants_by_binding,
        )
        if failure is not None:
            failures.append(failure)
    return failures


__all__ = ["validate_export_layout_record_coverage"]
