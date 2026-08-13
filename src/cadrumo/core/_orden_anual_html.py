"""Pure DOM extraction for annual-Orden IVA activity tables.

The annual BOE orders encode the simplified-regime quota catalogue as a
regular family of HTML tables.  This module is deliberately independent from
the registry and the development-side corpus writer: both consumers use this
one parser and project its immutable table IR into their own contracts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import ClassVar, Literal
from unicodedata import normalize

from bs4 import BeautifulSoup, Tag

_ACTIVITY_MARKER = "cuota devengada anual por unidad"
_ACTIVITY_HEADING_RE = re.compile(
    r"Actividad:\s*(.+?)(?=\s+Ep[ií]grafe\s+I\.A\.E\.?|\s+M[oó]dulo|$)",
    re.I,
)
_IAE_HEADING_RE = re.compile(r"Ep[ií]grafe\s+I\.A\.E\.?\s*:?\s*(.+?)(?=\s+M[oó]dulo|$)", re.I)
_MINIMUM_QUOTA_RE = re.compile(
    r"Cuota m[ií]nima por operaciones corrientes:\s*(\d+(?:,\d+)?)\s*%\s+de la cuota devengada",
    re.I,
)
_SPACE_RE = re.compile(r"\s+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class OrdenAnualHtmlParseError(ValueError):
    """Raised when an annual IVA quota table is structurally malformed."""

    __bare_base_rationale__: ClassVar[str] = "internal-orden-anual-html-structural-parser-carrier"


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaModule:
    """One source-stated annual IVA quota row before registry projection."""

    order: int
    definition: str
    unit: str
    coefficient: Decimal
    required_text: str


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaActivityTable:
    """One source-stated annual IVA activity table before registry projection."""

    annex_heading: Literal["ANEXO II"]
    activity_name: str
    iae_epigrafe: str
    modules: tuple[OrdenAnualIvaModule, ...]
    cuota_minima_pct: Decimal
    required_text: tuple[str, ...]


def extract_orden_anual_iva_tables(
    markup: bytes,
    *,
    source_label: str,
) -> tuple[OrdenAnualIvaActivityTable, ...]:
    """Extract every annual IVA quota table from one official Orden HTML source."""
    soup = BeautifulSoup(markup, "lxml")
    return tuple(
        _extract_activity_table(table, source_label=source_label)
        for table in soup.find_all("table")
        if _is_annual_iva_quota_table(table)
    )


def orden_anual_iva_table_text(activity: OrdenAnualIvaActivityTable) -> str:
    """Render the whole lexical evidence payload of one annual quota table."""
    return "\n".join(activity.required_text)


def orden_anual_iva_activity_anchors(
    activities: tuple[OrdenAnualIvaActivityTable, ...],
) -> tuple[str, ...]:
    """Return stable corpus-local anchors, suffixing only repeated identities."""
    base_anchors = tuple(_activity_anchor_base(activity) for activity in activities)
    totals = {anchor: base_anchors.count(anchor) for anchor in set(base_anchors)}
    occurrences: dict[str, int] = {}
    anchors: list[str] = []
    for base_anchor in base_anchors:
        occurrence = occurrences.get(base_anchor, 0) + 1
        occurrences[base_anchor] = occurrence
        suffix = f"-{occurrence}" if totals[base_anchor] > 1 else ""
        anchors.append(f"#{base_anchor}{suffix}")
    return tuple(anchors)


def _is_annual_iva_quota_table(table: Tag) -> bool:
    return _ACTIVITY_MARKER in _normalise_html_text(table.get_text(" ", strip=True)).casefold()


def _extract_activity_table(table: Tag, *, source_label: str) -> OrdenAnualIvaActivityTable:
    annex_heading = _annex_heading(table)
    if annex_heading != "ANEXO II":
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} quota table is not structurally scoped by ANEXO II",
        )
    table_text = _normalise_html_text(table.get_text(" ", strip=True))
    activity_name, iae_epigrafe = _extract_activity_identity(table, table_text, source_label=source_label)
    footer_text, cuota_minima_pct = _extract_minimum_quota(table, source_label=source_label)
    modules = _extract_modules(table, source_label=source_label)
    return OrdenAnualIvaActivityTable(
        annex_heading=annex_heading,
        activity_name=activity_name,
        iae_epigrafe=iae_epigrafe,
        modules=modules,
        cuota_minima_pct=cuota_minima_pct,
        required_text=(
            annex_heading,
            activity_name,
            iae_epigrafe,
            footer_text,
            *(module.required_text for module in modules),
        ),
    )


def _extract_activity_identity(table: Tag, table_text: str, *, source_label: str) -> tuple[str, str]:
    activity_name, iae_epigrafe = _activity_heading_from_text(table_text)
    if activity_name is None or iae_epigrafe is None:
        activity_name, iae_epigrafe = _activity_heading_from_preceding_siblings(table)
    if activity_name is None or iae_epigrafe is None:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has a quota table without activity/IAE headings",
        )
    return activity_name, iae_epigrafe


def _extract_minimum_quota(table: Tag, *, source_label: str) -> tuple[str, Decimal]:
    footer = table.find("tfoot")
    footer_text = _normalise_html_text(" ".join(footer.stripped_strings)) if footer is not None else ""
    minimum_quota_match = _MINIMUM_QUOTA_RE.search(footer_text)
    if minimum_quota_match is None:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} quota table lacks a numeric cuota mínima footer",
        )
    try:
        cuota_minima_pct = Decimal(minimum_quota_match.group(1).replace(",", "."))
    except InvalidOperation as exc:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} cuota mínima percentage is not a decimal",
        ) from exc
    return footer_text, cuota_minima_pct


def _extract_modules(table: Tag, *, source_label: str) -> tuple[OrdenAnualIvaModule, ...]:
    body = table.find("tbody")
    if body is None:
        raise OrdenAnualHtmlParseError(f"annual Orden source {source_label!r} quota table has no module body")
    modules = tuple(_extract_module_row(row, source_label=source_label) for row in body.find_all("tr", recursive=False))
    if tuple(module.order for module in modules) != tuple(range(1, len(modules) + 1)):
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has incomplete or unordered module rows",
        )
    return modules


def _extract_module_row(row: Tag, *, source_label: str) -> OrdenAnualIvaModule:
    cells = tuple(row.find_all(["td", "th"], recursive=False))
    if len(cells) != 4:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has a module row with {len(cells)} cells",
        )
    values = tuple(_normalise_html_text(cell.get_text(" ", strip=True)) for cell in cells)
    try:
        order = int(values[0])
    except ValueError as exc:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} module order is not a numeric first cell",
        ) from exc
    try:
        coefficient = Decimal(values[3].replace(".", "").replace(",", "."))
    except InvalidOperation as exc:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} module coefficient is not a decimal",
        ) from exc
    return OrdenAnualIvaModule(
        order=order,
        definition=values[1],
        unit=values[2],
        coefficient=coefficient,
        required_text=" ".join(values),
    )


def _activity_heading_from_text(text: str) -> tuple[str | None, str | None]:
    activity_match = _ACTIVITY_HEADING_RE.search(text)
    iae_match = _IAE_HEADING_RE.search(text)
    activity = activity_match.group(1) if activity_match is not None else None
    iae = iae_match.group(1) if iae_match is not None else None
    return (
        activity.strip() if isinstance(activity, str) else None,
        iae.strip() if isinstance(iae, str) else None,
    )


def _annex_heading(table: Tag) -> str:
    heading = table.find_previous(
        lambda tag: tag.name in {"h1", "h2", "h3", "h4", "h5", "h6"} and "anexo_num" in tag.get_attribute_list("class"),
    )
    return _normalise_html_text(heading.get_text(" ", strip=True)) if heading is not None else ""


def _activity_heading_from_preceding_siblings(table: Tag) -> tuple[str | None, str | None]:
    preceding_text = ""
    for sibling in table.previous_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name == "table":
            break
        preceding_text = f"{_normalise_html_text(sibling.get_text(' ', strip=True))} {preceding_text}"
        activity_name, iae_epigrafe = _activity_heading_from_text(preceding_text)
        if activity_name is not None and iae_epigrafe is not None:
            return activity_name, iae_epigrafe
    return None, None


def _activity_anchor_base(activity: OrdenAnualIvaActivityTable) -> str:
    identity = "-".join((_semantic_slug(activity.iae_epigrafe), _semantic_slug(activity.activity_name)))
    return f"m303-anexo-ii-iva-{identity}"


def _semantic_slug(value: str) -> str:
    decomposed = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").casefold()
    compact = _SLUG_RE.sub("-", decomposed).strip("-")
    if not compact:
        raise OrdenAnualHtmlParseError("annual Orden activity heading has no semantic identity")
    return compact


def _normalise_html_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value).strip()


__all__ = [
    "OrdenAnualHtmlParseError",
    "OrdenAnualIvaActivityTable",
    "OrdenAnualIvaModule",
    "extract_orden_anual_iva_tables",
    "orden_anual_iva_activity_anchors",
    "orden_anual_iva_table_text",
]
