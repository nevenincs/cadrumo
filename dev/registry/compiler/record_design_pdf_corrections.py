"""Corrections applied to reconstructed PDF record-design sheets after their rows are read."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from dev.registry.compiler.record_design_schema import (
    RecordDesignField,
    RecordDesignRangeStartCorrection,
    RecordDesignSheet,
)


def covered_positions(fields: Iterable[RecordDesignField]) -> set[int]:
    """Return all positions claimed by the supplied fields."""
    covered: set[int] = set()
    for parsed_field in fields:
        covered.update(range(parsed_field.offset, parsed_field.offset + parsed_field.length))
    return covered


def nonempty_field_texts(field: RecordDesignField) -> Iterable[str]:
    """Yield the available textual projections of one parsed field."""
    return filter(None, (field.content, field.description, field.validation))


#: A record row declaring a bracket constant: ``Constante "<VECTOR>"`` opens a
#: payload region and ``Constante "</VECTOR>"`` closes it.
_PDF_BRACKET_CONSTANT_RE = re.compile(r'Constante\s*"<(?P<closing>/?)(?P<tag>[A-Z][A-Z0-9_]*)>"')


def bracketed_payload_positions(sheet: RecordDesignSheet) -> set[int]:
    """Positions a record brackets as a payload region rather than numbering.

    Some AEAT records wrap a block of content between two constant rows --
    ``Constante "<VECTOR>"`` at 329-336 and ``Constante "</VECTOR>"`` at 637-645
    in modelo 200's 2010 orden edition -- and describe what sits between them in
    PROSE rather than as numbered field rows ("y el resto a blancos hasta
    completar las 300 posiciones"). The bytes are declared; only the numbering
    is absent.

    Contiguity reads that as a 300-byte hole and reports the record as partly
    read, which is wrong in a way that matters: it is indistinguishable from the
    dropped-row defect the check exists to catch, so a genuine reader bug in
    such a record would hide behind an expected complaint.

    The span is taken from the two constants' own offsets, never from the prose.
    That is what keeps this from being an invention: AEAT declares both markers
    as required content at fixed positions, so what they bracket is fixed too.
    The prose is corroboration and it agrees exactly -- 337 to 636 is 300
    positions -- but nothing here parses it.

    Only a MATCHED pair counts, and only in the order open-then-close. A lone
    marker, or a closing marker before its opening, describes no region and is
    left to be reported as the hole it is.
    """
    openings: dict[str, RecordDesignField] = {}
    covered: set[int] = set()
    for design_field in sorted(sheet.fields, key=lambda item: item.offset):
        for text in nonempty_field_texts(design_field):
            match = _PDF_BRACKET_CONSTANT_RE.search(str(text))
            if match is None:
                continue
            tag = match.group("tag")
            if not match.group("closing"):
                openings[tag] = design_field
            elif (opening := openings.pop(tag, None)) is not None:
                start = opening.offset + opening.length
                if start < design_field.offset and not _numbers_rows_inside(sheet, start, design_field.offset):
                    covered.update(range(start, design_field.offset))
            break
    return covered


def _numbers_rows_inside(sheet: RecordDesignSheet, start: int, end: int) -> bool:
    """Whether the design numbers any field row strictly inside ``start``..``end``.

    This is what keeps bracket accounting from weakening the hole check. A
    bracket credited unconditionally would hide a genuine dropped row that
    happened to fall between two markers, which is the exact defect contiguity
    exists to catch.

    So a bracket earns its region ONLY when AEAT numbers nothing inside it --
    the opaque-payload case, where the bytes are described in prose. Modelo
    200's structural ``<AUX>`` wrapper numbers five rows inside itself and is
    therefore NOT credited; it does not need to be, because those rows already
    tile it. Its ``<VECTOR>`` payload numbers none and is credited.
    """
    return any(start <= probe.offset < end for probe in sheet.fields)


#: A constant AEAT states inside a field's own description, in its own quotes:
#: ``Inicio del identificador de modelo y pagina. "<T840010>". OBLIGATORIO``.
_INLINE_CONSTANT_RE = re.compile(r'"([^"]{1,40})"')

#: A line-terminator row that names its constant by word instead of quoting it:
#: ``Salto de linea. Constante CRLF.`` The two bytes are CR LF, so the row reads
#: as that constant. Nothing wider is admitted: the row must open with the
#: terminator caption, name the constant CRLF and end there.
_INLINE_CRLF_CONSTANT_RE = re.compile(r"(?i)^salto de l[íi]nea\.\s*constante\s+CRLF\.?$")
_CRLF_CONSTANT_CONTENT = "Constante CRLF"
_CRLF_CONSTANT_LENGTH = 2


def _with_crlf_constant(design_field: RecordDesignField) -> RecordDesignField:
    """Give a CRLF terminator row without a quoted constant its two-byte content."""
    if (
        (design_field.content is not None and design_field.content != "")
        or design_field.length != _CRLF_CONSTANT_LENGTH
        or _INLINE_CRLF_CONSTANT_RE.fullmatch((design_field.description or "").strip()) is None
    ):
        return design_field
    return design_field.model_copy(update={"content": _CRLF_CONSTANT_CONTENT})


def recover_inline_constants(sheets: tuple[RecordDesignSheet, ...]) -> tuple[RecordDesignSheet, ...]:
    """Return ``sheets`` with inline-stated constants surfaced as field content.

    AEAT publishes most record designs with a Contenido column, and the reader fills
    ``content`` from it. A few designs have no such column and state the constant
    inside the description instead, so those fields arrive with ``content=None`` and
    every consumer that needs the official constant -- the export generator's literal
    fields above all -- has nothing to read.

    SCOPED TO THE DOCUMENT, NOT TO A MODELO. The fallback fires only when NO field in
    the whole extraction carries content, which is what "this design has no Contenido
    column" means. That matters: measured across the bundled corpus, 210 designs have
    the column and one does not, and a rule that fired per-field instead would have
    given content to 1,625 fields across 13 modelos -- including modelo 210, where the
    quoted text is an enumeration of alternatives ("Transferencia cuenta bancaria en
    Espana"-"Transferencia...") and not a constant at all.

    The caller takes that document-level decision on the text the line parser
    read, BEFORE column geometry separates a design's Contenido cells, and this
    only fills a field whose Contenido cell is empty. Modelo 840 is why: it
    prints a Contenido column but states its record tags inside the description
    cell, so once its other rows carry their own Contenido the old whole-document
    test would have stopped recovering exactly the constants it exists for.
    """
    recovered: list[RecordDesignSheet] = []
    for sheet in sheets:
        fields: list[RecordDesignField] = []
        for design_field in sheet.fields:
            match = (
                None
                if (design_field.content is not None and design_field.content)
                else _INLINE_CONSTANT_RE.search(design_field.description or "")
            )
            if match is None:
                fields.append(_with_crlf_constant(design_field))
                continue
            fields.append(design_field.model_copy(update={"content": match.group(0)}))
        recovered.append(sheet.model_copy(update={"fields": tuple(fields)}))
    return tuple(recovered)


def apply_range_start_corrections(
    sheets: tuple[RecordDesignSheet, ...],
    corrections: Mapping[tuple[str, int], RecordDesignRangeStartCorrection],
) -> tuple[RecordDesignSheet, ...]:
    """Extend a declared filler run backwards over a span no field describes.

    Applied to a row that WAS read, at a start AEAT mis-declared: Modelo 165's
    2013 orden prints ``104-500 BLANCOS`` where both later editions of the same
    orden print ``102-500``, leaving 102-103 described by nothing.

    THE PRECONDITION IS ENFORCED HERE, not trusted from the declaration, and it
    is the whole guard: every position the run would gain must currently be
    described by NO field on the sheet. A correction that would swallow, split
    or overlap a read field RAISES rather than applying, so this kind can only
    ever reclaim a hole -- it can never invent a field, displace one, or quietly
    absorb data AEAT actually declared. A declaration naming a start no row
    begins at raises too, because a correction that matches nothing is a
    mis-transcription and silently ignoring it would leave the hole it was
    written to close.
    """
    if not corrections:
        return sheets
    return tuple(_apply_sheet_range_start_corrections(sheet, corrections) for sheet in sheets)


def _apply_sheet_range_start_corrections(
    sheet: RecordDesignSheet,
    corrections: Mapping[tuple[str, int], RecordDesignRangeStartCorrection],
) -> RecordDesignSheet:
    """Apply this sheet's declarations after proving each reclaimed span is empty."""
    applicable = {start: correction for (name, start), correction in corrections.items() if name == sheet.name}
    if not applicable:
        return sheet
    described = covered_positions(sheet.fields)
    fields = list(sheet.fields)
    applied: list[RecordDesignRangeStartCorrection] = []
    for start, correction in sorted(applicable.items()):
        index = _range_correction_field_index(fields, sheet.name, start)
        gained = _range_correction_hole(sheet.name, start, correction, described)
        original = fields[index]
        fields[index] = original.model_copy(
            update={
                "offset": correction.corrected_start,
                "length": original.length + (start - correction.corrected_start),
            },
        )
        described |= gained
        applied.append(correction)
    return sheet.model_copy(update={"fields": tuple(fields), "corrections": (*sheet.corrections, *applied)})


def _range_correction_field_index(fields: list[RecordDesignField], sheet_name: str, start: int) -> int:
    """Find the field named by a range-start declaration or reject the declaration."""
    matches = [index for index, parsed in enumerate(fields) if parsed.offset == start]
    if not matches:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} declares a range-start correction at "
            f"{start} but no field begins there; the correction names nothing and the "
            "span it was written to close would stay open",
        )
    return matches[0]


def _range_correction_hole(
    sheet_name: str,
    start: int,
    correction: RecordDesignRangeStartCorrection,
    described: set[int],
) -> set[int]:
    """Return a correction's reclaimed positions after proving they are a hole."""
    gained = set(range(correction.corrected_start, start))
    if collides := sorted(gained & described):
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} range-start correction would extend a run "
            f"back over position(s) {collides} that a read field already describes; this "
            "correction kind reclaims a hole and must never displace declared data",
        )
    return gained
