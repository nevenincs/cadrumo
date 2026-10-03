"""Resolve authored export records against source-design constants and byte extents."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Final

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.resources.bundled_data import resolve_corpus_binary
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    FilingEnvelopeDefinition,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from dev.registry.compiler.record_design_schema import RecordDesignField, RecordDesignSheet
from dev.registry.pipeline.source_defects import (
    SourceDefectDeclaration,
    adjudicated_literal_for,
    source_defects_for,
)

from . import export_layout_required_positions as requirements
from .record_design import extract_record_design

#: AEAT's own filler words for a byte run, matched at the start of a field's
#: naturaleza or description. Anchored and word-bounded so 'RECTIFICACIONES'
#: is never mistaken for a filler run.
_FILLER_RUN_RE = re.compile(r"(?i)^(?:blancos?|ceros?)\b")

#: AEAT's declaration that a position holds a fixed value rather than a datum.
#: Read from any cell of the row, because AEAT splits the declaration across
#: cells as often as it keeps it in one: Modelo 714's ``714-02`` writes
#: ``Constante "<T"`` in a single ``Contenido`` cell, while Modelo 111 and
#: Modelo 714's own ``714-00`` envelope put ``Constante.`` in ``Descripción``
#: and ``"<T"`` in ``Contenido``. Modelo 360's design declares its identifier
#: constants without the word at all ("Inicio del identificador de modelo y
#: página obligatorio <T360010>"), so the identifier-block vocabulary is
#: accepted alongside -- those phrases name the fixed record-delimiter cells
#: and nothing else in any bundled design.
_CONSTANT_DECLARATION: Final = re.compile(
    r"[Cc]onstante|identificador de modelo y página|fin de registro",
)

#: The quoted value itself (``"714"``, ``'1'``, ``«720»``). ONLY the quoted
#: spelling is read: an unquoted "Constante 2021" or "Constante. Blanco" does
#: not delimit its own value, and guessing where the value ends would put a
#: wrong anchor into the join.
_QUOTED_VALUE: Final = re.compile(
    "[\"'«“‘]([^\"'»«”’‘“]{1,40})[\"'»”’]",
)

#: The identifier-block constant, read for cells whose row carries the
#: identifier vocabulary (``<T360010>``, ``</T360020>``): the angle-bracket
#: spelling AEAT prints without the word "Constante". Bounded to the ``<T``
#: marker so a stray quoted word in the same cell's nota text cannot become
#: a wrong anchor.
_IDENTIFIER_VALUE: Final = re.compile(r"</?T\d{1,10}>")

#: The identifier-block row vocabulary: the phrases AEAT uses for the fixed
#: record-delimiter cells, which is where ``<T`` identifiers appear.
_IDENTIFIER_VOCABULARY: Final = re.compile(r"identificador de modelo y página|fin de registro")


def _sheet_constants(sheet: RecordDesignSheet, *, source: SourceReference | None = None) -> dict[tuple[int, int], str]:
    """Return the discriminating constants AEAT declares, by exact coordinate.

    The declaration and its value are read across the ROW, not within one cell.
    AEAT writes them together as often as it splits them -- ``Constante "<T"``
    in one ``Contenido`` cell, versus ``Constante.`` in ``Descripción`` beside
    ``"<T"`` in ``Contenido`` -- and requiring them adjacent silently emptied
    the constant set for whole modelos. A sheet with no constants cannot be
    joined to its authored record at all, so the check quietly degraded to the
    weaker layout-wide question for Modelo 111, 115, 117, 123, 126, 128, 130,
    202, 220, 222, 303, 308, 309, 322, 341, 353 and Modelo 714's own envelope.
    Nothing announced the downgrade, which is what made it durable.

    Both halves stay required. The word alone anchors nothing, and an unquoted
    value does not delimit itself; demanding a quoted value in a row AEAT marks
    ``Constante`` is what keeps an ENUMERATION ("01" ... "12" o "1T") -- which
    would produce a WRONG join rather than a missing one -- out of the set.
    """
    corrections = {} if source is None else _adjudicated_source_constants(sheet, source)
    return {
        (field.offset, field.length): corrections.get((field.offset, field.length), value)
        for field in sheet.fields
        if (value := _field_constant(field)) is not None
    }


def _adjudicated_source_constants(sheet: RecordDesignSheet, source: SourceReference) -> dict[tuple[int, int], str]:
    """Apply only declarations pinned to this source, cell, content and slot width."""
    corrections: dict[tuple[int, int], str] = {}
    seen_cells: set[str] = set()
    declarations = source_defects_for(str(source.id))
    for declaration in declarations:
        _require_source_defect_pin(source, declaration)
        if declaration.sheet != sheet.name:
            continue
        if declaration.source_cell in seen_cells:
            raise RegistryValidationError(
                f"duplicate source-defect declaration for {source.id!r} sheet {sheet.name!r} "
                f"cell {declaration.source_cell!r}"
            )
        seen_cells.add(declaration.source_cell)
        field, value = _resolve_adjudicated_constant(sheet, source, declarations, declaration)
        corrections[(field.offset, field.length)] = value
    return corrections


def _require_source_defect_pin(source: SourceReference, declaration: SourceDefectDeclaration) -> None:
    if declaration.source_ref != str(source.id) or declaration.source_sha256 != source.sha256:
        raise RegistryValidationError(
            f"source-defect declaration for {source.id!r} is not pinned to the selected official design"
        )


def _resolve_adjudicated_constant(
    sheet: RecordDesignSheet,
    source: SourceReference,
    declarations: tuple[SourceDefectDeclaration, ...],
    declaration: SourceDefectDeclaration,
) -> tuple[RecordDesignField, str]:
    match = re.fullmatch(r"A([1-9][0-9]*)", declaration.source_cell)
    if match is None:
        raise RegistryValidationError(
            f"source-defect declaration cell {declaration.source_cell!r} has no supported field-row coordinate"
        )
    fields = tuple(field for field in sheet.fields if field.row == int(match.group(1)))
    if len(fields) != 1 or fields[0].content != declaration.published_content:
        raise RegistryValidationError(
            f"source-defect declaration for {source.id!r} sheet {sheet.name!r} "
            f"cell {declaration.source_cell!r} no longer matches the official content"
        )
    field = fields[0]
    value = adjudicated_literal_for(
        declarations,
        sheet=sheet.name,
        source_cell=declaration.source_cell,
        published_content=declaration.published_content,
    )
    if value is None or len(value.encode("iso-8859-1")) != field.length or _field_constant(field) is None:
        raise RegistryValidationError(
            f"source-defect declaration for {source.id!r} sheet {sheet.name!r} "
            f"cell {declaration.source_cell!r} no longer matches its constant geometry"
        )
    return field, value


def _require_adjudicated_source_sheets(source: SourceReference, sheets: Sequence[RecordDesignSheet]) -> None:
    """A parser revision must not silently drop a sheet carrying a pinned correction."""
    names = {sheet.name for sheet in sheets}
    for declaration in source_defects_for(str(source.id)):
        if declaration.sheet not in names:
            raise RegistryValidationError(
                f"source-defect declaration for {source.id!r} names missing sheet {declaration.sheet!r}"
            )


def _identity_constants(
    sheet: RecordDesignSheet, *, source: SourceReference | None = None
) -> dict[tuple[int, int], str]:
    """Return the sheet constants that identify WHICH record it describes.

    A constant on a row AEAT reserves for itself prescribes a value but names no
    record: Modelo 360's ``@1897+5`` "Reservado AEAT." / "constante '00000'"
    is the same on any record that carries it. Letting it vote in the join or
    the scope test would turn one mistyped reserved literal into a contradiction
    that drops the whole sheet out of scope -- a silent pass over every position
    it declares. Its value is still enforced, by :func:`_reserved_write_failures`.
    """
    reserved = _administration_reserved_bytes(sheet)
    return {
        coordinate: value
        for coordinate, value in _sheet_constants(sheet, source=source).items()
        if coordinate[0] not in reserved
    }


def _field_constant(field: RecordDesignField) -> str | None:
    """Return one field's constant, keeping identifier rows on their own grammar."""
    cells = (field.content, field.description)
    if any(text and _IDENTIFIER_VOCABULARY.search(text) for text in cells):
        return _identifier_constant(cells)
    if not any(text and _CONSTANT_DECLARATION.search(text) for text in cells):
        return None
    return _quoted_constant(cells)


def _identifier_constant(cells: tuple[str | None, str | None]) -> str | None:
    """Read the angle-bracket identifier from an identifier-block row."""
    for text in cells:
        if not text:
            continue
        identifier = _IDENTIFIER_VALUE.search(text)
        if identifier is not None:
            return identifier.group(0).strip()
    return None


def _quoted_constant(cells: tuple[str | None, str | None]) -> str | None:
    """Read a quoted constant declared in either design cell."""
    for text in cells:
        if not text:
            continue
        matched = _QUOTED_VALUE.search(text)
        if matched is not None:
            return str(matched.group(1)).strip()
    return None


def _design_constant_values(revision: ModeloRevision) -> Mapping[str, str]:
    """Return each ``design_constant`` binding's declared value, keyed by binding id.

    A design constant is a DECLARED constant that simply does not live on an
    inline literal field. Modelo 720 states its record-type marker and modelo
    number as constants in the diseño, but that layout represents every casilla
    through a binding and forbids inline literals, so the value rides on the
    binding selector instead.

    Reading it here is not a widening of what counts as a constant: the
    declaration already exists and is validated at registry build. Without this
    the join sees a record with no constants at all and cannot tell two
    otherwise-identical records apart, which is how a fully-declared layout ends
    up on the weaker any-record fallback.
    """
    values: dict[str, str] = {}
    for binding in revision.bindings:
        if binding.source is not BindingSourceKind.DESIGN_CONSTANT:
            continue
        selector = selector_as_dict(binding)
        value = selector.get("value")
        if isinstance(value, str):
            values[str(binding.id)] = value
    return values


def _record_literals(
    record: ExportRecordDefinition,
    constants_by_binding: Mapping[str, str] | None = None,
) -> dict[tuple[int, int], str]:
    """Return every constant this record declares, from either declared channel.

    An inline ``LITERAL`` field is one channel; a field bound to a
    ``design_constant`` binding is the other. Both are declarations validated at
    registry build, and a record that uses the second is no less identified than
    one that uses the first.
    """
    literals = _inline_record_literals(record)
    if not constants_by_binding:
        return literals
    for coordinate, value in _bound_record_literals(record, constants_by_binding).items():
        literals.setdefault(coordinate, value)
    return literals


def _inline_record_literals(record: ExportRecordDefinition) -> dict[tuple[int, int], str]:
    """Return literal fields that identify an authored record directly."""
    return {
        (field.offset, field.length): field.literal
        for field in record.fields
        if field.kind is CasillaFieldKind.LITERAL
        and field.literal is not None
        and field.offset is not None
        and field.length is not None
    }


def _bound_record_literals(
    record: ExportRecordDefinition,
    constants_by_binding: Mapping[str, str],
) -> dict[tuple[int, int], str]:
    """Return design-constant fields that identify an authored record."""
    literals: dict[tuple[int, int], str] = {}
    for field in record.fields:
        if field.offset is None or field.length is None or field.binding is None:
            continue
        value = constants_by_binding.get(str(field.binding))
        if value is not None:
            literals.setdefault((field.offset, field.length), value)
    return literals


def _written_bytes(fields: Iterable[ExportFieldDefinition], *, data_only: bool) -> set[int]:
    """Return every byte ``fields`` writes, optionally counting only real data.

    ``data_only`` drops :attr:`~.CasillaFieldKind.FILLER` slots. A filler emits
    blanks, so a required position it "covers" is a position the operator's
    filing leaves empty -- see :func:`_covers` for why that must not count.
    """
    written: set[int] = set()
    for field in fields:
        if field.offset is None or field.length is None:
            continue
        if data_only and field.kind is CasillaFieldKind.FILLER:
            continue
        written.update(range(field.offset, field.offset + field.length))
    return written


def _administration_reserved_bytes(sheet: RecordDesignSheet) -> dict[int, str]:
    """Return every byte AEAT reserves for itself, mapped to the row that says so.

    Walks sub-fields as well as top-level rows, because AEAT reserves inside a
    desglose too: Modelo 576's ``19.3 @520+8 RESERVADO para AEAT`` sits between
    seven real data sub-fields of one printed row.
    """
    reserved: dict[int, str] = {}
    for field in sheet.fields:
        for candidate in (field, *field.components):
            if requirements._OBLIGATORIO.search(candidate.validation or ""):
                continue
            if not requirements._administration_reserved(candidate):
                continue
            for byte in range(candidate.offset, candidate.offset + candidate.length):
                reserved[byte] = candidate.description
    return reserved


def _reserved_write_failures(
    sheet: RecordDesignSheet,
    fields: Iterable[ExportFieldDefinition],
    *,
    source: SourceReference | None = None,
) -> list[str]:
    """Return every authored field that writes taxpayer data into reserved bytes.

    Byte-extent coverage asks whether a required position's bytes are written,
    which is the right question and an incomplete one: one wide field satisfies
    every position it spans, INCLUDING the administración's own bytes in
    between. Modelo 576 is the worked case -- a single 40-byte field over row
    19 covers all seven of its real sub-fields and writes straight across
    ``19.3``, the eight bytes AEAT reserves. Under coverage alone that reads as
    complete, which is the same incentive inversion, one layer down, that
    requiring the parent span produced in the first place.

    A ``filler`` there is CORRECT and is not reported: the record is contiguous,
    so those bytes must still be emitted, as blanks. The rule is that a field
    carrying a value may not claim bytes the design says belong to AEAT -- never
    that fillers are suspect.

    The one value a field may write there is the one AEAT itself prescribes: a
    ``literal`` whose coordinates and value are exactly a constant the same
    sheet declares. Modelo 360's ``@1897+5`` is "Reservado AEAT." with contenido
    "constante '00000'"; a filler would emit blanks where the design states
    zeros. Any other value, or the right value at shifted coordinates, is still
    refused.
    """
    reserved = _administration_reserved_bytes(sheet)
    if not reserved:
        return []
    prescribed = _sheet_constants(sheet, source=source)
    failures: list[str] = []
    for field in fields:
        failure = _reserved_field_write_failure(field, reserved, prescribed)
        if failure is not None:
            failures.append(failure)
    return failures


def _reserved_field_write_failure(
    field: ExportFieldDefinition,
    reserved: Mapping[int, str],
    prescribed: Mapping[tuple[int, int], str],
) -> str | None:
    if field.offset is None or field.length is None or field.kind is CasillaFieldKind.FILLER:
        return None
    if field.kind is CasillaFieldKind.LITERAL and prescribed.get((field.offset, field.length)) == field.literal:
        return None
    clash = sorted(byte for byte in range(field.offset, field.offset + field.length) if byte in reserved)
    if not clash:
        return None
    return (
        f"field {field.id!r} (@{field.offset}+{field.length}) writes data into "
        f"@{clash[0]}..{clash[-1]}, which the design reserves for the Administración "
        f"({reserved[clash[0]]!r}); emit those bytes as a filler instead"
    )


def _covers(position: requirements._RequiredPosition, data_bytes: set[int], fill_bytes: set[int]) -> bool:
    """Whether the layout can really write every byte of ``position``.

    Coverage is measured by BYTE EXTENT, not by ``(offset, length)`` identity,
    because the design's grouping of bytes into rows and the layout's grouping
    of the same bytes into fields are independent and both are legitimate. AEAT
    declares one 193-byte ``DIRECCIÓN DEL INMUEBLE`` where the application holds
    fifteen separate facts, and declares eight sub-positions where Modelo 576
    holds one span; matching coordinates demanded that the two groupings agree,
    which they never had to.

    Insisting on identity was not merely imprecise, it was UNSATISFIABLE for
    three design sheets. Modelo 280's, Modelo 190's and Modelo 349's tipo-2
    sheets each declare a parent row AND its sub-rows, so identity demanded
    overlapping byte ranges -- and
    :func:`~._export._reject_overlapping_ranges` forbids any record from
    declaring two overlapping fields. No correct layout could satisfy both
    halves. Modelo 280 is authored complete against its official design and was
    reported at 33/53, every one of the twenty "unwritten" positions a
    coordinate it does in fact write.

    A FILLER never covers a required position. The gate counted one before, and
    across the bundled tree that hid 185 positions the operator's filing emits
    as blanks -- Modelo 270 reported 36/36 complete while blanking ``NÚMERO
    IDENTIFICATIVO DE LA DECLARACIÓN``, Modelo 341 33/33 while blanking
    ``SWIFT``, Modelo 190 96.2% against a real data coverage of 32%. A blank
    where AEAT expects a datum is exactly the silent under-declaration this gate
    exists to refuse, so a position is covered only when real data reaches every
    one of its bytes.

    A filler over bytes the design ITSELF declares omissible stays correct and
    stays legal: a fixed-width record is contiguous and those bytes must still
    be emitted. Such positions never reach here, because
    :func:`_required_positions` excluded them.

    The one position that DOES reach here and is satisfied by a filler is the
    obligatory BLANK -- AEAT marking a position obligatorio while its own
    ``Contenido`` cell declares the content to be blanks. Both statements are
    the authority's and neither overrides the other: the field must be emitted,
    and what it emits is blanks. Requiring real data there made 34 positions
    across Modelos 369, 322, 036, 210 and 353 UNSATISFIABLE -- a filler did not
    cover them, and a value-carrying field would both contradict the Contenido
    cell and trip :func:`_reserved_write_failures` for claiming reserved bytes.
    A rule no correct layout can satisfy is a rule that teaches authors to write
    the wrong shape, which is the incentive inversion this module exists to
    remove.
    """
    countable = fill_bytes if position.declared_blank else data_bytes
    return all(byte in countable for byte in range(position.offset, position.offset + position.length))


def _belongs_to_layout(
    sheet: RecordDesignSheet,
    records: Sequence[ExportRecordDefinition],
    constants_by_binding: Mapping[str, str] | None = None,
    *,
    source: SourceReference | None = None,
) -> bool:
    """Whether this design sheet is one THIS layout is supposed to render at all.

    One bundled workbook can describe several independent filing schemas. Modelo
    369 is the case: its ``union``, ``exterior`` and ``importación`` schemas each
    declare their own layout, and all three cite the SAME design workbook, whose
    sheets carry a per-schema ``Página`` constant (``01``-``03`` Ext, ``04``-``09``
    Un, ``10``-``12`` Imp). Measuring every layout against every sheet scored
    each complete schema against all 1,513 positions, including the other two
    schemas' -- a structural cap no authoring could lift, and the reason all
    three looked permanently incomplete while each writes its own sheets in full.

    The question is asked PER COORDINATE, not per record. Asking whether any
    record agrees overall answers "yes" for every sheet, because the envelope
    record declares only ``<T`` and ``369`` -- constants every sheet in the
    workbook shares -- and so agrees with all fourteen. The discriminating byte
    is the one where the layout's records actually disagree with each other.

    So a sheet is out of scope when, at some coordinate it declares, EVERY
    record that speaks to that coordinate contradicts it. Under the importación
    layout, sheet ``T36901 Ext`` declares ``(6,2) = "01"`` while every record
    declaring ``(6,2)`` says ``"00"``, ``"10"``, ``"11"``, ``"12"`` -- AEAT's own
    statement that this sheet is another schema's.

    Silence is never taken as exclusion: a coordinate no record speaks to, or a
    sheet declaring no constants at all, leaves the sheet IN scope and falls
    through to the weaker layout-wide question. "No evidence either way" must
    not shrink a denominator, which is the one direction this gate must never
    fail in.
    """
    literals_by_record = [_record_literals(record, constants_by_binding) for record in records]
    for coordinate, value in _identity_constants(sheet, source=source).items():
        declaring = [literals[coordinate] for literals in literals_by_record if coordinate in literals]
        if declaring and all(declared != value for declared in declaring):
            return False
    return True


def _sheet_run_is_filler(sheet: RecordDesignSheet, offset: int, length: int) -> bool | None:
    """Whether the design describes ``offset``..``offset+length-1`` as filler.

    Asks whether the design describes the WHOLE span as filler, because that is
    the question a discriminator asks -- "are these bytes blank in this record?"
    -- and a span may be described by several fields. Modelo 349's two sheets
    happen to describe theirs with one field each at an identical coordinate;
    Modelo 193's do not, declaring a 293-byte BLANCOS run against a 1-byte
    NATURALEZA DEL DECLARANTE at the same start. An exact-coordinate test
    answers the first and is simply blind to the second.

    Returns ``None`` when any byte of the span is described by nothing: silence
    over part of a run is silence over the run, and must never be read as
    blankness.

    "Filler" is AEAT's own word, read from the field's naturaleza or its
    description -- ``Blancos`` on Modelo 349's operador sheet against
    ``RECTIFICACIONES`` on its rectificaciones sheet, the latter subdivided into
    two real importe fields. The same vocabulary the row parser already treats
    as authoritative for a filler run, rather than a second reading of the same
    idea.
    """
    span = range(offset, offset + length)
    covering = [item for item in sheet.fields if item.offset < offset + length and offset < item.offset + item.length]
    if not covering:
        return None
    described = {position for item in covering for position in range(item.offset, item.offset + item.length)}
    if not set(span) <= described:
        # Part of the span is described by nothing, so the design does not say
        # whether it is blank. Silence over any byte of the run is silence over
        # the run.
        return None
    return all(_field_is_filler(item) for item in covering)


def _field_is_filler(field: RecordDesignField) -> bool:
    """Whether AEAT describes one field as a filler run."""
    return any(
        text is not None and _FILLER_RUN_RE.match(str(text).strip()) is not None
        for text in (field.type_code, field.description, field.content)
    )


def _discriminator_prefers(
    sheet: RecordDesignSheet,
    record: ExportRecordDefinition,
) -> bool | None:
    """Whether ``record``'s declared discriminator agrees with ``sheet`` at its coordinate.

    ``RecordDiscriminator`` exists for precisely the ambiguity this join hits:
    its own docstring says a literal-prefix matcher "cannot tell two records
    apart when they share their leading literal fields", which is the Tipo-2
    sub-shape case exactly. The parser already consults it while reading binding
    rows; the coverage join did not, so two records with identical prefixes tied
    and fell to the weaker layout-wide question even though the registry
    declared how to tell them apart.

    Returns ``None`` when the record declares no discriminator or the sheet says
    nothing at that coordinate -- silence is never taken as agreement.
    """
    discriminator = record.discriminator
    if discriminator is None:
        return None
    is_filler = _sheet_run_is_filler(sheet, discriminator.offset, discriminator.length)
    if is_filler is None:
        return None
    return is_filler if discriminator.requires == "blank" else not is_filler


def _join_record(
    sheet: RecordDesignSheet,
    records: Sequence[ExportRecordDefinition],
    constants_by_binding: Mapping[str, str] | None = None,
    *,
    source: SourceReference | None = None,
) -> ExportRecordDefinition | None:
    """Return the one authored record whose declared constants identify this sheet.

    Agreement is counted only over coordinates BOTH sides declare a constant at,
    and any contradiction there disqualifies the record outright -- Modelo 714's
    ``714-02`` writes ``"02000"`` where the ``714-01`` sheet declares ``"01000"``,
    which is precisely the byte AEAT uses to tell the two records apart.

    A unique maximum is required. Modelo 390's page records all agree on ``<T``
    and ``390``, so a merely-nonzero agreement would match every page to every
    sheet; the page discriminator breaks the tie, and where nothing does, the
    sheet stays unjoined rather than taking an arbitrary winner.
    """
    constants = _identity_constants(sheet, source=source)
    if not constants:
        return None
    scored = _score_records(constants, records, constants_by_binding)
    if not scored:
        return None
    winners = _best_records(scored)
    return _resolve_record_tie(sheet, winners)


def _score_records(
    constants: Mapping[tuple[int, int], str],
    records: Sequence[ExportRecordDefinition],
    constants_by_binding: Mapping[str, str] | None,
) -> list[tuple[int, ExportRecordDefinition]]:
    """Collect records whose shared constants agree with a design sheet."""
    return [
        (score, record)
        for record in records
        if (score := _record_constant_agreement(constants, record, constants_by_binding)) is not None
    ]


def _best_records(scored: Sequence[tuple[int, ExportRecordDefinition]]) -> list[ExportRecordDefinition]:
    """Return records tied for the highest constant agreement."""
    best = max(score for score, _ in scored)
    return [record for score, record in scored if score == best]


def _resolve_record_tie(
    sheet: RecordDesignSheet,
    winners: Sequence[ExportRecordDefinition],
) -> ExportRecordDefinition | None:
    """Resolve equal constant scores only through a declared discriminator."""
    if len(winners) == 1:
        return winners[0]
    # ONLY a tie-breaker, never an override: reached solely when the declared
    # constants leave more than one record at the same agreement score, so it
    # can turn "no join" into a join and can never change one the constants
    # already decided. Where the discriminator is silent too, the sheet stays
    # unjoined rather than taking an arbitrary winner.
    preferred = [record for record in winners if _discriminator_prefers(sheet, record) is True]
    return preferred[0] if len(preferred) == 1 else None


def _record_constant_agreement(
    constants: Mapping[tuple[int, int], str],
    record: ExportRecordDefinition,
    constants_by_binding: Mapping[str, str] | None,
) -> int | None:
    """Score one authored record against a design sheet's constants."""
    literals = _record_literals(record, constants_by_binding)
    shared = constants.keys() & literals.keys()
    if not shared or any(constants[key] != literals[key] for key in shared):
        return None
    return len(shared)


def _design_sources(
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
) -> tuple[SourceReference, ...]:
    return tuple(
        source
        for ref in layout.source_refs
        if (source := source_refs.get(ref)) is not None and source.kind is RegistrySourceKind.RECORD_DESIGN
    )


def _read_design_sheets(source: SourceReference) -> tuple[RecordDesignSheet, ...] | str:
    """Return the source's sheets, or the reason no complete design could be read.

    ``require_complete`` rather than ``accept_partial``: a coverage figure
    derived from a partly-read design is inflated by exactly the records that
    were dropped, and nothing downstream can tell that from real coverage.
    """
    path = resolve_corpus_binary(*source.corpus_path.split("/"))
    if path is None:
        return (
            f"its official record design {source.id!r} ({source.corpus_path!r}) is not reachable in "
            f"this installation, so its coverage cannot be verified. The corpus binaries ship in the "
            f"mandatory cadrumo_data companion namespace; an unreachable design is a broken "
            f"installation, and reporting a layout complete against a file nobody read is the one "
            f"outcome this gate must never produce"
        )
    try:
        return extract_record_design(path).require_complete()
    except RegistryValidationError as exc:
        return (
            f"its official record design {source.id!r} could not be read in full, so its coverage "
            f"cannot be verified: {exc}. A coverage figure derived from a partly-read design is "
            f"inflated by exactly the records that were dropped"
        )


def _envelope_written_bytes(envelope: FilingEnvelopeDefinition) -> set[int]:
    """Return every byte the filing envelope's prefix fields write.

    Every prefix field carries a real declared value, so none is filler and the
    data-only distinction :func:`_written_bytes` draws does not arise here.
    """
    written: set[int] = set()
    offset = 1
    for field in envelope.prefix_fields:
        written.update(range(offset, offset + field.length))
        offset += field.length
    return written
