"""Extract official AEAT record-design workbook sheets."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from pydantic import ValidationError

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet
    from xlrd.sheet import Sheet as XlrdSheet

from .errors import RegistryValidationError
from .record_design_layout_markers import split_record_terminator
from .record_design_pdf_rows import PdfRow
from .record_design_schema import (
    RecordDesignAuxiliaryEnvelopeHeader,
    RecordDesignAuxiliaryEnvelopeHeaderField,
    RecordDesignAuxiliaryEnvelopeHeaderRole,
    RecordDesignCompositeRelativeClosing,
    RecordDesignCorrection,
    RecordDesignField,
    RecordDesignFieldTypeCorrection,
    RecordDesignHeaderCellCorrection,
    RecordDesignNote,
    RecordDesignRelativeSuffixMarker,
    RecordDesignSheet,
    RecordDesignVariableBodyMarker,
    RecordDesignVariableEnvelope,
    RecordDesignVariableTotalMarker,
)
from .record_design_sources import EMPTY_CORRECTIONS, CorrectionIndex, TypeCorrectionIndex
from .record_design_workbook_headers import (
    WorkbookHeader,
    cell_at,
    field_description_text,
    find_header,
    find_xls_header,
    int_or_none,
    is_blank_row,
    optional_header_text,
    optional_text,
    ordinal_text,
    positive_integer_after,
    required_text,
    required_type_code,
    total_label_index,
)


@dataclass
class _WorkbookSheetRows:
    """Parsed workbook rows retained until their sheet-level shape is known."""

    fields: list[RecordDesignField] = field(default_factory=list)
    total_positions: int | None = None
    variable_bodies: list[RecordDesignVariableBodyMarker] = field(default_factory=list)
    relative_suffixes: list[RecordDesignRelativeSuffixMarker] = field(default_factory=list)
    variable_totals: list[RecordDesignVariableTotalMarker] = field(default_factory=list)
    variable_body_marker_rows: list[int] = field(default_factory=list)
    relative_suffix_marker_rows: list[int] = field(default_factory=list)
    variable_total_marker_rows: list[int] = field(default_factory=list)
    mixed_total_rows: list[int] = field(default_factory=list)
    corrections_applied: list[RecordDesignCorrection] = field(default_factory=list)
    #: ``Nota N`` definitions the sheet prints beneath its field table, keyed by
    #: the printed ordinal. A field's naming cell cites the ordinal; only the
    #: definition says what the citation MEANS, so the two must travel together.
    notes: dict[str, str] = field(default_factory=dict)


def extract_sheet(worksheet: Worksheet, corrections: CorrectionIndex = EMPTY_CORRECTIONS) -> RecordDesignSheet:
    header, header_correction = find_header(worksheet, corrections.header_corrections)
    return _extract_sheet_rows(
        worksheet.title,
        header,
        enumerate(
            worksheet.iter_rows(min_row=header.row_number + 1, values_only=True),
            start=header.row_number + 1,
        ),
        corrections,
        header_correction,
    )


def extract_xls_sheet(worksheet: XlrdSheet, corrections: CorrectionIndex = EMPTY_CORRECTIONS) -> RecordDesignSheet:
    header, header_correction = find_xls_header(worksheet, corrections.header_corrections)
    return _extract_sheet_rows(
        worksheet.name,
        header,
        ((rowx + 1, tuple(worksheet.row_values(rowx))) for rowx in range(header.row_number, worksheet.nrows)),
        corrections,
        header_correction,
    )


def _extract_sheet_rows(
    sheet_name: str,
    header: WorkbookHeader,
    rows: Iterator[tuple[int, tuple[object, ...]]],
    corrections: CorrectionIndex = EMPTY_CORRECTIONS,
    header_correction: RecordDesignHeaderCellCorrection | None = None,
) -> RecordDesignSheet:
    # AEAT Diseño workbooks occasionally carry surrounding whitespace on a
    # sheet tab (e.g. 'DP200026 '). The sheet name is the record-segment
    # identity that segment-qualified casillas and the calculation-
    # completeness derivation match against, so the raw tab whitespace
    # must not leak into that identity.
    sheet_name = sheet_name.strip()
    parsed_rows = _scan_sheet_rows(sheet_name, header, rows, corrections.type_corrections)
    if header_correction is not None:
        parsed_rows.corrections_applied.insert(0, header_correction)
    parsed_rows.fields[:] = fold_untagged_desglose_components(parsed_rows.fields)
    terminal_extent = _require_contiguous_field_geometry(sheet_name, parsed_rows.fields)
    if parsed_rows.total_positions is not None and terminal_extent != parsed_rows.total_positions:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} declares {parsed_rows.total_positions} total positions "
            f"but parsed fields fill {terminal_extent}",
        )
    variable_envelope = _variable_envelope(sheet_name, parsed_rows, terminal_extent)
    auxiliary_envelope_header = (
        None
        if variable_envelope is not None
        else _auxiliary_envelope_header(sheet_name, parsed_rows.fields, parsed_rows.total_positions, terminal_extent)
    )
    return RecordDesignSheet(
        name=sheet_name,
        fields=tuple(parsed_rows.fields),
        total_positions=parsed_rows.total_positions,
        variable_envelope=variable_envelope,
        auxiliary_envelope_header=auxiliary_envelope_header,
        corrections=tuple(parsed_rows.corrections_applied),
        notes=tuple(RecordDesignNote(ordinal=k, body=v) for k, v in sorted(parsed_rows.notes.items())),
    )


def _scan_sheet_rows(
    sheet_name: str,
    header: WorkbookHeader,
    rows: Iterator[tuple[int, tuple[object, ...]]],
    corrections: TypeCorrectionIndex | None = None,
) -> _WorkbookSheetRows:
    parsed_rows = _WorkbookSheetRows()
    trailing_blank_rows = 0
    for row_number, row in rows:
        values = tuple(row)
        if is_blank_row(values):
            trailing_blank_rows += 1
            if parsed_rows.fields and trailing_blank_rows >= 25:
                break
            continue
        trailing_blank_rows = 0
        if _consume_total_row(sheet_name, parsed_rows, row_number, values):
            continue
        if _consume_note_definition_row(parsed_rows, values):
            continue
        _consume_field_row(sheet_name, parsed_rows, header, row_number, values, corrections or {})
    return parsed_rows


#: A footnote definition row printed beneath a field table. AEAT marks these
#: three ways across its designs: "Nota 1 ...", "(**) ..." and -- where the
#: marker was simply not typed -- an unmarked body. The marker is captured
#: when present and left empty when it is not, never invented.
_NOTE_DEFINITION_RE = re.compile(
    r"^(?:Nota\s*(?P<ordinal>\d{1,2})|\((?P<symbol>[*]{1,3})\))[.:\s-]*(?P<body>.+)$",
    re.IGNORECASE,
)

#: A body that delegates its positions to the software house that produced
#: the file. Only a body matching this is worth retaining unmarked.
_DELEGATION_BODY_RE = re.compile(r"entidades\s+desarrolladoras|\(EEDD\)", re.IGNORECASE)


def _consume_note_definition_row(parsed_rows: _WorkbookSheetRows, values: tuple[object, ...]) -> bool:
    """Record a ``Nota N`` definition row, returning whether the row was one.

    AEAT prints these beneath the field table. They are not positions, so the
    field scanner would otherwise discard them -- and with them the only text
    that says what a field's ``(Nota N)`` citation means.
    """
    joined = " ".join(str(value).strip() for value in values if value is not None and str(value).strip())
    match = _NOTE_DEFINITION_RE.match(joined)
    if match is not None:
        body = match.group("body").strip()
        # A marker row carrying no prose is a LABEL, not a definition: several
        # designs print "Nota 1 :" with the sentence itself elsewhere. Recording
        # it would occupy the marker with punctuation and hide the real body.
        if sum(character.isalpha() for character in body) < 3:
            return True
        marker = match.group("ordinal") or match.group("symbol") or ""
        parsed_rows.notes.setdefault(marker, body)
        return True
    # An unmarked delegation body: AEAT prints the sentence without typing its
    # marker on some designs. Retained under the empty marker so a citation on
    # the same sheet can still resolve it; nothing else is kept unmarked, so a
    # stray sentence cannot become a note.
    if _DELEGATION_BODY_RE.search(joined):
        parsed_rows.notes.setdefault("", joined)
        return True
    return False


def _consume_total_row(
    sheet_name: str,
    parsed_rows: _WorkbookSheetRows,
    row_number: int,
    values: tuple[object, ...],
) -> bool:
    label_index = total_label_index(values)
    if label_index is None:
        return False
    row_total = positive_integer_after(values, label_index)
    has_variable_total = any(optional_text(candidate) == "Variable" for candidate in values[label_index + 1 :])
    if has_variable_total:
        parsed_rows.variable_total_marker_rows.append(row_number)
    if row_total is not None and has_variable_total:
        parsed_rows.mixed_total_rows.append(row_number)
    if row_total is not None:
        if parsed_rows.total_positions is not None:
            raise RegistryValidationError(f"record-design sheet {sheet_name!r} declares duplicate fixed totals")
        parsed_rows.total_positions = row_total
    elif has_variable_total:
        parsed_rows.variable_totals.append(
            RecordDesignVariableTotalMarker(
                sheet=sheet_name,
                row=row_number,
                label="total",
                length="Variable",
            ),
        )
    return True


def _consume_field_row(
    sheet_name: str,
    parsed_rows: _WorkbookSheetRows,
    header: WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    corrections: TypeCorrectionIndex,
) -> None:
    # ``RecordDesignField.ordinal`` is the printed LABEL (``ordinal_text``), never
    # an arithmetic value -- it is now representable verbatim, so there is no more
    # "printed but unreadable" case to refuse for it. The two MARKER rows below
    # (variable-body, relative-suffix) are unrelated types whose own ``ordinal``
    # field is still a plain sequential ``int``, so they keep reading the
    # int-or-None form.
    ordinal_int = int_or_none(cell_at(values, header.ordinal_index))
    ordinal_label = ordinal_text(cell_at(values, header.ordinal_index))
    offset = int_or_none(cell_at(values, header.offset_index))
    length = int_or_none(cell_at(values, header.length_index))
    raw_offset = optional_text(cell_at(values, header.offset_index))
    raw_length = optional_text(cell_at(values, header.length_index))
    if raw_length == "Variable":
        parsed_rows.variable_body_marker_rows.append(row_number)
        if ordinal_int is not None and offset is not None:
            parsed_rows.variable_bodies.append(
                _variable_body_marker(sheet_name, header, row_number, values, ordinal_int, offset),
            )
        return
    if raw_offset == "***":
        parsed_rows.relative_suffix_marker_rows.append(row_number)
        if ordinal_int is not None and length is not None:
            parsed_rows.relative_suffixes.append(
                _relative_suffix_marker(sheet_name, header, row_number, values, ordinal_int, length),
            )
        return
    if offset is None or length is None:
        return
    field, applied_correction = _record_design_field(
        sheet_name,
        header,
        row_number,
        values,
        ordinal_label,
        offset,
        length,
        corrections,
    )
    if applied_correction is not None:
        parsed_rows.corrections_applied.append(applied_correction)
    parent_index = _matching_component_parent_index(parsed_rows.fields, ordinal_label, offset, length)
    if parent_index is not None:
        parent = parsed_rows.fields[parent_index]
        parsed_rows.fields[parent_index] = parent.model_copy(update={"components": (*parent.components, field)})
        return
    parsed_rows.fields.append(field)


def _matching_component_parent_index(
    fields: list[RecordDesignField],
    ordinal_text: str | None,
    offset: int,
    length: int,
) -> int | None:
    """Return the index of the field ``ordinal_text``/``offset``/``length`` desglosa from.

    AEAT prints a component with a DOTTED ordinal (``19.1`` under parent ``19``),
    never a bare one -- Modelo 303's ``14bis`` has no dot and is a genuine peer,
    not a component of ``14``, and this is the discriminator that keeps them
    apart. The dotted integer prefix alone is not enough on its own -- an
    unrelated field elsewhere in the same sheet could coincidentally share an
    ordinal -- so BOTH conditions are required together: the immediately
    preceding field's ordinal is the exact dotted prefix, AND this row's byte
    span falls entirely inside that field's own already-declared span. Checked
    against only the immediately preceding field, matching every component's
    observed source position directly beneath its parent, never a scan of the
    whole sheet.
    """
    if ordinal_text is None or "." not in ordinal_text or not fields:
        return None
    prefix = ordinal_text.split(".", 1)[0]
    parent_index = len(fields) - 1
    parent = fields[parent_index]
    if parent.ordinal != prefix:
        return None
    if offset < parent.offset or offset + length > parent.offset + parent.length:
        return None
    return parent_index


def fold_untagged_desglose_components(fields: list[RecordDesignField]) -> list[RecordDesignField]:
    """Nest a desglose AEAT printed WITHOUT dotted ordinals under its parent.

    :func:`_matching_component_parent_index` nests on a dotted ordinal, which is
    the discriminator that correctly keeps Modelo 303's ``14bis`` a peer of
    ``14``. But AEAT does not always dot them: Modelo 184 prints ``12 @145+2
    "Este campo se subdivide en dos:"`` and then numbers its two sub-fields
    ``13`` and ``14``, as bare consecutive peers. Those rows arrive here as flat
    siblings, so ``components`` stays empty and every consumer sees the parent
    span as a position in its own right -- exactly what
    ``_required_positions`` documents as the wrong thing to ask a layout to
    write.

    Containment alone must NOT be the rule. Across the bundled corpus (1,702
    sheets, 133,753 fields) 51 bare-ordinal contained runs exist, and they are a
    mixed population: real desglose, and artefacts. Every one of Modelo 038's
    eleven comes from :func:`_extract_visual_chart_sheet`, whose merged
    chart-geometry fragments leave a small span loose inside a large one -- one
    of them reads ``OILOF )N.ICAUNITNOC( ED OREM.N``, mirrored text from a
    misread chart. Nesting those would reparent real fields under garbage.

    So the signal is EXACT TILING: the run must start on the parent's first
    byte, each row must resume precisely where the previous one ended, and the
    last must land on the parent's final byte. A printed row subdivided into
    parts is covered completely by those parts; a fragment sitting loose inside
    a larger one is not. That separates the corpus cleanly -- 35 runs tile and
    fold, 16 do not and are left exactly as they were, including all eleven of
    Modelo 038's.

    Folding only ever REMOVES the parent from the required-position set and
    never adds one, and the reserved-byte scan already walks
    ``(field, *field.components)``, so a ``RESERVADO`` sub-field keeps its
    protection after folding.
    """
    folded: list[RecordDesignField] = []
    index = 0
    while index < len(fields):
        parent = fields[index]
        run: list[RecordDesignField] = []
        cursor = index + 1
        while cursor < len(fields):
            candidate = fields[cursor]
            inside = (
                candidate.offset >= parent.offset
                and candidate.offset + candidate.length <= parent.offset + parent.length
                and (candidate.offset, candidate.length) != (parent.offset, parent.length)
            )
            if not inside:
                break
            run.append(candidate)
            cursor += 1
        if run and not parent.components and tiles_exactly(parent, run):
            folded.append(parent.model_copy(update={"components": tuple(run)}))
            index = cursor
            continue
        folded.append(parent)
        index += 1
    return folded


#: Spanish number words AEAT spells a subdivision count with, beside the digits.
_SUBDIVISION_COUNT_WORDS: Final = {
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}
#: AEAT stating how many sub-fields a printed row divides into -- "Este campo se
#: subdivide en cuatro:", "se subdivide en otros dos:", "se desglosa en 3". Read
#: from description and content together, because AEAT puts it in either.
_DECLARED_SUBDIVISION: Final = re.compile(
    r"se\s+(?:subdivide|desglosa|divide)\s+en\s+(?:otros\s+|los\s+)?"
    rf"(\d+|{'|'.join(_SUBDIVISION_COUNT_WORDS)})\b",
    re.IGNORECASE,
)


def declared_subdivision_count(field: RecordDesignField) -> int | None:
    """Return how many sub-fields ``field`` says it divides into, else ``None``."""
    text = f"{field.description or ''} {field.content or ''}"
    normalised = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    match = _DECLARED_SUBDIVISION.search(normalised)
    if match is None:
        return None
    token = match.group(1).lower()
    return int(token) if token.isdigit() else _SUBDIVISION_COUNT_WORDS[token]


def solve_declared_desglose_holes(
    *,
    parent: RecordDesignField,
    covered: set[int],
    by_offset: Mapping[int, list[PdfRow]],
    wanted: int,
) -> list[PdfRow] | None:
    """Return the ``wanted`` staged candidates that exactly fill ``parent``'s holes.

    A search rather than a walk, because AEAT nests these declarations and
    stages overlapping candidates at one offset: Modelo 184 holds both
    ``151-155 PORCENTAJE...`` and the ``151- 153 ENTERO`` inside it, and only the
    first yields the declared count. Taking whichever was read last picks the
    wrong one silently, so every candidate at a hole's first byte is tried and
    the solution must consume every hole byte in exactly ``wanted`` fields.

    Returns ``None`` unless the fill is unambiguous in that arithmetic sense.
    The search is bounded by the parent's own span, which is a printed row.
    """
    end = parent.offset + parent.length

    def walk(position: int, remaining: int) -> list[PdfRow] | None:
        while position < end and position in covered:
            position += 1
        if position >= end:
            return [] if remaining == 0 else None
        if remaining == 0:
            return None
        for candidate in by_offset.get(position, ()):
            stop = position + candidate.length
            if stop > end or any(byte in covered for byte in range(position, stop)):
                continue
            tail = walk(stop, remaining - 1)
            if tail is not None:
                return [candidate, *tail]
        return None

    return walk(parent.offset, wanted)


def tiles_exactly(parent: RecordDesignField, run: list[RecordDesignField]) -> bool:
    """Return whether ``run`` covers ``parent``'s span end to end with no gap."""
    expected = parent.offset
    for component in run:
        if component.offset != expected:
            return False
        expected = component.offset + component.length
    return expected == parent.offset + parent.length


def _variable_body_marker(
    sheet_name: str,
    header: WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: int,
    offset: int,
) -> RecordDesignVariableBodyMarker:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    return RecordDesignVariableBodyMarker(
        sheet=sheet_name,
        row=row_number,
        ordinal=ordinal,
        offset=offset,
        length="Variable",
        type_code=required_text(cell_at(values, header.type_index), sheet_name, row_number, "type"),
        description=description,
        validation=validation,
        content=content,
    )


def _relative_suffix_marker(
    sheet_name: str,
    header: WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: int,
    length: int,
) -> RecordDesignRelativeSuffixMarker:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    return RecordDesignRelativeSuffixMarker(
        sheet=sheet_name,
        row=row_number,
        ordinal=ordinal,
        offset="***",
        length=length,
        type_code=required_text(cell_at(values, header.type_index), sheet_name, row_number, "type"),
        description=description,
        validation=validation,
        content=content,
    )


def _record_design_field(
    sheet_name: str,
    header: WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: str | None,
    offset: int,
    length: int,
    corrections: TypeCorrectionIndex,
) -> tuple[RecordDesignField, RecordDesignFieldTypeCorrection | None]:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    type_code, applied_correction = required_type_code(
        cell_at(values, header.type_index),
        sheet_name,
        row_number,
        corrections,
    )
    return (
        RecordDesignField(
            sheet=sheet_name,
            row=row_number,
            ordinal=ordinal,
            offset=offset,
            length=length,
            type_code=type_code,
            complementary=optional_header_text(values, header.complementary_index),
            description=description,
            validation=validation,
            content=content,
        ),
        applied_correction,
    )


def _field_texts(
    sheet_name: str,
    header: WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
) -> tuple[str | None, str | None, str]:
    validation = optional_header_text(values, header.validation_index)
    content = optional_header_text(values, header.content_index)
    return (
        validation,
        content,
        field_description_text(
            values,
            header=header,
            content=content,
            sheet=sheet_name,
            row=row_number,
        ),
    )


def _variable_envelope(
    sheet_name: str,
    parsed_rows: _WorkbookSheetRows,
    terminal_extent: int | None,
) -> RecordDesignVariableEnvelope | None:
    if not (parsed_rows.variable_body_marker_rows or parsed_rows.mixed_total_rows):
        return None
    if parsed_rows.mixed_total_rows:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} mixes fixed and variable totals "
            f"in row {parsed_rows.mixed_total_rows[0]}",
        )
    _require_valid_variable_envelope_markers(sheet_name, parsed_rows)
    variable_body = parsed_rows.variable_bodies[0]
    closing_suffixes, terminator = split_record_terminator(parsed_rows.relative_suffixes)
    closing = _relative_closing(sheet_name, closing_suffixes)
    closing_parts = _relative_closing_parts(closing)
    variable_total = parsed_rows.variable_totals[0]
    if parsed_rows.total_positions is not None or terminal_extent is None:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} mixes fixed-total and variable-envelope geometry",
        )
    if variable_body.offset != terminal_extent + 1:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} variable body starts at {variable_body.offset} "
            f"after fixed prefix extent {terminal_extent}",
        )
    _require_ordered_variable_envelope(
        sheet_name,
        parsed_rows.fields,
        variable_body,
        closing_parts,
        variable_total,
    )
    _require_terminator_closes_the_record(sheet_name, closing_parts, terminator)
    return RecordDesignVariableEnvelope(
        name=sheet_name,
        prefix_fields=tuple(parsed_rows.fields),
        prefix_extent=terminal_extent,
        body=variable_body,
        closing=closing,
        terminator=terminator,
        variable_total=variable_total,
    )


def _auxiliary_envelope_header(
    sheet_name: str,
    fields: list[RecordDesignField],
    declared_total: int | None,
    terminal_extent: int | None,
) -> RecordDesignAuxiliaryEnvelopeHeader | None:
    """Recognise only the exact total-less Modelo 390 page-zero source shape.

    Fixed sheets otherwise remain unchanged. A no-total 328-byte sheet is not
    permitted to acquire a fixed-record total from terminal extent; only an
    exact thirteen-field M390 header receives this distinct classification.
    """
    if (
        declared_total is not None
        or terminal_extent != 328
        or len(fields) != len(RecordDesignAuxiliaryEnvelopeHeaderRole)
    ):
        return None
    try:
        return RecordDesignAuxiliaryEnvelopeHeader(
            sheet=sheet_name,
            record_identity=sheet_name,
            fields=tuple(
                RecordDesignAuxiliaryEnvelopeHeaderField(role=role, field=field)
                for role, field in zip(RecordDesignAuxiliaryEnvelopeHeaderRole, fields, strict=True)
            ),
            emitted_extent=terminal_extent,
        )
    except ValueError:
        return None


def _require_valid_variable_envelope_markers(sheet_name: str, parsed_rows: _WorkbookSheetRows) -> None:
    malformed_marker_rows = (
        set(parsed_rows.variable_body_marker_rows) - {body.row for body in parsed_rows.variable_bodies}
    ) | (set(parsed_rows.relative_suffix_marker_rows) - {suffix.row for suffix in parsed_rows.relative_suffixes})
    if malformed_marker_rows:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has malformed variable-envelope marker "
            f"in row {min(malformed_marker_rows)}",
        )
    if len(parsed_rows.variable_bodies) > 1:
        raise RegistryValidationError(f"record-design sheet {sheet_name!r} declares duplicate variable-body markers")
    if len(parsed_rows.variable_totals) > 1:
        raise RegistryValidationError(f"record-design sheet {sheet_name!r} declares duplicate variable totals")
    if not parsed_rows.variable_bodies or not parsed_rows.relative_suffixes or not parsed_rows.variable_totals:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has an incomplete variable-envelope composition"
        )


def _require_ordered_variable_envelope(
    sheet_name: str,
    fields: list[RecordDesignField],
    variable_body: RecordDesignVariableBodyMarker,
    closing_parts: tuple[RecordDesignRelativeSuffixMarker, ...],
    variable_total: RecordDesignVariableTotalMarker,
) -> None:
    first_closing_part = closing_parts[0]
    last_closing_part = closing_parts[-1]
    # POSITION IS THE ORDERING AUTHORITY, NOT THE ORDINAL.
    #
    # This checked composition order twice, once on source row and once on ordinal,
    # and the ordinal half asserted nothing the row half did not: both ask whether
    # the body sits after the fixed prefix and before the closing. Where the two
    # could disagree, the ordinal is the one that would be wrong, because AEAT's
    # ordinal is a PRINTED LABEL rather than an arithmetic value -- it publishes
    # ``14bis`` to insert a field between 14 and 15 without renumbering, exactly as
    # the law numbers an inserted article. Comparing labels arithmetically assumes a
    # density AEAT never promised.
    #
    # The bytes order themselves and are checked as such elsewhere: the prefix must
    # be contiguous from offset 1, and the variable body must begin at
    # ``prefix_extent + 1``. Those are the real geometric assertions; this one is
    # about which SOURCE ROWS compose the envelope, so it reads rows.
    ordered_rows = max(item.row for item in fields) < variable_body.row < first_closing_part.row
    ordered_rows = ordered_rows and first_closing_part.row <= last_closing_part.row < variable_total.row
    if not ordered_rows:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has misordered variable-envelope composition markers",
        )


#: How AEAT NAMES the physical end-of-record row, in the wordings it uses across
#: both workbook and PDF designs. ONE definition with two consumers: the workbook
#: closing splitter below, and the PDF compact-row recogniser further down which
#: composes this into its own line pattern.
#:
#: Two independent notions of "what a CRLF row is" is how the two parsers came to
#: disagree about one domain fact -- the PDF path has recognised the terminator
#: since it was written, while the workbook path refused thirty designs across
#: eight modelos for declaring one.


def _relative_closing(
    sheet_name: str,
    suffixes: list[RecordDesignRelativeSuffixMarker],
) -> RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing:
    if len(suffixes) == 1 and suffixes[0].length == 18:
        return suffixes[0]
    if len(suffixes) != 6:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has an incomplete or ambiguous relative closing",
        )
    try:
        return RecordDesignCompositeRelativeClosing(
            tag_prefix=suffixes[0],
            modelo=suffixes[1],
            discriminant=suffixes[2],
            filing_year=suffixes[3],
            period=suffixes[4],
            tag_suffix=suffixes[5],
        )
    except ValidationError as exc:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} has a malformed composite relative closing: {exc}",
        ) from exc


def _require_terminator_closes_the_record(
    sheet_name: str,
    closing_parts: tuple[RecordDesignRelativeSuffixMarker, ...],
    terminator: RecordDesignRelativeSuffixMarker | None,
) -> None:
    """Refuse a terminator that does not sit last in the record.

    Without this the split would accept a two-byte line-terminator row appearing
    anywhere among the closing parts and quietly reorder the record's tail. The
    terminator is the LAST thing in a record by definition, so a design declaring
    it earlier is either malformed or is something this parser has misread, and
    both deserve a refusal rather than a rearrangement.
    """
    if terminator is None:
        return
    last_part = closing_parts[-1]
    # Reads the SOURCE ROW only. An earlier version of this also compared ordinals,
    # which was the same mistake the envelope-order check carried: AEAT's ordinal is
    # a printed label, so ordering by it assumes a density the authority never
    # promised. It was harmless while every ordinal happened to be an integer and
    # would have failed the moment a ``bis`` label reached this comparison.
    if terminator.row <= last_part.row:
        raise RegistryValidationError(
            f"record-design sheet {sheet_name!r} declares an end-of-record terminator at row "
            f"{terminator.row} which does not follow its closing identifier at row "
            f"{last_part.row}; a terminator that is not last is not a terminator",
        )


def _relative_closing_parts(
    closing: RecordDesignRelativeSuffixMarker | RecordDesignCompositeRelativeClosing,
) -> tuple[RecordDesignRelativeSuffixMarker, ...]:
    if isinstance(closing, RecordDesignCompositeRelativeClosing):
        return closing.parts
    return (closing,)


def _require_contiguous_field_geometry(
    sheet_name: str,
    fields: list[RecordDesignField],
) -> int | None:
    """Return the exact terminal extent after proving source-order geometry."""
    expected_offset = 1
    for parsed_field in fields:
        if parsed_field.offset != expected_offset:
            defect = "an overlap" if parsed_field.offset < expected_offset else "a gap"
            raise RegistryValidationError(
                f"record-design sheet {sheet_name!r} has {defect} before field at row {parsed_field.row}: "
                f"expected offset {expected_offset}, got {parsed_field.offset}",
            )
        expected_offset = parsed_field.offset + parsed_field.length
    return expected_offset - 1 if fields else None
