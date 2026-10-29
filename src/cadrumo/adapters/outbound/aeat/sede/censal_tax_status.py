"""Parse rendered tax-status fieldsets without interpreting tax eligibility."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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
_REQUIRED_TAX_SECTIONS = frozenset(
    census_key(title)
    for title in (
        "Impuesto sobre el Valor Añadido",
        "Impuesto sobre la Renta de las Personas Físicas",
        "Impuesto sobre Sociedades",
        "Impuesto sobre la Renta de No Residentes",
        "Régimen fiscal especial del Título II de la ley 49/2002",
        "Retenciones e ingresos a cuenta",
        "Otros Impuestos",
        "Regímenes Especiales Comercio Intracomunitario (Ventas a Distancia y No Sujeción art. 14 Ley I.V.A.)",
    )
)


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


def _labelled_cells(element: Tag, text: str | None, label: str) -> tuple[CensalCell, ...]:
    cells = [CensalCell(role="label", text=label)]
    if text != label:
        remainder = census_document(str(element))
        for node in remainder.select(".ASWeb_multi_idioma, label, [data-censal-label]"):
            node.decompose()
        value = census_text(remainder)
        if value is not None and value:
            cells.append(CensalCell(role="value", text=value))
    return tuple(cells)


def _element_cells(element: Tag) -> tuple[CensalCell, ...]:
    text = census_text(element)
    label = _label(element)
    if label is not None and label:
        return _labelled_cells(element, text, label)
    shaded = "fondo_medio" in element.get_attribute_list("class")
    if text is not None and _CASILLA.fullmatch(text) and not shaded:
        return (CensalCell(role="casilla", text=text),)
    if bool(text) or shaded or element.has_attr("data-censal-value"):
        return (CensalCell(role="value", text=text),)
    return ()


def _row_cells(row: Tag) -> tuple[CensalCell, ...]:
    return tuple(
        cell for element in row.find_all(["li", "td", "th"], recursive=False) for cell in _element_cells(element)
    )


def _cell_labels(cells: tuple[CensalCell, ...]) -> tuple[str, ...]:
    return tuple(cell.text for cell in cells if cell.role == "label" and cell.text is not None and cell.text)


def _associate_columns(cells: tuple[CensalCell, ...], columns: tuple[str, ...]) -> tuple[CensalCell, ...]:
    # Only associate values when cardinality proves the relationship.
    if not columns or sum(cell.role == "value" for cell in cells) != len(columns):
        return cells
    names = iter(columns)
    return tuple(cell.model_copy(update={"column": next(names)}) if cell.role == "value" else cell for cell in cells)


@dataclass
class _TaxSectionRows:
    title: str
    current_title: str
    columns: tuple[str, ...] = ()
    records: list[CensalRow] = field(default_factory=list)
    sections: list[CensalSection] = field(default_factory=list)

    def header(self, labels: tuple[str, ...]) -> None:
        if all(census_key(label) in _COLUMN_LABELS for label in labels):
            self.columns = labels
            return
        self.sections.append(CensalSection(title=self.current_title, rows=tuple(self.records)))
        self.records = []
        self.current_title = f"{self.title} / {' / '.join(labels)}"
        self.columns = ()

    def append(self, cells: tuple[CensalCell, ...]) -> None:
        labels = _cell_labels(cells)
        if labels and all(cell.role == "label" for cell in cells):
            self.header(labels)
            return
        self.records.append(
            CensalRow(
                label=" / ".join(labels) or None, columns=self.columns, cells=_associate_columns(cells, self.columns)
            )
        )

    def finish(self) -> tuple[CensalSection, ...]:
        if self.records or self.current_title != self.title:
            self.sections.append(CensalSection(title=self.current_title, rows=tuple(self.records)))
        if not self.sections:
            raise census_shape_error("tax-status fieldset contains no recognizable rows")
        return tuple(self.sections)


def _retained_text(section: CensalSection) -> tuple[str, ...]:
    return (
        section.title,
        *(text for row in section.rows for text in (*row.columns, *(cell.text or "" for cell in row.cells))),
    )


def _check_text_coverage(fieldset: Tag, sections: tuple[CensalSection, ...]) -> None:
    retained = " ".join(text for section in sections for text in _retained_text(section))
    if any(" ".join(text.split()) not in retained for text in fieldset.stripped_strings):
        raise census_shape_error("tax-status section contains unparsed text")


def _sections(fieldset: Tag) -> tuple[CensalSection, ...]:
    legend = fieldset.find("legend", recursive=False)
    if not isinstance(legend, Tag) or not bool(census_text(legend)):
        raise census_shape_error("tax-status fieldset has no label")
    title = census_text(legend) or ""
    state = _TaxSectionRows(title=title, current_title=title)
    for row in fieldset.select("ul, tr"):
        if row.find_parent("fieldset") is not fieldset or row.find_parent("ul") is not None:
            continue
        cells = _row_cells(row)
        if cells:
            state.append(cells)
    sections = state.finish()
    _check_text_coverage(fieldset, sections)
    return sections


def _check_tax_sections(fieldsets: list[Tag]) -> None:
    if not fieldsets:
        raise census_shape_error("tax-status sections missing")
    titles = {
        census_key(census_text(legend) or "")
        for fieldset in fieldsets
        if isinstance(legend := fieldset.find("legend", recursive=False), Tag)
    }
    if not _REQUIRED_TAX_SECTIONS.issubset(titles):
        raise census_shape_error("required tax-status section is missing or renamed")


def parse_censal_tax_status(html: str, *, source_url: str) -> CensalConsultation:
    """Retain every rendered regime/option row, casilla and unknown label.

    Callers supply post-JavaScript HTML. Script literals are not observations;
    only the resulting marks, dates and text are retained.
    """
    soup = census_document(html)
    if not any(census_key(census_text(h) or "") == "situaciontributaria" for h in soup.select("h1, [role=heading]")):
        raise census_shape_error("tax-status heading missing")
    fieldsets = soup.select("fieldset")
    _check_tax_sections(list(fieldsets))
    sections = tuple(section for fieldset in fieldsets for section in _sections(fieldset))
    return CensalConsultation(kind="situacion_tributaria", source_url=census_source_url(source_url), sections=sections)
