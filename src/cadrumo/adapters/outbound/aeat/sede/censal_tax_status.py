"""Parse rendered tax-status fieldsets without interpreting tax eligibility."""

from __future__ import annotations

import re

from bs4 import Tag

from .....application.user_profile.censal_observation import (
    CensalCell,
    CensalConsultation,
    CensalRow,
    CensalSection,
)
from .censal_tables import census_document, census_key, census_shape_error, census_source_url, census_text

_COLUMN_LABELS = frozenset(
    {
        "si",
        "no",
        "alta",
        "baja",
        "fecha",
        "inclusion",
        "incluido",
        "exclusion",
        "excluido",
        "renuncia",
        "revocacion",
        "situacion",
    }
)
_CASILLA = re.compile(r"\d{3}")


def _label(cell: Tag) -> str | None:
    explicit = cell.get("data-label") or cell.get("aria-label")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    labels = cell.select(".ASWeb_multi_idioma, label, [data-censal-label]")
    if labels:
        return " ".join(filter(None, (census_text(label) for label in labels))) or None
    if cell.name == "th":
        return census_text(cell)
    return None


def _row_cells(row: Tag) -> tuple[CensalCell, ...]:
    elements = row.find_all(["li", "td", "th"], recursive=False)
    cells: list[CensalCell] = []
    for element in elements:
        text = census_text(element)
        label = _label(element)
        if label:
            cells.append(CensalCell(role="label", text=label))
            if text != label:
                remainder = census_document(str(element))
                for node in remainder.select(".ASWeb_multi_idioma, label, [data-censal-label]"):
                    node.decompose()
                value = census_text(remainder)
                if value:
                    cells.append(CensalCell(role="value", text=value))
        elif text and _CASILLA.fullmatch(text) and "fondo_medio" not in element.get("class", []):
            cells.append(CensalCell(role="casilla", text=text))
        elif text or "fondo_medio" in element.get("class", []) or element.has_attr("data-censal-value"):
            cells.append(CensalCell(role="value", text=text))
    return tuple(cells)


def _sections(fieldset: Tag) -> tuple[CensalSection, ...]:
    legend = fieldset.find("legend", recursive=False)
    if not isinstance(legend, Tag) or not census_text(legend):
        raise census_shape_error("tax-status fieldset has no label")
    title = census_text(legend) or ""
    current_title = title
    columns: tuple[str, ...] = ()
    records: list[CensalRow] = []
    sections: list[CensalSection] = []
    for row in fieldset.select("ul, tr"):
        if row.find_parent("fieldset") is not fieldset or row.find_parent("ul") is not None:
            continue
        cells = _row_cells(row)
        if not cells:
            continue
        labels = tuple(cell.text for cell in cells if cell.role == "label" and cell.text)
        values = tuple(cell for cell in cells if cell.role != "label")
        if labels and not values:
            if all(census_key(label) in _COLUMN_LABELS for label in labels):
                columns = labels
            else:
                sections.append(CensalSection(title=current_title, rows=tuple(records)))
                records = []
                current_title = f"{title} / {' / '.join(labels)}"
                columns = ()
            continue
        # Casilla and labelled cells remain in source order: a value without a
        # provable column association is retained, never guessed from CSS width.
        value_count = sum(cell.role == "value" for cell in cells)
        if columns and value_count == len(columns):
            names = iter(columns)
            cells = tuple(
                cell.model_copy(update={"column": next(names)}) if cell.role == "value" else cell for cell in cells
            )
        records.append(CensalRow(label=" / ".join(labels) or None, columns=columns, cells=cells))
    if records:
        sections.append(CensalSection(title=current_title, rows=tuple(records)))
    if not sections:
        raise census_shape_error("tax-status fieldset contains no recognizable rows")
    return tuple(sections)


def parse_censal_tax_status(html: str, *, source_url: str) -> CensalConsultation:
    """Retain every rendered regime/option row, casilla and unknown label.

    Callers supply post-JavaScript HTML. Script literals are not observations;
    only the resulting marks, dates and text are retained.
    """
    soup = census_document(html)
    if not any(census_key(census_text(h) or "") == "situaciontributaria" for h in soup.select("h1, [role=heading]")):
        raise census_shape_error("tax-status heading missing")
    fieldsets = soup.select("fieldset")
    if not fieldsets:
        raise census_shape_error("tax-status sections missing")
    sections = tuple(section for fieldset in fieldsets for section in _sections(fieldset))
    return CensalConsultation(kind="situacion_tributaria", source_url=census_source_url(source_url), sections=sections)
