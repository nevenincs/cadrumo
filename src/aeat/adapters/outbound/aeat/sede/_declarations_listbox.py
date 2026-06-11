"""Declaraciones-presentadas ZK listbox parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from bs4 import BeautifulSoup

from .....core import Period
from .....core.i18n import tr
from .....core.logging import get_logger
from ._adapter_utils import normalize_response_text
from ._declarations_schema import Declaracion
from ._errors import SedeParseError, SedeValidationError

__all__ = ["_has_class", "_parse_listbox", "_parse_presented_at"]

log = get_logger(__name__)

_NO_RESULTS_TEXT = "No se han encontrado resultados para la consulta realizada."
_PRESENTED_AT_RE = re.compile(
    r"^(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})$",
)


def _has_class(target: str):
    """Return a bs4 ``class_=`` matcher that yields ``True`` when ``target`` is present."""

    def _matcher(value: str | list[str] | None) -> bool:
        if not value:
            return False
        classes = value if isinstance(value, list) else [value]
        return target in classes

    return _matcher


def _parse_listbox(
    html: str,
    *,
    modelo: str,
    ejercicio: int,
) -> tuple[Declaracion, ...]:
    """Parse the post-Buscar listbox into typed Declaracion records."""
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        raise SedeParseError(
            f"failed to parse declaraciones HTML: {exc}",
            translated_message=tr("adapters.sede.errors.parse_failed"),
        ) from exc

    listbox = soup.find(class_=_has_class("z-listbox"))
    if listbox is None:
        raise SedeParseError(
            "declaraciones response missing .z-listbox container",
            translated_message=tr("adapters.sede.errors.listbox_missing"),
        )

    action_indexes = _listbox_action_indexes(listbox)
    if action_indexes is None:
        justificante_index: int | None = 7
        archive_index: int | None = 8
        declaration_copy_index: int | None = None
    else:
        justificante_index = action_indexes.justificante
        archive_index = action_indexes.submitted_file
        declaration_copy_index = action_indexes.declaration_pdf
    if justificante_index is None:
        raise SedeParseError(
            "declaraciones response missing justificante column",
            translated_message=tr("adapters.sede.errors.justificante_column_missing"),
        )
    items = listbox.find_all(class_=_has_class("z-listitem"))

    rows: list[Declaracion] = []
    for item in items:
        cells = item.find_all(class_=_has_class("z-listcell"))
        cell_texts = [cell.get_text(" ", strip=True) for cell in cells]

        if len(cell_texts) == 1 and cell_texts[0] == _NO_RESULTS_TEXT:
            return ()

        if len(cell_texts) < 7:
            log.debug("_parse_listbox: skipping malformed row with %d cell(s)", len(cell_texts))
            continue

        try:
            presented_at = _parse_presented_at(cell_texts[6])
        except ValueError as exc:
            raise SedeParseError(f"failed to parse presented_at {cell_texts[6]!r}: {exc}") from exc

        rows.append(
            Declaracion(
                modelo=modelo,
                ejercicio=ejercicio,
                period=Period.from_year_and_code(ejercicio, cell_texts[4]),
                expediente_id=cell_texts[3],
                estado=cell_texts[5],
                tipo_solicitud=cell_texts[1] or None,
                observaciones=cell_texts[2] or None,
                presented_at=presented_at,
                justificante_link_text=_cell_text(cell_texts, justificante_index),
                archive_link_text=_cell_text(cell_texts, archive_index),
                declaration_copy_link_text=_cell_text(cell_texts, declaration_copy_index),
                justificante_cell_index=justificante_index,
                archive_cell_index=archive_index,
                declaration_copy_cell_index=declaration_copy_index,
            ),
        )
    return tuple(rows)


@dataclass(slots=True, frozen=True)
class _ListboxActionIndexes:
    """Column indexes for the three action links in the declaraciones listbox."""

    justificante: int | None = None
    submitted_file: int | None = None
    declaration_pdf: int | None = None


def _listbox_action_indexes(listbox) -> _ListboxActionIndexes | None:
    headers = listbox.find_all(class_=_has_class("z-listheader"))
    if not headers:
        return None
    justificante: int | None = None
    submitted_file: int | None = None
    declaration_pdf: int | None = None
    for index, header in enumerate(headers):
        label = normalize_response_text(header.get_text(" ", strip=True))
        if "justificante" in label:
            justificante = index
        elif "fichero presentado" in label or ("descarga" in label and "fichero" in label):
            submitted_file = index
        elif "copia" in label and "declaracion" in label:
            declaration_pdf = index
    return _ListboxActionIndexes(
        justificante=justificante,
        submitted_file=submitted_file,
        declaration_pdf=declaration_pdf,
    )


def _cell_text(cell_texts: list[str], index: int | None) -> str | None:
    if index is None or index >= len(cell_texts):
        return None
    return cell_texts[index] or None


def _parse_presented_at(value: str) -> datetime:
    """Parse ``"01/02/2024 19:15:34"`` as the observed AEAT row timestamp."""
    match = _PRESENTED_AT_RE.match(value)
    if match is None:
        raise SedeValidationError(f"unexpected presented_at shape: {value!r}")
    return datetime(
        year=int(match["year"]),
        month=int(match["month"]),
        day=int(match["day"]),
        hour=int(match["hour"]),
        minute=int(match["minute"]),
        second=int(match["second"]),
        tzinfo=UTC,
    )
