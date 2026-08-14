"""Extraction of the non-activity sections of an annual IVA Orden."""

from __future__ import annotations

import re
from re import Match

from bs4 import BeautifulSoup, Tag

from ._orden_anual_html import (
    AGRICULTURAL_ACTIVITY_RE,
    AGRICULTURAL_INDEX_RE,
    DIFFICULT_JUSTIFICATION_RE,
    OrdenAnualHtmlParseError,
    OrdenAnualIvaAgriculturalIndex,
    OrdenAnualIvaAgriculturalIngresoACuenta,
    OrdenAnualIvaDifficultJustification,
    OrdenAnualIvaIngresoACuenta,
    OrdenAnualIvaLorca2022Reduction,
    annex_heading_for,
    normalise_html_text,
    parse_decimal,
    parse_percent,
    row_values,
)

_LORCA_2022_HEADING_MARKERS = (
    "Disposición adicional cuarta.",
    "Reducción en 2022",
    "término municipal de Lorca",
)
_LORCA_2022_IVA_MARKERS = (
    "2.",
    "anexo II de esta Orden",
    "régimen especial simplificado",
    "20 por ciento",
    "cuotas devengadas por operaciones corrientes",
    "año 2022",
)
_LORCA_2022_PERIOD_MARKERS = (
    "cuota trimestral",
    "cuota anual",
    "régimen especial simplificado",
    "año 2022",
)
_LORCA_2022_RATE_RE = re.compile(r"reducir\s+en\s+un\s+([0-9]+(?:,[0-9]+)?)\s+por\s+ciento", re.I)


def extract_agricultural_indexes(
    table: Tag,
    *,
    source_label: str,
) -> tuple[OrdenAnualIvaAgriculturalIndex, ...]:
    """Extract the ANEXO I activity/index pairs from one table."""
    _require_annex(table, expected="ANEXO I", source_label=source_label, kind="agricultural index")
    activity_rows: list[tuple[str, str]] = []
    indexes: list[OrdenAnualIvaAgriculturalIndex] = []
    for row_text in _table_row_texts(table):
        activity_match = AGRICULTURAL_ACTIVITY_RE.match(row_text)
        if activity_match is not None:
            _require_no_pending_activity(activity_rows, source_label=source_label)
            activity_rows.append((activity_match.group(1).strip(), row_text))
            continue
        index_match = AGRICULTURAL_INDEX_RE.match(row_text)
        if index_match is None:
            continue
        if not activity_rows:
            raise OrdenAnualHtmlParseError(
                f"annual Orden source {source_label!r} agricultural quota index has no activity heading",
            )
        activity_name, activity_text = activity_rows.pop()
        indexes.append(
            OrdenAnualIvaAgriculturalIndex(
                annex_heading="ANEXO I",
                activity_name=activity_name,
                cuota_devengada_index=parse_decimal(
                    index_match.group(1),
                    source_label=source_label,
                    context="agricultural quota index",
                ),
                required_text=("ANEXO I", activity_text, row_text),
            ),
        )
    if activity_rows or not indexes:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has incomplete agricultural quota-index rows",
        )
    return tuple(indexes)


def extract_ingresos_a_cuenta(
    soup: BeautifulSoup,
    *,
    source_label: str,
) -> tuple[tuple[OrdenAnualIvaAgriculturalIngresoACuenta, ...], tuple[OrdenAnualIvaIngresoACuenta, ...]]:
    """Extract the agricultural and IAE ingreso-a-cuenta tables."""
    agricultural, non_agricultural = _find_ingreso_tables(soup, source_label=source_label)
    agricultural_rows = _extract_agricultural_ingreso_rows(agricultural, source_label=source_label)
    non_agricultural_rows = _extract_non_agricultural_ingreso_rows(non_agricultural, source_label=source_label)
    if not agricultural_rows or not non_agricultural_rows:
        raise OrdenAnualHtmlParseError(f"annual Orden source {source_label!r} has an empty ingreso-a-cuenta table")
    return tuple(agricultural_rows), tuple(non_agricultural_rows)


def extract_difficult_justification(
    soup: BeautifulSoup,
    *,
    source_label: str,
) -> OrdenAnualIvaDifficultJustification:
    """Extract the matching one-percent difficult-justification clauses."""
    clauses = _difficult_justification_clauses(soup)
    agricultural = tuple(item for item in clauses if item[2] == "ANEXO I")
    non_agricultural = tuple(item for item in clauses if item[2] == "ANEXO II")
    if len(agricultural) != 1 or len(non_agricultural) != 1:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} must state one difficult-justification clause per IVA cohort",
        )
    agricultural_rate = _clause_rate(agricultural[0], source_label=source_label, cohort="agricultural")
    non_agricultural_rate = _clause_rate(non_agricultural[0], source_label=source_label, cohort="non-agricultural")
    if agricultural_rate != non_agricultural_rate:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has non-matching cohort difficult-justification rates",
        )
    return OrdenAnualIvaDifficultJustification(
        percentage=agricultural_rate,
        agricultural_required_text=agricultural[0][1],
        non_agricultural_required_text=non_agricultural[0][1],
    )


def extract_lorca_2022_reduction(
    soup: BeautifulSoup,
    *,
    source_label: str,
) -> OrdenAnualIvaLorca2022Reduction | None:
    """Return the sole exact 2022 Annex-II Lorca IVA reduction, when published."""
    heading = _find_lorca_2022_heading(soup, source_label=source_label)
    if heading is None:
        return None
    paragraphs = _lorca_2022_paragraphs(heading)
    iva_clause, period_clause = _lorca_2022_clauses(paragraphs, source_label=source_label)
    return OrdenAnualIvaLorca2022Reduction(
        municipality="Lorca",
        percentage=_lorca_2022_rate(iva_clause, source_label=source_label),
        required_text=(
            normalise_html_text(heading.get_text(" ", strip=True)),
            iva_clause,
            period_clause,
        ),
    )


def _find_lorca_2022_heading(soup: BeautifulSoup, *, source_label: str) -> Tag | None:
    headings = tuple(
        tag
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        if _contains_all_markers(normalise_html_text(tag.get_text(" ", strip=True)), _LORCA_2022_HEADING_MARKERS)
    )
    if not headings:
        return None
    if len(headings) != 1:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has ambiguous Lorca 2022 reduction headings",
        )
    return headings[0]


def _contains_all_markers(text: str, markers: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return bool(text) and all(marker.casefold() in folded for marker in markers)


def _lorca_2022_paragraphs(heading: Tag) -> tuple[str, ...]:
    paragraphs: list[str] = []
    for tag in heading.find_all_next(["h1", "h2", "h3", "h4", "h5", "h6", "p"]):
        if tag is not heading and tag.name.startswith("h"):
            break
        if tag.name == "p":
            text = normalise_html_text(tag.get_text(" ", strip=True))
            if text:
                paragraphs.append(text)
    return tuple(paragraphs)


def _lorca_2022_clauses(paragraphs: tuple[str, ...], *, source_label: str) -> tuple[str, str]:
    iva_clauses = tuple(text for text in paragraphs if _contains_all_markers(text, _LORCA_2022_IVA_MARKERS))
    period_clauses = tuple(text for text in paragraphs if _contains_all_markers(text, _LORCA_2022_PERIOD_MARKERS))
    if len(iva_clauses) != 1 or len(period_clauses) != 1:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has incomplete Lorca 2022 IVA reduction clauses",
        )
    return iva_clauses[0], period_clauses[0]


def _lorca_2022_rate(iva_clause: str, *, source_label: str):
    rate_match = _LORCA_2022_RATE_RE.search(iva_clause)
    if rate_match is None:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has no numeric Lorca 2022 IVA reduction rate",
        )
    return parse_percent(
        rate_match.group(1),
        source_label=source_label,
        context="Lorca 2022 IVA reduction",
    )


def _table_row_texts(table: Tag) -> tuple[str, ...]:
    return tuple(normalise_html_text(row.get_text(" ", strip=True)) for row in table.find_all("tr"))


def _require_no_pending_activity(rows: list[tuple[str, str]], *, source_label: str) -> None:
    if rows:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} agricultural activity has no quota index",
        )


def _require_annex(table: Tag, *, expected: str, source_label: str, kind: str) -> None:
    if annex_heading_for(table) != expected:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} {kind} table is not scoped by {expected}",
        )


def _find_ingreso_tables(soup: BeautifulSoup, *, source_label: str) -> tuple[Tag, Tag]:
    agricultural_tables: list[Tag] = []
    non_agricultural_tables: list[Tag] = []
    for table in soup.find_all("table"):
        headers = _first_row_headers(table)
        if headers == ("Actividad", "Porcentaje"):
            agricultural_tables.append(table)
        elif headers == ("IAE", "Actividad económica", "Porcentaje"):
            non_agricultural_tables.append(table)
    if len(agricultural_tables) != 1 or len(non_agricultural_tables) != 1:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} must have exactly one agricultural and one "
            "IAE ingreso-a-cuenta table",
        )
    agricultural, non_agricultural = agricultural_tables[0], non_agricultural_tables[0]
    _require_annex(agricultural, expected="ANEXO I", source_label=source_label, kind="agricultural ingreso-a-cuenta")
    return agricultural, non_agricultural


def _first_row_headers(table: Tag) -> tuple[str, ...]:
    first_row = table.find("tr")
    if first_row is None:
        return ()
    return tuple(
        normalise_html_text(cell.get_text(" ", strip=True))
        for cell in first_row.find_all(["td", "th"], recursive=False)
    )


def _extract_agricultural_ingreso_rows(
    table: Tag,
    *,
    source_label: str,
) -> list[OrdenAnualIvaAgriculturalIngresoACuenta]:
    rows: list[OrdenAnualIvaAgriculturalIngresoACuenta] = []
    for row in table.find_all("tr")[1:]:
        values = row_values(row, expected_cells=2, source_label=source_label, context="agricultural ingreso-a-cuenta")
        rows.append(
            OrdenAnualIvaAgriculturalIngresoACuenta(
                annex_heading="ANEXO I",
                activity_name=values[0],
                percentage=parse_percent(values[1], source_label=source_label, context="agricultural ingreso-a-cuenta"),
                required_text=("ANEXO I", " ".join(values)),
            ),
        )
    return rows


def _extract_non_agricultural_ingreso_rows(
    table: Tag,
    *,
    source_label: str,
) -> list[OrdenAnualIvaIngresoACuenta]:
    rows: list[OrdenAnualIvaIngresoACuenta] = []
    for row in table.find_all("tr")[1:]:
        values = row_values(row, expected_cells=3, source_label=source_label, context="IAE ingreso-a-cuenta")
        rows.append(
            OrdenAnualIvaIngresoACuenta(
                iae_epigrafe=values[0],
                activity_name=values[1],
                percentage=parse_percent(values[2], source_label=source_label, context="IAE ingreso-a-cuenta"),
                required_text=" ".join(values),
            ),
        )
    return rows


def _difficult_justification_clauses(
    soup: BeautifulSoup,
) -> tuple[tuple[Match[str], str, str], ...]:
    return tuple(
        (match, text, annex_heading_for(tag))
        for tag in soup.find_all("p")
        if (text := normalise_html_text(tag.get_text(" ", strip=True)))
        if (match := DIFFICULT_JUSTIFICATION_RE.search(text)) is not None
    )


def _clause_rate(clause: tuple[Match[str], str, str], *, source_label: str, cohort: str):
    return parse_decimal(
        clause[0].group("percentage"),
        source_label=source_label,
        context=f"{cohort} difficult-justification rate",
    )
