"""Generated per-modelo casilla reference pages from the registry projection.

The sibling of :mod:`dev.docs.glossary_reference`: a build-time projection
rendered from a typed authority (here the registry casilla projection) into
uncommitted pages the docs build emits, regenerated on every build so they can
never drift from the source. Where the glossary projects Handbook concepts into
one page, this projects every casilla into one page PER MODELO (``docs/
_generated/casillas/<modelo>.rst``) plus an ``index.rst`` toctree.

It calls :func:`~dev.docs.terminology.project_casilla_search_records` - the SAME
projection the injected search records consume - so a casilla card and its
landing page can never disagree on revision collapse or labels.

Presentation: the reader arrives from a search result knowing nothing, so each
casilla renders as a card that leads with MEANING - the official number, the
label in the build language, the help prose that says what goes in the box -
then the facts a filer needs (what shape of value, who fills it, whether it is
required, where it sits on the form), then the law behind it as resolvable links
into the generated legal reference. The registry's own identifiers (casilla id,
semantic role, binding/formula ids, source refs, source revisions) are machine
vocabulary a taxpayer does not read, so they are demoted into a collapsed
``<details>`` disclosure rather than dropped - the grounding stays on the page,
it just stops competing with the meaning.

One language per page. The projection carries every supported language's label
and help; a page built under ``CADRUMO_DOCS_LANGUAGE`` renders ONLY that
language's text, falling back to the Spanish invariant (marked ``lang="es"`` so
a screen reader switches voice) when a locale has no authored string. Rendering
all four at once - the shape this module shipped before - made every page a
four-language dump no reader of any single language could scan.

Anchors: every entry carries a page-local HTML id from
:func:`~dev.docs.terminology._casilla_anchor.casilla_page_anchor`, the exact
target the search record deep-links to. A raw-HTML id (not a Sphinx ``.. _:``
label) is used deliberately: casilla ids repeat across modelos, so a global
label would collide project-wide, while a page-local HTML id may safely repeat
on sibling pages. A post-slug anchor collision within one page is a hard
generator failure, never a silent merge (the ``-n -W`` build needs every
emitted id unique per page).
"""

from __future__ import annotations

import html
import os
import posixpath
import re
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .legal_reference import legal_reference_target, load_legal_provisions
from .terminology import CasillaSearchRecord, project_casilla_search_records
from .terminology._casilla_anchor import CASILLA_REFERENCE_DIR, casilla_page_anchor, casilla_page_relpath

if TYPE_CHECKING:
    from cadrumo.core.external_constants import OutputLanguage

    from .legal_reference import LegalProvisionRecord

_UTF_8 = "utf-8"


class CasillaReferenceError(RuntimeError):
    """Raised when a modelo page would emit a duplicate casilla anchor.

    A named, actionable boundary: two casilla ids on one modelo page folding to
    the same HTML anchor would ship a page whose ``#`` fragment is ambiguous and
    red the ``-n -W`` build. The generator refuses to write it.
    """


@dataclass(frozen=True)
class CasillaPage:
    """One rendered modelo page and its anchor / grounding inventory (for the gate)."""

    modelo: str
    output_relpath: str
    rst: str
    #: The ``casilla-<slug>`` anchor id emitted for each casilla, in page order.
    anchors: tuple[str, ...]
    #: ``anchor -> the legal_refs rendered on that entry`` (grounding coverage).
    rendered_legal_refs: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class CasillaReferenceResult:
    """Outcome of a casilla-reference generation pass."""

    pages: tuple[CasillaPage, ...]
    index_relpath: str
    modelo_count: int
    casilla_count: int
    legal_links: int


@dataclass(frozen=True)
class _LegalLink:
    """One catalogue provision projected for display on a casilla card."""

    #: Human reading of the provision ("Ley 37/1992, art. 92").
    label: str
    #: Site-relative target of the generated legal-reference destination.
    target: str


#: RST inline-markup start characters. Registry labels carry free AEAT prose
#: with footnote markers (``2025(*)``), pipes, and stray asterisks, so every
#: embedded free-text value reaching an RST heading is backslash-escaped or the
#: ``-n -W`` build reds on an unbalanced ``*`` / ``` ` ``` / ``|`` run. Card
#: bodies are raw HTML and are HTML-escaped instead.
_RST_SPECIAL = "\\`*_|[]"

#: Official Spanish naming for each authored catalogue ``kind``. AEAT publishes
#: these instruments under their Spanish names, so the display stays Spanish in
#: every build language (the domain-naming rule) - only the surrounding chrome
#: is English.
_LEGAL_KIND_DISPLAY: Final[dict[str, str]] = {
    "acuerdo_internacional": "Convenio",
    "dictionary": "Diccionario de datos AEAT",
    "form_spec": "Modelo oficial AEAT",
    "instruction": "Instrucciones AEAT",
    "instructions": "Instrucciones AEAT",
    "ley": "Ley",
    "manual_pdf": "Manual AEAT",
    "orden": "Orden",
    "real_decreto": "Real Decreto",
    "real_decreto_legislativo": "Real Decreto Legislativo",
    "real_decreto_ley": "Real Decreto-ley",
    "record_design": "Diseño de registro AEAT",
    "reglamento": "Reglamento",
    "suppression_notice": "Nota AEAT",
    "xsd": "Esquema XSD AEAT",
}

#: Leading id tokens that merely restate the authored ``kind`` and are dropped
#: from the display so ``ley-37-1992`` reads "Ley 37/1992", not "Ley ley 37/1992".
_LEGAL_KIND_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "acuerdo",
        "convenio",
        "decreto",
        "dl",
        "instruccion",
        "ley",
        "orden",
        "rd",
        "rdl",
        "rdleg",
        "real",
        "refundido",
        "reglamento",
        "resolucion",
        "texto",
        "trlirnr",
        "trlirpf",
        "trlis",
    },
)

_YEAR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(19|20)\d{2}$")

#: What the filer actually has to type, per registry ``data_type``. The registry
#: token is machine vocabulary; this is the reading a taxpayer needs.
_DATA_TYPE_DISPLAY: Final[dict[str, str]] = {
    "boolean": "Yes or no",
    "country_code": "Country code",
    "date": "Date",
    "decimal": "Decimal number",
    "iban": "IBAN",
    "integer": "Whole number",
    "money": "Amount in euros",
    "municipality_code": "Municipality code",
    "name": "Name",
    "nif": "NIF",
    "nif_iva": "VAT-registered NIF",
    "period_code": "Period",
    "postal_code": "Postcode",
    "province_code": "Province code",
    "ratio": "Percentage",
    "text": "Text",
    "year": "Year",
}

#: Who supplies the value, per registry ``input_kind``.
_INPUT_KIND_DISPLAY: Final[dict[str, str]] = {
    "bound": "Filled from your records",
    "computed": "Calculated for you",
    "informational": "Reference only",
    "manual": "You enter this",
}


def _rst_escape(text: str) -> str:
    """Backslash-escape RST inline-markup characters in arbitrary free text."""
    return "".join(f"\\{ch}" if ch in _RST_SPECIAL else ch for ch in text)


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(len(text), 3)}\n"


def _raw_html(lines: list[str]) -> str:
    """Wrap rendered HTML lines in an RST ``raw`` directive block."""
    body = "\n".join(f"   {line}" for line in lines)
    return f".. raw:: html\n\n{body}\n"


#: Registry section tokens that are AEAT acronyms, not words: capitalising them
#: as prose would render the tax itself as "Iva".
_SECTION_ACRONYMS: Final[frozenset[str]] = frozenset(
    {"aeat", "cif", "iae", "irnr", "irpf", "isp", "iva", "nif", "ue"},
)


def _humanise_token(token: str) -> str:
    """Read a snake_case registry token as prose (``rdto_trabajo`` -> ``Rdto trabajo``)."""
    words = token.replace("_", " ").replace("-", " ").strip()
    return words[:1].upper() + words[1:] if words else ""


def _section_token_display(token: str) -> str:
    """Render one section path token, preserving AEAT acronyms in upper case."""
    return token.upper() if token.lower() in _SECTION_ACRONYMS else _humanise_token(token)


def _section_display(section: tuple[str, ...]) -> str:
    """The human display for a registry section path, humanised token by token."""
    return " › ".join(_section_token_display(part) for part in section if part) or "General"


def _section_anchor(section: tuple[str, ...]) -> str:
    """A page-local id for one section group, distinct from the casilla ids."""
    joined = "-".join(part for part in section if part) or "general"
    slug = re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")
    return f"section-{slug or 'general'}"


def _display_language() -> OutputLanguage:
    """The one language this build renders, read from the shared build signal."""
    from .build import docs_build_language

    return docs_build_language(os.environ)


def _legal_numeral(tokens: list[str]) -> tuple[str | None, list[str]]:
    """Split a trailing ``<number>-<year>`` pair off a document-id token run."""
    if len(tokens) >= 2 and _YEAR_PATTERN.match(tokens[-1]) and tokens[-2].isdigit():
        return f"{tokens[-2]}/{tokens[-1]}", tokens[:-2]
    return None, tokens


def _legal_provision_display(legal_id: str, provision: LegalProvisionRecord) -> str:
    """Read one catalogue provision as its official Spanish name plus its article.

    Built only from authored fields (``kind``, ``article``, ``section``) and the
    document half of the catalogue id, which encodes the instrument's number and
    year. An id whose shape yields nothing falls back to the raw id, so the
    display never invents a citation it cannot derive.
    """
    document_part, _, provision_part = legal_id.partition(":")
    tokens = [token for token in document_part.split("-") if token]
    numeral, remainder = _legal_numeral(tokens)
    remainder = [token for token in remainder if token.lower() not in _LEGAL_KIND_TOKENS]
    separator = "/" if numeral else "-"
    qualifier = separator.join(token.upper() if len(token) <= 4 else _humanise_token(token) for token in remainder)

    kind_display = _LEGAL_KIND_DISPLAY.get(provision.kind, _humanise_token(provision.kind))
    name = " ".join(part for part in (kind_display, qualifier) if part)
    if numeral:
        name = f"{name}{separator if qualifier else ' '}{numeral}"
    name = name.strip()
    if not name:
        return legal_id

    # The authored ``section`` prose is the most human reading of a provision;
    # ``article`` is next (numeric articles take the ``art.`` prefix, worded
    # ones already read as prose); the id's own provision half is the floor.
    if provision.section:
        return f"{name}, {provision.section}"
    if provision.article:
        prefix = "art. " if provision.article[:1].isdigit() else ""
        return f"{name}, {prefix}{provision.article}"
    if provision_part:
        return f"{name}, {provision_part.replace('-', ' ')}"
    return name


@lru_cache(maxsize=4)
def _legal_links(repo_root: Path) -> dict[str, _LegalLink]:
    """Map every catalogue provision id to its display name and generated destination.

    The destination is the generated legal-reference page the sibling generator
    writes, derived through that module's own target helper, so a casilla's
    grounding lands on the in-site provision entry rather than dumping a raw
    token or bouncing the reader straight out to BOE.
    """
    links: dict[str, _LegalLink] = {}
    for provision in load_legal_provisions(repo_root):
        target = legal_reference_target(
            provision.document_id,
            provision.legal_id,
            article=provision.article,
            section=provision.section,
            corpus_ref=provision.corpus_ref,
            permalink=provision.permalink,
        )
        links[provision.legal_id] = _LegalLink(
            label=_legal_provision_display(provision.legal_id, provision),
            target=_relative_to_casilla_page(target),
        )
    return links


def _relative_to_casilla_page(site_target: str) -> str:
    """Rewrite a site-relative target as a link relative to a casilla page."""
    page, _, fragment = site_target.partition("#")
    relative = posixpath.relpath(page, CASILLA_REFERENCE_DIR)
    return f"{relative}#{fragment}" if fragment else relative


def _localised(record: CasillaSearchRecord, language: OutputLanguage) -> tuple[str, bool, str | None, bool]:
    """Return ``(label, label_is_fallback, help_text, help_is_fallback)`` for one language.

    The Spanish invariant is the fallback for every language, and the caller
    stamps ``lang="es"`` on a fallen-back string so the page never silently
    claims Spanish prose is the reader's language.
    """
    from cadrumo.core.external_constants import OutputLanguage as Language

    def _clean(value: str | None) -> str | None:
        return value if value is not None and value.strip() else None

    spanish_label = _clean(record.descriptions.get(Language.ES)) or record.description_es
    spanish_help = _clean(record.localized_help.get(Language.ES.value))

    if language is Language.ES:
        return spanish_label, False, spanish_help, False

    label = _clean(record.descriptions.get(language))
    help_text = _clean(record.localized_help.get(language.value))
    return (
        label or spanish_label,
        label is None,
        help_text or spanish_help,
        help_text is None and spanish_help is not None,
    )


def _fact_chips(record: CasillaSearchRecord) -> list[str]:
    """The scannable filer-facing facts: who fills it, what shape, is it required."""
    chips: list[str] = []
    input_kind = record.input_kind.value
    chips.append(
        f'<li class="casilla-fact casilla-fact--{html.escape(input_kind, quote=True)}">'
        f"{html.escape(_INPUT_KIND_DISPLAY.get(input_kind, _humanise_token(input_kind)))}</li>",
    )
    data_type = _DATA_TYPE_DISPLAY.get(record.data_type, _humanise_token(record.data_type))
    chips.append(f'<li class="casilla-fact">{html.escape(data_type)}</li>')
    if record.required:
        chips.append('<li class="casilla-fact casilla-fact--required">Required</li>')
    if record.segmento:
        chips.append(f'<li class="casilla-fact">Segmento {html.escape(record.segmento)}</li>')
    return chips


def _legal_block(
    record: CasillaSearchRecord,
    links: dict[str, _LegalLink],
) -> tuple[list[str], tuple[str, ...], int]:
    """Render the legal grounding as human-named links into the legal reference.

    Every ``legal_ref`` the record carries is rendered: one resolving in the
    catalogue becomes a named link to its provision entry, one that does not
    renders as its raw id, so the grounding the record carries is never dropped
    (the D6 destination-grounding contract). Returns ``(lines, rendered_refs,
    resolved_link_count)``.
    """
    if not record.legal_refs:
        return [], (), 0
    items: list[str] = []
    resolved = 0
    for ref in record.legal_refs:
        link = links.get(ref)
        if link is None:
            items.append(f'<li><span class="casilla-legal-ref casilla-legal-ref--raw">{html.escape(ref)}</span></li>')
            continue
        resolved += 1
        items.append(
            f'<li><a class="casilla-legal-ref" href="{html.escape(link.target, quote=True)}"'
            f' title="{html.escape(ref, quote=True)}">{html.escape(link.label)}</a></li>',
        )
    lines = [
        '<div class="casilla-card__legal">',
        '<span class="casilla-card__legal-label">Legal basis</span>',
        '<ul class="casilla-card__legal-list">',
        *items,
        "</ul>",
        "</div>",
    ]
    return lines, tuple(record.legal_refs), resolved


def _internals_block(record: CasillaSearchRecord) -> list[str]:
    """The registry's own identifiers, demoted into a collapsed disclosure.

    Machine vocabulary a taxpayer never reads, kept on the page because an
    operator debugging a value needs the exact ids the registry carries.
    """
    rows: list[tuple[str, str]] = [("Casilla id", f"<code>{html.escape(str(record.casilla_id))}</code>")]
    if record.semantic_role:
        rows.append(("Semantic role", f"<code>{html.escape(record.semantic_role)}</code>"))
    if record.binding is not None:
        rows.append(("Binding", f"<code>{html.escape(str(record.binding))}</code>"))
    if record.formula_id is not None:
        rows.append(("Formula", f"<code>{html.escape(str(record.formula_id))}</code>"))
    rows.append(("Registry section", f"<code>{html.escape('.'.join(record.section) or 'general')}</code>"))
    if record.source_refs:
        rows.append(
            ("Sources", " ".join(f"<code>{html.escape(ref)}</code>" for ref in record.source_refs)),
        )
    if record.source_revisions:
        rows.append(
            ("Revisions", " ".join(f"<code>{html.escape(rev)}</code>" for rev in record.source_revisions)),
        )
    lines = [
        '<details class="casilla-card__internals">',
        "<summary>Registry identifiers</summary>",
        '<dl class="casilla-internals">',
    ]
    for term, value in rows:
        lines.append(f"<dt>{html.escape(term)}</dt><dd>{value}</dd>")
    lines.extend(["</dl>", "</details>"])
    return lines


def _render_entry(
    record: CasillaSearchRecord,
    links: dict[str, _LegalLink],
    language: OutputLanguage,
) -> tuple[str, str, tuple[str, ...], int]:
    """Render one casilla card.

    Returns ``(rst, anchor, rendered_legal_refs, resolved_link_count)``.
    """
    anchor = casilla_page_anchor(record.modelo, record.casilla_id)
    label, label_fallback, help_text, help_fallback = _localised(record, language)
    label_lang = ' lang="es"' if label_fallback else ""

    lines = [
        f'<article class="casilla-card" id="{html.escape(anchor, quote=True)}">',
        '<header class="casilla-card__head">',
        f'<span class="casilla-card__number">{html.escape(record.number)}</span>',
        f'<h3 class="casilla-card__title"{label_lang}>{html.escape(label)}</h3>',
        "</header>",
    ]
    if help_text:
        help_lang = ' lang="es"' if help_fallback else ""
        lines.append(f'<p class="casilla-card__help"{help_lang}>{html.escape(help_text)}</p>')
    lines.append('<ul class="casilla-card__facts">')
    lines.extend(_fact_chips(record))
    lines.append("</ul>")
    legal_lines, rendered_refs, resolved = _legal_block(record, links)
    lines.extend(legal_lines)
    lines.extend(_internals_block(record))
    lines.append("</article>")
    return _raw_html(lines), anchor, rendered_refs, resolved


def _page_intro(modelo: str, sections: list[tuple[tuple[str, ...], int]], casilla_count: int) -> str:
    """The page lead: what this page is, plus a jump list over its sections."""
    lines = [
        '<div class="casilla-page-intro">',
        f'<p class="casilla-page-lead">Every box on Modelo {html.escape(modelo)}: what it holds, who fills it,'
        " where it sits on the official form, and the law that establishes it.</p>",
        f'<p class="casilla-page-count">{casilla_count} casillas in {len(sections)} sections</p>',
        "</div>",
    ]
    if len(sections) > 1:
        lines.append('<nav class="casilla-section-nav" aria-label="Sections of this modelo">')
        lines.append("<ul>")
        for section, count in sections:
            lines.append(
                f'<li><a href="#{html.escape(_section_anchor(section), quote=True)}">'
                f'{html.escape(_section_display(section))}<span class="casilla-section-nav__count">{count}</span>'
                "</a></li>",
            )
        lines.extend(["</ul>", "</nav>"])
    return _raw_html(lines)


def _render_modelo_page(
    modelo: str,
    records: tuple[CasillaSearchRecord, ...],
    links: dict[str, _LegalLink],
    language: OutputLanguage,
) -> tuple[CasillaPage, int]:
    """Render one modelo page grouped by section; return the page and its legal-link count."""
    header = (
        "..\n"
        "   Generated by dev/docs/casilla_reference.py from the registry casilla\n"
        "   projection. Do not edit by hand; regenerate.\n\n"
    )
    title = _rst_heading(f"Modelo {modelo}", "=")

    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]] = OrderedDict()
    for record in records:
        grouped.setdefault(record.section, []).append(record)
    section_counts = [(section, len(items)) for section, items in grouped.items()]

    blocks: list[str] = [
        header + title,
        _page_intro(modelo, section_counts, len(records)),
    ]
    anchors: list[str] = []
    seen: set[str] = set()
    rendered_legal_refs: dict[str, tuple[str, ...]] = {}
    legal_links = 0
    for section, section_records in grouped.items():
        blocks.append(_rst_heading(_rst_escape(_section_display(section)), "-"))
        blocks.append(_raw_html([f'<span class="casilla-section-anchor" id="{_section_anchor(section)}"></span>']))
        for record in section_records:
            entry, anchor, refs, resolved = _render_entry(record, links, language)
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


def _render_index(modelos: list[str]) -> str:
    """Render the casilla reference toctree index over the per-modelo pages."""
    header = "..\n   Generated by dev/docs/casilla_reference.py. Do not edit by hand; regenerate.\n\n"
    title = _rst_heading("Casilla reference", "=")
    intro = (
        "One page per modelo. Every casilla carries what it holds, who fills it,\n"
        "where it sits on the official form, and links to the law behind it.\n\n"
    )
    lines = [".. toctree::", "   :maxdepth: 1", ""]
    lines.extend(f"   {modelo} <{modelo}>" for modelo in modelos)
    return header + title + "\n" + intro + "\n".join(lines) + "\n"


def render_casilla_reference(
    repo_root: Path,
    records: tuple[CasillaSearchRecord, ...] | None = None,
    *,
    language: OutputLanguage | None = None,
) -> CasillaReferenceResult:
    """Render every modelo's casilla reference page and the index.

    Args:
        repo_root: Repository root (for the legal-catalogue read).
        records: Optional pre-projected casilla records; defaults to the full
            registry projection. Injectable so the parity gate and a narrowed
            test can drive the same renderer deterministically.
        language: The one language the pages render in; defaults to the build
            language signal so a localized build is single-language end to end.

    Returns:
        A :class:`CasillaReferenceResult` with one :class:`CasillaPage` per
        modelo, the index page path, and the render counts.
    """
    links = _legal_links(repo_root.resolve())
    resolved = records if records is not None else project_casilla_search_records()[0]
    resolved_language = language if language is not None else _display_language()

    by_modelo: OrderedDict[str, list[CasillaSearchRecord]] = OrderedDict()
    for record in resolved:
        by_modelo.setdefault(record.modelo.value, []).append(record)

    pages: list[CasillaPage] = []
    legal_links = 0
    casilla_count = 0
    for modelo in sorted(by_modelo):
        page, page_legal_links = _render_modelo_page(modelo, tuple(by_modelo[modelo]), links, resolved_language)
        pages.append(page)
        legal_links += page_legal_links
        casilla_count += len(page.anchors)

    index_relpath = f"{CASILLA_REFERENCE_DIR}/index.rst"
    return CasillaReferenceResult(
        pages=tuple(pages),
        index_relpath=index_relpath,
        modelo_count=len(pages),
        casilla_count=casilla_count,
        legal_links=legal_links,
    )


def generate_casilla_reference(docs_root: Path) -> CasillaReferenceResult:
    """Materialise the generated casilla reference pages under ``docs_root/_generated/``.

    Mirrors :func:`~dev.docs.glossary_reference.generate_glossary_reference`: it
    renders every modelo page plus the toctree index and writes them to the
    generated (gitignored, uncommitted) location, returning a summary. Wired at
    the ``builder-inited`` seam so the pages exist before Sphinx reads the tree.

    Args:
        docs_root: The documentation root (the directory holding ``index.md``).

    Returns:
        A :class:`CasillaReferenceResult` summarising the render.
    """
    repo_root = docs_root.resolve().parent
    result = render_casilla_reference(repo_root)
    out_dir = docs_root / CASILLA_REFERENCE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    modelos = [page.modelo for page in result.pages]
    _write_if_changed(out_dir / "index.rst", _render_index(modelos))
    for page in result.pages:
        _write_if_changed(docs_root / page.output_relpath, page.rst)
    return result


def _write_if_changed(path: Path, rst: str) -> None:
    """Write the page only when its content changed, forcing LF newlines.

    The default newline translation emits CRLF on Windows, which doc8's
    CheckCarriageReturn (D004) then flags on every regeneration; force LF so the
    generated page is byte-identical across platforms (the glossary precedent).
    """
    if not (path.is_file() and path.read_text(encoding=_UTF_8) == rst):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rst, encoding=_UTF_8, newline="\n")
