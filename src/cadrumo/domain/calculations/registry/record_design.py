"""Read-only extraction of official AEAT record-design rows.

Parses official AEAT record-design workbooks (PDF or XLS/XLSX) and derives
coverage casillas from a :class:`ModeloRevision` so that the extracted layout
can be compared against the registry declarations.
"""

from __future__ import annotations

import json
import re
import unicodedata
import warnings
from collections.abc import Generator, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import ConfigDict, TypeAdapter, ValidationError

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these never need to exist at runtime. The parser
    # backends themselves (openpyxl, pdfplumber, pypdfium2, xlrd) are among the
    # heaviest third-party imports in the tree and are deferred into the
    # extraction functions that actually call them -- importing the registry
    # must not pay for a PDF/XLS parser stack no calculation touches.
    from openpyxl.worksheet.worksheet import Worksheet
    from pdfplumber.page import Page
    from xlrd.sheet import Sheet as XlrdSheet

from ....core.external_constants import PDF_EXTENSION as _PDF_EXTENSION
from ....core.external_constants import UTF_8_ENCODING
from ....core.external_constants import XLS_EXTENSION as _XLS_EXTENSION
from ....core.external_constants import XLSM_EXTENSION as _XLSM_EXTENSION
from ....core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from ....core.logging import get_logger
from ....core.paths import path_stat_fingerprint
from ....core.tabular import coerce_cell_text
from .record_design_coverage import (
    DerivedDisenoCasilla,
    DisenoCoverageReport,
    build_diseno_coverage_report,
    calculation_closure_casilla_ids,
    calculation_closure_legal_refs,
    calculation_closure_record_design_metadata,
    derive_calculation_completeness_casillas,
    derive_diseno_coverage_casillas,
)
from .record_design_schema import (
    AUXILIARY_ENVELOPE_HEADER_CONTENT,
    AUXILIARY_ENVELOPE_HEADER_LENGTHS,
    AUXILIARY_ENVELOPE_HEADER_ORDINALS,
    AUXILIARY_ENVELOPE_HEADER_ROWS,
    RecordDesignAuxiliaryEnvelopeHeader,
    RecordDesignAuxiliaryEnvelopeHeaderField,
    RecordDesignAuxiliaryEnvelopeHeaderRole,
    RecordDesignCompositeRelativeClosing,
    RecordDesignCorrection,
    RecordDesignExtraction,
    RecordDesignField,
    RecordDesignFieldTypeCorrection,
    RecordDesignHeaderCellCorrection,
    RecordDesignNote,
    RecordDesignRelativeSuffixMarker,
    RecordDesignSheet,
    RecordDesignSinglePositionCorrection,
    RecordDesignSkippedSheet,
    RecordDesignVariableBodyMarker,
    RecordDesignVariableEnvelope,
    RecordDesignVariableTotalMarker,
    validate_auxiliary_envelope_header_contents,
)
from .errors import RegistryValidationError

_log = get_logger(__name__)

_OPENPYXL_HEADER_FOOTER_WARNING = "Cannot parse header or footer so it will be ignored"
_OPENPYXL_PRINT_AREA_WARNING = r"Print area cannot be set to Defined name: .*"
_NUMERIC_TUPLE_ADAPTER: TypeAdapter[tuple[int | float, ...]] = TypeAdapter(
    tuple[int | float, ...], config=ConfigDict(strict=True)
)


@dataclass(frozen=True)
class _WorkbookHeader:
    row_number: int
    ordinal_index: int
    offset_index: int
    length_index: int
    type_index: int
    complementary_index: int | None
    description_index: int
    validation_index: int | None
    content_index: int | None


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


type _TypeCorrectionIndex = Mapping[tuple[str, int], RecordDesignFieldTypeCorrection]
type _HeaderCorrectionIndex = Mapping[tuple[str, int, str], RecordDesignHeaderCellCorrection]
type _SinglePositionCorrectionIndex = Mapping[tuple[str, int], RecordDesignSinglePositionCorrection]

_CORRECTION_SUFFIX: Final[str] = ".record-design-correction.json"
_CORRECTION_ADAPTER: Final[TypeAdapter[RecordDesignCorrection]] = TypeAdapter(RecordDesignCorrection)


@dataclass(frozen=True)
class _CorrectionIndex:
    """One binary's declared corrections, split by the row they address.

    ``type_corrections`` keys on ``(sheet, source_row)`` -- one data row.
    ``header_corrections`` keys on ``(sheet, header_row, column_role)`` -- one
    header column, since a header row's blank cell is looked up by ROLE
    (``"length"``) at probe time, not by a data row number.
    ``single_position_corrections`` keys on ``(sheet, position)`` -- one PDF row
    that was never read, so it has no source row to be keyed by.
    """

    type_corrections: _TypeCorrectionIndex
    header_corrections: _HeaderCorrectionIndex
    single_position_corrections: _SinglePositionCorrectionIndex = field(default_factory=dict)


_EMPTY_CORRECTIONS: Final[_CorrectionIndex] = _CorrectionIndex(
    type_corrections={},
    header_corrections={},
    single_position_corrections={},
)


def _load_corrections(source_path: Path) -> _CorrectionIndex:
    """Load a hand-authored, per-binary sidecar declaring record-design corrections.

    Colocated with the exact source binary it corrects, named
    ``<binary-name>.record-design-correction.json`` -- a distinct suffix from
    the parser's own generated ``.extracted.json``/``.extracted.md`` cache, so
    a hand-authored grounding declaration is never confused with, or
    overwritten by, machine output. Absent for the overwhelming majority of
    bundled binaries, which read as AEAT published them; this returns empty
    indexes for those, so the parser's behaviour is unchanged unless a sidecar
    is deliberately authored. One file, one discriminated ``corrections`` list
    -- a field-type correction and a header-cell correction may both appear in
    it, per :data:`RecordDesignCorrection`.
    """
    sidecar_path = source_path.with_name(source_path.name + _CORRECTION_SUFFIX)
    if not sidecar_path.is_file():
        return _EMPTY_CORRECTIONS
    payload = json.loads(sidecar_path.read_text(encoding=UTF_8_ENCODING))
    entries = payload.get("corrections") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise RegistryValidationError(f"{sidecar_path}: correction sidecar must declare a 'corrections' list")
    type_corrections: dict[tuple[str, int], RecordDesignFieldTypeCorrection] = {}
    header_corrections: dict[tuple[str, int, str], RecordDesignHeaderCellCorrection] = {}
    single_position_corrections: dict[tuple[str, int], RecordDesignSinglePositionCorrection] = {}
    for entry in entries:
        # ``strict=False`` here only: JSON has no tuple literal, so the sidecar's
        # ``editions_read`` array arrives as a ``list`` and needs the ordinary
        # list-to-tuple coercion. Every field's own type is still checked --
        # this does not relax ``min_length``, blank-string, discriminator, or shape checks.
        correction = _CORRECTION_ADAPTER.validate_python(entry, strict=False)
        if isinstance(correction, RecordDesignFieldTypeCorrection):
            type_key = (correction.sheet, correction.source_row)
            if type_key in type_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate type correction for sheet {correction.sheet!r} "
                    f"row {correction.source_row}",
                )
            type_corrections[type_key] = correction
        elif isinstance(correction, RecordDesignSinglePositionCorrection):
            position_key = (correction.sheet, correction.position)
            if position_key in single_position_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate single-position correction for sheet "
                    f"{correction.sheet!r} position {correction.position}",
                )
            single_position_corrections[position_key] = correction
        else:
            header_key = (correction.sheet, correction.header_row, correction.column_role)
            if header_key in header_corrections:
                raise RegistryValidationError(
                    f"{sidecar_path}: duplicate header correction for sheet {correction.sheet!r} "
                    f"row {correction.header_row} role {correction.column_role!r}",
                )
            header_corrections[header_key] = correction
    return _CorrectionIndex(
        type_corrections=type_corrections,
        header_corrections=header_corrections,
        single_position_corrections=single_position_corrections,
    )


_DECLARED_NON_RECORD_SHEETS_FILENAME: Final[str] = "declared-non-record-sheets.json"


def _load_declared_non_record_sheet_reasons(source_path: Path) -> Mapping[str, str]:
    """Load one modelo's declared, sourced reasons for sheets that are never records.

    Lives once per MODELO directory (sibling to that modelo's own
    ``manifest.json``), not per binary: a legend or lookup tab AEAT republishes
    unchanged across several editions is one judgement, not one per file. This
    never turns a skip into a read -- the sheet stays in
    :attr:`RecordDesignExtraction.skipped` exactly as before -- it only
    replaces the parser's own generic header-probe failure message with the
    grounded reason a reviewer recorded after opening the design. The
    extractor cannot itself tell a lookup tab apart from a dropped record
    body, so that judgement is a registry act, never inferred here.
    """
    modelo_root = source_path.parent.parent
    declaration_path = modelo_root / _DECLARED_NON_RECORD_SHEETS_FILENAME
    if not declaration_path.is_file():
        return {}
    payload = json.loads(declaration_path.read_text(encoding=UTF_8_ENCODING))
    entries = payload.get("declared_non_record_sheets") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise RegistryValidationError(
            f"{declaration_path}: must declare a 'declared_non_record_sheets' list",
        )
    reasons: dict[str, str] = {}
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("sheet"), str)
            or not isinstance(
                entry.get("reason"),
                str,
            )
        ):
            raise RegistryValidationError(
                f"{declaration_path}: every entry needs a string 'sheet' and a string 'reason'",
            )
        sheet = entry["sheet"].strip()
        reason = entry["reason"].strip()
        if not sheet or not reason:
            raise RegistryValidationError(f"{declaration_path}: 'sheet' and 'reason' must be non-blank")
        if sheet in reasons:
            raise RegistryValidationError(f"{declaration_path}: duplicate declaration for sheet {sheet!r}")
        reasons[sheet] = reason
    return reasons


def extract_record_design(path: Path) -> RecordDesignExtraction:
    """Return one official record-design source's parsed sheets AND what it could not read.

    Returns:
        The :class:`RecordDesignExtraction` for the source, which names both the
        sheets that parsed and any the extractor had to skip.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design source not found: {path}")
    return _extract_record_design_cached(*path_stat_fingerprint(resolved))


@lru_cache(maxsize=256)
def _extract_record_design_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix == _PDF_EXTENSION:
        return extract_record_design_pdf(source_path)
    if suffix in {_XLSX_EXTENSION, _XLSM_EXTENSION}:
        return extract_record_design_workbook(source_path)
    if suffix == _XLS_EXTENSION:
        return extract_record_design_xls_workbook(source_path)
    raise RegistryValidationError(f"unsupported record-design source extension: {source_path.suffix}")


def _extraction(
    source_path: Path,
    sheets: list[RecordDesignSheet],
    skipped: list[RecordDesignSkippedSheet],
) -> RecordDesignExtraction:
    """Assemble one source's result, refusing only when NOTHING could be read.

    A source where every sheet failed is still a hard error -- there is no design
    there to hand back. A source where SOME sheets failed is a partial read, and
    it is returned rather than raised so a caller can decide: refusing outright
    would drop Modelo 232, whose ``TABLAS`` tab is a legitimate lookup table and
    not a record at all. The extractor cannot tell a lookup tab from a lost
    record body, so it reports both and adjudicates neither.
    """
    if not sheets:
        detail = "; ".join(f"{item.name!r}: {item.reason}" for item in skipped) if skipped else "none"
        raise RegistryValidationError(
            f"{source_path}: no record-design sheets found; skipped sheets: {detail}",
        )
    return RecordDesignExtraction(source=str(source_path), sheets=tuple(sheets), skipped=tuple(skipped))


def extract_record_design_workbook(path: Path) -> RecordDesignExtraction:
    """Return the :class:`RecordDesignExtraction` workbook ``path`` describes."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design workbook not found: {path}")
    return _extract_record_design_workbook_cached(*path_stat_fingerprint(resolved))


def extract_record_design_xls_workbook(path: Path) -> RecordDesignExtraction:
    """Return a legacy binary XLS workbook's parsed sheets AND any it could not read.

    Returns:
        The :class:`RecordDesignExtraction` for the workbook.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design XLS workbook not found: {path}")
    return _extract_record_design_xls_workbook_cached(*path_stat_fingerprint(resolved))


@lru_cache(maxsize=256)
def _extract_record_design_workbook_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    from openpyxl import load_workbook

    source_path = Path(path)
    corrections = _load_corrections(source_path)
    declared_skip_reasons = _load_declared_non_record_sheet_reasons(source_path)
    with _ignore_openpyxl_header_footer_metadata_warnings():
        workbook = load_workbook(source_path, read_only=True, data_only=True)
        try:
            sheets: list[RecordDesignSheet] = []
            skipped: list[RecordDesignSkippedSheet] = []
            for worksheet in workbook.worksheets:
                try:
                    sheets.append(_extract_sheet(worksheet, corrections))
                except ValueError as exc:
                    if "has no record-design header" not in str(exc):
                        raise
                    sheet_title = worksheet.title.strip()
                    declared = declared_skip_reasons.get(sheet_title)
                    skipped.append(
                        RecordDesignSkippedSheet(
                            name=sheet_title,
                            reason=declared if declared is not None else str(exc),
                            declared_non_record=declared is not None,
                        ),
                    )
            return _extraction(source_path, sheets, skipped)
        finally:
            workbook.close()


@lru_cache(maxsize=128)
def _extract_record_design_xls_workbook_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    import xlrd

    source_path = Path(path)
    corrections = _load_corrections(source_path)
    declared_skip_reasons = _load_declared_non_record_sheet_reasons(source_path)
    workbook = xlrd.open_workbook(str(source_path), on_demand=True)
    try:
        sheets: list[RecordDesignSheet] = []
        skipped: list[RecordDesignSkippedSheet] = []
        for sheet_name in workbook.sheet_names():
            worksheet = workbook.sheet_by_name(sheet_name)
            try:
                sheets.append(_extract_xls_sheet(worksheet, corrections))
            except ValueError as exc:
                if "has no record-design header" not in str(exc):
                    raise
                stripped_name = sheet_name.strip()
                declared = declared_skip_reasons.get(stripped_name)
                skipped.append(
                    RecordDesignSkippedSheet(
                        name=stripped_name,
                        reason=declared if declared is not None else str(exc),
                        declared_non_record=declared is not None,
                    ),
                )
        return _extraction(source_path, sheets, skipped)
    finally:
        workbook.release_resources()


@contextmanager
def _ignore_openpyxl_header_footer_metadata_warnings() -> Generator[None]:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=_OPENPYXL_HEADER_FOOTER_WARNING,
            category=UserWarning,
            module=r"openpyxl\.worksheet\.header_footer",
        )
        warnings.filterwarnings(
            "ignore",
            message=_OPENPYXL_PRINT_AREA_WARNING,
            category=UserWarning,
            module=r"openpyxl\.reader\.workbook",
        )
        yield


def extract_record_design_pdf(path: Path) -> RecordDesignExtraction:
    """Return the :class:`RecordDesignExtraction` read from an official AEAT PDF."""
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"record-design PDF not found: {path}")
    return _extract_record_design_pdf_cached(*path_stat_fingerprint(resolved))


#: The two halves of a row whose columns were emitted out of order. The first
#: line carries LENGTH, TYPE and the description; the second carries the ORDINAL
#: and POSITION, optionally followed by the casilla reference that belongs to
#: the description's tail.
_REVERSED_ROW_TAIL_RE = re.compile(
    r"^\s*(?P<length>\d+)\s+(?P<type>An|Num|Tit|N|A)\.?\s+(?P<description>\S.*)$",
    re.IGNORECASE,
)
_REVERSED_ROW_HEAD_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s*(?P<tail>\[[^\]]*\]\s*)?$",
)


#: A head half carrying description text after its position: ``79 1236 (2 a 6)
#: [021]``. Admitted only under the continuity constraint below, never on the
#: pattern alone -- prose beginning with two numbers is common.
_REVERSED_ROW_HEAD_WITH_TAIL_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<trailing>\S.*)$",
)


def _continues(previous: _PdfRow | None, ordinal: str, offset: int) -> bool:
    """Whether this ordinal and position resume exactly where ``previous`` ended.

    The same over-determination the glued-ordinal split relies on: the ordinal
    must follow by one AND the position must resume at the previous row's end.
    Two independent facts, from a row already read, that must agree -- which is
    what lets a head half be admitted when description text has bled onto its
    line and the pattern alone would match prose.
    """
    if previous is None or previous.ordinal is None or not previous.ordinal.isdigit():
        return False
    return ordinal == str(int(previous.ordinal) + 1) and offset == previous.offset + previous.length


def _row_identities_by_record(lines: tuple[str, ...]) -> list[frozenset[tuple[str, int]]]:
    """For each line, the row identities its OWN record already states intact.

    Scoped per record, and that scoping is the whole point. The duplicate guard
    exists to stop a split row being joined when the design also emits it whole,
    which is a statement about one record -- but every record restarts at
    ordinal 1 position 1, so low identities recur throughout a design. Measured
    on modelo 200's 2010 edition, ``(30, 419)`` is stated intact by 28 different
    records and ``(7, 28)`` by 34. A design-wide guard therefore refused almost
    every legitimate join, and did so silently, because a refused join is
    indistinguishable from no join at all.

    Record boundaries come from the same geometry the parser uses: a row
    declaring position 1 begins a record, because a fixed-width record is
    contiguous from its first byte.
    """
    boundaries: list[int] = []
    identities: list[set[tuple[str, int]]] = []
    current: set[tuple[str, int]] = set()
    for number, line in enumerate(lines, start=1):
        parsed = _parse_pdf_row(line, number)
        if parsed is not None and parsed.offset == 1 and current:
            identities.append(current)
            boundaries.append(number - 1)
            current = set()
        if parsed is not None and parsed.ordinal is not None:
            current.add((parsed.ordinal, parsed.offset))
    identities.append(current)

    frozen = [frozenset(entry) for entry in identities]
    per_line: list[frozenset[tuple[str, int]]] = []
    segment = 0
    for index in range(len(lines)):
        while segment < len(boundaries) and index >= boundaries[segment]:
            segment += 1
        per_line.append(frozen[segment])
    return per_line


def _undouble_struck_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Repair a row whose glyphs the PDF text layer emitted twice.

    Modelo 390's 2015 edition double-strikes some rows: ``4422 662255 1177 NN
    55.. OOppeerraacciioonneess`` is ``42 625 17 N 5. Operaciones``, every
    character duplicated while the separating spaces stay single. Eight rows
    arrive that way and each one is a position the record otherwise reports as
    dropped.

    The repair is self-verifying, which is what keeps it from being a guess: a
    line is rewritten ONLY when it does not parse as a row, every token it is
    built from is an exact pairwise repetition, and the de-doubled result does
    parse. A line failing any of the three is returned untouched. Nothing here
    reasons about what the row ought to say -- the doubling either undoes
    cleanly into a row or it does not.

    Tokens that are not doubled are left alone rather than making the whole line
    ineligible, because AEAT's own text mixes them: a description can carry a
    single-struck fragment beside doubled ones.
    """
    repaired: list[str] = []
    for number, line in enumerate(lines, start=1):
        if _parse_pdf_row(line, number) is not None:
            repaired.append(line)
            continue
        candidate = " ".join(
            token[::2]
            if len(token) >= 2
            and len(token) % 2 == 0
            and all(token[i] == token[i + 1] for i in range(0, len(token), 2))
            else token
            for token in line.split(" ")
        )
        repaired.append(candidate if candidate != line and _parse_pdf_row(candidate, number) is not None else line)
    return tuple(repaired)


def _rejoin_reversed_column_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Reassemble a row whose PDF columns were emitted in the wrong order.

    Modelo 200's older editions emit some rows as two lines with the columns
    swapped -- ``17 Num Ret. e ingr. a cuenta ... `` followed by ``30 419
    [596]`` -- where AEAT's row is ``30 419 17 Num Ret. e ingr. a cuenta ...
    [596]``. Every one of those positions is otherwise unread, and they are the
    bulk of modelo 200's reported damage: 592 such pairs across six editions.

    Neither half is a row on its own, and that is the evidence. The first line
    has a length and a naturaleza but declares no position, so it can state
    nothing about the record's extent; the second names an ordinal and a
    position but no width. Only together do they make a field, and each supplies
    exactly the columns the other lacks -- nothing here is inferred from
    neighbouring rows or from a sequence.

    A wrong pairing cannot pass quietly: it would place a field at a position
    some other row already covers, and :func:`contiguity_failure` refuses
    partial overlap and any extent past the declared total. The join is
    therefore checked by the same arithmetic that reports the holes it closes.
    """
    # A design may emit the SAME row both split and intact. Joining the split
    # copy would then declare a position the intact row already declares --
    # harmless to contiguity, which permits containment, and therefore silent:
    # modelo 200's 2012-2014 editions each gained twelve duplicate importe
    # fields that way, in records that had no holes at all. So the intact rows
    # are collected first and a pair claiming one of their (ordinal, position)
    # identities is left alone.
    claimed = _row_identities_by_record(lines)
    joined: list[str] = []
    index = 0
    previous_row: _PdfRow | None = None
    while index < len(lines):
        line = lines[index]
        parsed_here = _parse_pdf_row(line, index + 1)
        if parsed_here is not None:
            previous_row = parsed_here
        if index + 1 < len(lines):
            # The two halves arrive in either order. Swapped -- length, type and
            # description first -- is how modelo 200's 2010 editions emit some
            # rows; in natural order the row simply breaks after its position,
            # leaving ``7 28`` above ``17 Num Deducc...``. Both are one row split
            # over two lines, and neither half is a row alone, so the same
            # evidence and the same duplicate guard apply to each.
            forward_head = _REVERSED_ROW_HEAD_RE.match(line)
            forward_tail = _REVERSED_ROW_TAIL_RE.match(lines[index + 1])
            if (
                forward_head is not None
                and forward_tail is not None
                and _parse_pdf_row(line, index + 1) is None
                and _parse_pdf_row(lines[index + 1], index + 2) is None
                and (forward_head.group("ordinal"), int(forward_head.group("offset"))) not in claimed[index]
            ):
                casilla = (forward_head.group("tail") or "").strip()
                description = forward_tail.group("description").rstrip()
                joined.append(
                    f"{forward_head.group('ordinal')} {forward_head.group('offset')} "
                    f"{forward_tail.group('length')} {forward_tail.group('type')} "
                    f"{description}{' ' + casilla if casilla else ''}",
                )
                index += 2
                continue
            # The head may carry description text bled onto its line. That
            # pattern alone matches prose, so it is admitted only when the
            # ordinal and position resume exactly where the last read row ended.
            tail = _REVERSED_ROW_TAIL_RE.match(line)
            bled = _REVERSED_ROW_HEAD_WITH_TAIL_RE.match(lines[index + 1])
            if (
                tail is not None
                and bled is not None
                and _REVERSED_ROW_HEAD_RE.match(lines[index + 1]) is None
                and _parse_pdf_row(line, index + 1) is None
                and _parse_pdf_row(lines[index + 1], index + 2) is None
                and _continues(previous_row, bled.group("ordinal"), int(bled.group("offset")))
                and (bled.group("ordinal"), int(bled.group("offset"))) not in claimed[index]
            ):
                joined.append(
                    f"{bled.group('ordinal')} {bled.group('offset')} "
                    f"{tail.group('length')} {tail.group('type')} "
                    f"{tail.group('description').rstrip()} {bled.group('trailing').strip()}",
                )
                index += 2
                continue
            head = _REVERSED_ROW_HEAD_RE.match(lines[index + 1])
            if (
                tail is not None
                and head is not None
                and _parse_pdf_row(line, index + 1) is None
                and _parse_pdf_row(lines[index + 1], index + 2) is None
                and (head.group("ordinal"), int(head.group("offset"))) not in claimed[index]
            ):
                casilla = (head.group("tail") or "").strip()
                description = tail.group("description").rstrip()
                joined.append(
                    f"{head.group('ordinal')} {head.group('offset')} "
                    f"{tail.group('length')} {tail.group('type')} "
                    f"{description}{' ' + casilla if casilla else ''}",
                )
                index += 2
                continue
        joined.append(line)
        index += 1
    return tuple(joined)


#: A row whose ordinal and position are emitted twice before the rest of the
#: row: ``99 1592 99 1592 17 Num ...``. The repeat is the evidence -- the line
#: states the same two numbers twice, so dropping the first pair asserts nothing
#: the row does not already say about itself.
_STUTTERED_PDF_ROW_RE = re.compile(
    r"^(?P<indent>\s*)(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P=ordinal)\s+(?P=offset)\s+(?P<rest>\d.*)$",
)


def _collapse_stuttered_row_prefix(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Drop a row's duplicated ordinal-and-position prefix.

    Modelo 200's 2010 and 2011 editions emit nine rows this way, and every one
    of their positions is currently reported as a hole, so the duplication is
    not cosmetic -- it costs the record the field.

    Deliberately narrow to the SELF-EVIDENCING case. A row may also arrive with
    genuine leading text, where the tail of a wrapped description spills onto
    its line, and those cannot be admitted on the line's own evidence: measured
    across the bundled corpus, lines of that shape include both real rows and
    prose carrying number sequences, and nothing in the line distinguishes them.
    A back-reference to the same two numbers has no such ambiguity.
    """
    return tuple(
        f"{match.group('indent')}{match.group('ordinal')} {match.group('offset')} {match.group('rest')}"
        if (match := _STUTTERED_PDF_ROW_RE.match(line)) is not None
        else line
        for line in lines
    )


#: The TRUE ordinal and position of a damaged row, restated on a line of its
#: own: ``54 827 Ajustes por valoracion [380]``. The line is not itself a row --
#: it carries no length and no naturaleza -- so it can only be read together
#: with the half that does.
_COORDINATE_STUTTER_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<rest>\S.*)$",
)

#: The other half: length, naturaleza and description with no coordinates at
#: all, which is what a row whose coordinate column was lost leaves behind.
_ORPHAN_MEASURE_RE = re.compile(
    r"^\s*(?P<length>\d+)\s+(?P<naturaleza>An|Num|N|A)\.?\s+(?P<description>\S.*)$",
    re.IGNORECASE,
)

#: A casilla reference anywhere in a line.
_ANY_CASILLA_TAG_RE = re.compile(r"\[\d+\]")


def _recover_coordinate_stutter_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Rebuild a row whose coordinate column was damaged, from the stutter restating it.

    Modelo 200's 2010 and 2011 editions lose the coordinate column on some rows
    and then restate it. The damage takes two forms: the coordinates vanish
    entirely, leaving ``17 N <description>``; or they survive mangled, so
    ``54 827`` arrives as ``4 82`` and parses as a real but WRONG row at
    ordinal 4, position 82. Either way a following line states the true pair.

    Both halves are required, and that is the whole guard. The coordinates are
    admitted only when they are OVER-DETERMINED against the last undamaged row
    -- the ordinal must follow by one AND the position must resume where that
    row ended, the same two independent facts :func:`_continues` checks
    everywhere else. The length and naturaleza are never inferred: they must be
    stated by the donor half. Where no donor exists the site is left alone,
    which is why this declines the three sites in these same two editions that
    state coordinates and a casilla tag but nothing else -- recovering those
    would mean inventing a naturaleza and truncating a description.
    """
    parsed = tuple(_parse_pdf_row(line, index + 1) for index, line in enumerate(lines))

    def _anchor(before: int) -> _PdfRow | None:
        for index in range(before - 1, -1, -1):
            if parsed[index] is not None:
                return parsed[index]
        return None

    rebuilt: dict[int, str] = {}
    dropped: set[int] = set()
    for index, line in enumerate(lines):
        if parsed[index] is not None or index == 0:
            continue
        stutter = _COORDINATE_STUTTER_RE.match(line)
        if stutter is None or not _ANY_CASILLA_TAG_RE.search(line):
            continue
        donor_index = index - 1
        if donor_index in dropped or donor_index in rebuilt:
            continue
        anchor = _anchor(donor_index)
        donor_row = parsed[donor_index]
        if donor_row is None:
            measure = _ORPHAN_MEASURE_RE.match(lines[donor_index])
            if measure is None:
                continue
            length = measure.group("length")
            naturaleza = measure.group("naturaleza")
            description = measure.group("description")
        else:
            if _continues(anchor, donor_row.ordinal or "", donor_row.offset):
                continue  # the neighbour is a healthy row, not a damaged half
            length = str(donor_row.length)
            naturaleza = donor_row.type_code
            description = donor_row.description
        ordinal = stutter.group("ordinal")
        offset = int(stutter.group("offset"))
        if not _continues(anchor, ordinal, offset):
            continue
        rebuilt[donor_index] = f"{ordinal} {offset} {length} {naturaleza} {description} {stutter.group('rest')}"
        dropped.add(index)

    if not rebuilt:
        return lines
    return tuple(rebuilt.get(index, line) for index, line in enumerate(lines) if index not in dropped)


#: A row whose three coordinate numbers were emitted ALONE on their own line,
#: with the naturaleza and description following on the next: ``5 10 1`` then
#: ``An C Indicador de pagina complementaria.``. Deliberately anchored end to
#: end, so the line must be EXACTLY ordinal, position and length and nothing
#: else -- a looser pattern that tolerated a trailing fragment was measured
#: claiming forty lines on one design where two were real.
_BARE_COORDINATE_TRIPLE_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s*$",
)

#: How far past the naturaleza half the anchoring successor row may sit. The
#: wrapped Contenido cell runs to three lines in the measured corpus.
_BARE_COORDINATE_LOOKAHEAD = 6

#: How far ABOVE a bare triple its naturaleza half may sit. Wider than the
#: lookahead because a page break drops several lines of running furniture --
#: the modelo name, the version and the two-line subtitle -- between them.
_BARE_COORDINATE_LOOKBEHIND = 12

#: The half that follows it: naturaleza then description, no numbers of its own.
_NATURALEZA_HEAD_RE = re.compile(
    r"^\s*(?P<naturaleza>An|Num|N|A)\s+(?P<rest>\D\S*.*)$",
)


def _rejoin_bare_coordinate_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Rebuild a row split between a bare coordinate line and its naturaleza half.

    Modelo 200's ``17-200-orden-eha-1338-2010`` design emits the ``Indicador de
    pagina complementaria`` row of its Pag. 21 and Pag. 22 records this way::

        5 10 1
        An C Indicador de pagina complementaria.
        Blanco (No
        complementaria) o
        "C" (Complementaria)
        6 11 1 A C Operaciones fusion, escision, canje valores - ...

    Position 10 is then the ONLY hole on either record, and a record read with a
    hole is skipped whole, so two sheets are lost to one split row.

    ANCHORED ON THE SUCCESSOR, NOT THE PREDECESSOR, and that is forced rather
    than chosen. On these pages the rows above -- ordinals 2, 3 and 4 -- are
    emitted with their ordinal and position FUSED (``23 3 Num``, ``36 3 An``)
    and are not recovered until record assembly, so at line-repair time the
    nearest parsed row above is ordinal 1 and a backward check can never be
    satisfied. The row BELOW is intact.

    The over-determination is the same strength either way: the successor's
    ordinal must be one more than the rebuilt row's AND its position must resume
    exactly where the rebuilt row ends. Two independent facts, from a row read
    without help, that must agree.

    The intervening lines are the wrapped ``Contenido`` cell and are folded into
    the description rather than dropped, so nothing AEAT printed is discarded.
    """
    parsed = tuple(_parse_pdf_row(line, index + 1) for index, line in enumerate(lines))

    rebuilt: dict[int, str] = {}
    consumed: set[int] = set()
    for index, line in enumerate(lines):
        if parsed[index] is not None or index + 1 >= len(lines):
            continue
        triple = _BARE_COORDINATE_TRIPLE_RE.match(line)
        if triple is None or parsed[index + 1] is not None:
            continue
        head = _NATURALEZA_HEAD_RE.match(lines[index + 1])
        head_index = index + 1
        if head is None:
            # The naturaleza half may sit ABOVE the triple instead, separated by
            # the wrapped Contenido cell and a page break's running furniture.
            # Modelo 200's 2010 and 2011 designs print it that way; the 2010
            # update prints it below. Same row, mirrored.
            for candidate in range(index - 1, max(-1, index - 1 - _BARE_COORDINATE_LOOKBEHIND), -1):
                if parsed[candidate] is not None:
                    break
                found = _NATURALEZA_HEAD_RE.match(lines[candidate])
                if found is not None:
                    head, head_index = found, candidate
                    break
        if head is None:
            continue
        ordinal = triple.group("ordinal")
        offset = int(triple.group("offset"))
        length = int(triple.group("length"))

        successor_index = None
        for candidate in range(index + 2, min(index + 2 + _BARE_COORDINATE_LOOKAHEAD, len(lines))):
            if parsed[candidate] is not None:
                successor_index = candidate
                break
        if successor_index is None:
            continue
        successor = parsed[successor_index]
        assert successor is not None
        if successor.ordinal != str(int(ordinal) + 1) or successor.offset != offset + length:
            continue

        start = min(index, head_index)
        middle = " ".join(
            lines[position].strip() for position in range(start, successor_index) if position not in {index, head_index}
        )
        rebuilt[start] = (
            f"{ordinal} {offset} {length} {head.group('naturaleza')} {head.group('rest')} {middle}".rstrip()
        )
        consumed.update(position for position in range(start, successor_index) if position != start)

    if not rebuilt:
        return lines
    return tuple(rebuilt.get(index, line) for index, line in enumerate(lines) if index not in consumed)


#: A row whose ORDINAL and POSITION were emitted as one token, with the length
#: and naturaleza intact behind them: ``23 3 Num C Modelo.`` for AEAT's
#: ``2 3 3 Num C Modelo.``. Distinct from :data:`_FUSED_ROW_RE`, which covers a
#: position glued to its NATURALEZA (``59 1A Num``); here the two numbers ran
#: together and nothing is glued to a letter.
_FUSED_ORDINAL_POSITION_RE = re.compile(
    r"^\s*(?P<fused>\d+)\s+(?P<length>\d+)\s+(?P<naturaleza>An|Num|N|A)\s+(?P<rest>\S.*)$",
)


def _split_fused_ordinal_position_prefix(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Split a row whose ordinal and position were emitted as a single number.

    Modelo 200's 2010 and 2011 PDF designs open several records this way::

        1 1 2 An C Inicio del identificador de modelo y pagina.
        23 3 Num C Modelo. Constante "200"
        36 3 An C Pagina. Constante "021"
        49 1 An C Fin de identificador de modelo.

    Read literally the second line is ordinal 23 at position 3, which is not a
    row anyone printed. It is ordinal 2 at position 3, and the ordinal ran into
    the position because AEAT's two narrow columns touch.

    RECONSTRUCTED FROM THE PREVIOUS ROW, NEVER GUESSED, and admitted only when
    both halves agree. The previous row fixes exactly one candidate -- its
    ordinal plus one, and the position where it ends -- and that candidate is
    accepted only if concatenating the two reproduces the fused token
    CHARACTER FOR CHARACTER. ``2`` and ``3`` give ``23``; anything else leaves
    the line alone.

    That is the same over-determination the sibling splitter uses, and it is
    what keeps this away from rows that legitimately open with a large ordinal:
    a real ``23 3 Num`` row at position 3 would follow a row ending at 3 with
    ordinal 22, and ``22`` and ``3`` do not spell ``23``.
    """
    split: list[str] = []
    previous: _PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = _parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        fused = _FUSED_ORDINAL_POSITION_RE.match(line)
        if fused is None or previous is None or previous.ordinal is None or not previous.ordinal.isdigit():
            split.append(line)
            continue
        ordinal = str(int(previous.ordinal) + 1)
        offset = previous.offset + previous.length
        if f"{ordinal}{offset}" != fused.group("fused"):
            split.append(line)
            continue
        rebuilt = f"{ordinal} {offset} {fused.group('length')} {fused.group('naturaleza')} {fused.group('rest')}"
        reparsed = _parse_pdf_row(rebuilt, index + 1)
        if reparsed is None:
            split.append(line)
            continue
        previous = reparsed
        split.append(rebuilt)
    return tuple(split)


#: A row whose NATURALEZA ran into the content-column marker that follows it:
#: ``170 1697 9 AnC ...`` for AEAT's ``170 1697 9 An C ...``. The sibling
#: :data:`_DOUBLED_COORDINATE_ROW_RE` covers the same gluing when the
#: coordinates are ALSO doubled; this covers it on its own.
_GLUED_NATURALEZA_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+"
    r"(?P<naturaleza>An|Num|N|A)(?P<marker>[A-Z])\s+(?P<rest>\S.*)$",
)


def _split_glued_naturaleza_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a naturaleza that ran into the following content-column marker.

    Modelo 200's 2010 design loses one row of its ``Pag. 22`` record this way::

        169 1690 7 Num C Agrup.interes economico y UTES - Modelo de info...
        170 1697 9 AnC A i t   i UTES M d l d i f i  R l i  d i 18 NIF
        171 1706 1 Num C Agrup.interes economico y UTES - Modelo de info...

    Nothing is missing: ordinal 170 at position 1697, nine bytes, naturaleza
    ``An``, content column ``A``. Only the space between ``An`` and the marker
    is gone, and without it the row does not parse and its nine positions read
    as a hole -- which costs the whole record.

    ADMITTED ON OVER-DETERMINATION and on the split parsing. The coordinates
    must continue the previous row -- ordinal one more, position resuming where
    it ended -- and the separated line must then parse as a row. A line that
    merely looks like this but sits at the wrong position is left alone.

    The description here is visibly mangled -- AEAT's own PDF drops characters
    from that cell -- and that is NOT this repair's business. Recovering the
    row's POSITION is what stops the record being skipped; the description is
    carried through exactly as extracted rather than being cleaned up, because
    inventing text is a different and worse failure than reporting it damaged.
    """
    split: list[str] = []
    previous: _PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = _parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        glued = _GLUED_NATURALEZA_ROW_RE.match(line)
        if glued is None or previous is None:
            split.append(line)
            continue
        if not _continues(previous, glued.group("ordinal"), int(glued.group("offset"))):
            split.append(line)
            continue
        rebuilt = (
            f"{glued.group('ordinal')} {glued.group('offset')} {glued.group('length')} "
            f"{glued.group('naturaleza')} {glued.group('marker')} {glued.group('rest')}"
        )
        reparsed = _parse_pdf_row(rebuilt, index + 1)
        if reparsed is None:
            split.append(line)
            continue
        previous = reparsed
        split.append(rebuilt)
    return tuple(split)


#: A row's TRUE ordinal and position, restated alone on the line below it after
#: the row itself was printed with a truncated position: ``18 215`` under
#: ``18 21 17 N ...``. Anchored end to end -- two integers and nothing else --
#: because a looser pattern would claim any line opening with two numbers.
_STRANDED_COORDINATE_PAIR_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s*$",
)


def _repair_truncated_offset_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Restore a row whose position lost a digit, from the pair restating it below.

    Modelo 200's 2011 design loses one row of its ``Pag. 44`` record this way::

        17 198 17 N  Inst. inversion colectiva - Cuenta perdidas y ganancias ...
        18 21 17 N   Inst. inversion colectiva - Cuenta perdidas y ganancias ...
        18 215
        19 232 17 N  Inst. inversion colectiva - Cuenta perdidas y ganancias ...

    The middle row PARSES, which is what makes this dangerous: it reads as
    ordinal 18 at position 21, seventeen bytes, and nothing downstream doubts
    it. Position 215 is then a hole and the record is skipped, while the row
    quietly claims bytes 21-37 that belong to other fields.

    The truncation is visible only against the neighbours, and they settle it
    three ways at once. The stranded pair must repeat the parsed row's OWN
    ordinal; the position it states must resume exactly where the row above
    ends; and the position the row currently claims must NOT. All three, or the
    line is left alone -- the third is what stops this touching a healthy row
    that merely happens to sit above a stray pair.

    Distinct from :func:`_recover_coordinate_stutter_rows`, which handles the
    same restatement when the stutter line also carries the casilla tag and the
    damaged half does not parse at all. Here the line is bare and the damaged
    half parses wrongly, so neither of that function's halves matches.
    """
    parsed = list(_parse_pdf_row(line, index + 1) for index, line in enumerate(lines))

    repaired: dict[int, str] = {}
    dropped: set[int] = set()
    for index in range(1, len(lines)):
        pair = _STRANDED_COORDINATE_PAIR_RE.match(lines[index])
        if pair is None:
            continue
        damaged = parsed[index - 1]
        if damaged is None or damaged.ordinal != pair.group("ordinal"):
            continue
        anchor = None
        for candidate in range(index - 2, -1, -1):
            if parsed[candidate] is not None:
                anchor = parsed[candidate]
                break
        if anchor is None:
            continue
        stated = int(pair.group("offset"))
        resumes = anchor.offset + anchor.length
        if stated != resumes or damaged.offset == resumes:
            continue
        rebuilt = re.sub(
            rf"^(\s*{re.escape(damaged.ordinal)})\s+{damaged.offset}\s",
            rf"\g<1> {stated} ",
            lines[index - 1],
            count=1,
        )
        if _parse_pdf_row(rebuilt, index) is None:
            continue
        repaired[index - 1] = rebuilt
        parsed[index - 1] = _parse_pdf_row(rebuilt, index)
        dropped.add(index)

    if not repaired:
        return lines
    return tuple(repaired.get(index, line) for index, line in enumerate(lines) if index not in dropped)


#: A field row whose four tokens are complete but whose DESCRIPTION wrapped onto
#: the next line. AEAT does this often enough to matter: modelo 202 writes
#: ``15 80 1 Num`` and puts "Datos adicionales (3) - Cooperativa fiscalmente
#: protegida ..." underneath.
_BARE_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*\d+\s+\d+\s+\d+\s+(?:An|Num|N|A)\s*$",
    re.IGNORECASE,
)


#: A casilla reference AEAT emitted on a line of its own, orphaned from the
#: description it terminates.
_STRANDED_CASILLA_TAG_RE = re.compile(r"^\s*\[\d+\]\s*$")

#: A bracketed casilla reference already closing a line.
_TRAILING_CASILLA_TAG_RE = re.compile(r"\[\d+\]\s*$")


def _reattach_stranded_casilla_tags(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Fold a casilla reference emitted alone back onto the row it terminates.

    Residue of the same wrapping the neighbouring repairs address, in two
    shapes. Modelo 200's 2010 editions split a row across its columns and then
    put the casilla on a THIRD line -- ``102 1529`` / ``17 Num Deducciones ...
    aplic`` / ``[121]`` -- while its 2011-2012 editions keep the row intact and
    strand only the tag: ``15 164 17 N Balance: ... Acciones y partic`` /
    ``[194]``. Modelo 390's 2015 edition strands one the same way. In every
    shape the tag sits immediately after the description it closes, because
    extraction emits in reading order and the tag is that description's tail.

    Nothing downstream recovers it. :func:`_join_wrapped_row_descriptions`
    absorbs a following line only into a row that has NO description, which
    neither shape is, and :data:`_REVERSED_ROW_HEAD_RE` admits a casilla only
    where it rides on the head half. So the tag is simply lost, and a position
    that loses its tag contributes no casilla number to coverage -- the quiet
    half of the damage found on modelo 390's ``@115``.

    The tag is folded onto the PRECEDING line, never a following one, and only
    where that line is itself field-shaped: a row, or one of the two halves of a
    split row. A heading carries a record boundary and prose carries nothing, so
    a tag next to either is left stranded and reported rather than attached to
    bytes AEAT did not put it on -- which is the failure this repair could
    otherwise cause, and the one a tiling mis-attribution proved can pass
    quietly.
    """
    folded: list[str] = []
    for line in lines:
        if folded and _STRANDED_CASILLA_TAG_RE.match(line):
            previous = folded[-1]
            cleaned = _clean_pdf_line(previous)
            if (
                previous.strip()
                and not _TRAILING_CASILLA_TAG_RE.search(previous)
                and _pdf_page_name(cleaned) is None
                and _pdf_record_heading_name(cleaned) is None
                and _pdf_candidate_record_name(cleaned) is None
                and (
                    _parse_pdf_row(previous, len(folded)) is not None
                    or _REVERSED_ROW_TAIL_RE.match(previous) is not None
                    or _REVERSED_ROW_HEAD_RE.match(previous) is not None
                )
            ):
                folded[-1] = f"{previous.rstrip()} {line.strip()}"
                continue
        folded.append(line)
    return tuple(folded)


#: A row whose ORDINAL and OFFSET arrived fused into one token and whose LENGTH
#: and NATURALEZA arrived fused into another: ``59 1A Indicador ...`` for what
#: AEAT prints as ``5 9 1 A Indicador ...``.
_FUSED_ROW_RE = re.compile(r"^\s*(\d+)\s+(\d+)([A-Za-z][A-Za-z.]*)\s+(\S.*)$")


#: A row whose OFFSET and LENGTH were emitted twice and whose naturaleza was
#: glued to the description's opening column marker:
#: ``137 1777 15 1777 15 AnC B Participaciones ...`` for AEAT's
#: ``137 1777 15 An C B Participaciones ...``.
_DOUBLED_COORDINATE_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s+"
    r"(?P=offset)\s+(?P=length)\s+(?P<naturaleza>An|Num|Tit|N|A)(?P<rest>\S.*)$",
)


def _split_tail_from_leading_fragment(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a reversed-column TAIL from the previous row's trailing fragment.

    Modelo 200's 2010 edition prints two consecutive RIC rows whose descriptions
    differ only by a footnote marker, and the extraction runs the first row's
    trailing ``(1) [020]`` into the second row's tail::

        '78 1219 17 Num Reg.reserva ... Inv.anticipadas futuras dotaciones R'
        '(1) [020] 17 Num Reg.reserva ... Inv.anticipadas futuras dotaciones'
        '79 1236 (2 a 6) [021]'

    The middle line is row 79's length, naturaleza and description; the last is
    its ordinal and position. :func:`_rejoin_reversed_column_rows` pairs a tail
    with an adjacent head, but that tail cannot match
    :data:`_REVERSED_ROW_TAIL_RE` while a footnote and a casilla tag sit in
    front of it, so the pair is never formed and position 1236 is lost.

    Two independent facts are required before splitting, neither read off the
    line being changed. The SUFFIX must be a well-formed tail, and the FOLLOWING
    line must be a head whose ordinal follows the last row read by one and whose
    offset resumes exactly where that row ended. A fragment that happens to
    precede tail-shaped text, with no head continuing the sequence after it, is
    left alone.

    The fragment is emitted as its own line rather than dropped: it is the
    previous row's own content, and discarding text to make a row appear is the
    defect this repair exists to undo, inverted.
    """
    split: list[str] = []
    previous: _PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = _parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        recovered = False
        if (
            previous is not None
            and previous.ordinal is not None
            and previous.ordinal.isdigit()
            and index + 1 < len(lines)
            and _REVERSED_ROW_TAIL_RE.match(line) is None
        ):
            head = _REVERSED_ROW_HEAD_RE.match(lines[index + 1]) or _REVERSED_ROW_HEAD_WITH_TAIL_RE.match(
                lines[index + 1],
            )
            if head is not None and _continues(previous, head.group("ordinal"), int(head.group("offset"))):
                tokens = line.split()
                for cut in range(1, len(tokens)):
                    suffix = " ".join(tokens[cut:])
                    if _REVERSED_ROW_TAIL_RE.match(suffix) is not None:
                        split.append(" ".join(tokens[:cut]))
                        split.append(suffix)
                        recovered = True
                        break
        if not recovered:
            split.append(line)
    return tuple(split)


def _collapse_doubled_coordinate_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Collapse a row whose position and length were printed twice.

    Modelo 200's 2010 edition emits some rows with the coordinate pair repeated
    and the naturaleza run into the description's stray column marker, which
    matches no column shape and is refused -- leaving a hole the width of the
    row it lost.

    Two independent confirmations are required, and the first is what makes this
    safe: the repeat must be EXACT, matched by backreference rather than by
    re-reading two numbers that merely look similar, so the source itself states
    the coordinate twice. The row must then also continue the previous one --
    ordinal by one, offset resuming where it ended -- so a doubled pair that
    lands in the wrong place is still refused.

    The naturaleza is separated on its own evidence: it is a closed set, so a
    token beginning with one of its members and continuing into text can only be
    that member followed by description. No position is inferred anywhere; every
    number written out here was read from the line.
    """
    collapsed: list[str] = []
    previous: _PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = _parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            collapsed.append(line)
            continue
        doubled = _DOUBLED_COORDINATE_ROW_RE.match(line)
        if (
            doubled is not None
            and previous is not None
            and previous.ordinal is not None
            and previous.ordinal.isdigit()
            and _continues(previous, doubled.group("ordinal"), int(doubled.group("offset")))
        ):
            rebuilt = (
                f"{doubled.group('ordinal')} {doubled.group('offset')} {doubled.group('length')} "
                f"{doubled.group('naturaleza')} {doubled.group('rest').strip()}"
            )
            candidate = _parse_pdf_row(rebuilt, index + 1)
            if candidate is not None:
                previous = candidate
                collapsed.append(rebuilt)
                continue
        collapsed.append(line)
    return tuple(collapsed)


def _split_fused_ordinal_offset_rows(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a row whose first two columns were emitted without a space.

    Modelo 100's 2012, 2013 and 2014 editions each lose exactly one position --
    9 -- and always the same row: the ``Indicador de pagina complementaria``
    flag arrives as ``59 1A ...`` where AEAT prints ``5 9 1 A ...``. Both the
    ordinal/offset pair and the length/naturaleza pair are fused, so no
    column-shaped pattern matches and the row is refused.

    Splitting ``59`` needs no guesswork, and that is what makes this safe: the
    previous row already fixes both values. The ordinal must follow by one and
    the offset must resume where that row ended, so the split is accepted ONLY
    when concatenating those two expected numbers reproduces the fused token
    exactly. ``5`` and ``9`` give ``59``; any other reading of that token, and
    any line whose neighbours do not agree, is left alone.
    """
    split: list[str] = []
    previous: _PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = _parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        fused = _FUSED_ROW_RE.match(line)
        if fused is not None and previous is not None and previous.ordinal is not None and previous.ordinal.isdigit():
            ordinal = int(previous.ordinal) + 1
            offset = previous.offset + previous.length
            if fused.group(1) == f"{ordinal}{offset}":
                rebuilt = f"{ordinal} {offset} {fused.group(2)} {fused.group(3)} {fused.group(4)}"
                candidate = _parse_pdf_row(rebuilt, index + 1)
                if candidate is not None:
                    previous = candidate
                    split.append(rebuilt)
                    continue
        split.append(line)
    return tuple(split)


def _split_row_from_wrapped_content(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Separate a row from a preceding fragment of the previous cell's content.

    AEAT's ``Contenido`` column wraps, and its last fragment can be emitted on
    the same line as the NEXT row. Modelo 131's 2009 design does exactly that:
    the payment-form codes wrap over three lines and the third arrives as
    ``Domiciliacion 48 465 1 Num Ingreso (4) - Forma de pago``. The line does
    not begin with its ordinal, so the row is refused and position 465 is the
    record's only hole.

    Splitting on appearance alone would fabricate rows out of prose, so the
    suffix must satisfy the same OVER-DETERMINATION the reversed-column repair
    relies on: it parses as a row AND its ordinal follows the previous row's by
    one AND its offset resumes exactly where that row ended. Two independent
    facts from an already-read row must both agree, which prose beginning with
    two numbers cannot do by accident.

    The stripped fragment is emitted as its own line rather than discarded. It
    is content, the parser already ignores standalone content lines, and
    dropping text to make a row appear would be the same defect in reverse.
    """
    split: list[str] = []
    previous: _PdfRow | None = None
    for index, line in enumerate(lines):
        parsed = _parse_pdf_row(line, index + 1)
        if parsed is not None:
            previous = parsed
            split.append(line)
            continue
        recovered = False
        if previous is not None:
            tokens = line.split()
            for cut in range(1, len(tokens)):
                suffix = " ".join(tokens[cut:])
                candidate = _parse_pdf_row(suffix, index + 1)
                if candidate is None or candidate.ordinal is None:
                    continue
                if _continues(previous, candidate.ordinal, candidate.offset):
                    split.append(" ".join(tokens[:cut]))
                    split.append(suffix)
                    previous = candidate
                    recovered = True
                    break
        if not recovered:
            split.append(line)
    return tuple(split)


def _join_wrapped_row_descriptions(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Reattach a description AEAT wrapped onto the line after its row.

    Done as a pre-pass rather than by loosening the row pattern, and the
    difference is not cosmetic. Admitting a description-less row creates a field
    that may never receive one -- the continuation handler only fills the field
    still under construction, so anything that intervenes leaves it empty and a
    later validator refuses the whole design. Three modelo 200 editions failed
    exactly that way when the pattern was loosened. Joining first means every
    row still reaches the parser complete, and no invariant downstream changes.

    The line consumed must not itself look like a row, a page heading or a
    record heading: those carry their own meaning and absorbing one would lose a
    field or a record boundary. A row whose next line offers nothing usable is
    left exactly as it was, to be reported as the hole it is.
    """
    joined: list[str] = []
    absorbed = False
    for index, line in enumerate(lines):
        if absorbed:
            absorbed = False
            continue
        if _BARE_COMPACT_PDF_ROW_RE.match(line) and index + 1 < len(lines):
            candidate = lines[index + 1]
            cleaned = _clean_pdf_line(candidate)
            if (
                candidate.strip()
                and _parse_pdf_row(candidate, index + 2) is None
                and _pdf_page_name(cleaned) is None
                and _pdf_record_heading_name(cleaned) is None
                and _pdf_candidate_record_name(cleaned) is None
            ):
                joined.append(f"{line.rstrip()} {candidate.strip()}")
                absorbed = True
                continue
        joined.append(line)
    return tuple(joined)


@lru_cache(maxsize=256)
def _extract_record_design_pdf_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
) -> RecordDesignExtraction:
    del byte_count, modified_ns
    source_path = Path(path)
    corrections = _load_corrections(source_path)
    with source_path.open("rb") as pdf_file:
        return _extract_record_design_pdf_stream(
            pdf_file,
            source_label=str(source_path),
            corrections=corrections,
        )


def extract_record_design_pdf_bytes(
    pdf_bytes: bytes,
    *,
    source_label: str = "in-memory record-design PDF",
) -> RecordDesignExtraction:
    """Return the record design extracted from PDF bytes.

    Returns:
        The :class:`RecordDesignExtraction` for the PDF content.
    """
    return _extract_record_design_pdf_stream(BytesIO(pdf_bytes), source_label=source_label)


def _extract_record_design_pdf_stream(
    stream: BufferedReader | BytesIO,
    *,
    source_label: str,
    corrections: _CorrectionIndex = _EMPTY_CORRECTIONS,
) -> RecordDesignExtraction:
    import pdfplumber

    pdf_bytes = stream.read()
    base_lines = _extract_pdf_text_lines(pdf_bytes, source_label=source_label)
    lines = _reattach_stranded_casilla_tags(
        _split_row_from_wrapped_content(
            _split_fused_ordinal_offset_rows(
                _collapse_doubled_coordinate_rows(
                    _collapse_stuttered_row_prefix(_join_wrapped_row_descriptions(base_lines)),
                ),
            ),
        ),
    )
    if _uses_page_record_layout(base_lines):
        page_lines = _reattach_stranded_casilla_tags(
            _collapse_stuttered_row_prefix(
                _join_wrapped_row_descriptions(
                    _extract_pdfplumber_text_lines(pdf_bytes, source_label=source_label),
                ),
            ),
        )
        lines = _better_page_record_lines(
            page_lines,
            lines,
            source_label=source_label,
            corrections=corrections,
        )
    if not any(line.strip() for line in lines):
        raise RegistryValidationError(f"no text extracted from record-design PDF {source_label}")
    try:
        return _read_with_reversed_column_repair(lines, source_label=source_label, corrections=corrections)
    except ValueError as pdfium_exc:
        text_fallback_error = pdfium_exc
        try:
            fallback_lines = _extract_pdfplumber_text_lines(pdf_bytes, source_label=source_label)
            return _extract_pdf_lines(fallback_lines, source_label=source_label, corrections=corrections)
        except ValueError as fallback_exc:
            text_fallback_error = fallback_exc
        if "did not contain parseable field rows" not in str(text_fallback_error):
            raise text_fallback_error from pdfium_exc
        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                pages = tuple(_snapshot_pdf_page(page) for page in pdf.pages)
        except Exception as pdf_exc:  # pragma: no cover - defensive; pdfplumber surface
            raise RegistryValidationError(
                f"pdfplumber could not open record-design PDF {source_label}: {pdf_exc}",
            ) from pdf_exc
        visual_chart = _extract_visual_record_design_chart(pages, source_label=source_label)
        if visual_chart:
            # The geometry reader was documented as "complete by construction",
            # and it is not: modelo 349's 2002 edition and modelo 180's 2000
            # edition both reconstruct here with 40-to-65-byte runs missing from
            # every record, and reported ``is_complete`` because nothing checked.
            # It is a READER like any other, so it answers to the same contiguity
            # question -- a sheet whose rows do not tile its declared extent is
            # reported as skipped rather than handed over as whole.
            broken = {sheet.name: reason for sheet in visual_chart if (reason := contiguity_failure(sheet)) is not None}
            return RecordDesignExtraction(
                source=source_label,
                sheets=tuple(sheet for sheet in visual_chart if sheet.name not in broken),
                skipped=tuple(RecordDesignSkippedSheet(name=name, reason=reason) for name, reason in broken.items()),
            )
        raise


def _better_page_record_lines(
    page_lines: tuple[str, ...],
    base_lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: _CorrectionIndex,
) -> tuple[str, ...]:
    """Return whichever text extraction reads a page-record design more completely.

    A design that names its records by page is read through pdfplumber, because
    the plain text extractor does not recover those headings. That switch was
    unconditional, and it is not free: pdfplumber emits some rows' columns in an
    order the line repairs cannot reassemble, and where a row's tail is lost the
    damage is not only a hole. Modelo 390's 2015 edition is the worked case --
    under pdfplumber its ``Pág. 7`` loses the row at ``@132`` AND mis-pairs the
    surviving tail onto ``@115``, so that position carried casilla ``[654]``
    where five sibling editions (2016, 2017, 2018, 2019-2020 and 2025, all read
    cleanly) agree it is ``[523]``. The plain extraction reads the same design
    whole, all nine records, with both descriptions matching those siblings.

    So the choice is MEASURED per design rather than decided by the heading
    heuristic alone, in the idiom :func:`_read_with_reversed_column_repair`
    already uses: the page-record read stands unless the alternative is strictly
    better, so a design the switch serves today cannot be perturbed. "Better" is
    fewer skipped records first -- a skipped record is a whole record nobody can
    read -- and fewer uncovered positions only as a tie-break.

    The wrong-pairing half of that damage is worth stating plainly, because the
    reversed-column repair's own docstring says a wrong pairing "cannot pass
    quietly: it would place a field at a position some other row already
    covers". Here it did pass quietly: the mis-paired tail tiled exactly, and
    only the orphaned head left a hole for :func:`contiguity_failure` to find.
    A pairing that tiles is invisible to that check.
    """

    def read(candidate: tuple[str, ...]) -> RecordDesignExtraction | None:
        try:
            return _read_with_reversed_column_repair(
                candidate,
                source_label=source_label,
                corrections=corrections,
            )
        except (ValueError, RegistryValidationError):
            return None

    page_read = read(page_lines)
    if page_read is not None and not page_read.skipped:
        return page_lines
    base_read = read(base_lines)
    if base_read is None:
        return page_lines
    if page_read is None:
        return base_lines
    if len(base_read.skipped) != len(page_read.skipped):
        return base_lines if len(base_read.skipped) < len(page_read.skipped) else page_lines
    page_unread = _unread_positions_over_lines(
        page_lines,
        source_label=source_label,
        corrections=corrections,
    )
    base_unread = _unread_positions_over_lines(
        base_lines,
        source_label=source_label,
        corrections=corrections,
    )
    return base_lines if base_unread < page_unread else page_lines


def _read_with_reversed_column_repair(
    lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: _CorrectionIndex,
) -> RecordDesignExtraction:
    """Read the design, retrying with the reversed-column repair only where it can help.

    The repair reassembles a row whose PDF columns were emitted out of order. It
    recovers a great deal -- roughly 8,800 positions across modelo 200's three
    oldest editions -- but a design may emit the SAME row both split and intact,
    and a line-level view cannot tell those apart. Applied unconditionally it
    added twelve duplicate importe fields to each of modelo 200's 2012-2014
    editions, which had no unread positions at all, and contiguity permits that
    as containment, so it would have been silent.

    So the decision is made at DESIGN level, on two exact quantities rather than
    on a judgement about any line. A design that reports nothing skipped has
    nothing for this repair to recover and is never offered one -- its first
    read is what it returns, so a clean design cannot be perturbed. Where
    something IS skipped, the repaired read is kept only if it skips no more
    sheets and leaves strictly fewer positions uncovered -- counted across every
    record the lines produce, including the ones that stay reported, because
    that is where this repair does its work.
    """
    first = _extract_pdf_lines(lines, source_label=source_label, corrections=corrections)
    if not first.skipped:
        return first
    repaired_lines = _recover_coordinate_stutter_rows(
        _repair_truncated_offset_rows(
            _rejoin_bare_coordinate_rows(
                _split_glued_naturaleza_rows(
                    _split_fused_ordinal_position_prefix(
                        _reattach_stranded_casilla_tags(
                            _collapse_stuttered_row_prefix(
                                _join_wrapped_row_descriptions(
                                    _rejoin_reversed_column_rows(
                                        _split_tail_from_leading_fragment(_undouble_struck_rows(lines)),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    try:
        repaired = _extract_pdf_lines(
            repaired_lines,
            source_label=source_label,
            corrections=corrections,
            repair_glued_rows=True,
        )
    except ValueError:
        return first
    if len(repaired.skipped) > len(first.skipped):
        return first
    before = _unread_positions_over_lines(lines, source_label=source_label, corrections=corrections)
    after = _unread_positions_over_lines(
        repaired_lines,
        source_label=source_label,
        corrections=corrections,
        repair_glued_rows=True,
    )
    return repaired if after < before else first


def _unread_positions_over_lines(
    lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: _CorrectionIndex,
    repair_glued_rows: bool = False,
) -> int:
    """Positions no row covers, counted over EVERY record these lines produce.

    Deliberately measured on the parse state rather than on the finished
    extraction, and that is the whole reason this function exists. A record
    whose rows do not tile its extent is reported instead of handed over, so it
    is absent from ``sheets`` -- and the reversed-column repair recovers rows
    precisely inside such records, which stay incomplete for other reasons.
    Every quantity the extraction exposes is therefore identical either side of
    the repair while thousands of positions differ, which is what made two
    earlier decision rules read as "no improvement" and leave the repair dead.
    """
    state = _PdfParseState(
        source_label=source_label,
        corrections=corrections,
        repair_glued_rows=repair_glued_rows,
    )
    for number, line in enumerate(lines, start=1):
        state.feed(line, number)
    state._close_current_body()
    total = 0
    for result in state.results:
        sheet = result.sheet
        if sheet.total_positions is None or not sheet.fields:
            continue
        covered: set[int] = set()
        for parsed_field in sheet.fields:
            covered.update(range(parsed_field.offset, parsed_field.offset + parsed_field.length))
        total += len(set(range(1, sheet.total_positions + 1)) - covered)
    return total


def _extract_sheet(worksheet: Worksheet, corrections: _CorrectionIndex = _EMPTY_CORRECTIONS) -> RecordDesignSheet:
    header, header_correction = _find_header(worksheet, corrections.header_corrections)
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


def _extract_xls_sheet(worksheet: XlrdSheet, corrections: _CorrectionIndex = _EMPTY_CORRECTIONS) -> RecordDesignSheet:
    header, header_correction = _find_xls_header(worksheet, corrections.header_corrections)
    return _extract_sheet_rows(
        worksheet.name,
        header,
        ((rowx + 1, tuple(worksheet.row_values(rowx))) for rowx in range(header.row_number, worksheet.nrows)),
        corrections,
        header_correction,
    )


def _extract_sheet_rows(
    sheet_name: str,
    header: _WorkbookHeader,
    rows: Iterator[tuple[int, tuple[object, ...]]],
    corrections: _CorrectionIndex = _EMPTY_CORRECTIONS,
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
    parsed_rows.fields[:] = _fold_untagged_desglose_components(parsed_rows.fields)
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
    header: _WorkbookHeader,
    rows: Iterator[tuple[int, tuple[object, ...]]],
    corrections: _TypeCorrectionIndex | None = None,
) -> _WorkbookSheetRows:
    parsed_rows = _WorkbookSheetRows()
    trailing_blank_rows = 0
    for row_number, row in rows:
        values = tuple(row)
        if _is_blank_row(values):
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
    total_label_index = _total_label_index(values)
    if total_label_index is None:
        return False
    row_total = _positive_integer_after(values, total_label_index)
    has_variable_total = any(_optional_text(candidate) == "Variable" for candidate in values[total_label_index + 1 :])
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
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    corrections: _TypeCorrectionIndex,
) -> None:
    # ``RecordDesignField.ordinal`` is the printed LABEL (``ordinal_text``), never
    # an arithmetic value -- it is now representable verbatim, so there is no more
    # "printed but unreadable" case to refuse for it. The two MARKER rows below
    # (variable-body, relative-suffix) are unrelated types whose own ``ordinal``
    # field is still a plain sequential ``int``, so they keep reading the
    # int-or-None form.
    ordinal_int = _int_or_none(_cell(values, header.ordinal_index))
    ordinal_text = _ordinal_text(_cell(values, header.ordinal_index))
    offset = _int_or_none(_cell(values, header.offset_index))
    length = _int_or_none(_cell(values, header.length_index))
    raw_offset = _optional_text(_cell(values, header.offset_index))
    raw_length = _optional_text(_cell(values, header.length_index))
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
        ordinal_text,
        offset,
        length,
        corrections,
    )
    if applied_correction is not None:
        parsed_rows.corrections_applied.append(applied_correction)
    parent_index = _matching_component_parent_index(parsed_rows.fields, ordinal_text, offset, length)
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


def _fold_untagged_desglose_components(fields: list[RecordDesignField]) -> list[RecordDesignField]:
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
        if run and not parent.components and _tiles_exactly(parent, run):
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


def _declared_subdivision_count(field: RecordDesignField) -> int | None:
    """Return how many sub-fields ``field`` says it divides into, else ``None``."""
    text = f"{field.description or ''} {field.content or ''}"
    normalised = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    match = _DECLARED_SUBDIVISION.search(normalised)
    if match is None:
        return None
    token = match.group(1).lower()
    return int(token) if token.isdigit() else _SUBDIVISION_COUNT_WORDS[token]


def _solve_declared_desglose_holes(
    *,
    parent: RecordDesignField,
    covered: set[int],
    by_offset: Mapping[int, list[_PdfRow]],
    wanted: int,
) -> list[_PdfRow] | None:
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

    def walk(position: int, remaining: int) -> list[_PdfRow] | None:
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


def _tiles_exactly(parent: RecordDesignField, run: list[RecordDesignField]) -> bool:
    """Return whether ``run`` covers ``parent``'s span end to end with no gap."""
    expected = parent.offset
    for component in run:
        if component.offset != expected:
            return False
        expected = component.offset + component.length
    return expected == parent.offset + parent.length


def _variable_body_marker(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: int | None,
    offset: int,
) -> RecordDesignVariableBodyMarker:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    return RecordDesignVariableBodyMarker(
        sheet=sheet_name,
        row=row_number,
        ordinal=ordinal,
        offset=offset,
        length="Variable",
        type_code=_required_text(_cell(values, header.type_index), sheet_name, row_number, "type"),
        description=description,
        validation=validation,
        content=content,
    )


def _relative_suffix_marker(
    sheet_name: str,
    header: _WorkbookHeader,
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
        type_code=_required_text(_cell(values, header.type_index), sheet_name, row_number, "type"),
        description=description,
        validation=validation,
        content=content,
    )


def _record_design_field(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
    ordinal: str | None,
    offset: int,
    length: int,
    corrections: _TypeCorrectionIndex,
) -> tuple[RecordDesignField, RecordDesignFieldTypeCorrection | None]:
    validation, content, description = _field_texts(sheet_name, header, row_number, values)
    type_code, applied_correction = _required_type_code(
        _cell(values, header.type_index),
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
            complementary=_optional_header_text(values, header.complementary_index),
            description=description,
            validation=validation,
            content=content,
        ),
        applied_correction,
    )


def _field_texts(
    sheet_name: str,
    header: _WorkbookHeader,
    row_number: int,
    values: tuple[object, ...],
) -> tuple[str | None, str | None, str]:
    validation = _optional_header_text(values, header.validation_index)
    content = _optional_header_text(values, header.content_index)
    return (
        validation,
        content,
        _field_description_text(
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
    closing_suffixes, terminator = _split_record_terminator(parsed_rows.relative_suffixes)
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
_RECORD_TERMINATOR_PHRASE = r"fin de registro|salto de l[íi]nea|\bCRLF\b"
#: Matched on the declared MEANING rather than on width: a two-byte relative
#: suffix that is not a line terminator is part of the closing identifier and
#: must not be mistaken for one.
_RECORD_TERMINATOR = re.compile(_RECORD_TERMINATOR_PHRASE, re.IGNORECASE)


def _split_record_terminator(
    suffixes: list[RecordDesignRelativeSuffixMarker],
) -> tuple[list[RecordDesignRelativeSuffixMarker], RecordDesignRelativeSuffixMarker | None]:
    """Separate a trailing physical end-of-record row from the closing identifier.

    The closing identifies the record; the terminator ends the line. AEAT declares
    them as adjacent relative-offset rows, and the closing recogniser below reads
    only the first kind, so a design declaring both was refused outright -- thirty
    of them, across eight modelos, every one well formed.

    Split rather than skipped. The terminator is returned to the caller and stored
    on the envelope, because its two bytes are part of the record: discarding it
    would let all thirty parse while every emitted record came out two bytes short,
    which is a clean-looking wrong answer rather than a refusal.
    """
    if not suffixes:
        return suffixes, None
    last = suffixes[-1]
    if last.length == 2 and _RECORD_TERMINATOR.search(last.description):
        return suffixes[:-1], last
    return suffixes, None


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


def _is_blank_row(values: tuple[object, ...]) -> bool:
    return all(value is None or str(value).strip() == "" for value in values)


def _probe_header_row(
    values: tuple[object, ...],
    row_number: int,
    *,
    label: str,
    sheet_name: str,
    header_corrections: _HeaderCorrectionIndex,
) -> tuple[_WorkbookHeader, RecordDesignHeaderCellCorrection | None] | None:
    """Match one row against either recognised AEAT record-design header shape.

    Shape A is AEAT's ordinary header: ``Posic.``/``Lon``/``Tipo``/``Descripcion``,
    with an optional ``Validacion`` and an optional ``Com.`` (complementary
    indicator) column. Its ``Lon`` cell may be recovered by a declared
    ``RecordDesignHeaderCellCorrection`` when AEAT's own publication leaves it
    blank -- applied ONLY when a sidecar names this exact
    ``(sheet, row, "length")``, never inferred from column position alone.

    Shape B is a second, real AEAT shape -- confirmed only in bundled Modelo
    151 annex sheets (``M15100000``, ``M15102000``-``M15109000``) -- carrying
    the same ``Posic.``/``Lon``/``Tipo`` columns, but where the description
    column holds the sheet's own topical caption instead of the literal word
    ``Descripcion``, sitting directly after a recognised ``Com.`` column, with
    no separate ``Validacion`` column at all. This is resilience to a real
    AEAT format variation, not a widened match: Shape B still requires the
    ``Com.`` token by its own recognised alias AND the very next column to
    carry real text, so a sheet lacking either -- no ``Descripcion`` token, no
    ``Com.`` token, or a blank column following ``Com.`` -- matches neither
    shape and still refuses.
    """
    if not _is_ordinal_header(_cell(values, 0)):
        return None
    try:
        offset_index = _required_header_index(values, "posic.")
        type_index = _required_header_index(values, "tipo")
    except ValueError as header_exc:
        _log.debug(
            "record-design header probe (%s): row %d missing required columns (%s); trying next",
            label,
            row_number,
            header_exc,
        )
        return None
    length_correction: RecordDesignHeaderCellCorrection | None = None
    try:
        length_index = _required_header_index(values, "lon")
    except ValueError:
        length_correction = header_corrections.get((sheet_name, row_number, "length"))
        if length_correction is None:
            _log.debug(
                "record-design header probe (%s): row %d missing required columns ('lon'); trying next",
                label,
                row_number,
            )
            return None
        length_index = length_correction.column_index
    complementary_index = _optional_header_index(values, "com", "comp")
    description_index = _optional_header_index(values, "descripcion")
    validation_index = _optional_header_index(values, "validacion", "oblig.")
    if description_index is None:
        if complementary_index is None:
            _log.debug(
                "record-design header probe (%s): row %d matches neither header shape "
                "(no 'descripcion' and no 'com'/'comp'); trying next",
                label,
                row_number,
            )
            return None
        caption_index = complementary_index + 1
        if caption_index >= len(values) or not coerce_cell_text(_cell(values, caption_index)):
            _log.debug(
                "record-design header probe (%s): row %d has 'com'/'comp' but no caption in the "
                "following column; trying next",
                label,
                row_number,
            )
            return None
        description_index = caption_index
        validation_index = None
    header = _WorkbookHeader(
        row_number=row_number,
        ordinal_index=0,
        offset_index=offset_index,
        length_index=length_index,
        type_index=type_index,
        complementary_index=complementary_index,
        description_index=description_index,
        validation_index=validation_index,
        content_index=_optional_header_index(values, "contenido"),
    )
    return header, length_correction


def _find_header(
    worksheet: Worksheet,
    header_corrections: _HeaderCorrectionIndex | None = None,
) -> tuple[_WorkbookHeader, RecordDesignHeaderCellCorrection | None]:
    sheet_name = worksheet.title.strip()
    for row_number, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        matched = _probe_header_row(
            tuple(row),
            row_number,
            label=f"xlsx {worksheet.title}",
            sheet_name=sheet_name,
            header_corrections=header_corrections or {},
        )
        if matched is not None:
            return matched
    raise RegistryValidationError(f"{worksheet.title!r} has no record-design header")


def _find_xls_header(
    worksheet: XlrdSheet,
    header_corrections: _HeaderCorrectionIndex | None = None,
) -> tuple[_WorkbookHeader, RecordDesignHeaderCellCorrection | None]:
    sheet_name = worksheet.name.strip()
    header_corrections = header_corrections or {}
    for rowx in range(min(10, worksheet.nrows)):
        matched = _probe_header_row(
            tuple(worksheet.row_values(rowx)),
            rowx + 1,
            label="xls",
            sheet_name=sheet_name,
            header_corrections=header_corrections,
        )
        if matched is not None:
            return matched
    raise RegistryValidationError(f"{worksheet.name!r} has no record-design header")


def _is_ordinal_header(value: object | None) -> bool:
    normalized = _normalise_header_cell(value)
    return normalized in {"no", "n"} or re.fullmatch(r"version \d+(?:\.\d+)*", normalized) is not None


def _cell(values: tuple[object, ...], index: int) -> object | None:
    return values[index] if index < len(values) else None


def _optional_text(value: object | None) -> str | None:
    cleaned = coerce_cell_text(value)
    return cleaned or None


def _ordinal_text(value: object | None) -> str | None:
    """Render a printed ordinal cell verbatim, including a non-numeric label.

    ``integral_floats_as_int=True`` because openpyxl hands back a whole-number
    ordinal cell as a ``float`` (``19.0``); rendering that as ``"19.0"`` would
    break BOTH the M390 auxiliary-header ordinal sequence (which compares
    against plain ``"1"``..``"13"``) and the dotted-component prefix match
    (``"19.1"``'s prefix must equal parent ``"19"``, not ``"19.0"``).
    """
    cleaned = coerce_cell_text(value, integral_floats_as_int=True)
    return cleaned or None


def _optional_header_text(values: tuple[object, ...], index: int | None) -> str | None:
    if index is None:
        return None
    return _optional_text(_cell(values, index))


def _required_text(value: object | None, sheet: str, row: int, field: str) -> str:
    """Render a required cell verbatim, as an integer where the sheet stored a float.

    ``integral_floats_as_int=True`` for the same reason :func:`_ordinal_text`
    carries it: a spreadsheet hands back a whole-number cell as a ``float``, so
    a ``Tipo`` of ``6`` arrives as ``6.0`` and renders as ``"6.0"``. AEAT never
    prints a type code that way, and the artifact is reader-dependent rather
    than a property of the design -- the same modelo 100 2016 design read from
    its ``.xls`` yielded ``"6.0"`` where its ``.xlsx`` conversion yielded
    ``"6"``, which is how this surfaced.

    This function serves only the ``Tipo`` column, so the coercion cannot reach
    a description or any other cell whose text might legitimately end in
    ``.0``.
    """
    cleaned = coerce_cell_text(value, integral_floats_as_int=True)
    if not cleaned:
        raise RegistryValidationError(f"{sheet!r} row {row} missing {field}")
    return cleaned


def _required_type_code(
    value: object | None,
    sheet: str,
    row: int,
    corrections: _TypeCorrectionIndex,
) -> tuple[str, RecordDesignFieldTypeCorrection | None]:
    """Return the row's ``Tipo`` value, applying a declared correction for a blank cell.

    A correction fires ONLY when the cell is genuinely blank AND a sidecar
    declares one for this exact ``(sheet, row)`` -- never as a fallback for a
    present-but-unreadable value, which stays a hard refusal exactly as
    before. This is the sole read path that can turn a "missing type" refusal
    into a read.

    Carries ``integral_floats_as_int=True`` for the same reason
    :func:`_required_text` does: this is the other read path for the same
    ``Tipo`` column, and leaving one of the two uncoerced would make the
    rendered type code depend on whether a correction sidecar happened to
    exist for the row.
    """
    cleaned = coerce_cell_text(value, integral_floats_as_int=True)
    if cleaned:
        return cleaned, None
    correction = corrections.get((sheet, row))
    if correction is not None:
        return correction.corrected_type, correction
    raise RegistryValidationError(f"{sheet!r} row {row} missing type")


def _field_description_text(
    values: tuple[object, ...],
    *,
    header: _WorkbookHeader,
    content: str | None,
    sheet: str,
    row: int,
) -> str:
    description = _optional_text(_cell(values, header.description_index))
    if description is not None:
        return description
    if content is not None:
        return content
    raise RegistryValidationError(f"{sheet!r} row {row} missing description")


def _int_or_none(value: object | None) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


#: The six folds this header comparison has always applied, as one translation
#: table. Every mapping is one character to one character, so a single
#: `str.translate` pass produces exactly the text the chained `str.replace`
#: calls did -- six passes over every cell became one.
#:
#: Deliberately NOT `core.text_fold.fold_diacritics`: that folds every combining
#: mark via NFKD, which would newly collapse characters this comparison has
#: always kept distinct (ñ -> n among them). Matching more headers is a parsing
#: behaviour change, not a speed-up, so the narrow table stays.
_HEADER_CELL_FOLD_TABLE = str.maketrans({"º": "o", "ó": "o", "í": "i", "á": "a", "é": "e", "ú": "u"})


@lru_cache(maxsize=4096)
def _fold_header_text(text: str) -> str:
    """Fold one already-coerced header cell for comparison.

    Split from :func:`_normalise_header_cell` so the pure text step can be
    memoised: a record design re-scans the same few header spellings across
    every row of every sheet, so the distinct inputs number in the dozens while
    the calls numbered sixteen million in one cold `aeat app modelo list`.
    """
    return text.casefold().translate(_HEADER_CELL_FOLD_TABLE)


def _normalise_header_cell(value: object | None) -> str:
    return _fold_header_text(coerce_cell_text(value))


def _required_header_index(values: tuple[object, ...], header_name: str) -> int:
    index = _optional_header_index(values, header_name)
    if index is None:
        raise RegistryValidationError(f"missing workbook header {header_name!r}")
    return index


def _header_token(value: str) -> str:
    """Return a header cell's identity, ignoring AEAT's abbreviating full stop.

    AEAT abbreviates header labels inconsistently WITHIN one workbook: Modelo
    115 writes ``Lon`` on its first sheet and ``Lon.`` on its second. Exact
    membership therefore matched one sheet and missed the other, and because a
    sheet failing header detection is skipped, the entire record body was
    dropped while the file looked healthy.

    The stop is typography, not identity, so it is ignored on BOTH sides rather
    than by enrolling each spelling separately -- which is what the accepted set
    already does ad hoc for ``posic.`` and ``oblig.``, and what would have to be
    remembered again for every future label.
    """
    return value.rstrip(".")


def _header_names_one_column(cell: str, expected: str) -> bool:
    """Whether a header cell names the column ``expected`` names.

    AEAT ABBREVIATES BY TRUNCATION, and inconsistently within a single workbook:
    the length column is ``Lon`` on one Modelo 115 sheet and ``Lon.`` on the next,
    and ``Long.`` throughout Modelo 100 and on Modelo 714's header sheet. Matching
    on truncation-compatibility rather than against an enrolled list of spellings
    is what stops the next abbreviation needing a code change -- and the enrolled
    pairs already in this module (``com``/``comp``, ``validacion``/``oblig.``) are
    that treadmill visible in progress.

    Measured across every bundled workbook design before shipping: 117 sources
    unchanged, 6 improved, ZERO degraded. Modelo 714's four editions go from a
    silently dropped sheet to a complete read, and Modelo 100's 2019 design from
    refusing outright to 41 sheets.

    The three-character floor stops a one- or two-letter cell prefix-matching its
    way onto a column it does not name; without it a stray ``N`` or ``No`` cell
    would claim whichever column happened to start with it.
    """
    if cell == expected:
        return True
    shorter, longer = sorted((cell, expected), key=len)
    return len(shorter) >= 3 and longer.startswith(shorter)


def _optional_header_index(values: tuple[object, ...], *header_names: str) -> int | None:
    expected = [_header_token(name) for name in header_names]
    for index, value in enumerate(values):
        cell = _header_token(_normalise_header_cell(value))
        if cell and any(_header_names_one_column(cell, candidate) for candidate in expected):
            return index
    return None


def _total_label_index(values: tuple[object, ...]) -> int | None:
    for index, value in enumerate(values):
        if _normalise_header_cell(value) in {"total", "total:"}:
            return index
    return None


def _positive_integer_after(values: tuple[object, ...], label_index: int) -> int | None:
    for candidate in values[label_index + 1 :]:
        total = _int_or_none(candidate)
        if total is not None and total > 0:
            return total
    return None


#: The space between LENGTH and TYPE is optional because the PDF text layer
#: loses it: modelo 100's 2009 through 2011 editions all write
#: ``5 9 1A Indicador de pagina complementaria`` for a row that is length 1,
#: type A. Requiring the space dropped the row and reported the byte it
#: declares -- position 9 -- as a hole in a record that was otherwise whole.
#:
#: The split stays unambiguous because length is digits and type is a closed
#: alternation, so ``1A`` can only be 1 + A. Measured over every bundled PDF
#: before allowing it, this admits three lines in three designs, all the same
#: genuine row.
#: ``Tit`` is a naturaleza in its own right, not a typo. Modelo 100 uses it
#: for the one-byte code naming WHICH titular an entry belongs to, and the
#: rows say so themselves: every occurrence ends its description in
#: "... - Titular" or "... - Contribuyente". Across the six bundled editions
#: that use it there are 454 such rows and every one declares length 1, which
#: is what a holder code is.
#:
#: Leaving it unrecognised dropped all 454, and because they sit BETWEEN
#: read rows the loss showed up as scattered single-byte holes -- 12, 192,
#: 372, 581 in one record alone -- which reads like corpus damage rather
#: than one missing token.
#: A trailing period after the type is abbreviation punctuation, not a
#: different token: modelo 131 writes ``52 464 13 An. Complementaria (7) -
#: Numero de Justificante anterior``. The narrative path has always accepted
#: it -- ``_naturaleza_or_none`` strips ' .' before matching -- so this only
#: brings the compact path into line with the recogniser beside it.
#:
#: Three lines in three designs, and they are the whole of modelo 131's
#: reported damage: each edition lost this one 13-byte row and reported it as
#: a dropped run at 464-476, 477-489 and 503-515 respectively.
_COMPACT_PDF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<length>\d+)\s*(?P<type>An|Num|Tit|N|A)\.?\s+(?P<text>.+)$",
    re.IGNORECASE,
)
#: A PDF row declaring the physical end of record. Its DESCRIPTION half composes
#: the SHARED terminator phrase rather than carrying a second private spelling, so
#: the workbook splitter and this recogniser cannot drift on what a CRLF row is.
#: They already had: this one has known the terminator since it was written, while
#: the workbook path refused every design that declared one.
_COMPACT_PDF_CRLF_ROW_RE = re.compile(
    r"^\s*(?P<ordinal>\d+)\s+(?P<offset>\d+)\s+(?P<type>An|Num|N|A)\s+"
    rf"(?P<text>(?:{_RECORD_TERMINATOR_PHRASE}).*)$",
    re.IGNORECASE,
)
#: One narrative-PDF position row: ``<start>[-<end>] <naturaleza> <description>``.
#:
#: The naturaleza is captured LOOSELY here and validated afterwards by
#: :func:`_naturaleza_or_none`, rather than spelled out as a closed alternation.
#: AEAT's own spelling varies across the bundled corpus -- gender ("Numérica"
#: beside "Numérico"), accent placement ("Alfanúmerico" for "Alfanumérico") and
#: outright typos ("Afabético") all ship -- and a closed alternation turns every
#: variant into a SILENTLY dropped row, because a line that fails to match is
#: indistinguishable from ordinary prose.
#:
#: The dash alternative accepts AEAT's genuine dash-naturaleza rows
#: ("176-237 -------------- BLANCOS") but MUST NOT be followed by a digit.
#: Without that guard the engine backtracks on any row whose naturaleza it does
#: not recognise, re-reads the RANGE SEPARATOR as the type, and manufactures a
#: one-byte field at the start position carrying the rest of the line as its
#: description. Both known fabrications come from that one path: Modelo 190's
#: phantom @108+1 out of the prose "(posiciones 108 - 147) tenga contenido", and
#: Modelo 156's "36 - 75 Afabético APELLIDOS Y NOMBRE" read as a 1-byte field
#: instead of a 40-byte campo. An invented position is the worst failure
#: available here: it inflates the denominator, so an author chasing the ratio
#: would write bytes AEAT never defined -- for Modelo 156, truncating a real
#: taxpayer's name to one character. A genuine dash-naturaleza row is always
#: followed by its description, never by a number, so the guard costs nothing.
#:
#: UNDERSCORES count as that same rule. AEAT draws the empty naturaleza cell
#: with whatever character the source used: most designs use dashes
#: ("226-487 -------------- BLANCOS"), Modelo 185 uses underscores
#: ("58 ______ BLANCOS."). Both mean the same thing -- no naturaleza, the
#: description says BLANCOS -- and ``[^\W\d_]+`` cannot pick an underscore run
#: up because it excludes ``_`` by construction, so without this the rows drop.
#: Measured across every bundled PDF design before widening: exactly TWO rows in
#: ONE design newly match, both of them ``BLANCOS`` fill in Modelo 185, whose
#: two sheets were each skipped for the resulting hole and left that design
#: yielding nothing at all.
#: A design may letter a field row as an item of a lettered group before
#: giving its position: modelo 604's English ATF design writes
#: ``A. 325 Alphabetic CORRECTION.`` and ``A. 350-367 Numeric CORRECTED TAX``
#: for the two rows of its correction block, while every other row in that
#: record opens with the position. Requiring the position first dropped both,
#: leaving a one-byte hole at 325 that read as a dropped row.
#:
#: The marker is admitted, NOT the looseness it could imply: the naturaleza
#: guard still decides, so a prose line opening ``A. 15 personas`` is rejected
#: exactly as ``15 personas`` is. Measured over every bundled PDF before
#: allowing it, this admits two lines in one design and nothing else.
_NARRATIVE_PDF_ROW_RE = re.compile(
    r"^\s*(?:[^\W\d_]{1,2}\.\s+)?(?P<start>\d+)(?:\s*[-\u2013]\s*(?P<end>\d+))?\s+"
    r"(?P<type>[^\W\d_]+|[-\u2013_]+(?!\s*\d))\s*"
    r"(?P<text>.*)$",
    re.IGNORECASE,
)
#: ``Pag`` is abbreviated WITH a period in some designs and without in others
#: -- Modelo 360 heads its page two "Pag. 2 DISENO DE REGISTRO 25/03/2021" --
#: and requiring whitespace straight after the stem lost every period-form
#: heading, leaving that record body unidentified and the design partly read.
_PDF_PAGE_RECORD_RE = re.compile(r"^P[áa]g\.?\s+(?P<page>\d+)\s+DISE[ÑN]O DE REGISTRO\b", re.IGNORECASE)
#: Some designs head a further record "Anexo" in the SAME running-header shape
#: their numbered pages use, rather than as the quoted `ANEXO <<...>>` title
#: :data:`_PDF_RECORD_ANEXO_HEADING_RE` recognises. Modelo 840 writes
#: "Pag 1 DISENO DE REGISTRO", "Pag 2 DISENO DE REGISTRO" and then
#: "Anexo DISENO DE REGISTRO" for its third record, whose own opening tag is
#: `<T840030>` beside the pages' `<T840010>` and `<T840020>`. Without this the
#: third record has no read identity and the whole design reports PARTIAL --
#: correctly, because a real record body was going unread.
_PDF_ANEXO_PAGE_RECORD_RE = re.compile(r"^Anexo\s+DISE[ÑN]O DE REGISTRO\b", re.IGNORECASE)
_PDF_RECORD_HEADING_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?(?:TIPO DE REGISTRO|Tipo de registro|RECORD TYPE|Record [Tt]ype)\s+"
    r"(?P<record>\d+)\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)
#: English AEAT record-design translations also head a record with the reversed
#: word order "TYPE <n> RECORD: <title>" (observed in the modelo 604 ATF English
#: appendix), distinct from the "RECORD TYPE <n>: <title>" order above.
_PDF_RECORD_HEADING_REVERSED_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?TYPE\s+(?P<record>\d+)\s+RECORD\s*:\s*(?P<title>.+)$",
    re.IGNORECASE,
)
#: A THIRD Spanish word order -- "REGISTRO DE TIPO <n>: <title>" -- which AEAT
#: uses at least as often as the two above: modelos 165, 180, 182, 184, 187, 188,
#: 193, 296 and 345 all head their perceptor/declarado record with it, several
#: separating number from title with a full stop rather than a colon.
#:
#: DELIBERATELY NOT A SPLITTING HEADING. The same phrase occurs inside ordinary
#: field prose ("Consignar lo contenido en estas mismas posiciones del registro
#: de tipo 1.", "... del registro de tipo 2. Registro de perceptor, toma el valor
#: 1) ..."), so treating a match as a record boundary on the text alone would
#: manufacture records that do not exist -- the opposite defect, and a worse one,
#: because an invented record inflates every coverage denominator derived from
#: the design. A match here only STAGES a name; whether a record actually starts
#: is decided by geometry, in :meth:`_PdfParseState._begins_a_new_record_body`.
_PDF_RECORD_HEADING_TYPE_LAST_RE = re.compile(
    r"^(?:[A-Z]\.?\s*-?\s*)?REGISTRO DE TIPO\s+(?P<record>\d+)\s*[:.]\s*(?P<title>\S.*)$",
    re.IGNORECASE,
)


#: A FOURTH shape: an annex record headed by its own quoted title, which is how
#: Modelo 296 heads the two anexos that follow its perceptor record --
#: ``ANEXO <<VALORES NEGOCIABLES. RELACION DE PAGO A CONTRIBUYENTES`` and
#: ``ANEXO <<VALORES NEGOCIABLES. RELACION DE CERTIFICADOS DE PAGO``, each with
#: its hoja discriminator on the following line. Both were read as prose, so both
#: record bodies arrived unidentified and the design never read whole.
#:
#: The opening quotation mark is REQUIRED, and that is what separates a titled
#: annex record from a prose reference to a numbered annex ("... que figuran en
#: el anexo II de la Orden EHA/3496/2011"). Like the type-last shape above this
#: only STAGES a name; geometry decides whether a record starts.
_PDF_RECORD_ANEXO_HEADING_RE = re.compile(
    r"^ANEXO\s+[«“\"'](?P<title>[^»”\"']{4,120})",
    re.IGNORECASE,
)
#: A bare anexo IDENTIFIER standing alone on its line: modelo 100's 2014 edition
#: heads its extra record ``Anexo B.5``, with no quoted title for
#: :data:`_PDF_RECORD_ANEXO_HEADING_RE` to take and no ``DISEÑO DE REGISTRO``
#: for :data:`_PDF_ANEXO_PAGE_RECORD_RE`. Without it that record body restarts
#: at position 1 with no read identity and the design reports PARTIAL.
#:
#: Anchored to the WHOLE line and to the ``letter.digit`` shape, so a sentence
#: mentioning an anexo cannot match: the identifier must be all the line says.
_PDF_RECORD_BARE_ANEXO_RE = re.compile(r"^ANEXO\s+(?P<tag>[A-Z]\.\d{1,2})$", re.IGNORECASE)

#: A bare ``<modelo>-<page>`` tag standing alone on its line, which is how the
#: Modelo 100 PDFs head each of their record bodies -- "100-01", "100-02" and so
#: on, printed above the ``Nº Posic. Long. Tipo`` column header. It is the same
#: naming AEAT uses for the Modelo 714 workbook tabs ("714-01 Patrimonio"),
#: which arrive named because they are sheet tabs; in a PDF the tag is only a
#: line of text and nothing was reading it.
#:
#: Anchored to the WHOLE line, which is what keeps it from eating a position
#: range: a field row always carries a naturaleza and a description after its
#: range, so a line holding nothing but the tag is never one. Measured across
#: every bundled PDF design before adding it: six designs match, all six are
#: Modelo 100, and every occurrence names that design's own modelo. Like its
#: sibling above it only STAGES a name -- geometry still decides whether a
#: record starts -- so a tag appearing anywhere else stays inert.
_PDF_RECORD_MODELO_PAGE_TAG_RE = re.compile(r"^(?P<tag>\d{3}-\d{2})$")


@dataclass(slots=True)
class _PdfFieldDraft:
    sheet: str
    row: int
    ordinal: str | None
    offset: int
    length: int
    type_code: str
    description_parts: list[str] = field(default_factory=list)
    content_parts: list[str] = field(default_factory=list)

    def append_continuation(self, line: str) -> None:
        if not self.description_parts or (not self.content_parts and _looks_like_title_continuation(line)):
            self.description_parts.append(line)
            return
        self.content_parts.append(line)

    def finish(self) -> RecordDesignField:
        description = _join_pdf_parts(self.description_parts)
        if not description and self.type_code == "Blancos":
            # A fill run needs no description: AEAT writes the naturaleza alone
            # ("58 BLANCO", "187-390 BLANCOS") because there is no datum to name.
            # Demanding one here discarded the row, and a discarded fill run
            # leaves a hole that reads as "the reader lost a field".
            description = "Blancos"
        if not description:
            raise RegistryValidationError(f"{self.sheet!r} PDF row {self.row} missing description")
        return RecordDesignField(
            sheet=self.sheet,
            row=self.row,
            ordinal=self.ordinal,
            offset=self.offset,
            length=self.length,
            type_code=self.type_code,
            complementary=None,
            description=description,
            validation=None,
            content=_join_pdf_parts(self.content_parts) or None,
        )


@dataclass(slots=True)
class _PdfSheetDraft:
    name: str
    fields: list[RecordDesignField] = field(default_factory=list)
    current: _PdfFieldDraft | None = None
    #: Whether the source NAMED this record body. ``False`` marks a body the
    #: geometry proved exists -- its positions restart at 1 -- whose heading the
    #: parser did not recognise, so its identity is unknown. Such a body is
    #: reported as a skipped sheet rather than returned, because handing back a
    #: record under a name nobody read would be an invented record identity.
    identified: bool = True
    #: The source row at which this body's first position was seen, used to name
    #: an unidentified body by where it is rather than by what it might be.
    opened_at_row: int | None = None
    #: Rows carrying a position RANGE and a description but no naturaleza, held
    #: for :meth:`fill_unread_gaps`. Staged rather than admitted on sight because
    #: the shape is dominated by prose; see :func:`_unnamed_position_candidate`.
    unnamed_candidates: list[_PdfRow] = field(default_factory=list)
    #: Declared corrections that authorised a staged candidate, recorded so a
    #: design read only BECAUSE of a declaration is never reported as one AEAT
    #: published cleanly.
    applied_corrections: list[RecordDesignSinglePositionCorrection] = field(default_factory=list)
    #: Rows carrying a length, a naturaleza and a description but NO position,
    #: paired with the position the row before them implies. The mirror image of
    #: ``unnamed_candidates``, and admitted by the same containment test.
    headless_candidates: list[_PdfRow] = field(default_factory=list)

    def has_started(self) -> bool:
        """Whether any field of this record body has been seen yet."""
        return bool(self.fields) or self.current is not None

    def start_field(self, row: _PdfRow) -> None:
        self.finish_current()
        self.current = _PdfFieldDraft(
            sheet=self.name,
            row=row.source_row,
            ordinal=row.ordinal if row.ordinal is not None else str(len(self.fields) + 1),
            offset=row.offset,
            length=row.length,
            type_code=row.type_code,
            description_parts=[row.description] if row.description else [],
        )

    def finish_current(self) -> None:
        if self.current is None:
            return
        self.fields.append(self.current.finish())
        self.current = None

    def fill_unread_gaps(self) -> None:
        """Admit staged candidates that fall wholly inside a span no row claims.

        A fixed-width record is contiguous, so an interior span no read row
        covers is a row that was dropped, not a span AEAT left undescribed. Where
        a staged candidate covers exactly such a span it is the dropped row, and
        admitting it is the only reading that makes the record whole.

        The containment test is what keeps this safe. A candidate overlapping any
        claimed position is discarded, so a prose line restating a field's own
        range -- the shape this parser must keep refusing -- can never be
        admitted: its range is claimed by the very field it describes. Only a
        genuine hole can absorb one.

        Modelo 296 is the worked case: its perceptor record declares 500
        positions and read none of 413-432, because AEAT printed
        ``413-432 CODIGO LEI DEL PERCEPTOR`` with no naturaleza while its
        neighbour ``433-452 Alfanumerico NIF EN EL PAIS...`` carries one.
        """
        staged = [*self.unnamed_candidates, *self.headless_candidates]
        if not staged or not self.fields:
            return
        claimed: set[int] = set()
        for read in self.fields:
            claimed.update(range(read.offset, read.offset + read.length))
        admitted: list[RecordDesignField] = []
        for candidate in staged:
            span = range(candidate.offset, candidate.offset + candidate.length)
            if claimed.isdisjoint(span):
                admitted.append(
                    RecordDesignField(
                        sheet=self.name,
                        row=candidate.source_row,
                        ordinal=None,
                        offset=candidate.offset,
                        length=candidate.length,
                        type_code=candidate.type_code,
                        description=candidate.description,
                    ),
                )
                claimed.update(span)
        if admitted:
            self.fields = sorted([*self.fields, *admitted], key=lambda read: read.offset)

    def fill_declared_desglose_gaps(self) -> None:
        """Admit a dropped sub-field whose absence AEAT's own declared COUNT proves.

        :meth:`fill_unread_gaps` admits only into a span NO read row claims, and
        that guard is deliberately conservative: the candidate shape is
        overwhelmingly prose, because AEAT routinely opens a field's description
        with that field's own range, and 41 bundled designs do. Admitting into a
        claimed span on containment alone would turn that prose into invented
        positions -- the Modelo 190 ``@108+1`` and Modelo 156 one-byte
        ``APELLIDOS`` class of fabrication, the worst failure available here.

        A desglose parent's span is the one place that guard is too strong, and
        only when the design itself supplies the arithmetic. Where AEAT writes
        "Este campo se subdivide en cuatro", the count is the authority stating
        how many sub-fields exist. If fewer were read, the run leaves a hole, and
        a staged candidate fills that hole EXACTLY such that the sub-fields then
        tile the parent end to end AND number exactly the declared count, then
        the candidate is the dropped row and nothing else fits: three
        independent facts -- the count, the tiling, and the exact hole -- all have
        to agree at once.

        Modelo 184 is the worked case and, measured across every bundled PDF
        design, the ONLY site where all three agree. Its ``@147+9`` says "se
        subdivide en cuatro:" over sub-fields at 147, 148 and 149-150, leaving
        151-155 unread, because AEAT printed ``151-155 PORCENTAJE DE RENTA
        ATRIBUIBLE A MIEMBROS RESIDENTES`` with no naturaleza on the naming row
        while its neighbour ``149-150 Alfabetico CLAVE PAIS:`` carries one -- the
        same omission that cost Modelo 296 its ``413-432 CODIGO LEI``.

        The conjunction is what keeps this safe, and each clause excludes real
        sites. Modelo 038's eleven chart-geometry artefacts declare no count and
        are refused at the first clause. Modelos 165 and 280 declare TWO, already
        read two, and hold a one-byte gap: admitting there would make three where
        AEAT says two, so the count clause refuses them and their genuine
        one-byte defect is left visible rather than papered over.
        """
        if not self.unnamed_candidates or not self.fields:
            return
        # Grouped, never a single candidate per offset: AEAT nests these. Modelo
        # 184 stages BOTH "151-155 PORCENTAJE..." and the "151- 153 ENTERO" it
        # subdivides into, so keying one candidate per offset silently picks
        # whichever was read last and loses the one that actually fits.
        by_offset: dict[int, list[_PdfRow]] = {}
        for candidate in self.unnamed_candidates:
            by_offset.setdefault(candidate.offset, []).append(candidate)
        admitted: list[RecordDesignField] = []
        index = 0
        while index < len(self.fields):
            parent = self.fields[index]
            run: list[RecordDesignField] = []
            cursor = index + 1
            while cursor < len(self.fields):
                child = self.fields[cursor]
                if (
                    child.offset >= parent.offset
                    and child.offset + child.length <= parent.offset + parent.length
                    and (child.offset, child.length) != (parent.offset, parent.length)
                ):
                    run.append(child)
                    cursor += 1
                else:
                    break
            index = cursor if run else index + 1
            declared = _declared_subdivision_count(parent)
            # ``run`` may be EMPTY. Modelo 190's 81-107 and 108-147 each say
            # "Este campo se subdivide en tres/cuatro" and NONE of their
            # sub-rows was read, so requiring an already-read child would
            # skip exactly the designs where the whole desglose went unread.
            # The declared count still carries the proof: the candidates must
            # tile the parent end to end AND number exactly what it declares.
            if declared is None or _tiles_exactly(parent, run) or len(run) >= declared:
                continue
            covered: set[int] = set()
            for child in run:
                covered.update(range(child.offset, child.offset + child.length))
            chosen = _solve_declared_desglose_holes(
                parent=parent,
                covered=covered,
                by_offset=by_offset,
                wanted=declared - len(run),
            )
            if chosen is None:
                continue
            fillers = [
                RecordDesignField(
                    sheet=self.name,
                    row=candidate.source_row,
                    ordinal=None,
                    offset=candidate.offset,
                    length=candidate.length,
                    type_code=candidate.type_code,
                    description=candidate.description,
                )
                for candidate in chosen
            ]
            if not _tiles_exactly(parent, sorted([*run, *fillers], key=lambda read: read.offset)):
                continue
            admitted.extend(fillers)
        if admitted:
            self.fields = sorted([*self.fields, *admitted], key=lambda read: read.offset)

    def finish(self, *, source_label: str) -> RecordDesignSheet:
        self.finish_current()
        self.fill_unread_gaps()
        self.fill_declared_desglose_gaps()
        self.fields = _fold_untagged_desglose_components(self.fields)
        total_positions = max((field.offset + field.length - 1 for field in self.fields), default=None)
        sheet = RecordDesignSheet(
            name=self.name,
            fields=tuple(self.fields),
            total_positions=total_positions,
            corrections=tuple(self.applied_corrections),
        )
        _validate_pdf_sheet(sheet, source_label=source_label)
        return sheet


@dataclass(frozen=True, slots=True)
class _PdfRow:
    source_row: int
    ordinal: str | None
    offset: int
    length: int
    type_code: str
    description: str


@dataclass(frozen=True, slots=True)
class _PdfWord:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True, slots=True)
class _PdfRect:
    x0: float
    x1: float
    top: float
    bottom: float
    width: float
    height: float
    fill: object | None


@dataclass(frozen=True, slots=True)
class _PdfPageSnapshot:
    lines: tuple[str, ...]
    words: tuple[_PdfWord, ...]
    rects: tuple[_PdfRect, ...]


@dataclass(frozen=True, slots=True)
class _VisualChartFragment:
    start: int
    end: int
    description: str


def _extract_pdf_text_lines(pdf_bytes: bytes, *, source_label: str) -> tuple[str, ...]:
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:  # pragma: no cover - pdfium parser surface
        raise RegistryValidationError(f"pypdfium2 could not open record-design PDF {source_label}: {exc}") from exc
    try:
        lines: list[str] = []
        for page in document:
            text_page = page.get_textpage()
            try:
                lines.extend(text_page.get_text_range().splitlines())
            finally:
                text_page.close()
                page.close()
        return tuple(lines)
    finally:
        document.close()


def _extract_pdfplumber_text_lines(pdf_bytes: bytes, *, source_label: str) -> tuple[str, ...]:
    import pdfplumber

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            return tuple(line for page in pdf.pages for line in _extract_pdf_page_lines(page))
    except Exception as exc:  # pragma: no cover - defensive; pdfplumber surface
        raise RegistryValidationError(f"pdfplumber could not open record-design PDF {source_label}: {exc}") from exc


def _uses_page_record_layout(lines: tuple[str, ...]) -> bool:
    return any(_pdf_page_name(_clean_pdf_line(line)) is not None for line in lines)


def _snapshot_pdf_page(page: Page) -> _PdfPageSnapshot:
    return _PdfPageSnapshot(
        lines=_extract_pdf_page_lines(page),
        words=tuple(
            _PdfWord(
                text=str(word["text"]),
                x0=float(word["x0"]),
                x1=float(word["x1"]),
                top=float(word["top"]),
                bottom=float(word["bottom"]),
            )
            for word in page.extract_words()
        ),
        rects=_snapshot_pdf_chart_rects(page),
    )


def _snapshot_pdf_chart_rects(page: Page) -> tuple[_PdfRect, ...]:
    """Return the painted geometry a visual record-design chart can use.

    AEAT's older diagram PDFs encode the same filled horizontal field rule as
    either a PDF rectangle or a closed PDF curve, depending on the producer.
    The visual reader consumes only thin, black, horizontal geometry later; it
    must therefore preserve both source representations here.  This remains a
    physical-document normalisation, not a modelo-specific recovery.
    """
    return tuple(
        _PdfRect(
            x0=float(shape["x0"]),
            x1=float(shape["x1"]),
            top=float(shape["top"]),
            bottom=float(shape["bottom"]),
            width=float(shape["width"]),
            height=float(shape["height"]),
            fill=shape.get("non_stroking_color"),
        )
        for shape in (*page.rects, *page.curves)
    )


def _extract_pdf_page_lines(page: Page) -> tuple[str, ...]:
    text = page.extract_text() or ""
    return tuple(text.splitlines())


@dataclass(frozen=True, slots=True)
class _PdfSheetResult:
    """One finished record body and whether the source named it."""

    sheet: RecordDesignSheet
    identified: bool
    opened_at_row: int | None


#: A record's own closing identifier, which names the modelo and the page it
#: belongs to: ``</T200001>`` closes page 1 of modelo 200. AEAT writes it as the
#: last field of every page record in the designs that head their records with
#: nothing a heading recogniser can see.
_PDF_RECORD_END_IDENTIFIER_RE = re.compile(r"</T(?P<modelo>\d{3})(?P<page>[A-Z0-9]{2,5})>")
#: The same fact stated at the TOP of the record, as the contenido of its
#: ``Página`` row: ``3 6 3 An Página. OBLIGATORIO Constante "001"``.
_PDF_PAGE_CONSTANT_RE = re.compile(r'Constante\s*"(?P<page>[A-Z0-9]{2,5})"')


#: The widths AEAT writes a página constant in, observed across the bundled
#: corpus: two digits (modelo 763), three (modelo 200), five (modelo 390's
#: composite). Four is deliberately absent -- that is an ejercicio.
_PAGE_CONSTANT_WIDTHS: Final[frozenset[int]] = frozenset({2, 3, 5})


def _page_label_from_token(token: str) -> str:
    """The page a record's página constant names, as the design writes it.

    Most designs write a number directly: modelo 200's ``001``, modelo 763's
    ``02``. Two shapes are not plain numbers and both are read as AEAT states
    them.

    Modelo 390's 2015 edition writes a five-digit composite, ``01000`` through
    ``08000``, where the leading digits are the page and the trailing ``000`` is
    a sub-counter. That split is not assumed: the design cross-checks it, since
    the record its running header names ``Pag. 1`` is the record declaring
    ``Constante "01000"``.

    Modelo 200 writes an ALPHABETIC page for one record -- ``Constante "DID"``,
    closing ``</T200DID>`` -- and its own vector example lists that record in
    the page sequence beside the numbered ones
    (``...017018019019DIDFIN``). There is no number to derive, so the token is
    the label.
    """
    if token.isdigit():
        if len(token) == 5 and token.endswith("000"):
            return str(int(token[:2]))
        return str(int(token))
    return token


def _recovered_record_identity(sheet: RecordDesignSheet) -> str | None:
    """Name an unheaded record body from the identity it declares about itself.

    Some AEAT designs never head a record with a title. Each record states which
    page it is twice: as the ``Constante "006"`` of its Página field, and as the
    ``</T200006>`` closing identifier AEAT requires as the record's last field.
    Both are declared required CONTENT, so reading them is recovery rather than
    guesswork.

    The closing identifier is preferred, because it names the modelo as well as
    the page and a stray constant elsewhere in the body cannot imitate it. It is
    set aside in exactly one circumstance: when its page component is not as
    wide as the Página field DECLARES that component to be. The identifier is a
    concatenation, so a lost digit inside it is silent -- modelo 390's seventh
    record closes ``</T3900700>``, seven digits where its siblings carry eight,
    which read as page 700. The field's own length is what exposes that, and
    where the two disagree without such a width contradiction the identifier is
    still trusted, because nothing says which side is the corrupt one.

    The Página strategy is keyed on GEOMETRY, never on the word "Página". These
    designs are published as PDFs whose text layer does not survive decoding
    intact -- the label arrives as ``P?gina`` -- so a reader matching the
    Spanish label would work on the editions that decode cleanly and fail on the
    ones that do not. AEAT fixes the geometry instead: the modelo constant at
    positions 3-5 and the page constant immediately after it. Requiring BOTH is
    what makes this safe, since a lone constant elsewhere cannot satisfy it, and
    the constant must be exactly as wide as its field declares.

    Returns ``None`` when the body declares neither identity, leaving it
    unidentified and on the worklist exactly as before. Recovering a name the
    record did not state would be inventing an identity, which is worse than
    reporting the gap.
    """
    by_offset = {field.offset: field for field in sheet.fields}
    modelo_field, page_field = by_offset.get(3), by_offset.get(6)
    declared_page: str | None = None
    if (
        modelo_field is not None
        and page_field is not None
        and modelo_field.length == 3
        and _pdf_declared_constant(modelo_field) is not None
    ):
        candidate = _pdf_declared_constant(page_field)
        # Two conditions, and both earn their place. The constant must be as
        # wide as its own field declares -- that is what lets modelo 763's two
        # digits, modelo 200's three and modelo 390's five all be read without a
        # reader-side assumption. And the width must be one AEAT actually uses
        # for a page: a FOUR-digit constant at this position is an ejercicio,
        # ``Constante "2011"``, and self-consistency alone would happily read it
        # as page 2011.
        if candidate is not None and len(candidate) == page_field.length and page_field.length in _PAGE_CONSTANT_WIDTHS:
            declared_page = candidate

    for design_field in reversed(sheet.fields):
        for text in (design_field.content, design_field.description, design_field.validation):
            if not text:
                continue
            match = _PDF_RECORD_END_IDENTIFIER_RE.search(str(text))
            if match is None:
                continue
            closing = match.group("page")
            # The closing identifier is matched anywhere in a field's text, so a
            # token bled in from a neighbouring record can be picked up. That is
            # tolerable for a numeric page, which the width check still guards,
            # but not for an ALPHABETIC one: modelo 200's ``</T200DID>`` appears
            # in prose inside other records, and reading it there renamed a
            # 1,618-field record after the token that belongs to a 45-field one.
            # An alphabetic page is therefore taken only from the Página field,
            # which geometry anchors.
            if not closing.isdigit():
                break
            if declared_page is not None and len(closing) != len(declared_page):
                return f"Pág. {_page_label_from_token(declared_page)}"
            return f"Pág. {_page_label_from_token(closing)}"

    if declared_page is not None:
        return f"Pág. {_page_label_from_token(declared_page)}"
    return None


def _pdf_declared_constant(field: RecordDesignField) -> str | None:
    """The three-digit constant a field declares as its required content."""
    for text in (field.content, field.description, field.validation):
        if not text:
            continue
        match = _PDF_PAGE_CONSTANT_RE.search(str(text))
        if match is not None:
            return match.group("page")
    return None


def _unidentified_record_body_name(row_number: int) -> str:
    """Name an unnamed record body by WHERE it is, never by what it might be."""
    return f"<unidentified record body beginning at source row {row_number}>"


class _PdfParseState:
    """Mutable state for the PDF record-design line parser.

    Encapsulates the locals (``current`` draft sheet, ``in_table`` flag,
    ``pending_name`` carried across page-name boundaries, ``pending_record_name``
    staged by a candidate record heading) so the per-line dispatch can mutate
    them without threading out-parameters through every helper.
    """

    __slots__ = (
        "corrections",
        "current",
        "in_table",
        "pending_name",
        "pending_record_name",
        "repair_glued_rows",
        "results",
        "source_label",
    )

    def __init__(
        self,
        *,
        source_label: str,
        corrections: _CorrectionIndex = _EMPTY_CORRECTIONS,
        repair_glued_rows: bool = False,
    ) -> None:
        self.repair_glued_rows = repair_glued_rows
        self.results: list[_PdfSheetResult] = []
        self.current: _PdfSheetDraft | None = None
        self.in_table: bool = False
        self.pending_name: str | None = None
        self.pending_record_name: str | None = None
        self.source_label = source_label
        self.corrections = corrections

    def finalise(self) -> RecordDesignExtraction:
        """Return the parsed records, naming every one the parser did not read.

        Three things land in ``skipped`` rather than being dropped, and each was
        previously invisible:

        * a record heading the parser recognised but found no field rows under;
        * a record body whose existence geometry proves -- its positions restart
          at 1 -- but whose heading the parser did not recognise, so it has no
          identity to return it under;
        * both together.

        The rule is one sentence: A READ THAT RETURNS FEWER RECORDS THAN THE
        DOCUMENT CONTAINS MUST NEVER REPORT COMPLETE. Every one of these makes
        :attr:`RecordDesignExtraction.is_complete` false, so
        :meth:`RecordDesignExtraction.require_complete` -- the guard that exists
        precisely to catch an incomplete read -- can finally see them.
        """
        self._close_current_body()
        self._recover_unidentified_bodies()
        read = tuple(result.sheet for result in self.results if result.identified and result.sheet.fields)
        if not read:
            raise RegistryValidationError("record-design PDF did not contain parseable field rows")
        read = _recover_inline_constants(read)
        # A sheet whose rows do not tile its own declared extent was not read as
        # published, so it is reported as SKIPPED rather than handed over as if
        # it were whole. See :func:`contiguity_failure`.
        broken = {sheet.name: reason for sheet in read if (reason := contiguity_failure(sheet)) is not None}
        return RecordDesignExtraction(
            source=self.source_label,
            sheets=tuple(sheet for sheet in read if sheet.name not in broken),
            skipped=(
                *(
                    RecordDesignSkippedSheet(name=result.sheet.name, reason=_skipped_record_reason(result))
                    for result in self.results
                    if not (result.identified and result.sheet.fields)
                ),
                *(RecordDesignSkippedSheet(name=name, reason=reason) for name, reason in broken.items()),
            ),
        )

    def _recover_unidentified_bodies(self) -> None:
        """Give every unheaded body the identity it declares about itself.

        A recovered name must be UNIQUE within the design. Two bodies resolving
        to one name would silently merge two records into one identity, which is
        the failure the unidentified-body report exists to prevent -- so a
        collision leaves both on the worklist rather than picking a winner.
        """
        taken = {result.sheet.name for result in self.results if result.identified}
        recovered: dict[int, str] = {}
        seen: dict[str, int] = {}
        for index, result in enumerate(self.results):
            if result.identified or not result.sheet.fields:
                continue
            name = _recovered_record_identity(result.sheet)
            if name is None or name in taken:
                continue
            if name in seen:
                recovered.pop(seen[name], None)
                continue
            seen[name] = index
            recovered[index] = name
        for index, name in recovered.items():
            result = self.results[index]
            self.results[index] = _PdfSheetResult(
                sheet=result.sheet.model_copy(update={"name": name}),
                identified=True,
                opened_at_row=result.opened_at_row,
            )

    def feed(self, line: str, row_number: int) -> None:
        if not line or _is_pdf_footer(line):
            return
        if self._consume_page_name(line):
            return
        if self._consume_record_heading(line):
            return
        self._stage_candidate_record_name(line)
        if self._consume_table_header(line):
            return
        if self._consume_title_continuation(line):
            return
        if _is_pdf_page_heading(line):
            return
        if self._consume_field_row(line, row_number):
            return
        self._stage_unnamed_position_candidate(line, row_number)
        self._stage_headless_tail(line, row_number)
        self._consume_field_continuation(line)

    def _stage_unnamed_position_candidate(self, line: str, row_number: int) -> None:
        """Hold a range-carrying row whose naturaleza AEAT omitted, for the gap fill.

        Staged even though the line ALSO reaches
        :meth:`_consume_field_continuation`, which is deliberate: the two are not
        alternatives, because at this point nothing knows whether the line is a
        dropped row or the continuation prose it far more often is. The gap fill
        decides later on geometry. Where it admits one, the text appears both on
        the admitted field and on the neighbouring description it was absorbed
        into -- accepted, because a duplicated description is visible and
        harmless while a dropped field is neither.
        """
        if self.current is None:
            return
        candidate = _unnamed_position_candidate(
            line,
            row_number,
            sheet=self.current.name,
            single_position_corrections=self.corrections.single_position_corrections,
        )
        if candidate is None:
            return
        self.current.unnamed_candidates.append(candidate)
        declared = self.corrections.single_position_corrections.get((self.current.name, candidate.offset))
        if declared is not None and candidate.length == 1:
            self.current.applied_corrections.append(declared)

    def _stage_headless_tail(self, line: str, row_number: int) -> None:
        """Hold a row that kept its length and naturaleza but lost its position.

        A page break can swallow a row's position half outright, leaving only
        ``17 N Sociedades de garantia reciproca - ...`` with the ``6 11`` above
        it gone. The position is not guessed from that line: it is taken from
        where the previous row ENDS, and the candidate is then subject to the
        same containment test every staged candidate faces -- admitted only if
        the span it would occupy is one no read row claims.

        That test is what makes this a reading. Three independent facts must
        agree before such a row appears: the position follows the previous row,
        the length is the one AEAT printed, and the span is exactly a hole. A
        fragment that would overlap anything already read is discarded, so a
        wrapped description restating a field's width can never be admitted.
        """
        if self.current is None or not self.repair_glued_rows:
            return
        match = _REVERSED_ROW_TAIL_RE.match(line)
        if match is None or _parse_pdf_row(line, row_number) is not None:
            return
        previous = self._last_seen_field()
        if previous is None:
            return
        naturaleza = _naturaleza_or_none(match.group("type"))
        if naturaleza is None and match.group("type") not in {"An", "Num", "N", "A", "Tit"}:
            return
        self.current.headless_candidates.append(
            _PdfRow(
                source_row=row_number,
                ordinal=None,
                offset=previous.offset + previous.length,
                length=int(match.group("length")),
                type_code=match.group("type"),
                description=match.group("description").strip(),
            ),
        )

    def _last_seen_field(self) -> _PdfFieldDraft | RecordDesignField | None:
        """The most recent field of the body under construction, finished or not."""
        if self.current is None:
            return None
        if self.current.current is not None:
            return self.current.current
        return self.current.fields[-1] if self.current.fields else None

    def _close_current_body(self) -> None:
        if self.current is None:
            return
        self.results.append(
            _PdfSheetResult(
                sheet=self.current.finish(source_label=self.source_label),
                identified=self.current.identified,
                opened_at_row=self.current.opened_at_row,
            ),
        )
        self.current = None

    def _open_body(self, name: str, *, identified: bool = True) -> None:
        self._close_current_body()
        self.current = _PdfSheetDraft(name, identified=identified)
        self.pending_record_name = None

    def _consume_page_name(self, line: str) -> bool:
        page_name = _pdf_page_name(line)
        if page_name is None:
            return False
        self.pending_name = page_name
        if self.current is not None and self.current.name != page_name:
            self._open_body(page_name)
        return True

    def _consume_record_heading(self, line: str) -> bool:
        heading_name = _pdf_record_heading_name(line)
        if heading_name is None:
            return False
        self._open_body(heading_name)
        self.in_table = False
        return True

    def _consume_table_header(self, line: str) -> bool:
        if not _is_pdf_header(line):
            return False
        if self.current is None:
            self.current = _PdfSheetDraft(self.pending_name or "PDF record design")
        self.in_table = True
        return True

    def _consume_title_continuation(self, line: str) -> bool:
        if self.in_table or self.current is None or self.current.fields:
            return False
        if not _looks_like_title_continuation(line):
            return False
        self.current.name = _normalise_pdf_sheet_name(_join_pdf_parts([self.current.name, line]))
        return True

    def _stage_candidate_record_name(self, line: str) -> None:
        """Remember a candidate record name WITHOUT acting on it.

        Staged rather than consumed on both counts: the line stays in the
        parser's ordinary pipeline exactly as before (so no field description
        loses text it used to carry), and no record boundary is created from
        the text. Only :meth:`_begins_a_new_record_body`, reading position
        geometry, decides a record actually starts -- at which point this name
        is used if one was staged since the last field row, and discarded
        otherwise. A candidate matched inside field prose is therefore inert.
        """
        candidate = _pdf_candidate_record_name(line)
        if candidate is not None:
            self.pending_record_name = candidate

    def _begins_a_new_record_body(self, row: _PdfRow) -> bool:
        """Whether ``row`` starts a record body distinct from the one being read.

        POSITION 1 OCCURS EXACTLY ONCE PER RECORD. A fixed-width record is
        contiguous from its first byte, so a row declaring position 1 while the
        body under construction already holds fields is not a continuation of
        that body under any reading -- it is the next record. This is geometry
        AEAT itself declares, not a text heuristic, so it holds for every
        heading spelling, every word order and every design that heads its
        records with no recognisable line at all.

        Modelo 180 is the worked case: AEAT heads its perceptor record
        ``REGISTRO DE TIPO 2: REGISTRO DE PERCEPTOR.`` -- a word order the
        heading recogniser did not know -- so seventeen perceptor positions
        were appended to the declarante record, the extraction returned ONE
        sheet for a two-record document, and it reported itself complete.
        """
        return self.current is not None and row.offset == 1 and self.current.has_started()

    def _consume_field_row(self, line: str, row_number: int) -> bool:
        row = _parse_pdf_row(line, row_number)
        if row is None and self.repair_glued_rows:
            row = _split_glued_ordinal_position(line, row_number, previous=self._last_seen_field())
        if row is None:
            return False
        if self.current is None:
            self.current = _PdfSheetDraft(self.pending_name or "PDF record design")
        elif self._begins_a_new_record_body(row):
            staged = self.pending_record_name
            self._open_body(
                staged if staged is not None else _unidentified_record_body_name(row_number),
                identified=staged is not None,
            )
        if self.current.opened_at_row is None:
            self.current.opened_at_row = row_number
        self.current.start_field(row)
        self.in_table = True
        self.pending_record_name = None
        return True

    def _consume_field_continuation(self, line: str) -> None:
        if self.in_table and self.current is not None and self.current.current is not None:
            self.current.current.append_continuation(line)


def _skipped_record_reason(result: _PdfSheetResult) -> str:
    if not result.sheet.fields:
        return "record heading recognised but no field rows parsed under it"
    return (
        f"a distinct record body begins here -- its positions restart at 1 at source row "
        f"{result.opened_at_row} -- but the source's heading for it was not recognised, so this "
        f"record has no read identity. It is reported unread rather than merged into the record "
        f"above it, because merging understates the document by a whole record while still "
        f"reporting the read complete"
    )


def _extract_pdf_lines(
    lines: tuple[str, ...],
    *,
    source_label: str,
    corrections: _CorrectionIndex = _EMPTY_CORRECTIONS,
    repair_glued_rows: bool = False,
) -> RecordDesignExtraction:
    state = _PdfParseState(
        source_label=source_label,
        corrections=corrections,
        repair_glued_rows=repair_glued_rows,
    )
    for row_number, raw_line in enumerate(lines, start=1):
        state.feed(_clean_pdf_line(raw_line), row_number)
    return state.finalise()


def _validate_pdf_sheet(sheet: RecordDesignSheet, *, source_label: str) -> None:
    if not sheet.fields:
        return
    first_field = sheet.fields[0]
    if first_field.offset != 1:
        raise RegistryValidationError(
            f"{source_label} {sheet.name!r} first field starts at position {first_field.offset}; expected 1",
        )
    for parsed_field in sheet.fields:
        if parsed_field.offset < 1:
            raise RegistryValidationError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"position {parsed_field.offset}",
            )
        if parsed_field.length < 1:
            raise RegistryValidationError(
                f"{source_label} {sheet.name!r} field ordinal {parsed_field.ordinal} has invalid "
                f"length {parsed_field.length}",
            )
    terminal_position = max(parsed_field.offset + parsed_field.length - 1 for parsed_field in sheet.fields)
    if sheet.total_positions is not None and terminal_position != sheet.total_positions:
        raise RegistryValidationError(
            f"{source_label} {sheet.name!r} declares {sheet.total_positions} total positions "
            f"but parsed fields fill {terminal_position}",
        )


#: A record row declaring a bracket constant: ``Constante "<VECTOR>"`` opens a
#: payload region and ``Constante "</VECTOR>"`` closes it.
_PDF_BRACKET_CONSTANT_RE = re.compile(r'Constante\s*"<(?P<closing>/?)(?P<tag>[A-Z][A-Z0-9_]*)>"')


def _bracketed_payload_positions(sheet: RecordDesignSheet) -> set[int]:
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
        for text in (design_field.content, design_field.description, design_field.validation):
            if not text:
                continue
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


def _recover_inline_constants(sheets: tuple[RecordDesignSheet, ...]) -> tuple[RecordDesignSheet, ...]:
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
    """
    if any(existing.content for sheet in sheets for existing in sheet.fields):
        return sheets
    recovered: list[RecordDesignSheet] = []
    for sheet in sheets:
        fields = []
        for design_field in sheet.fields:
            match = _INLINE_CONSTANT_RE.search(design_field.description or "")
            if match is None:
                fields.append(design_field)
                continue
            fields.append(design_field.model_copy(update={"content": match.group(0)}))
        recovered.append(sheet.model_copy(update={"fields": tuple(fields)}))
    return tuple(recovered)


def contiguity_failure(sheet: RecordDesignSheet) -> str | None:
    """Return why ``sheet``'s parsed rows do not tile its declared extent, else ``None``.

    Reported as a SKIPPED sheet rather than raised, so
    :meth:`RecordDesignExtraction.require_complete` refuses -- which is what the
    coverage gate calls -- while ``accept_partial`` consumers keep working. A
    hard extraction error would have destroyed the reading of every design that
    is merely PARTLY unreadable, taking live modelos out of measurement
    entirely; a skip states the same fact without that collateral.

    The terminal-position check above compares only the LAST byte, so a row
    dropped or invented in the MIDDLE of a record leaves it satisfied. That is
    how every silent reader defect survived: modelo 156's ``36-75 Afabetico
    APELLIDOS Y NOMBRE`` vanished, leaving a 40-byte hole in a 250-byte record
    while ``is_complete`` stayed ``True`` and the modelo reported clean --
    coverage measured over 19 positions that AEAT declares as 20, with the
    taxpayer's name no longer checked at all. A false green is strictly worse
    than the refusal it replaced.

    A fixed-width record is contiguous, so the parsed rows must cover every byte
    from 1 to the declared total. Overlap by CONTAINMENT is expected and
    permitted -- AEAT prints a parent row and its own subdivisions (Modelo 190's
    ``@81+27`` over its three sub-ranges, Modelo 180's ``@135+193`` over
    fifteen), and both are real statements about the same bytes. What is refused
    is a HOLE (rows were dropped) and a PARTIAL overlap or an extent past the
    declared total (rows were invented), because neither can be a faithful read
    of a contiguous record.

    This is the visible-refusal principle applied where it is unambiguous. Doing
    it per LINE is not possible: AEAT routinely opens a field's description with
    that field's own range ("68-107 APELLIDOS Y NOMBRE: Se consignara el
    primer"), so "looks like a position row" is dominated by prose -- measured
    across the bundled corpus, 41 designs carry such lines. At sheet level the
    arithmetic is decisive and needs no classification.
    """
    if sheet.total_positions is None:
        return None
    covered: set[int] = set()
    for parsed_field in sheet.fields:
        covered.update(range(parsed_field.offset, parsed_field.offset + parsed_field.length))
    covered |= _bracketed_payload_positions(sheet)
    declared = set(range(1, sheet.total_positions + 1))
    if holes := sorted(declared - covered):
        return (
            f"declares {sheet.total_positions} total positions but {_position_runs(holes)} were not "
            f"read at all, so rows were dropped; a record read with holes understates every coverage "
            f"figure derived from it"
        )
    # No "beyond the declared extent" leg: ``total_positions`` is DERIVED as
    # ``max(offset + length - 1)`` on the PDF paths, so the covered set is a
    # subset of the declared span by construction and such a check can never
    # fire. Measured across 2,581 bundled sheets: zero hits. A check whose zero
    # is not evidence is worse than no check, because it reads as coverage.
    # Fabricated rows show up as OVERLAP and as a length sum exceeding the
    # extent, which is where they are caught.
    return None


def _position_runs(positions: list[int]) -> str:
    """Render a sorted position list as compact ``a-b`` runs."""
    runs: list[str] = []
    start = previous = positions[0]
    for position in positions[1:]:
        if position == previous + 1:
            previous = position
            continue
        runs.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = position
    runs.append(str(start) if start == previous else f"{start}-{previous}")
    return ", ".join(runs[:6]) + (" and more" if len(runs) > 6 else "")


def _parse_pdf_row(line: str, source_row: int) -> _PdfRow | None:
    compact = _COMPACT_PDF_ROW_RE.match(line)
    if compact is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=compact.group("ordinal"),
            offset=int(compact.group("offset")),
            length=int(compact.group("length")),
            type_code=compact.group("type"),
            description=compact.group("text").strip(),
        )

    crlf = _COMPACT_PDF_CRLF_ROW_RE.match(line)
    if crlf is not None:
        return _PdfRow(
            source_row=source_row,
            ordinal=crlf.group("ordinal"),
            offset=int(crlf.group("offset")),
            length=2,
            type_code=crlf.group("type"),
            description=crlf.group("text").strip(),
        )

    narrative = _NARRATIVE_PDF_ROW_RE.match(line)
    if narrative is None:
        return None

    naturaleza = _naturaleza_or_none(narrative.group("type"))
    if naturaleza is None:
        # The line has a leading number but the token after it names no
        # naturaleza AEAT uses, so this is prose, not a position row. AEAT
        # routinely opens a field's DESCRIPTION with that field's own range
        # ("68-107 APELLIDOS Y NOMBRE: Se consignara el primer ..."), and
        # treating those as rows would invent positions wholesale -- measured
        # across the bundled corpus, 41 designs carry such prose.
        return None

    start = int(narrative.group("start"))
    end_group = narrative.group("end")
    end = int(end_group) if end_group is not None else start
    if end < start:
        raise RegistryValidationError(f"PDF row {source_row} has inverted position range {start}-{end}")
    return _PdfRow(
        source_row=source_row,
        ordinal=None,
        offset=start,
        length=end - start + 1,
        type_code=naturaleza,
        description=narrative.group("text").strip(),
    )


#: A row whose ORDINAL and POSITION were run together by the PDF text layer:
#: ``23 3 Num Modelo. OBLIGATORIO Constante "200"`` is ordinal 2 at position 3,
#: not ordinal 23. Three leading tokens where a row has four.
_GLUED_ORDINAL_POSITION_ROW_RE = re.compile(
    r"^\s*(?P<glued>\d{2,})\s+(?P<length>\d+)\s+(?P<type>An|Num|Tit|N|A)\.?\s+(?P<text>.+)$",
    re.IGNORECASE,
)


def _split_glued_ordinal_position(
    line: str,
    row_number: int,
    *,
    previous: _PdfFieldDraft | RecordDesignField | None,
) -> _PdfRow | None:
    """Recover a row whose ordinal and position were run together.

    Modelo 200's older editions lose the space after the ordinal for the three
    identifier rows of most records, writing ``23 3 Num``, ``36 3 An`` and
    ``49 1 An`` where AEAT declares ordinals 2, 3 and 4 at positions 3, 6 and 9.
    Thirty-two of the forty holed records in the 2010 edition report the
    resulting ``3-9`` gap, and it is the single most common hole shape in the
    corpus.

    A split is admitted ONLY when it is over-determined. ``23`` is read as
    ordinal 2 and position 3 only if BOTH the ordinal continues the previous
    row's ordinal by one AND the position resumes exactly where the previous row
    ended -- two independent facts that must agree, from a row already read
    rather than from a guess about this one. Any other split, or either
    constraint failing, returns ``None`` and the gap stays reported.

    This is why the shape was recorded and left alone when it was first met on
    modelo 100: there the glued row sits alone, with no read row before it to
    close the constraint, and ``59`` is as readable as ordinal 59. Nothing about
    the token changed -- what changed is that here the surrounding rows pin it.
    """
    if previous is None:
        return None
    match = _GLUED_ORDINAL_POSITION_ROW_RE.match(line)
    if match is None or _parse_pdf_row(line, row_number) is not None:
        return None
    glued = match.group("glued")
    expected_ordinal = None if previous.ordinal is None or not previous.ordinal.isdigit() else int(previous.ordinal) + 1
    expected_offset = previous.offset + previous.length
    if expected_ordinal is None or glued != f"{expected_ordinal}{expected_offset}":
        return None
    naturaleza = _naturaleza_or_none(match.group("type")) or match.group("type")
    return _PdfRow(
        source_row=row_number,
        ordinal=str(expected_ordinal),
        offset=expected_offset,
        length=int(match.group("length")),
        # The normalised naturaleza, matching the sibling constructor above. It was
        # computed here and then discarded in favour of the raw token, which is why
        # the assignment read as dead.
        type_code=naturaleza,
        description=match.group("text").strip(),
    )


def _unnamed_position_candidate(
    line: str,
    source_row: int,
    *,
    sheet: str = "",
    single_position_corrections: _SinglePositionCorrectionIndex | None = None,
) -> _PdfRow | None:
    """Return a position row whose naturaleza AEAT omitted, else ``None``.

    Deliberately NOT consulted by :func:`_parse_pdf_row`, which must keep
    refusing these outright: the same shape is overwhelmingly prose, because AEAT
    routinely opens a field's description with that field's own range, and 41
    bundled designs do. A candidate returned here is admitted only by
    :meth:`_PdfSheetDraft.fill_unread_gaps`, and only into a span no read row
    claims -- so it can add a field the sheet was missing entirely and can never
    displace, override or duplicate one that was read.

    """
    narrative = _NARRATIVE_PDF_ROW_RE.match(line)
    if narrative is None or _naturaleza_or_none(narrative.group("type")) is not None:
        return None
    start = int(narrative.group("start"))
    end_group = narrative.group("end")
    if end_group is None:
        # A single position with no naturaleza is indistinguishable from a
        # numbered prose sentence; only an explicit range is evidence of
        # extent, or a declared correction naming this exact position. See
        # :class:`RecordDesignSinglePositionCorrection` for why the declaration
        # is the only admissible substitute for the missing range.
        declared = (single_position_corrections or {}).get((sheet, start))
        if declared is None:
            return None
        return _PdfRow(
            source_row=source_row,
            ordinal=None,
            offset=start,
            length=1,
            type_code=declared.corrected_type,
            description=declared.description,
        )
    end = int(end_group)
    if end < start:
        return None
    text = (narrative.group("type") + " " + narrative.group("text")).strip()
    return _PdfRow(
        source_row=source_row,
        ordinal=None,
        offset=start,
        length=end - start + 1,
        type_code=ABSENT_NATURALEZA_TYPE_CODE,
        description=text,
    )


def _naturaleza_or_none(value: str) -> str | None:
    """Return the canonical naturaleza ``value`` names, or ``None`` if it names none.

    Matched on an ACCENT-STRIPPED stem rather than an exact spelling, because
    AEAT's designs are not spelled consistently and every unmatched spelling was
    a row dropped in silence. ``Numérica`` (feminine) and ``Alfanúmerico``
    (accent on the u, not the e) both ship in the bundled corpus and both read
    correctly here; before this, the first cost modelo 193 its positions
    182-192 and the second its 315-321, with ``is_complete`` still ``True``.

    Returning ``None`` rather than echoing the raw token back is the point: an
    unrecognised naturaleza must not become a field's type_code, because that is
    how a line of prose turns into a position.
    """
    raw = value.strip(" .")
    # The dash naturaleza is tested on the RAW token, before normalisation.
    # Stripping accents encodes to ASCII, which discards an en-dash entirely and
    # leaves an empty string, so testing it afterwards silently rejected every
    # genuine "226-487 - BLANCOS." row in the corpus.
    #
    # UNDERSCORES are the same rule drawn with a different character: Modelo 185
    # writes "58 ______ BLANCOS." where other designs write dashes. Both are an
    # empty naturaleza cell whose description says BLANCOS.
    if raw and set(raw) <= {"-", "–", "_"}:
        return "Blancos"
    normalised = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower()
    if not normalised:
        return None
    # AEAT names the fill naturaleza in Spanish far more often than in English:
    # "58 BLANCO", "187-390 BLANCOS", "58-107 Blancos BLANCOS". Recognising only
    # the English "blank" and the dash form dropped every one of those rows, and
    # a dropped filler run is not cosmetic -- modelo 349 lost 204 bytes at
    # 187-390 and 32 at 147-178, which took its whole design below the
    # contiguity check and left a live layout unmeasurable.
    if normalised.startswith("blanco") or normalised == "blank":
        return "Blancos"
    # The ADJECTIVE stems, never the bare noun. "num" also prefixes
    # "NUMERO"/"NÚMERO", which opens a great many AEAT field NAMES
    # ("147-151 NÚMERO DE REGISTRO DEL FONDO DE PENSIONES:"). Reading that as a
    # naturaleza promoted the wrapped tail of the description to a top-level
    # field and pushed modelo 345's tipo 2 record 45 bytes past its declared
    # 500 -- inventing two positions inside spans the layout already writes,
    # which no record may declare because they would overlap.
    if normalised.startswith(("alfanumeric", "alphanumeric")):
        return "Alfanumérico"
    # "afabetic" is AEAT's own typo for "alfabético", shipped in modelo 156's
    # "36 - 75 Afabético APELLIDOS Y NOMBRE DEL AFILIADO O MUTUALISTA". Dropping
    # it left a 40-byte hole exactly where the taxpayer's name belongs. It is
    # listed explicitly rather than folded into a looser stem because a wider
    # prefix would start matching field-name words.
    if normalised.startswith(("alfabetic", "alphabetic", "afabetic")):
        return "Alfabético"
    if normalised.startswith("numeric"):
        return "Numérico"
    return None


def _pdf_page_name(line: str) -> str | None:
    match = _PDF_PAGE_RECORD_RE.match(line)
    if match is not None:
        return f"Pág. {match.group('page')}"
    if _PDF_ANEXO_PAGE_RECORD_RE.match(line) is not None:
        return "Anexo"
    return None


def _pdf_record_heading_name(line: str) -> str | None:
    match = _PDF_RECORD_HEADING_RE.match(line) or _PDF_RECORD_HEADING_REVERSED_RE.match(line)
    if match is None:
        return None
    title = _normalise_pdf_sheet_name(match.group("title"))
    return f"Tipo {match.group('record')} - {title}"


def _pdf_candidate_record_name(line: str) -> str | None:
    """Return the record name a line MIGHT be heading, for geometry to confirm.

    Separate from :func:`_pdf_record_heading_name` precisely because it is not
    trusted on its own: see :data:`_PDF_RECORD_HEADING_TYPE_LAST_RE` for why
    this word order cannot split a record on the text alone.
    """
    tag = _PDF_RECORD_MODELO_PAGE_TAG_RE.match(line.strip())
    if tag is not None:
        return tag.group("tag")
    anexo = _PDF_RECORD_ANEXO_HEADING_RE.match(line.strip())
    if anexo is not None:
        return "Anexo - " + _normalise_pdf_sheet_name(anexo.group("title"))
    bare_anexo = _PDF_RECORD_BARE_ANEXO_RE.match(line.strip())
    if bare_anexo is not None:
        return "Anexo " + bare_anexo.group("tag").upper()
    match = _PDF_RECORD_HEADING_TYPE_LAST_RE.match(line)
    if match is None:
        return None
    title = _normalise_pdf_sheet_name(match.group("title"))
    return f"Tipo {match.group('record')} - {title}"


# The column-header spellings AEAT prints across diseño-de-registro PDFs.
# Each variant is a list of required column groups; a group holds the
# interchangeable spellings of one column, so a line matches a variant when
# every group contributes at least one token.
_PDF_HEADER_VARIANTS: Final[tuple[tuple[tuple[str, ...], ...], ...]] = (
    (("POSICIONES", "POSICIÓN"), ("NATURALEZA",), ("DESCRIPCI",)),
    (("Nº POSIC",), ("LON",), ("TIPO",), ("DESCRIPCI",)),
    (("POSITIONS",), ("NATURE",), ("DESCRIPTION",)),
)


def _is_pdf_header(line: str) -> bool:
    normalised = line.upper()
    return any(
        all(any(token in normalised for token in column) for column in variant) for variant in _PDF_HEADER_VARIANTS
    )


def _is_pdf_footer(line: str) -> bool:
    return bool(
        re.match(r"^P[áa]gina\s+\d+\s+de\s+\d+$", line, re.IGNORECASE)
        or re.match(r"^Ejercicio\s+\d{4}(?:\s+\d+)?$", line, re.IGNORECASE)
        or re.match(r"^\d+$", line),
    )


def _is_pdf_page_heading(line: str) -> bool:
    return bool(
        line.startswith("Modelo ")
        or line.startswith("Agencia Tributaria")
        or line.startswith("Declaración Informativa")
        or line.startswith("Declaración informativa")
        or line.startswith("determinados ")
        or line.startswith("determinadas ")
        or line == "Resumen anual"
        or line == "MODELO 193"
        or line == "MODELO 190"
        or line == "DISEÑOS DE REGISTRO",
    )


def _looks_like_title_continuation(line: str) -> bool:
    letters = [char for char in line if char.isalpha()]
    if not letters:
        return False
    return not any(char.islower() for char in letters)


def _clean_pdf_line(line: str) -> str:
    return " ".join(line.strip().split())


def _join_pdf_parts(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part.strip())


def _normalise_pdf_sheet_name(value: str) -> str:
    return _join_pdf_parts([value.replace(".", " ").strip()]).strip(". ").title()


def _extract_visual_record_design_chart(
    pages: tuple[_PdfPageSnapshot, ...],
    *,
    source_label: str,
) -> tuple[RecordDesignSheet, ...]:
    pages_by_sheet: dict[str, list[_PdfPageSnapshot]] = {}
    for page in pages:
        sheet_name = _visual_chart_page_sheet_name(page)
        if sheet_name is not None:
            pages_by_sheet.setdefault(sheet_name, []).append(page)
    if not pages_by_sheet:
        return ()

    sheets = tuple(
        _extract_visual_chart_sheet(sheet_name, tuple(sheet_pages), source_label=source_label)
        for sheet_name, sheet_pages in pages_by_sheet.items()
    )
    return sheets if all(sheet.fields for sheet in sheets) else ()


def _visual_chart_page_sheet_name(page: _PdfPageSnapshot) -> str | None:
    for line in page.lines:
        match = _VISUAL_CHART_HEADER_RE.match(_clean_pdf_line(line))
        if match is not None:
            title = _normalise_pdf_sheet_name(match.group("title"))
            return f"Tipo {match.group('record')} - {title}"
    return None


def _extract_visual_chart_sheet(
    name: str,
    pages: tuple[_PdfPageSnapshot, ...],
    *,
    source_label: str,
) -> RecordDesignSheet:
    fragments: list[_VisualChartFragment] = []
    for page in pages:
        fragments.extend(_extract_visual_chart_fragments(page))

    merged = _merge_visual_chart_fragments(sorted(fragments, key=lambda fragment: fragment.start))
    fields = tuple(
        RecordDesignField(
            sheet=name,
            row=ordinal,
            ordinal=str(ordinal),
            offset=fragment.start,
            length=fragment.end - fragment.start + 1,
            type_code=_VISUAL_CHART_TYPE_CODE,
            description=fragment.description,
            content="Extracted from visual record-design chart geometry.",
        )
        for ordinal, fragment in enumerate(merged, start=1)
    )
    total_positions = max((field.offset + field.length - 1 for field in fields), default=None)
    sheet = RecordDesignSheet(name=name, fields=fields, total_positions=total_positions)
    _validate_pdf_sheet(sheet, source_label=source_label)
    return sheet


def _extract_visual_chart_fragments(page: _PdfPageSnapshot) -> list[_VisualChartFragment]:
    grid = _visual_chart_grid(page)
    if grid is None:
        return []
    left, cell_width, horizontal_rules = grid
    fragments: list[_VisualChartFragment] = []
    number_rows = _visual_chart_number_rows(page)
    for index, (number_top, first_position) in enumerate(number_rows):
        row_rules = _visual_chart_rules_for_number_row(horizontal_rules, number_top)
        if not row_rules:
            continue
        region_top = number_rows[index - 1][0] + 8 if index else 20
        for rule in row_rules:
            start = first_position - 1 + round((rule.x0 - left) / cell_width) + 1
            end = first_position - 1 + round((rule.x1 - left) / cell_width)
            if start > end:
                continue
            fragments.append(
                _VisualChartFragment(
                    start=start,
                    end=end,
                    description=_visual_chart_description(page, rule, region_top=region_top),
                ),
            )
    return fragments


def _is_black_fill(fill: object | None) -> bool:
    """Return whether a pdfplumber rect ``fill`` value is opaque black.

    pdfplumber reports a rect's ``non_stroking_color`` in whatever colour
    space the source PDF declared: a bare grayscale float (``0.0`` is
    black), an RGB triple (``(0.0, 0.0, 0.0)``), or a named/indexed
    colourspace string the geometry-only chart extractor does not attempt
    to resolve. Both numeric shapes are checked so a rule ruled in RGB
    (observed in the AEAT modelo 038 record-design PDF) is not silently
    excluded from the visual-chart grid the way a bare ``fill == 0.0``
    comparison would exclude it.
    """
    if isinstance(fill, int | float):
        return fill == 0.0
    if isinstance(fill, tuple):
        try:
            components = _NUMERIC_TUPLE_ADAPTER.validate_python(fill)
        except ValidationError:
            return False
        return bool(components) and all(component == 0.0 for component in components)
    return False


def _visual_chart_grid(page: _PdfPageSnapshot) -> tuple[float, float, tuple[_PdfRect, ...]] | None:
    horizontal_rules = tuple(
        rect for rect in page.rects if _is_black_fill(rect.fill) and rect.height <= 2.0 and rect.width >= 8.0
    )
    full_width_rules = tuple(rect for rect in horizontal_rules if rect.width > 700.0)
    if not full_width_rules:
        return None
    left = min(rect.x0 for rect in full_width_rules)
    right = max(rect.x1 for rect in full_width_rules)
    return left, (right - left) / 65, horizontal_rules


def _visual_chart_number_rows(page: _PdfPageSnapshot) -> list[tuple[float, int]]:
    grouped_words: dict[float, list[_PdfWord]] = {}
    for word in page.words:
        if _visual_chart_number_values(word.text):
            grouped_words.setdefault(round(word.top, 1), []).append(word)

    rows: list[tuple[float, int]] = []
    for top, words in grouped_words.items():
        values = [
            value
            for word in sorted(words, key=lambda current: current.x0)
            for value in _visual_chart_number_values(word.text)
        ]
        if len(values) >= 20 and max(values) - min(values) >= 30:
            rows.append((top, min(values)))
    return sorted(rows)


def _visual_chart_number_values(text: str) -> tuple[int, ...]:
    if not text.isdigit():
        return ()
    if len(text) <= 3:
        return (int(text),)
    if len(text) % 3 == 0:
        return tuple(int(text[index : index + 3]) for index in range(0, len(text), 3))
    return ()


def _visual_chart_rules_for_number_row(
    horizontal_rules: tuple[_PdfRect, ...],
    number_top: float,
) -> tuple[_PdfRect, ...]:
    candidate_rules = tuple(rule for rule in horizontal_rules if 0 < number_top - rule.top <= 30)
    if not candidate_rules:
        return ()
    # A single printed rule band may arrive as adjacent PDF shapes whose
    # vertical bounds overlap without sharing an identical ``top`` coordinate.
    # Select the physical band nearest the number ruler by overlap, rather than
    # rounding coordinates and silently dropping the offset segments that a
    # producer represented a few tenths of a point differently.
    nearest = max(candidate_rules, key=lambda rule: rule.top)
    band_top = nearest.top
    band_bottom = nearest.bottom
    band: list[_PdfRect] = []
    while True:
        expanded = tuple(rule for rule in candidate_rules if rule.bottom >= band_top and rule.top <= band_bottom)
        expanded_top = min(rule.top for rule in expanded)
        expanded_bottom = max(rule.bottom for rule in expanded)
        if expanded_top == band_top and expanded_bottom == band_bottom:
            band = list(expanded)
            break
        band_top = expanded_top
        band_bottom = expanded_bottom
    return tuple(sorted(band, key=lambda rule: rule.x0))


def _visual_chart_description(
    page: _PdfPageSnapshot,
    rule: _PdfRect,
    *,
    region_top: float,
) -> str:
    words = [
        word
        for word in page.words
        if rule.x0 - 2 <= (word.x0 + word.x1) / 2 <= rule.x1 + 2
        and region_top <= word.top <= rule.top - 1
        and not _is_visual_chart_number_text(word.text)
    ]
    description = _normalise_visual_chart_description(words)
    return description or "BLANCOS."


def _normalise_visual_chart_description(words: list[_PdfWord]) -> str:
    tokens = [word.text for word in sorted(words, key=lambda word: (word.top, word.x0))]
    tokens = [
        _REVERSED_VISUAL_CHART_TOKENS.get(visual_word, visual_word) for visual_word in tokens if visual_word != "D"
    ]
    if not tokens:
        return ""
    if any(token.strip(".").upper() in _REVERSED_VISUAL_CHART_WORDS for token in tokens):
        tokens = [token[::-1] for token in reversed(tokens)]
    return _clean_visual_chart_description(_dedupe_visual_chart_tokens(tokens))


def _dedupe_visual_chart_tokens(tokens: list[str]) -> str:
    deduped: list[str] = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return " ".join(deduped).strip()


def _clean_visual_chart_description(description: str) -> str:
    replacements = {
        "DEL DECLARANTE N.I.F. DEL DECLARANTE": "N.I.F. DEL DECLARANTE",
        "DECLARANTE N.I.F. DECLARANTE": "N.I.F. DECLARANTE",
        "PROVINCIA AICNIVORP OGIDOC": "CODIGO PROVINCIA",
        "CODIGO PAIS SIAP": "CODIGO PAIS",
        "DECIMAL ED": "DECIMAL",
        "I TIPO DE HOJA": "TIPO DE HOJA",
        "REFERENCIA CATASTRAL REFERENCIA CATASTRAL": "REFERENCIA CATASTRAL",
    }
    for before, after in replacements.items():
        description = description.replace(before, after)
    return description


def _is_visual_chart_number_text(text: str) -> bool:
    return bool(re.fullmatch(r"\d+", text) or re.fullmatch(r"\d{3}(?:\d{3})+", text))


def _merge_visual_chart_fragments(
    fragments: list[_VisualChartFragment],
) -> tuple[_VisualChartFragment, ...]:
    merged: list[_VisualChartFragment] = []
    for fragment in fragments:
        if (
            merged
            and fragment.start == merged[-1].end + 1
            and merged[-1].end % 65 == 0
            and _visual_chart_fragments_should_merge(merged[-1], fragment)
        ):
            previous = merged[-1]
            description = _merge_visual_chart_descriptions(previous.description, fragment.description)
            merged[-1] = _VisualChartFragment(start=previous.start, end=fragment.end, description=description)
            continue
        merged.append(fragment)
    return tuple(merged)


def _visual_chart_fragments_should_merge(
    previous: _VisualChartFragment,
    current: _VisualChartFragment,
) -> bool:
    return not (previous.description == "BLANCOS." and current.description != "BLANCOS.")


def _merge_visual_chart_descriptions(previous: str, current: str) -> str:
    parts = [description for description in (previous, current) if description != "BLANCOS."]
    return _clean_visual_chart_description(_join_pdf_parts(parts)) or "BLANCOS."


_VISUAL_CHART_HEADER_RE = re.compile(
    r"^MODELO\s+\d+\s+REGISTRO DE TIPO\s+(?P<record>\d+)\.?\s+(?P<title>REGISTRO DE .+)$",
    re.IGNORECASE,
)
_VISUAL_CHART_TYPE_CODE = "No consta en gráfico"

#: The naturaleza a row carries when AEAT printed a position range and a
#: description but omitted the type token between them. Distinct from
#: :data:`_VISUAL_CHART_TYPE_CODE`, which marks a design that has no type column
#: at all: here the column exists and this one row is blank in it. Never a
#: guess -- an inferred "Alfanumerico" would be indistinguishable from one AEAT
#: actually printed.
ABSENT_NATURALEZA_TYPE_CODE = "No consta"

_REVERSED_VISUAL_CHART_WORDS = {
    "AICNIVORP",
    "AJOH",
    "DNERRA",
    "EVALC",
    "ETROPOS",
    "LACOL",
    "LAMICED",
    "NÓICAREPO",
    "OPIT",
    "ORTSIGER",
}
_REVERSED_VISUAL_CHART_TOKENS = {
    "AIRATNEMELPMOC.CED": "DEC. COMPLEMENTARIA",
    "AVITUTITSUS.CED": "DEC. SUSTITUTIVA",
    ".REPO": "OPER.",
    "ORUGES": "SEGURO",
    "ELBEUMNI": "INMUEBLE",
    ".CAUTIS": "SITUAC.",
    "ARELACSE": "ESCALERA",
    "IMNUEBLE": "INMUEBLE",
}


__all__ = [
    "AUXILIARY_ENVELOPE_HEADER_CONTENT",
    "AUXILIARY_ENVELOPE_HEADER_LENGTHS",
    "AUXILIARY_ENVELOPE_HEADER_ORDINALS",
    "AUXILIARY_ENVELOPE_HEADER_ROWS",
    "DerivedDisenoCasilla",
    "DisenoCoverageReport",
    "RecordDesignCompositeRelativeClosing",
    "RecordDesignCorrection",
    "RecordDesignExtraction",
    "RecordDesignField",
    "RecordDesignFieldTypeCorrection",
    "RecordDesignHeaderCellCorrection",
    "RecordDesignRelativeSuffixMarker",
    "RecordDesignSheet",
    "RecordDesignSkippedSheet",
    "RecordDesignVariableBodyMarker",
    "RecordDesignVariableEnvelope",
    "RecordDesignVariableTotalMarker",
    "build_diseno_coverage_report",
    "calculation_closure_casilla_ids",
    "calculation_closure_legal_refs",
    "calculation_closure_record_design_metadata",
    "derive_calculation_completeness_casillas",
    "derive_diseno_coverage_casillas",
    "extract_record_design",
    "extract_record_design_pdf",
    "extract_record_design_pdf_bytes",
    "extract_record_design_workbook",
    "validate_auxiliary_envelope_header_contents",
]
