"""Declaraciones-presentadas ZK listbox parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.period import Period
from .._html import parse_html
from ._adapter_utils import cell_text, normalize_response_text
from .declarations_schema import Declaracion
from .errors import SedeFailureMode, SedeParseError, SedeValidationError

__all__ = [
    "DeclaracionesRegisterPage",
    "_has_class",
    "_parse_listbox",
    "_parse_presented_at",
]

log = get_logger(__name__)

NO_RESULTS_TEXT = "No se han encontrado resultados para la consulta realizada."
_PRESENTED_AT_RE = re.compile(
    r"^(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})$",
)
# ZK renders the grid's own record count in its pager label, e.g.
# "Pagina 1/3, registros 1-3 de 8 en total". Matched against the
# accent-folded, casefolded pager text so a diacritic or capitalisation
# difference in AEAT's wording does not silence the count.
_DECLARED_TOTAL_RE = re.compile(r"de (\d+) en total")


class DeclaracionesRegisterPage(BaseModel):
    """One rendered page of the declaraciones register, with its own declared size.

    The register grid is read from a single DOM snapshot, so the rows parsed out
    of it are only ever the rows AEAT chose to render. When the grid carries a
    pager label, that label states how many records exist in total, which is the
    one signal available for deciding whether the snapshot is the whole answer.
    ``declared_total`` is ``None`` when the markup carries no pager at all — a
    one-page result by construction, not a shortfall.
    """

    model_config = _STRICT_FROZEN

    rows: tuple[Declaracion, ...]
    declared_total: int | None = Field(default=None, ge=0)

    @property
    def truncated(self) -> bool:
        """Whether fewer rows were rendered than the grid's own label declares."""
        return self.declared_total is not None and len(self.rows) < self.declared_total


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
) -> DeclaracionesRegisterPage:
    """Parse the post-Buscar listbox into a typed register page.

    Returns:
        The rendered :class:`Declaracion` rows together with the record total the
        grid's own pager label declares, so a caller can tell a complete answer
        from a rendered-page-only one.
    """
    try:
        soup = parse_html(html)
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
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={"modelo": modelo, "ejercicio": ejercicio},
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
            failure_mode=SedeFailureMode.EXTERNAL_SHAPE_CHANGED,
            context={"modelo": modelo, "ejercicio": ejercicio},
        )
    items = listbox.find_all(class_=_has_class("z-listitem"))
    declared_total = _parse_declared_total(soup)

    rows: list[Declaracion] = []
    for item in items:
        cells = item.find_all(class_=_has_class("z-listcell"))
        cell_texts = [cell.get_text(" ", strip=True) for cell in cells]

        if len(cell_texts) == 1 and cell_texts[0] == NO_RESULTS_TEXT:
            return DeclaracionesRegisterPage(rows=(), declared_total=declared_total)

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
                justificante_link_text=cell_text(cell_texts, justificante_index),
                archive_link_text=cell_text(cell_texts, archive_index),
                declaration_copy_link_text=cell_text(cell_texts, declaration_copy_index),
                justificante_cell_index=justificante_index,
                archive_cell_index=archive_index,
                declaration_copy_cell_index=declaration_copy_index,
            ),
        )
    return DeclaracionesRegisterPage(rows=tuple(rows), declared_total=declared_total)


def _parse_declared_total(soup: BeautifulSoup) -> int | None:
    """Return the record total the grid's pager label states, or ``None`` when absent.

    A grid with no pager markup renders every record it has, so an absent label
    is not a missing total — there is nothing to reconcile against.
    """
    pager = soup.find(class_=_has_class("z-paging"))
    if pager is None:
        return None
    match = _DECLARED_TOTAL_RE.search(normalize_response_text(pager.get_text(" ", strip=True)))
    if match is None:
        log.debug("_parse_declared_total: pager present but its label states no record total")
        return None
    return int(match.group(1))


@dataclass(slots=True, frozen=True)
class _ListboxActionIndexes:
    """Column indexes for the three action links in the declaraciones listbox."""

    justificante: int | None = None
    submitted_file: int | None = None
    declaration_pdf: int | None = None


def _listbox_action_indexes(listbox: Tag) -> _ListboxActionIndexes | None:
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
