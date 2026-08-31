"""Pure DOM extraction for the annual-Orden IVA simplified-regime authority.

The annual BOE Orders publish a single regulatory programme: non-agricultural
module tables, agricultural quota indexes, ingreso-a-cuenta percentage tables,
seasonal indexes, and the difficult-justification deduction.  The registry and
the development-side corpus writer both project this immutable source IR; no
consumer is permitted to parse a competing subset of the HTML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, ClassVar, Final, Literal

from pydantic import TypeAdapter

from .text_fold import fold_diacritics

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

# BeautifulSoup and its lxml backend cost roughly 100 ms to import and are
# reached only when an orden anual HTML document is actually parsed. Binding
# them here put that cost on every importer of the core facade, including the
# supervised key-derivation child process, which parses no HTML at all. Every
# other reference in this module is an annotation, and annotations are strings
# under ``from __future__ import annotations``, so only the two runtime uses
# below need the real objects.

_ACTIVITY_MARKER = "cuota devengada anual por unidad"
_AGRICULTURAL_INDEX_MARKER = "índice de cuota devengada por operaciones corrientes"
_ACTIVITY_HEADING_RE = re.compile(
    r"Actividad:\s*(.+?)(?=\s+Ep[ií]grafe\s+I\.?A\.?E\.?\s*:?|\s+M[oó]dulo|$)",
    re.I,
)
AGRICULTURAL_ACTIVITY_RE = re.compile(r"^Actividad:\s*(.+?)\.?$", re.I)
AGRICULTURAL_INDEX_RE = re.compile(
    r"^Índice de cuota devengada por operaciones corrientes:\s*([0-9]+(?:,[0-9]+)?)\.?$",
    re.I,
)
_IAE_HEADING_RE = re.compile(r"Ep[ií]grafe\s+I\.?A\.?E\.?\s*:?\s*(.+?)(?=\s+M[oó]dulo|$)", re.I)
_MINIMUM_QUOTA_RE = re.compile(
    r"Cuota m[ií]nima por operaciones corrientes:\s*(\d+(?:,\d+)?)\s*%\s+de la cuota devengada",
    re.I,
)
_MODULE_ORDER_RE = re.compile(r"(?P<order>[1-7])\.?$")
_SEASONAL_INDEX_RE = re.compile(
    r"(?:Hasta\s+(?P<until_60>60)\s+d[ií]as de temporada|"
    r"De\s+(?P<from_61>61)\s+a\s+(?P<until_120>120)\s+d[ií]as de temporada|"
    r"De\s+(?P<from_121>121)\s+a\s+(?P<until_180>180)\s+d[ií]as de temporada)"
    r"\s*:\s*(?P<coefficient>[0-9]+(?:,[0-9]+)?)\.?",
    re.I,
)
DIFFICULT_JUSTIFICATION_RE = re.compile(
    r"ser[aá]\s+deducible\s+el\s+(?P<percentage>[0-9]+)\s+por\s+ciento.*?"
    r"cuotas soportadas.*?dif[ií]cil justificaci[oó]n",
    re.I,
)
_SPACE_RE = re.compile(r"\s+")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class OrdenAnualHtmlParseError(ValueError):
    """Raised when an annual IVA authority source is structurally malformed."""

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
    """One non-agricultural source-stated annual IVA quota table."""

    annex_heading: Literal["ANEXO II"]
    activity_name: str
    iae_epigrafe: str
    modules: tuple[OrdenAnualIvaModule, ...]
    cuota_minima_pct: Decimal
    required_text: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaAgriculturalIndex:
    """One agricultural IVA quota index, published without a DP30302 code."""

    annex_heading: Literal["ANEXO I"]
    activity_name: str
    cuota_devengada_index: Decimal
    required_text: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaIngresoACuenta:
    """One non-agricultural IAE ingreso-a-cuenta percentage row."""

    iae_epigrafe: str
    activity_name: str
    percentage: Decimal
    required_text: str


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaAgriculturalIngresoACuenta:
    """One agricultural ingreso-a-cuenta row, published without a code crosswalk."""

    annex_heading: Literal["ANEXO I"]
    activity_name: str
    percentage: Decimal
    required_text: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaSeasonalIndex:
    """One source-stated seasonal-days coefficient band."""

    minimum_days: int
    maximum_days: int
    coefficient: Decimal
    required_text: str


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaDifficultJustification:
    """The mutually agreeing agricultural/non-agricultural one-percent clauses."""

    percentage: Decimal
    agricultural_required_text: str
    non_agricultural_required_text: str


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaLorca2022Reduction:
    """The source-stated Annex-II Lorca reduction for the 2022 IVA regime."""

    municipality: Literal["Lorca"]
    percentage: Decimal
    required_text: tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaAuthority:
    """Complete annual-Orden IVA simplified-regime source IR for one exercise."""

    non_agricultural_activities: tuple[OrdenAnualIvaActivityTable, ...]
    agricultural_indexes: tuple[OrdenAnualIvaAgriculturalIndex, ...]
    non_agricultural_ingresos_a_cuenta: tuple[OrdenAnualIvaIngresoACuenta, ...]
    agricultural_ingresos_a_cuenta: tuple[OrdenAnualIvaAgriculturalIngresoACuenta, ...]
    seasonal_indexes: tuple[OrdenAnualIvaSeasonalIndex, ...]
    difficult_justification: OrdenAnualIvaDifficultJustification
    lorca_2022_reduction: OrdenAnualIvaLorca2022Reduction | None


@dataclass(frozen=True, slots=True)
class OrdenAnualIvaAuthorityUnit:
    """One corpus unit rendered from the same source authority IR."""

    anchor: str
    title: str
    section: str
    text: str


def extract_orden_anual_iva_authority(markup: bytes, *, source_label: str) -> OrdenAnualIvaAuthority:
    """Extract the complete IVA simplified-regime authority from one Orden source."""
    from bs4 import BeautifulSoup

    from .orden_anual_sections import (
        extract_agricultural_indexes,
        extract_difficult_justification,
        extract_ingresos_a_cuenta,
        extract_lorca_2022_reduction,
    )

    soup = BeautifulSoup(markup, "lxml")
    non_agricultural_activities = tuple(
        _extract_activity_table(table, source_label=source_label)
        for table in soup.find_all("table")
        if _is_annual_iva_quota_table(table)
    )
    agricultural_indexes = tuple(
        item
        for table in soup.find_all("table")
        if _is_agricultural_index_table(table)
        for item in extract_agricultural_indexes(table, source_label=source_label)
    )
    agricultural_ingresos_a_cuenta, non_agricultural_ingresos_a_cuenta = extract_ingresos_a_cuenta(
        soup,
        source_label=source_label,
    )
    seasonal_indexes = _extract_seasonal_indexes(soup, source_label=source_label)
    difficult_justification = extract_difficult_justification(soup, source_label=source_label)
    return OrdenAnualIvaAuthority(
        non_agricultural_activities=non_agricultural_activities,
        agricultural_indexes=agricultural_indexes,
        non_agricultural_ingresos_a_cuenta=non_agricultural_ingresos_a_cuenta,
        agricultural_ingresos_a_cuenta=agricultural_ingresos_a_cuenta,
        seasonal_indexes=seasonal_indexes,
        difficult_justification=difficult_justification,
        lorca_2022_reduction=extract_lorca_2022_reduction(soup, source_label=source_label),
    )


def extract_orden_anual_iva_tables(
    markup: bytes,
    *,
    source_label: str,
) -> tuple[OrdenAnualIvaActivityTable, ...]:
    """Return the non-agricultural activity projection of the aggregate authority."""
    return extract_orden_anual_iva_authority(markup, source_label=source_label).non_agricultural_activities


def orden_anual_iva_authority_units(authority: OrdenAnualIvaAuthority) -> tuple[OrdenAnualIvaAuthorityUnit, ...]:
    """Render stable corpus units from all annual-Orden IVA authority axes."""
    activity_anchors = orden_anual_iva_activity_anchors(authority.non_agricultural_activities)
    agricultural_anchors = _stable_anchors(
        tuple(f"m303-anexo-i-iva-{_semantic_slug(item.activity_name)}" for item in authority.agricultural_indexes),
    )
    units: list[OrdenAnualIvaAuthorityUnit] = [
        OrdenAnualIvaAuthorityUnit(
            anchor=anchor,
            title=activity.activity_name,
            section="ANEXO II · IVA",
            text=orden_anual_iva_table_text(activity),
        )
        for activity, anchor in zip(authority.non_agricultural_activities, activity_anchors, strict=True)
    ]
    units.extend(
        OrdenAnualIvaAuthorityUnit(
            anchor=anchor,
            title=item.activity_name,
            section="ANEXO I · IVA",
            text="\n".join(item.required_text),
        )
        for item, anchor in zip(authority.agricultural_indexes, agricultural_anchors, strict=True)
    )
    units.extend(
        (
            OrdenAnualIvaAuthorityUnit(
                anchor="#m303-anexo-i-iva-ingreso-a-cuenta",
                title="Porcentajes de ingreso a cuenta agrícolas",
                section="ANEXO I · IVA",
                text="\n".join("\n".join(item.required_text) for item in authority.agricultural_ingresos_a_cuenta),
            ),
            OrdenAnualIvaAuthorityUnit(
                anchor="#m303-anexo-ii-iva-ingreso-a-cuenta",
                title="Porcentajes de ingreso a cuenta por IAE",
                section="ANEXO II · IVA",
                text="\n".join(item.required_text for item in authority.non_agricultural_ingresos_a_cuenta),
            ),
            OrdenAnualIvaAuthorityUnit(
                anchor="#m303-iva-indices-correctores-temporada",
                title="Índices correctores por días de temporada",
                section="IVA · Régimen simplificado",
                text="\n".join(item.required_text for item in authority.seasonal_indexes),
            ),
            OrdenAnualIvaAuthorityUnit(
                anchor="#m303-iva-cuotas-soportadas-dificil-justificacion",
                title="Cuotas soportadas de difícil justificación",
                section="IVA · Régimen simplificado",
                text="\n".join(
                    (
                        authority.difficult_justification.agricultural_required_text,
                        authority.difficult_justification.non_agricultural_required_text,
                    ),
                ),
            ),
        ),
    )
    if authority.lorca_2022_reduction is not None:
        units.append(
            OrdenAnualIvaAuthorityUnit(
                anchor="#m303-da-4-lorca-2022-reduction",
                title="Reducción Lorca 2022 de cuota devengada IVA",
                section="Disposición adicional cuarta · IVA",
                text="\n".join(authority.lorca_2022_reduction.required_text),
            ),
        )
    return tuple(units)


def orden_anual_iva_table_text(activity: OrdenAnualIvaActivityTable) -> str:
    """Render the whole lexical evidence payload of one annual quota table."""
    return "\n".join(activity.required_text)


def orden_anual_iva_activity_anchors(
    activities: tuple[OrdenAnualIvaActivityTable, ...],
) -> tuple[str, ...]:
    """Return stable non-agricultural corpus anchors, suffixing repeated identities."""
    return _stable_anchors(tuple(_activity_anchor_base(activity) for activity in activities))


def _is_annual_iva_quota_table(table: Tag) -> bool:
    return _ACTIVITY_MARKER in normalise_html_text(table.get_text(" ", strip=True)).casefold()


def _is_agricultural_index_table(table: Tag) -> bool:
    return _AGRICULTURAL_INDEX_MARKER in normalise_html_text(table.get_text(" ", strip=True)).casefold()


def _extract_activity_table(table: Tag, *, source_label: str) -> OrdenAnualIvaActivityTable:
    annex_heading = annex_heading_for(table)
    if annex_heading != "ANEXO II":
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} non-agricultural quota table is not scoped by ANEXO II",
        )
    table_text = normalise_html_text(table.get_text(" ", strip=True))
    activity_name, iae_epigrafe = _extract_activity_identity(table, table_text, source_label=source_label)
    footer_text, cuota_minima_pct = _extract_minimum_quota(table, source_label=source_label)
    modules = _extract_modules(table, source_label=source_label)
    return OrdenAnualIvaActivityTable(
        annex_heading="ANEXO II",
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


def _extract_seasonal_indexes(soup: BeautifulSoup, *, source_label: str) -> tuple[OrdenAnualIvaSeasonalIndex, ...]:
    matches = tuple(
        (match, text)
        for tag in soup.find_all(["p", "li"])
        if (text := normalise_html_text(tag.get_text(" ", strip=True)))
        for match in _SEASONAL_INDEX_RE.finditer(text)
    )
    if len(matches) != 3:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} must state exactly three seasonal index bands, got {len(matches)}",
        )
    bands: list[OrdenAnualIvaSeasonalIndex] = []
    for match, text in matches:
        if match.group("until_60") is not None:
            minimum_days, maximum_days = 1, 60
        elif match.group("until_120") is not None:
            minimum_days, maximum_days = 61, 120
        elif match.group("until_180") is not None:
            minimum_days, maximum_days = 121, 180
        else:
            raise OrdenAnualHtmlParseError(f"annual Orden source {source_label!r} has an unrecognised seasonal band")
        bands.append(
            OrdenAnualIvaSeasonalIndex(
                minimum_days=minimum_days,
                maximum_days=maximum_days,
                coefficient=parse_decimal(
                    match.group("coefficient"),
                    source_label=source_label,
                    context="seasonal index",
                ),
                required_text=text,
            ),
        )
    return tuple(bands)


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
    matches = tuple(
        (text, match)
        for row in table.find_all("tr")
        if (text := normalise_html_text(row.get_text(" ", strip=True)))
        if (match := _MINIMUM_QUOTA_RE.search(text)) is not None
    )
    if len(matches) != 1:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} quota table lacks a numeric cuota mínima footer",
        )
    footer_text, minimum_quota_match = matches[0]
    return footer_text, parse_decimal(
        minimum_quota_match.group(1), source_label=source_label, context="cuota mínima percentage"
    )


def _extract_modules(table: Tag, *, source_label: str) -> tuple[OrdenAnualIvaModule, ...]:
    body = table.find("tbody")
    if body is None:
        raise OrdenAnualHtmlParseError(f"annual Orden source {source_label!r} quota table has no module body")
    modules = tuple(
        module
        for row in body.find_all("tr", recursive=False)
        for module in _extract_module_rows(row, source_label=source_label)
    )
    if tuple(module.order for module in modules) != tuple(range(1, len(modules) + 1)):
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has incomplete or unordered module rows",
        )
    return modules


def _extract_module_rows(row: Tag, *, source_label: str) -> tuple[OrdenAnualIvaModule, ...]:
    cells = tuple(row.find_all(["td", "th"], recursive=False))
    if len(cells) != 4:
        return ()
    columns = tuple(tuple(normalise_html_text(value) for value in cell.stripped_strings) for cell in cells)
    if columns[0] == ("Módulo",):
        return ()
    lengths = {len(column) for column in columns}
    if len(lengths) != 1 or not columns[0]:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} module row has incomplete column values",
        )
    return tuple(_module_from_values(values, source_label=source_label) for values in zip(*columns, strict=True))


def _module_from_values(values: tuple[str, str, str, str], *, source_label: str) -> OrdenAnualIvaModule:
    order_match = _MODULE_ORDER_RE.fullmatch(values[0])
    if order_match is None:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} module order is not a numeric first cell",
        )
    order = int(order_match.group("order"))
    return OrdenAnualIvaModule(
        order=order,
        definition=values[1],
        unit=values[2],
        coefficient=parse_decimal(values[3], source_label=source_label, context="module coefficient", thousands=True),
        required_text=" ".join(values),
    )


def row_values(row: Tag, *, expected_cells: int, source_label: str, context: str) -> tuple[str, ...]:
    cells = tuple(row.find_all(["td", "th"], recursive=False))
    if len(cells) != expected_cells:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} has a {context} row with {len(cells)} cells",
        )
    return tuple(normalise_html_text(cell.get_text(" ", strip=True)) for cell in cells)


def parse_decimal(value: str, *, source_label: str, context: str, thousands: bool = False) -> Decimal:
    normalised = value.replace("%", "").strip()
    if thousands:
        normalised = normalised.replace(".", "")
    try:
        return Decimal(normalised.replace(",", "."))
    except InvalidOperation as exc:
        raise OrdenAnualHtmlParseError(
            f"annual Orden source {source_label!r} {context} is not a decimal",
        ) from exc


def parse_percent(value: str, *, source_label: str, context: str) -> Decimal:
    """Parse a source percentage through the annual-Orden decimal authority."""
    return parse_decimal(value, source_label=source_label, context=context)


def _activity_heading_from_text(text: str) -> tuple[str | None, str | None]:
    activity_match = _ACTIVITY_HEADING_RE.search(text)
    iae_match = _IAE_HEADING_RE.search(text)
    activity = activity_match.group(1) if activity_match is not None else None
    iae = iae_match.group(1) if iae_match is not None else None
    return (
        activity.strip() if isinstance(activity, str) else None,
        iae.strip() if isinstance(iae, str) else None,
    )


_HEADING_LEVELS: Final[frozenset[str]] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_ANNEX_HEADING_CLASSES: Final[frozenset[str]] = frozenset({"anexo_num", "anexo"})

#: Attribute the per-document annex index is stashed under, on the parse root.
#:
#: Keyed by ``id()``, which is sound ONLY because the index lives on the root
#: that owns every element it indexes: the keys and the objects they identify
#: are freed together, so an id can never be reused while the map still claims
#: it. An index held anywhere else would not have that guarantee.
_ANNEX_INDEX_ATTRIBUTE: Final[str] = "_cadrumo_annex_heading_index"
_ANNEX_INDEX_ADAPTER: TypeAdapter[dict[int, str]] = TypeAdapter(dict[int, str])


def _is_annex_heading(tag: Tag) -> bool:
    return tag.name in _HEADING_LEVELS and bool(
        _ANNEX_HEADING_CLASSES.intersection(tag.get_attribute_list("class")),
    )


def _annex_heading_index(root: Tag) -> dict[int, str]:
    """Return, for every element under ``root``, the annex heading before it.

    One forward pass in document order carrying the last annex heading seen,
    which is the same answer walking backwards from each element gives, because
    ``descendants`` order IS document order. The heading is recorded BEFORE the
    current element is examined, so an annex heading maps to the heading above
    it rather than to itself -- matching a backward search, which never returns
    the element it starts from.
    """
    # Imported here, not at module scope: binding bs4 eagerly would put its
    # ~100 ms import on every importer of the core facade, which is the whole
    # reason this module defers it.
    from bs4 import Tag as _Tag

    cached_raw = getattr(root, _ANNEX_INDEX_ATTRIBUTE, None)
    if cached_raw is not None:
        return _ANNEX_INDEX_ADAPTER.validate_python(cached_raw)
    index: dict[int, str] = {}
    current = ""
    for element in root.descendants:
        if not isinstance(element, _Tag):
            continue
        index[id(element)] = current
        if _is_annex_heading(element):
            current = normalise_html_text(element.get_text(" ", strip=True))
    setattr(root, _ANNEX_INDEX_ATTRIBUTE, index)
    return index


def annex_heading_for(tag: Tag) -> str:
    """Return the annex heading scoping ``tag``, or ``""`` when it has none.

    Answered from a per-document index rather than by searching backwards from
    ``tag``. The backward form called a Python predicate on every preceding
    element, so cost grew with the tag's depth into the document and the same
    prefix was rescanned once per call; over the bundled corpus that was 617s
    against 0.13s for the indexed form, identical answers throughout.
    """
    root = tag
    while root.parent is not None:
        root = root.parent
    return _annex_heading_index(root).get(id(tag), "")


def _activity_heading_from_preceding_siblings(table: Tag) -> tuple[str | None, str | None]:
    from bs4 import Tag as _Tag

    preceding_text = ""
    for sibling in table.previous_siblings:
        if not isinstance(sibling, _Tag):
            continue
        if sibling.name == "table":
            break
        preceding_text = f"{normalise_html_text(sibling.get_text(' ', strip=True))} {preceding_text}"
        activity_name, iae_epigrafe = _activity_heading_from_text(preceding_text)
        if activity_name is not None and iae_epigrafe is not None:
            return activity_name, iae_epigrafe
    return None, None


def _activity_anchor_base(activity: OrdenAnualIvaActivityTable) -> str:
    identity = "-".join((_semantic_slug(activity.iae_epigrafe), _semantic_slug(activity.activity_name)))
    return f"m303-anexo-ii-iva-{identity}"


def _stable_anchors(base_anchors: tuple[str, ...]) -> tuple[str, ...]:
    totals = {anchor: base_anchors.count(anchor) for anchor in set(base_anchors)}
    occurrences: dict[str, int] = {}
    anchors: list[str] = []
    for base_anchor in base_anchors:
        occurrence = occurrences.get(base_anchor, 0) + 1
        occurrences[base_anchor] = occurrence
        suffix = f"-{occurrence}" if totals[base_anchor] > 1 else ""
        anchors.append(f"#{base_anchor}{suffix}")
    return tuple(anchors)


def _semantic_slug(value: str) -> str:
    decomposed = fold_diacritics(value).encode("ascii", "ignore").decode("ascii").casefold()
    compact = _SLUG_RE.sub("-", decomposed).strip("-")
    if not compact:
        raise OrdenAnualHtmlParseError("annual Orden activity heading has no semantic identity")
    return compact


def normalise_html_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value).strip()


__all__ = [
    "OrdenAnualHtmlParseError",
    "OrdenAnualIvaActivityTable",
    "OrdenAnualIvaAgriculturalIndex",
    "OrdenAnualIvaAgriculturalIngresoACuenta",
    "OrdenAnualIvaAuthority",
    "OrdenAnualIvaAuthorityUnit",
    "OrdenAnualIvaDifficultJustification",
    "OrdenAnualIvaIngresoACuenta",
    "OrdenAnualIvaLorca2022Reduction",
    "OrdenAnualIvaModule",
    "OrdenAnualIvaSeasonalIndex",
    "extract_orden_anual_iva_authority",
    "extract_orden_anual_iva_tables",
    "orden_anual_iva_activity_anchors",
    "orden_anual_iva_authority_units",
    "orden_anual_iva_table_text",
]
