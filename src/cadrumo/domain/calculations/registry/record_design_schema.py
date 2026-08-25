"""Record-design parser output models."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ....core import Modelo
from .errors import RegistryValidationError
from .schema import RegistryModel

__all__ = [
    "AUXILIARY_ENVELOPE_HEADER_CONTENT",
    "AUXILIARY_ENVELOPE_HEADER_LENGTHS",
    "AUXILIARY_ENVELOPE_HEADER_ORDINALS",
    "AUXILIARY_ENVELOPE_HEADER_ROWS",
    "RecordDesignAuxiliaryEnvelopeHeader",
    "RecordDesignAuxiliaryEnvelopeHeaderField",
    "RecordDesignAuxiliaryEnvelopeHeaderRole",
    "RecordDesignCompositeRelativeClosing",
    "RecordDesignCorrection",
    "RecordDesignExtraction",
    "RecordDesignField",
    "RecordDesignFieldTypeCorrection",
    "RecordDesignHeaderCellCorrection",
    "RecordDesignNote",
    "RecordDesignRelativeSuffixMarker",
    "RecordDesignSheet",
    "RecordDesignSkippedSheet",
    "RecordDesignVariableBodyMarker",
    "RecordDesignVariableEnvelope",
    "RecordDesignVariableTotalMarker",
    "validate_auxiliary_envelope_header_contents",
]


class RecordDesignField(RegistryModel):
    """One fixed-width field described by an AEAT record-design sheet."""

    sheet: str
    row: int
    #: The ordinal AEAT printed, verbatim, or ``None`` where the sheet declares
    #: none.
    #:
    #: ``None`` means the ORDINAL CELL IS EMPTY, never that the parser could not
    #: read it. AEAT leaves it blank for rows it declines to number -- Modelo 036
    #: writes a `Fecha de constitución` as three unnumbered rows for día, mes and
    #: año, sharing one casilla -- and dropping them put their eight bytes into a
    #: downstream geometry gap that blamed the design.
    #:
    #: A ``str`` rather than an ``int`` because AEAT's ordinal is a PRINTED LABEL,
    #: not an arithmetic value: Modelo 303 prints ``14bis`` beside its ``14`` and
    #: Modelo 576 desglosa a field's ordinal into ``19.1``..``19.8``. Never
    #: synthesised -- a fabricated ordinal indistinguishable from a printed one is
    #: the false-green shape this field exists to avoid.
    ordinal: str | None = None
    offset: int
    length: int
    type_code: str
    complementary: str | None = None
    description: str
    validation: str | None = None
    content: str | None = None
    #: Sub-fields AEAT desglosa (breaks out) from this field's own printed span,
    #: e.g. Modelo 576's ``19.1``..``19.8`` under parent ordinal ``19``.
    #:
    #: ADDITIVE ONLY. This field's own ``offset``/``length`` continue to span the
    #: WHOLE group exactly as they did before components existed, so every
    #: consumer computing geometry from ``offset``/``length`` alone -- the
    #: contiguity check, the IR projection, the export-tree join -- sees exactly
    #: what it saw before. A component is detail a consumer may ignore, never a
    #: replacement for the parent's own span. A component's own ``components``
    #: tuple is always empty; nothing in the corpus nests two levels deep, and
    #: this field does not assert that it could.
    components: tuple[RecordDesignField, ...] = ()


class RecordDesignAuxiliaryEnvelopeHeaderRole(StrEnum):
    """One exact source role in the fixed AEAT auxiliary page-zero header."""

    OPENING_TAG = "opening_tag"
    MODELO = "modelo"
    DISCRIMINANT = "discriminant"
    FILING_YEAR = "filing_year"
    ANNUAL_PERIOD = "annual_period"
    RECORD_TYPE = "record_type"
    AUXILIARY_OPENING_TAG = "auxiliary_opening_tag"
    PRE_PROGRAM_RESERVED = "pre_program_reserved"
    PROGRAM_IDENTIFIER = "program_identifier"
    BETWEEN_IDENTITIES_RESERVED = "between_identities_reserved"
    SOFTWARE_DEVELOPER_TAX_ID = "software_developer_tax_id"
    POST_DEVELOPER_RESERVED = "post_developer_reserved"
    AUXILIARY_CLOSING_TAG = "auxiliary_closing_tag"


_AUXILIARY_HEADER_ROLES: tuple[RecordDesignAuxiliaryEnvelopeHeaderRole, ...] = tuple(
    RecordDesignAuxiliaryEnvelopeHeaderRole,
)
AUXILIARY_ENVELOPE_HEADER_LENGTHS: tuple[int, ...] = (2, 3, 1, 4, 2, 5, 5, 70, 4, 4, 9, 213, 6)
#: The exact Contenido cell every design writes at this position. Two indices
#: are deliberately absent and validated separately, because AEAT spells them
#: differently across designs while the WIRE fact is identical.
AUXILIARY_ENVELOPE_HEADER_CONTENT: tuple[str | None, ...] = (
    'Constante "<T"',
    None,
    'Constante "0"',
    None,
    '"0A"',
    '"0000>"',
    '"<AUX>"',
    "BLANCOS",
    None,
    "BLANCOS",
    None,
    "BLANCOS",
    '"</AUX>"',
)
#: The slot carrying the modelo's OWN three-digit constant. Pinning it to one
#: modelo made this header contract single-modelo by accident: every other
#: structural check -- roles, lengths, rows, ordinals, extent -- is already
#: modelo-neutral, so the literal was the only thing rejecting an identical
#: header on another form.
_AUXILIARY_ENVELOPE_HEADER_MODELO_INDEX: Final[int] = 1
_AUXILIARY_ENVELOPE_HEADER_MODELO_RE: Final[re.Pattern[str]] = re.compile(r'^Constante "\d{3}"$')
#: Slots AEAT footnotes rather than fills: the filing year and the two entidad
#: desarrolladora identity positions. Modelo 390 writes the marker IN the
#: Contenido cell ("Nota 2", "Nota 1"); Modelo 232 leaves the cell empty and
#: puts the same footnote in the description instead. Neither spelling is a wire
#: fact -- the values come from the producer either way -- so both are admitted,
#: and nothing else is.
_AUXILIARY_ENVELOPE_HEADER_FOOTNOTE_INDICES: Final[frozenset[int]] = frozenset({3, 8, 10})
_AUXILIARY_ENVELOPE_HEADER_FOOTNOTE_RE: Final[re.Pattern[str]] = re.compile(r"^Nota\s+\d+$", re.IGNORECASE)
AUXILIARY_ENVELOPE_HEADER_ROWS: tuple[int, ...] = tuple(range(6, 19))
AUXILIARY_ENVELOPE_HEADER_ORDINALS: tuple[str, ...] = tuple(str(i) for i in range(1, 14))


class RecordDesignAuxiliaryEnvelopeHeaderField(RegistryModel):
    """One exact parser field with its source-proved auxiliary-header role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: RecordDesignAuxiliaryEnvelopeHeaderRole
    field: RecordDesignField


class RecordDesignAuxiliaryEnvelopeHeader(RegistryModel):
    """A source-proved fixed header deliberately outside fixed-record totals.

    The admitted shape is the thirteen-slot AEAT auxiliary header: fixed
    roles, lengths, rows, ordinals and literals, with the modelo's own
    constant and AEAT's footnoted slots the only modelo-varying parts.  Its
    terminal extent is an emitted-byte property, never a parser
    ``declared_total`` for a fixed record.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sheet: str
    record_identity: str
    fields: tuple[RecordDesignAuxiliaryEnvelopeHeaderField, ...] = Field(min_length=13, max_length=13)
    emitted_extent: Literal[328]

    @model_validator(mode="after")
    def _require_exact_auxiliary_header_source_shape(self) -> Self:
        raw_fields = tuple(item.field for item in self.fields)
        _validate_auxiliary_header_roles(self.fields)
        _validate_auxiliary_header_lengths(raw_fields)
        validate_auxiliary_envelope_header_contents(tuple(field.content for field in raw_fields))
        _validate_auxiliary_header_positions(raw_fields)
        _validate_auxiliary_header_extent(raw_fields, self.emitted_extent)
        return self

    @property
    def source_fields(self) -> tuple[RecordDesignField, ...]:
        """Return the thirteen parser fields in their official source order."""
        return tuple(item.field for item in self.fields)


def _validate_auxiliary_header_roles(
    fields: tuple[RecordDesignAuxiliaryEnvelopeHeaderField, ...],
) -> None:
    if tuple(item.role for item in fields) != _AUXILIARY_HEADER_ROLES:
        raise ValueError("auxiliary envelope header does not retain its exact thirteen source roles")


def _validate_auxiliary_header_lengths(fields: tuple[RecordDesignField, ...]) -> None:
    if tuple(field.length for field in fields) != AUXILIARY_ENVELOPE_HEADER_LENGTHS:
        raise ValueError("auxiliary envelope header has an unsupported source length sequence")


def validate_auxiliary_envelope_header_contents(contents: tuple[str | None, ...]) -> None:
    """Require the exact auxiliary-header Contenido shape, modelo-neutrally.

    The ONE definition of this rule. The parser's own header model and the
    development intermediate that re-projects it both call it; a second copy is
    how the two came to disagree about which modelos have an auxiliary header.

    Raises:
        ValueError: when a slot carries neither its required literal, the
            modelo's own three-digit constant, nor an admitted footnote spelling.
    """
    for index, (expected, value) in enumerate(zip(AUXILIARY_ENVELOPE_HEADER_CONTENT, contents, strict=True)):
        if index == _AUXILIARY_ENVELOPE_HEADER_MODELO_INDEX:
            if value is None or not _AUXILIARY_ENVELOPE_HEADER_MODELO_RE.fullmatch(value.strip()):
                raise ValueError(
                    "auxiliary envelope header does not declare a three-digit modelo constant at its "
                    f"second slot: {value!r}",
                )
            continue
        if index in _AUXILIARY_ENVELOPE_HEADER_FOOTNOTE_INDICES:
            stripped = (value or "").strip()
            if stripped and not _AUXILIARY_ENVELOPE_HEADER_FOOTNOTE_RE.fullmatch(stripped):
                raise ValueError(
                    "auxiliary envelope header footnoted slot carries neither a footnote marker nor an "
                    f"empty cell: {value!r}",
                )
            continue
        if value != expected:
            raise ValueError(
                f"auxiliary envelope header slot {index} carries {value!r}, not the required {expected!r}",
            )


def _validate_auxiliary_header_positions(fields: tuple[RecordDesignField, ...]) -> None:
    if tuple(field.row for field in fields) != AUXILIARY_ENVELOPE_HEADER_ROWS:
        raise ValueError("auxiliary envelope header does not match the exact auxiliary-header source rows")
    if tuple(field.ordinal for field in fields) != AUXILIARY_ENVELOPE_HEADER_ORDINALS:
        raise ValueError("auxiliary envelope header does not match exact Modelo 390 source ordinals")


def _validate_auxiliary_header_extent(fields: tuple[RecordDesignField, ...], emitted_extent: int) -> None:
    expected_offset = 1
    for field in fields:
        if field.offset != expected_offset:
            raise ValueError("auxiliary envelope header source geometry is not contiguous")
        expected_offset += field.length
    if expected_offset - 1 != emitted_extent:
        raise ValueError("auxiliary envelope header extent must derive from all thirteen source fields")


class RecordDesignVariableBodyMarker(RegistryModel):
    """Official marker that opens a variable-length composed body."""

    sheet: str
    row: int = Field(gt=0)
    ordinal: int = Field(gt=0)
    offset: int = Field(gt=0)
    length: Literal["Variable"]
    type_code: str
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignRelativeSuffixMarker(RegistryModel):
    """Official closing suffix positioned relative to a variable body."""

    sheet: str
    row: int = Field(gt=0)
    ordinal: int = Field(gt=0)
    offset: Literal["***"]
    length: int = Field(gt=0)
    type_code: str
    description: str
    validation: str | None = None
    content: str | None = None


def _validate_m220_closing_part_shape(parts: tuple[RecordDesignRelativeSuffixMarker, ...]) -> None:
    if tuple(part.offset for part in parts) != ("***",) * 6:
        raise ValueError("composite relative closing requires six relative offsets")
    if tuple(part.length for part in parts) != (3, 3, 1, 4, 2, 5):
        raise ValueError("composite relative closing has an unsupported length sequence")
    if tuple(part.type_code.strip().casefold() for part in parts) != ("an",) * 6:
        raise ValueError("composite relative closing requires six alphanumeric parts")
    if tuple(part.content for part in parts) != (
        "</T",
        Modelo.M220.value,
        "(*)[A|E|I|0]",
        None,
        "0A",
        "0000>",
    ):
        raise ValueError("composite relative closing does not match the exact Modelo 220 source content")


def _validate_m220_closing_source_sequence(parts: tuple[RecordDesignRelativeSuffixMarker, ...]) -> None:
    if tuple(part.row for part in parts) != tuple(range(parts[0].row, parts[0].row + 6)):
        raise ValueError("composite relative closing source rows are not consecutive")
    if tuple(part.ordinal for part in parts) != tuple(range(parts[0].ordinal, parts[0].ordinal + 6)):
        raise ValueError("composite relative closing ordinals are not consecutive")


class RecordDesignCompositeRelativeClosing(RegistryModel):
    """Exact six-row relative closing declared by Modelo 220 designs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag_prefix: RecordDesignRelativeSuffixMarker
    modelo: RecordDesignRelativeSuffixMarker
    discriminant: RecordDesignRelativeSuffixMarker
    filing_year: RecordDesignRelativeSuffixMarker
    period: RecordDesignRelativeSuffixMarker
    tag_suffix: RecordDesignRelativeSuffixMarker

    @model_validator(mode="after")
    def _validate_exact_m220_sequence(self) -> Self:
        parts = self.parts
        _validate_m220_closing_part_shape(parts)
        _validate_m220_closing_source_sequence(parts)
        return self

    @property
    def parts(self) -> tuple[RecordDesignRelativeSuffixMarker, ...]:
        """Return the six source rows in official order without concatenating them."""
        return (
            self.tag_prefix,
            self.modelo,
            self.discriminant,
            self.filing_year,
            self.period,
            self.tag_suffix,
        )


class RecordDesignVariableTotalMarker(RegistryModel):
    """Official declaration that the composed record has variable total length."""

    sheet: str
    row: int = Field(gt=0)
    label: Literal["total"]
    length: Literal["Variable"]


class RecordDesignVariableEnvelope(RegistryModel):
    """Variable composition wrapper, distinct from a fixed-width record.

    ITS TOTAL EXTENT IS NOT CHECKABLE, and that is a property of the design rather
    than a gap in the checking. Every one of these sheets declares its total row as
    ``Variable`` -- the body length varies by construction -- so there is no AEAT
    figure to compare a computed extent against. What IS asserted is the fixed
    tail: the closing identifier keeps its declared width and the terminator keeps
    its two bytes, both carried rather than consumed.

    Stated here because the absence otherwise reads as an oversight. A later
    reader finding no extent assertion should conclude that AEAT declares no total,
    not that nobody checked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    prefix_fields: tuple[RecordDesignField, ...] = Field(min_length=1)
    prefix_extent: int = Field(gt=0)
    body: RecordDesignVariableBodyMarker
    closing: RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing
    #: The physical end-of-record marker, when the design declares one as its own row.
    #:
    #: SEPARATE FROM ``closing`` because it is a different kind of thing. The closing
    #: is the record's identifier -- ``</T100020150A0000>`` names the modelo, the
    #: discriminant and the ejercicio. The terminator is two bytes of CRLF that end
    #: the physical line and identify nothing.
    #:
    #: REPRESENTED RATHER THAN PEELED AWAY, and that is the whole reason this field
    #: exists. Thirty bundled designs across eight modelos declare the terminator as
    #: a relative-offset row, and the closing recogniser -- which accepted one suffix
    #: of length 18, or exactly six -- refused every one of them. Simply skipping the
    #: row would have made all thirty parse, and every emitted record would have been
    #: two bytes shorter than AEAT declares: a clean-looking parse that is wrong,
    #: which is worse than the refusal it replaced. Keeping it here means the bytes
    #: are still accounted for and a consumer computing a record's extent can see
    #: them.
    terminator: RecordDesignRelativeSuffixMarker | None = None
    variable_total: RecordDesignVariableTotalMarker


class RecordDesignFieldTypeCorrection(RegistryModel):
    """A declared, sourced correction of one blank ``Tipo`` cell AEAT itself omitted.

    Subject is one DATA ROW; the consequence is that one field's type. Never
    inferred and never a silent fallback: the parser applies a correction ONLY
    when a hand-authored sidecar next to the exact source binary declares one
    for this exact ``(sheet, source_row)``, and every correction carries its
    own grounding inline -- the specific editions read and the reason the
    omission occurred -- so a design read this way is never indistinguishable
    from one AEAT published cleanly. See :class:`RecordDesignCorrection` for
    the sibling that corrects a HEADER cell instead, and
    :attr:`RecordDesignExtraction.corrections` for where both land.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["field_type"] = "field_type"
    sheet: str = Field(min_length=1)
    source_row: int = Field(gt=0)
    corrected_type: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    editions_read: tuple[str, ...] = Field(min_length=1)


class RecordDesignHeaderCellCorrection(RegistryModel):
    """A declared, sourced correction of one blank HEADER cell AEAT itself omitted.

    Subject is a COLUMN of the header row; the consequence is the whole
    sheet's parse, not one field. Deliberately a separate model from
    :class:`RecordDesignFieldTypeCorrection` rather than an extension of it --
    overloading one model to carry both would mean widening its validation to
    admit a row-less, type-less entry, weakening every existing type
    correction's guarantee that it names one real data row. Applied ONLY when
    a sidecar declares one for this exact ``(sheet, header_row, column_index)``,
    and only where the parser's header probe would otherwise find that column
    role missing -- never a fallback for a column that is merely misspelled or
    differently ordered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["header_cell"] = "header_cell"
    sheet: str = Field(min_length=1)
    header_row: int = Field(gt=0)
    column_index: int = Field(ge=0)
    #: Closed to the one shape observed so far. Extend when a new blank-header
    #: shape is grounded, never widen to a free-form string.
    column_role: Literal["length"]
    reason: str = Field(min_length=1)
    editions_read: tuple[str, ...] = Field(min_length=1)


class RecordDesignSinglePositionCorrection(RegistryModel):
    """A declared, sourced admission of ONE naturaleza-less single-position row.

    Subject is one PDF position row that AEAT printed without its naturaleza and
    without a range -- ``58 TIPO DE SOPORTE`` in Modelo 280's declarante record,
    whose type column is simply absent and whose description continues on the
    next page.

    Separate from :class:`RecordDesignFieldTypeCorrection` rather than a widening
    of it, for the same reason the header-cell correction is separate: that model
    keys on a workbook ``source_row`` and asserts the row was READ with a blank
    type cell, whereas this one asserts a row was not read at all and names the
    position instead. Folding them together would mean loosening the row-based
    model to admit a row-less entry, weakening every existing type correction's
    guarantee that it names one real data row.

    The narrow gate is deliberate. A single position with no naturaleza is
    otherwise indistinguishable from a numbered prose sentence -- AEAT routinely
    opens a description with the field's own range, and 41 bundled designs do --
    so the parser refuses the shape outright and only a declaration for this
    exact ``(sheet, position)`` admits one. Admission is still subject to the
    gap-fill containment test, so a declared correction can fill a genuine hole
    and can never displace, override, or duplicate a row that WAS read.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["single_position"] = "single_position"
    sheet: str = Field(min_length=1)
    #: One-based start position of the unread single-byte row.
    position: int = Field(gt=0)
    corrected_type: str = Field(min_length=1)
    #: The field name AEAT printed, with the naturaleza column absent.
    description: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    editions_read: tuple[str, ...] = Field(min_length=1)


#: One concept, one collection: a design reads only because of a declared,
#: sourced correction whether the correction fixed a data cell, a header
#: cell, or admitted a row the parser could not safely infer, so all three feed
#: the SAME :attr:`RecordDesignExtraction.corrections` tuple through this
#: discriminated union. A worklist reading ``corrections`` needs no per-kind
#: branch to keep treating "corrected" as distinct from "complete" -- see
#: ``_classify()`` in ``test_every_bundled_design_is_read_or_reported.py``.
RecordDesignCorrection = Annotated[
    RecordDesignFieldTypeCorrection | RecordDesignHeaderCellCorrection | RecordDesignSinglePositionCorrection,
    Field(discriminator="kind"),
]


class RecordDesignNote(RegistryModel):
    """One ``Nota N`` definition a record-design sheet prints beneath its table.

    A field's naming cell cites the ordinal (``Versión del Programa (Nota 1)``);
    only this body says what the citation MEANS. Reading a citation without its
    definition would let one design's ``Nota 1`` be interpreted as another's, so
    both travel together on the sheet that printed them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    ordinal: str
    body: str


class RecordDesignSheet(RegistryModel):
    """Parsed field rows and declared total length for one workbook sheet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[RecordDesignField, ...]
    total_positions: int | None = None
    variable_envelope: RecordDesignVariableEnvelope | None = None
    auxiliary_envelope_header: RecordDesignAuxiliaryEnvelopeHeader | None = None
    #: Declared corrections applied while reading this sheet -- a data row's
    #: type or a header column, per :data:`RecordDesignCorrection`. Empty for
    #: the overwhelming majority of sheets, which read as published.
    corrections: tuple[RecordDesignCorrection, ...] = ()
    #: ``Nota N`` definitions printed beneath this sheet's field table.
    notes: tuple[RecordDesignNote, ...] = ()

    def note_body(self, ordinal: str) -> str | None:
        """Return the body of ``Nota <ordinal>`` as this sheet printed it."""
        for note in self.notes:
            if note.ordinal == ordinal:
                return note.body
        return None

    @model_validator(mode="after")
    def _require_one_record_composition_kind(self) -> Self:
        if self.variable_envelope is not None and self.auxiliary_envelope_header is not None:
            raise ValueError("record-design sheet cannot be both variable envelope and auxiliary header")
        if self.auxiliary_envelope_header is not None:
            if self.total_positions is not None:
                raise ValueError("auxiliary envelope header must not declare a fixed-record total")
            if self.auxiliary_envelope_header.sheet != self.name:
                raise ValueError("auxiliary envelope header sheet identity does not match its parser sheet")
            if self.auxiliary_envelope_header.record_identity != self.name:
                raise ValueError("auxiliary envelope header record identity does not match its parser sheet")
            if self.auxiliary_envelope_header.source_fields != self.fields:
                raise ValueError("auxiliary envelope header fields must exactly be its parser sheet fields")
        return self


class RecordDesignSkippedSheet(RegistryModel):
    """A sheet the extractor could not read, and the reason it gave.

    Recorded rather than discarded. The extractor used to keep this list only long
    enough to compose the message for the case where EVERY sheet failed, and threw
    it away the moment one sheet parsed -- so a design that lost half its records
    was handed to the caller looking exactly like one that lost none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    reason: str
    #: Whether a reviewer DECLARED this tab is not a record-design sheet, in the
    #: source's ``declared-non-record-sheets.json``, as opposed to the extractor
    #: simply failing to find a header on it.
    #:
    #: The judgement already existed and was thrown away: the declaration was
    #: read only to replace the parser's generic probe message with the
    #: reviewer's prose, so a workbook carrying an adjudicated lookup tab was
    #: indistinguishable from one that lost a record body, and both refused.
    #: Modelo 232 is completely read -- all three record sheets, 263 anchors --
    #: and could not be generated solely because its ``TABLAS`` lookup tab is
    #: correctly not a record design.
    #:
    #: Defaults False so an undeclared skip stays a partial read. Only the
    #: declaration can clear it, and the declaration is a registry act.
    declared_non_record: bool = False


class RecordDesignExtraction(RegistryModel):
    """What one design source yielded, INCLUDING what it did not.

    The completeness of a read is a property of the READ, so it belongs in the
    value the read returns. A bare tuple of sheets cannot express "these are all of
    them" separately from "these are the ones that worked", which is why a partial
    extraction was previously indistinguishable from a whole one at every consumer
    and in every count derived downstream.

    Consumers do not receive sheets without saying what they think about
    partiality: :meth:`require_complete` refuses an incomplete read, and
    :meth:`accept_partial` takes it deliberately. There is no accessor that hands
    over the sheets without that choice being written at the call site, which is
    the point -- an omission is what produced the original defect, so an omission
    has to stop being expressible.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    sheets: tuple[RecordDesignSheet, ...]
    skipped: tuple[RecordDesignSkippedSheet, ...] = ()

    @property
    def unread_record_sheets(self) -> tuple[RecordDesignSkippedSheet, ...]:
        """Every skipped sheet a reviewer has NOT adjudicated as a non-record tab.

        This is the set that makes a read partial. A declared non-record tab is
        not a missing record: the reviewer opened the workbook and recorded that
        it never carries ``Posic.``/``Lon``/``Tipo``/``Contenido`` at all.
        """
        return tuple(item for item in self.skipped if not item.declared_non_record)

    @property
    def is_complete(self) -> bool:
        """Whether every RECORD sheet of the source was read.

        A declared non-record tab does not make a read incomplete; an
        undeclared skip does.
        """
        return not self.unread_record_sheets

    @property
    def corrections(self) -> tuple[RecordDesignCorrection, ...]:
        """Every declared correction applied anywhere in this source, flattened.

        Non-empty here means this design reads fully only BECAUSE of a
        declared, sourced correction -- a fact a caller reporting on the read
        (never a downstream consumer of the values themselves, which are
        correct either way) must not collapse into "read as published".
        """
        return tuple(correction for sheet in self.sheets for correction in sheet.corrections)

    def require_complete(self) -> tuple[RecordDesignSheet, ...]:
        """Return every sheet, refusing when the source was only partly read.

        Returns:
            The parsed sheets, when the whole source was read.

        Raises:
            RegistryValidationError: when a RECORD sheet of the source was
                skipped without a reviewer declaring it a non-record tab.
        """
        unread = self.unread_record_sheets
        if unread:
            detail = "; ".join(f"{item.name!r}: {item.reason}" for item in unread)
            raise RegistryValidationError(
                f"{self.source}: read {len(self.sheets)} sheet(s) but could not read "
                f"{len(unread)} more, so this is a PARTIAL design and every count "
                f"derived from it understates the source -- {detail}. If a listed tab "
                "carries no record design at all, declare it in the source's "
                "declared-non-record-sheets.json rather than widening this refusal.",
            )
        return self.sheets

    def accept_partial(self) -> tuple[RecordDesignSheet, ...]:
        """Return the sheets that were read, deliberately tolerating a partial read.

        Returns:
            The parsed sheets, whether or not the source was read completely.
        """
        return self.sheets
