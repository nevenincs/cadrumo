"""Parse workbook record-design headers and cells."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from ....core.logging import get_logger
from ....core.tabular import coerce_cell_text
from .errors import RegistryValidationError
from .record_design_schema import RecordDesignFieldTypeCorrection, RecordDesignHeaderCellCorrection
from .record_design_sources import _EMPTY_HEADER_CORRECTIONS, _HeaderCorrectionIndex, _TypeCorrectionIndex

if TYPE_CHECKING:
    from openpyxl.worksheet.worksheet import Worksheet
    from xlrd.sheet import Sheet as XlrdSheet


_log = get_logger(__name__)


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
            header_corrections=header_corrections or _EMPTY_HEADER_CORRECTIONS,
        )
        if matched is not None:
            return matched
    raise RegistryValidationError(f"{worksheet.title!r} has no record-design header")


def _find_xls_header(
    worksheet: XlrdSheet,
    header_corrections: _HeaderCorrectionIndex | None = None,
) -> tuple[_WorkbookHeader, RecordDesignHeaderCellCorrection | None]:
    sheet_name = worksheet.name.strip()
    header_corrections = header_corrections or _EMPTY_HEADER_CORRECTIONS
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
