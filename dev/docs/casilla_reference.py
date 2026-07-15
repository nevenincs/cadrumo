"""Generated per-modelo casilla reference pages from the registry projection.

The sibling of :mod:`dev.docs.glossary_reference`: a build-time projection
rendered from a typed authority (here the registry casilla projection) into
uncommitted pages the docs build emits, regenerated on every build so they can
never drift from the source. Where the glossary projects Handbook concepts into
one page, this projects every casilla into one page PER MODELO (``docs/
_generated/casillas/<modelo>.rst``) plus an ``index.rst`` toctree.

It calls :func:`~dev.docs.terminology.project_casilla_search_records` - the SAME
projection the injected search records consume - so a casilla card and its
landing page can never disagree on revision collapse or labels. Each casilla is
a reference-table row: the entry renders the number and Spanish label, the
localised labels, segmento, section path, semantic role, its ``legal_refs`` as
BOE permalinks where the legal catalogue resolves them (reusing the glossary
generator's :func:`~dev.docs.glossary_reference._legal_permalinks` read),
``source_refs``, and ``source_revisions`` latest-first. Entries group by the
registry ``section`` path so the two large modelos (M200, M100) stay navigable.

Anchors: every entry carries a page-local raw-HTML anchor span whose id is
:func:`~dev.docs.terminology._casilla_anchor.casilla_page_anchor`, the exact
target the search record deep-links to. A raw-HTML span (not a Sphinx ``.. _:``
label) is used deliberately: casilla ids repeat across modelos, so a global
label would collide project-wide, while a page-local HTML id may safely repeat
on sibling pages. A post-slug anchor collision within one page is a hard
generator failure, never a silent merge (the ``-n -W`` build needs every
emitted id unique per page).
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .glossary_reference import _legal_permalinks
from .terminology import CasillaSearchRecord, project_casilla_search_records
from .terminology._casilla_anchor import CASILLA_REFERENCE_DIR, casilla_page_anchor, casilla_page_relpath

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


#: RST inline-markup start characters. Registry labels carry free AEAT prose
#: with footnote markers (``2025(*)``), pipes, and stray asterisks, so every
#: embedded free-text value is backslash-escaped before it reaches RST or the
#: ``-n -W`` build reds on an unbalanced ``*`` / ``` ` ``` / ``|`` run.
_RST_SPECIAL = "\\`*_|[]"


def _rst_escape(text: str) -> str:
    """Backslash-escape RST inline-markup characters in arbitrary free text."""
    return "".join(f"\\{ch}" if ch in _RST_SPECIAL else ch for ch in text)


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(len(text), 3)}\n"


def _section_display(section: tuple[str, ...]) -> str:
    """The human display for a registry section path (``a > b > c``), escaped."""
    return " › ".join(_rst_escape(part) for part in section if part) or "General"


def _localised_lines(record: CasillaSearchRecord) -> list[str]:
    """Field lines for the non-Spanish localised labels, where authored."""
    from cadrumo.core.external_constants import OutputLanguage

    lines: list[str] = []
    for language, label in (
        ("en", record.descriptions.get(OutputLanguage.EN)),
        ("ca", record.descriptions.get(OutputLanguage.CA)),
        ("hu", record.descriptions.get(OutputLanguage.HU)),
    ):
        if label:
            lines.append(f":Label ({language}): {_rst_escape(label)}")
    return lines


def _legal_field(record: CasillaSearchRecord, permalinks: dict[str, str]) -> tuple[str | None, tuple[str, ...], int]:
    """Render the ``Legal basis`` field for a casilla, plus its rendered refs.

    Every ``legal_ref`` the record carries is rendered: one that resolves in the
    legal catalogue becomes a BOE permalink, one that does not renders as inline
    literal text so the grounding the record carries is never dropped (the D6
    destination-grounding contract). Returns ``(field_line, rendered_refs,
    permalink_count)``.
    """
    if not record.legal_refs:
        return None, (), 0
    parts: list[str] = []
    permalink_count = 0
    for ref in record.legal_refs:
        permalink = permalinks.get(ref)
        if permalink:
            parts.append(f"`{ref} <{permalink}>`__")
            permalink_count += 1
        else:
            parts.append(f"``{ref}``")
    return f":Legal basis: {', '.join(parts)}", tuple(record.legal_refs), permalink_count


def _render_entry(
    record: CasillaSearchRecord,
    permalinks: dict[str, str],
) -> tuple[str, str, tuple[str, ...], int]:
    """Render one casilla entry.

    Returns ``(rst, anchor, rendered_legal_refs, permalink_count)``. The entry
    opens with a raw-HTML anchor span carrying the page-local id, then a bold
    number+label paragraph, then a field list of the provenance.
    """
    from cadrumo.core.external_constants import OutputLanguage

    anchor = casilla_page_anchor(record.modelo, record.casilla_id)
    label = record.descriptions[OutputLanguage.ES]
    lines = [
        ".. raw:: html",
        "",
        f'   <span id="{anchor}"></span>',
        "",
        f"**{_rst_escape(record.number)}** — {_rst_escape(label)}",
        "",
    ]
    fields = [f":Casilla id: ``{record.casilla_id}``"]
    fields.extend(_localised_lines(record))
    if record.segmento:
        fields.append(f":Segmento: {_rst_escape(record.segmento)}")
    fields.append(f":Section: {_section_display(record.section)}")
    if record.semantic_role:
        fields.append(f":Role: {_rst_escape(record.semantic_role)}")
    legal_field, rendered_refs, permalink_count = _legal_field(record, permalinks)
    if legal_field is not None:
        fields.append(legal_field)
    if record.source_refs:
        fields.append(f":Source: {', '.join(f'``{ref}``' for ref in record.source_refs)}")
    if record.source_revisions:
        fields.append(f":Revisions: {', '.join(record.source_revisions)}")
    lines.extend(fields)
    lines.append("")
    return "\n".join(lines), anchor, rendered_refs, permalink_count


def _render_modelo_page(
    modelo: str,
    records: tuple[CasillaSearchRecord, ...],
    permalinks: dict[str, str],
) -> tuple[CasillaPage, int]:
    """Render one modelo page grouped by section; return the page and its legal-link count."""
    header = (
        "..\n"
        "   Generated by dev/docs/casilla_reference.py from the registry casilla\n"
        "   projection. Do not edit by hand; regenerate.\n\n"
    )
    title = _rst_heading(f"Modelo {modelo} casillas", "=")
    intro = (
        f"Every casilla of Modelo {modelo}, grouped by its official section, with the\n"
        "legal and source grounding carried from the registry. This page is the\n"
        "destination the search palette's casilla results link to.\n"
    )

    grouped: OrderedDict[tuple[str, ...], list[CasillaSearchRecord]] = OrderedDict()
    for record in records:
        grouped.setdefault(record.section, []).append(record)

    blocks: list[str] = [header + title + "\n" + intro]
    anchors: list[str] = []
    seen: set[str] = set()
    rendered_legal_refs: dict[str, tuple[str, ...]] = {}
    legal_links = 0
    for section, section_records in grouped.items():
        blocks.append(_rst_heading(_section_display(section), "-"))
        for record in section_records:
            entry, anchor, refs, permalink_count = _render_entry(record, permalinks)
            if anchor in seen:
                raise CasillaReferenceError(
                    f"modelo {modelo}: duplicate casilla anchor {anchor!r} "
                    f"(casilla {record.casilla_id!r}); ids must fold to a unique per-page anchor"
                )
            seen.add(anchor)
            anchors.append(anchor)
            rendered_legal_refs[anchor] = refs
            legal_links += permalink_count
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
        "One page per modelo listing every casilla with its legal and source\n"
        "grounding. The search palette's casilla results deep-link into these pages.\n\n"
    )
    lines = [".. toctree::", "   :maxdepth: 1", ""]
    lines.extend(f"   {modelo} <{modelo}>" for modelo in modelos)
    return header + title + "\n" + intro + "\n".join(lines) + "\n"


def render_casilla_reference(
    repo_root: Path,
    records: tuple[CasillaSearchRecord, ...] | None = None,
) -> CasillaReferenceResult:
    """Render every modelo's casilla reference page and the index.

    Args:
        repo_root: Repository root (for the legal-catalogue permalink read).
        records: Optional pre-projected casilla records; defaults to the full
            registry projection. Injectable so the parity gate and a narrowed
            test can drive the same renderer deterministically.

    Returns:
        A :class:`CasillaReferenceResult` with one :class:`CasillaPage` per
        modelo, the index page path, and the render counts.
    """
    permalinks = _legal_permalinks(repo_root)
    resolved = records if records is not None else project_casilla_search_records()[0]

    by_modelo: OrderedDict[str, list[CasillaSearchRecord]] = OrderedDict()
    for record in resolved:
        by_modelo.setdefault(record.modelo.value, []).append(record)

    pages: list[CasillaPage] = []
    legal_links = 0
    casilla_count = 0
    for modelo in sorted(by_modelo):
        page, page_legal_links = _render_modelo_page(modelo, tuple(by_modelo[modelo]), permalinks)
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
