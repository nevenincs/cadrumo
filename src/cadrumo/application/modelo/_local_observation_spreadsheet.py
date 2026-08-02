"""Parse a two-column casilla-value spreadsheet into a decimal mapping.

An operator keeps a hand-authored CSV or XLSX spreadsheet of ``casilla_code, value``
rows — a cert-free reconstruction path for a past filing when neither the
justificante PDF (:mod:`application.filing._import`) nor a live AEAT pull
is available. This module owns exactly the tabular-to-mapping projection: read
the two declared columns, coerce every value to :class:`~decimal.Decimal`, and
hand the caller a plain ``{casilla_code: Decimal}`` mapping keyed by the raw
spreadsheet token (not yet validated against any registry revision).

Casilla-id canonicalisation, registry-membership validation, and
:class:`~domain.calculations.registry.CasillaObservation` construction
remain owned by :func:`~application.modelo._local_observation_actions.record_operator_local_observation`,
which this module's CLI caller feeds directly — there is no second casilla
validation path here (``no-dormant-source-resolvers`` companion: one
validation authority, not two).

See Also:
    :func:`~application.modelo._local_observation_actions.record_operator_local_observation`:
        Consumes the parsed mapping, validates every casilla id against the
        law-determined :class:`~domain.calculations.registry.RegistrySnapshot`,
        and persists the non-official observation.
    :mod:`adapters.inbound.financial.providers._csv`:
        Sibling tabular-ingest module for bank-statement rows; this module is
        deliberately smaller — a casilla-value sheet has two logical columns
        and no bank-layout detection, date parsing, or currency handling.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from openpyxl import load_workbook

from ...core.decimal import normalize_decimal_separators
from ...core.external_constants import CSV_ENCODING_FALLBACK_CHAIN, XLSX_EXTENSION
from ._action_errors import ModeloLocalObservationError

CSV_EXTENSIONS: Final[frozenset[str]] = frozenset({".csv", ".txt"})
"""Extensions routed to the CSV reader; anything else is routed to XLSX."""

_CASILLA_CODE_HEADER_ALIASES: Final[frozenset[str]] = frozenset(
    {"casilla_code", "casilla", "casilla_id", "code", "id", "box", "casilla.id"},
)
_VALUE_HEADER_ALIASES: Final[frozenset[str]] = frozenset({"value", "valor", "amount", "importe"})


def _normalise_header(value: object) -> str:
    return str(value if value is not None else "").strip().lower().replace(" ", "_")


def parse_casilla_value_spreadsheet(path: Path) -> dict[str, Decimal]:
    """Parse a ``casilla_code, value`` spreadsheet into a raw code-to-Decimal mapping.

    Accepts CSV (``.csv`` / ``.txt``) or XLSX (``.xlsx``). The first
    non-blank row is treated as the header; a header row naming both a
    casilla-code column (``casilla_code`` / ``casilla`` / ``casilla_id`` /
    ``code`` / ``id`` / ``box``) and a value column (``value`` / ``valor`` /
    ``amount`` / ``importe``, case-insensitive) selects those columns by
    name. A headerless two-column sheet falls back positionally: column A is
    the casilla code, column B is the value.

    Every value is coerced to :class:`~decimal.Decimal`; a non-numeric value
    raises :class:`ModeloLocalObservationError` naming the offending row. A
    blank row is skipped. A row that omits the casilla code but carries a
    value (or vice versa) raises, naming the row.

    Returns:
        A ``{raw_casilla_code: Decimal}`` mapping in row order. Keys are the
        spreadsheet's literal cell text — not yet canonicalised or validated
        against any registry revision.

    Raises:
        ModeloLocalObservationError: The file cannot be opened, carries no
            data rows, or a data row cannot be parsed into a
            ``(casilla_code, Decimal)`` pair.
    """
    if not path.exists() or not path.is_file():
        raise ModeloLocalObservationError(
            f"casilla-value spreadsheet {path} does not exist",
            context={"path": str(path)},
        )
    suffix = path.suffix.lower()
    rows = _read_xlsx_rows(path) if suffix == XLSX_EXTENSION else _read_csv_rows(path)
    if not rows:
        raise ModeloLocalObservationError(
            f"casilla-value spreadsheet {path} contains no rows",
            context={"path": str(path)},
        )

    code_index, value_index, data_rows = _locate_columns(rows)
    values: dict[str, Decimal] = {}
    first_row_by_code: dict[str, int] = {}
    malformed: list[str] = []
    for row_number, row in enumerate(data_rows, start=1):
        code = _cell(row, code_index)
        raw_value = _cell(row, value_index)
        if not code and not raw_value:
            continue
        if not code or not raw_value:
            malformed.append(f"row {row_number}: incomplete (casilla_code={code!r}, value={raw_value!r})")
            continue
        first_row = first_row_by_code.get(code)
        if first_row is not None:
            malformed.append(
                f"row {row_number}: duplicate casilla_code {code!r} (first declared on row {first_row})",
            )
            continue
        first_row_by_code[code] = row_number
        try:
            normalized = normalize_decimal_separators(raw_value, strip_thousands="," in raw_value)
            value = Decimal(normalized)
        except InvalidOperation:
            malformed.append(f"row {row_number}: value {raw_value!r} for casilla {code!r} is not numeric")
            continue
        if not value.is_finite():
            malformed.append(f"row {row_number}: value {raw_value!r} for casilla {code!r} must be finite")
            continue
        values[code] = value
    if malformed:
        raise ModeloLocalObservationError(
            f"casilla-value spreadsheet {path} has malformed rows: {'; '.join(malformed)}",
            context={"path": str(path), "malformed_row_count": str(len(malformed))},
        )
    if not values:
        raise ModeloLocalObservationError(
            f"casilla-value spreadsheet {path} contains no usable casilla_code/value rows",
            context={"path": str(path)},
        )
    return values


def _locate_columns(rows: list[list[str]]) -> tuple[int, int, list[list[str]]]:
    """Return ``(code_column_index, value_column_index, data_rows)``.

    Selects by header-alias name when the first row matches; otherwise falls
    back to the positional convention (column 0 = code, column 1 = value)
    and treats every row as data.
    """
    header = rows[0]
    normalised = [_normalise_header(cell) for cell in header]
    code_index = next((i for i, cell in enumerate(normalised) if cell in _CASILLA_CODE_HEADER_ALIASES), None)
    value_index = next((i for i, cell in enumerate(normalised) if cell in _VALUE_HEADER_ALIASES), None)
    if code_index is not None and value_index is not None:
        return code_index, value_index, rows[1:]
    return 0, 1, rows


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return row[index].strip()


def _read_csv_rows(path: Path) -> list[list[str]]:
    source_bytes = path.read_bytes()
    text = _decode_bytes(source_bytes, path=path)
    reader = csv.reader(io.StringIO(text))
    rows = [[cell.strip() for cell in row] for row in reader]
    return [row for row in rows if any(cell for cell in row)]


def _decode_bytes(source_bytes: bytes, *, path: Path) -> str:
    for candidate in CSV_ENCODING_FALLBACK_CHAIN:
        try:
            return source_bytes.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    raise ModeloLocalObservationError(
        f"casilla-value spreadsheet {path} could not be decoded as utf-8/cp1252/iso-8859-1",
        context={"path": str(path)},
    )


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    try:
        workbook = load_workbook(filename=path, read_only=True, data_only=False)
    except Exception as exc:  # openpyxl raises multiple unrelated types (OSError/KeyError/...) on a bad workbook
        raise ModeloLocalObservationError(
            f"casilla-value spreadsheet {path} could not be opened as an XLSX workbook",
            context={"path": str(path)},
        ) from exc
    try:
        worksheet = workbook.worksheets[0]
        rows: list[list[str]] = []
        for row_index, cells in enumerate(worksheet.iter_rows(), start=1):
            for column_index, cell in enumerate(cells, start=1):
                if cell.data_type == "f":
                    raise ModeloLocalObservationError(
                        f"casilla-value spreadsheet {path} contains formula cell at row {row_index}, "
                        f"column {column_index}; formula cached values are not accepted",
                        context={
                            "path": str(path),
                            "row": str(row_index),
                            "column": str(column_index),
                        },
                    )
            rows.append([_coerce_cell_text(cell.value) for cell in cells])
        return [row for row in rows if any(cell for cell in row)]
    finally:
        workbook.close()


def _coerce_cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


__all__ = [
    "CSV_EXTENSIONS",
    "parse_casilla_value_spreadsheet",
]
