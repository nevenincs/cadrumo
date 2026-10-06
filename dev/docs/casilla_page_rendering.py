"""Render ordered modelo pages, their section navigation, and the casilla index.

These pages write their own raw HTML, so they escape what they put in it through
:func:`~dev.docs.compile_slots.escape` rather than :func:`html.escape`: a chrome
string or a registry label is a mark under the one multilingual compile, and
escaping the mark would leave every language's string unescaped.
"""

from __future__ import annotations

import html
import re
from collections import OrderedDict
from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

from ._locale_chrome import docs_chrome, docs_fragment, docs_line, toctree_title_chrome
from .casilla_card_rendering import _box_number, _localised, _render_entry
from .casilla_display import _section_anchor, _section_display, _token_display
from .casilla_legal_grounding import _legal_list, _LegalLink
from .casilla_markup import _raw_html, _rst_escape, _rst_heading
from .casilla_reference_models import CasillaPage, CasillaReferenceError, CompiledSchema, ModeloOverview
from .compile_slots import escape
from .terminology.casilla_anchor import casilla_page_anchor, casilla_page_relpath
from .terminology.search_record import CasillaSearchRecord

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage


# ── Page rendering ───────────────────────────────────────────────────────────


def _box_sort_key(box_number: str) -> tuple[int, int, str]:
    """Order boxes the way the printed form does, and name the two kinds apart.

    Box numbers are strings in the schema and have to be: leading zeros are
    significant and some boxes carry no number at all. Sorting them as strings
    puts 150 between 15 and 16, so a reader scanning for box 16 finds it six
    entries late. This reads a leading integer run where there is one and falls
    back to the string, which also separates numbered boxes from named ones -
    the first element of the key is the group.
    """
    leading = re.match(r"^(\d+)", box_number)
    if leading is not None:
        return (0, int(leading.group(1)), box_number)
    return (1, 0, box_number)


def _chip_title(record: CasillaSearchRecord, language: OutputLanguage) -> str:
    """Return one index chip's hover title in ``language``, escaped as an attribute.

    A casilla with no label in that language is named by its registry id, which
    is what the chip already links to, so the chip never loses its hover title.
    """
    label, _help = _localised(record, language)
    return escape(" ".join((label or str(record.casilla_id)).split()), quote=True)


def _casilla_index(
    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]],
    schema: CompiledSchema,
    modelo: str,
    language: OutputLanguage,
) -> list[str]:
    """Render a jump index over every casilla on the page.

    One chip per casilla, carrying its box number and its label as the hover
    title, grouped under the section it belongs to. Modelo 100 renders 2258 of
    them, so the chips flow rather than stack and the whole index scrolls inside
    a bounded box: a reader reaches any casilla without paging through the form,
    and the index never pushes the first card off the screen.
    """
    heading = docs_chrome("docs.casilla.chrome.casilla_index", language)
    hint = docs_chrome("docs.casilla.chrome.casilla_index_hint", language)
    lines = [
        f'<nav class="casilla-index" aria-label="{escape(heading, quote=True)}">',
        '<p class="casilla-index__lead">'
        f'<span class="casilla-index__title">{escape(heading)}</span> '
        f'<span class="casilla-index__hint">{escape(hint)}</span>'
        "</p>",
        '<div class="casilla-index__scroll">',
    ]
    for section, section_records in grouped.items():
        lines.append('<div class="casilla-index__group">')
        lines.append(
            f'<a class="casilla-index__section" href="#{escape(_section_anchor(section), quote=True)}">'
            f"{escape(_section_display(section, language))}</a>",
        )
        numbered: list[str] = []
        named: list[str] = []
        for record in section_records:
            facts = schema.casillas.get((modelo, str(record.casilla_id)))
            anchor = casilla_page_anchor(record.modelo, record.casilla_id)
            # The hover title is the casilla's registry label, which the
            # authority holds per language. The chip is one attribute value in a
            # line of ordinary markup, so each language's title is escaped and
            # folded where it is read rather than after the fact.
            title = docs_fragment(partial(_chip_title, record), language)
            box = _box_number(record, facts)
            chip = f'<a href="#{escape(anchor, quote=True)}" title="{title}">{escape(box)}</a>'
            # A casilla with no printed number falls back to its id, which is
            # five times the width of a number and would tear the grid apart.
            # The two kinds get two affordances rather than one clamped chip.
            (numbered if _box_sort_key(box)[0] == 0 else named).append(chip)
        if numbered:
            lines.append('<div class="casilla-index__chips">')
            lines.extend(numbered)
            lines.append("</div>")
        if named:
            lines.append('<div class="casilla-index__named">')
            lines.extend(named)
            lines.append("</div>")
        lines.append("</div>")
    lines.extend(["</div>", "</nav>"])
    return lines


def _definition_paragraph(overview: ModeloOverview, language: OutputLanguage) -> str | None:
    """Return the curated-definition paragraph in one language, or None where it has none.

    The definition is already one language's own string, so it is escaped as
    plain HTML rather than through the slot-aware escape: there is no mark left
    inside a value the per-language rendering resolved.
    """
    definition = overview.definitions.get(language.value)
    if not definition:
        return None
    return f'<p class="modelo-overview__definition">{html.escape(definition)}</p>'


def _page_header(
    modelo: str,
    overview: ModeloOverview | None,
    records: tuple[CasillaSearchRecord, ...],
    sections: list[tuple[tuple[str, ...], int]],
    links: dict[str, _LegalLink],
    language: OutputLanguage,
) -> tuple[str, int]:
    """Render what this modelo IS, then the jump list over its sections."""
    lines = ['<div class="modelo-overview">']
    resolved = 0
    if overview is not None:
        lines.append(f'<p class="modelo-overview__name">{escape(overview.official_name)}</p>')
        # A curated definition is authored per language, so the paragraph is a
        # paragraph only the languages that have one carry; it rides at the end
        # of the line before it with its own line break.
        lines[-1] += docs_line(lambda carried: _definition_paragraph(overview, carried), language)

    counted: dict[str, int] = {}
    for record in records:
        counted[record.input_kind.value] = counted.get(record.input_kind.value, 0) + 1
    facts: list[str] = []
    if overview is not None:
        facts.append(_token_display(overview.tax_domain))
        facts.append(docs_chrome(f"docs.casilla.cadence.{overview.cadence}", language))
    facts.append(
        docs_chrome("docs.casilla.chrome.casilla_count", language, casillas=len(records), sections=len(sections))
    )
    facts.extend(
        f"{count} {docs_chrome(f'docs.casilla.input_kind_count.{kind}', language)}"
        for kind, count in sorted(counted.items())
    )
    lines.append('<ul class="modelo-overview__facts">')
    lines.extend(f'<li class="casilla-fact">{escape(fact)}</li>' for fact in facts)
    lines.append("</ul>")

    if overview is not None and overview.legal_refs:
        legal_lines, resolved = _legal_list(
            overview.legal_refs, links, docs_chrome("docs.casilla.chrome.established_by", language)
        )
        lines.extend(legal_lines)
    lines.append("</div>")

    return _raw_html(lines), resolved


def _render_modelo_page(
    modelo: str,
    records: tuple[CasillaSearchRecord, ...],
    links: dict[str, _LegalLink],
    language: OutputLanguage,
    schema: CompiledSchema,
) -> tuple[CasillaPage, int]:
    """Render one modelo page grouped by section; return the page and its legal-link count."""
    header = (
        "..\n"
        "   Generated by dev/docs/casilla_reference.py from the registry casilla\n"
        "   projection. Do not edit by hand; regenerate.\n\n"
    )
    overview = schema.modelos.get(modelo)
    heading = (
        f"Modelo {modelo}"
        if overview is None
        else docs_chrome("docs.casilla.chrome.page_heading", language, modelo=modelo, title=overview.title)
    )
    title = _rst_heading(_rst_escape(heading), "=")

    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]] = OrderedDict()
    for record in records:
        grouped.setdefault(record.section, []).append(record)

    # Within a section, read in the order the printed form numbers its boxes.
    # Sorting here rather than in the index keeps the cards and the index in ONE
    # order: sorting only the index would send a reader clicking 16 to a card
    # sitting after 155. Section order itself is the registry's, which is the
    # official structure.
    def _order(record: CasillaSearchRecord) -> tuple[int, int, str]:
        return _box_sort_key(_box_number(record, schema.casillas.get((modelo, str(record.casilla_id)))))

    for items in grouped.values():
        items.sort(key=_order)
    section_counts = _validated_section_counts(grouped, modelo)

    numbers_by_id = {
        str(record.casilla_id): _box_number(record, schema.casillas.get((modelo, str(record.casilla_id))))
        for record in records
    }
    page_header, legal_links = _page_header(modelo, overview, records, section_counts, links, language)
    blocks: list[str] = [header + title, page_header, _raw_html(_casilla_index(grouped, schema, modelo, language))]
    anchors: list[str] = []
    seen: set[str] = set()
    rendered_legal_refs: dict[str, tuple[str, ...]] = {}
    for section, section_records in grouped.items():
        blocks.append(_rst_heading(_rst_escape(_section_display(section, language)), "-"))
        blocks.append(_raw_html([f'<span class="casilla-section-anchor" id="{_section_anchor(section)}"></span>']))
        for record in section_records:
            facts = schema.casillas.get((modelo, str(record.casilla_id)))
            entry, anchor, refs, resolved = _render_entry(record, links, language, facts, numbers_by_id)
            if anchor in seen:
                raise CasillaReferenceError(
                    f"modelo {modelo}: duplicate casilla anchor {anchor!r} "
                    f"(casilla {record.casilla_id!r}); ids must fold to a unique per-page anchor"
                )
            seen.add(anchor)
            anchors.append(anchor)
            rendered_legal_refs[anchor] = refs
            legal_links += resolved
            blocks.append(entry)

    rst = "\n".join(blocks).rstrip("\n") + "\n"
    page = CasillaPage(
        modelo=modelo,
        output_relpath=str(casilla_page_relpath(modelo)).replace("\\", "/"),
        rst=rst,
        anchors=tuple(anchors),
        rendered_legal_refs=rendered_legal_refs,
    )
    return page, legal_links


def _render_index(pages: tuple[CasillaPage, ...], schema: CompiledSchema, language: OutputLanguage) -> str:
    """Render the casilla reference toctree index over the per-modelo pages."""
    header = "..\n   Generated by dev/docs/casilla_reference.py. Do not edit by hand; regenerate.\n\n"
    title = _rst_heading(_rst_escape(docs_chrome("docs.casilla.chrome.index_title", language)), "=")
    intro = _rst_escape(docs_chrome("docs.casilla.chrome.index_intro", language)) + "\n\n"
    lines = [".. toctree::", "   :maxdepth: 1", ""]
    for page in pages:
        overview = schema.modelos.get(page.modelo)
        # The same heading as the page's own, recorded as the entry title it is
        # here: nothing educates a title the toctree directive took from its
        # own line, where the page's heading is a text block and is educated.
        label = (
            f"Modelo {page.modelo}"
            if overview is None
            else toctree_title_chrome(
                "docs.casilla.chrome.page_heading", language, modelo=page.modelo, title=overview.title
            )
        )
        lines.append(f"   {_rst_escape(label)} <{page.modelo}>")
    return header + title + "\n" + intro + "\n".join(lines) + "\n"


def _validated_section_counts(
    grouped: Mapping[tuple[str, ...], list[CasillaSearchRecord]], modelo: str
) -> list[tuple[tuple[str, ...], int]]:
    section_counts = [(section, len(items)) for section, items in grouped.items()]

    # Two distinct registry section paths can fold to one anchor slug (``a_b``
    # and ``a-b`` both give ``section-a-b``), which would ship a page whose jump
    # target is ambiguous. Refuse it the same way a casilla anchor collision is
    # refused, never silently emitting the duplicate id.
    section_anchors = [_section_anchor(section) for section, _count in section_counts]
    if len(set(section_anchors)) != len(section_anchors):
        duplicates = sorted({anchor for anchor in section_anchors if section_anchors.count(anchor) > 1})
        raise CasillaReferenceError(
            f"modelo {modelo}: duplicate section anchor(s) {duplicates}; "
            "registry section paths must fold to a unique per-page anchor"
        )

    return section_counts
