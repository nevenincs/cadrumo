"""Project authored legal rows into localized RST pages and their link inventories."""

from __future__ import annotations

from html import escape
from typing import Final

from cadrumo.core.external_constants import OutputLanguage

from ._locale_chrome import docs_chrome
from .compile_slots import Rendering, language_text
from .legal_reference_models import LegalPage, LegalProvisionRecord, LegalReferenceError
from .legal_reference_routing import (
    legal_document_slug,
    legal_instrument_designation,
    legal_page_relpath,
    legal_provision_anchor,
    legal_provision_designation,
    legal_reference_target,
)

_DATE_FIELDS: Final[tuple[str, ...]] = (
    "published_at",
    "effective_from",
    "effective_to",
    "consolidated_as_of",
    "reviewed_at",
)


def _rst_escape(text: str) -> str:
    """Escape free catalogue text before it enters RST body prose."""
    return "".join(f"\\{char}" if char in "\\`*_|[]" else char for char in text)


def _rst_literal(text: str) -> str:
    """Wrap catalogue text as an RST inline literal without escaping it.

    Inline literals are verbatim: RST interprets no markup inside them, so a
    backslash added by :func:`_rst_escape` is rendered as a visible backslash
    rather than consumed.  An identifier such as ``legal_authority`` must
    therefore enter the literal unescaped.
    """
    if "`" in text:
        raise LegalReferenceError(f"catalogue value {text!r} cannot be rendered as an inline literal")
    return f"``{text}``"


def _rst_heading(text: str, underline: str) -> str:
    return f"{text}\n{underline * max(len(text), 3)}\n"


def _in_force_sentence(record: LegalProvisionRecord, language: OutputLanguage) -> str | None:
    """Render the authored effectivity dates as one reader-facing sentence.

    Dates stay ISO in every language: they are data, and an ISO date is read
    the same way by every reader without a per-language format to maintain.
    """
    if record.effective_from is not None and record.effective_to is not None:
        span = docs_chrome(
            "docs.legal.provision.in_force_between",
            language,
            start=record.effective_from.isoformat(),
            end=record.effective_to.isoformat(),
        )
    elif record.effective_from is not None:
        span = docs_chrome("docs.legal.provision.in_force_from", language, start=record.effective_from.isoformat())
    elif record.effective_to is not None:
        span = docs_chrome("docs.legal.provision.in_force_until", language, end=record.effective_to.isoformat())
    else:
        span = ""
    published = (
        docs_chrome("docs.legal.provision.published", language, date=record.published_at.isoformat())
        if record.published_at is not None
        else ""
    )
    if span and published:
        return f"{span} ({published})."
    if span:
        return f"{span}."
    if published:
        return f"{published[:1].upper()}{published[1:]}."
    return None


def _official_wording_block(required_text: tuple[str, ...], language: OutputLanguage) -> list[str]:
    """Render the authored extracts of the official text, marked as Spanish.

    Emitted as raw HTML rather than RST for two reasons that both protect the
    text.  It carries ``lang="es"``, which RST offers no way to set and which
    is what tells a browser, a screen reader and a translation tool that this
    run is Spanish inside an otherwise non-Spanish page -- the language
    boundary made explicit rather than left for the reader to infer.  And HTML
    escaping is total, so wording that opens with a subparagraph marker
    ("b) ...") cannot be reparsed into a list item the way RST would; the
    official text reaches the page as authored or not at all.

    Each phrase is its own paragraph.  Run together they would read as one
    continuous piece of statutory wording that the provision does not contain.
    """
    quoted = "".join(f"<p>{escape(item.rstrip())}</p>" for item in required_text)
    label = escape(docs_chrome("docs.legal.provision.official_wording", language))
    # The label's own language is the page's, which the one compile does not
    # have: the tag is as much a per-language string as the label is, and this
    # block's own raw HTML is where it is written.
    label_language = language_text(lambda carried: carried, language.value, rendering=Rendering.VERBATIM)
    return [
        ".. raw:: html",
        "",
        '   <div class="cadrumo-legal-wording">',
        f'     <p class="cadrumo-legal-wording-label" lang="{label_language}">{label}</p>',
        f'     <blockquote lang="es">{quoted}</blockquote>',
        "   </div>",
        "",
    ]


def _catalogue_record_block(record: LegalProvisionRecord, language: OutputLanguage) -> list[str]:
    """The demoted provenance panel: the identifiers and the review trail.

    Everything a reader does not need in order to understand the provision, but
    which must stay visible for anyone auditing where the figure came from: the
    catalogue id, the instrument kind, the bundled-corpus locator, and the
    review stamp.  It renders after the content and is styled as subordinate.

    The authored ``notes`` field lives here rather than leading the entry.  It
    is a single free-text field with no declared language -- measured across
    the catalogue it is roughly three quarters Spanish and one quarter English
    -- so it cannot be marked honestly for the reader, and presenting it as the
    entry's summary would put unlabelled other-language prose in the position
    where a reader expects the answer.  As provenance beside the review stamp
    it is what it actually is: the cataloguer's own note.
    """

    # Every key is spelled out at its call site rather than composed from a
    # field name. A composed key is invisible to the locale scanner, which then
    # reports the catalogue entry as one no code requests and prunes it.
    fields = [
        f":{docs_chrome('docs.legal.record.catalogue_id', language)}: {_rst_literal(record.legal_id)}",
        f":{docs_chrome('docs.legal.record.instrument_kind', language)}: {_rst_literal(record.kind)}",
        f":{docs_chrome('docs.legal.record.boe_document', language)}: {_rst_literal(record.document_id)}",
        f":{docs_chrome('docs.legal.record.bundled_corpus', language)}: {_rst_literal(record.corpus_ref)}",
    ]
    if record.authority is not None:
        fields.append(f":{docs_chrome('docs.legal.record.authority', language)}: {_rst_literal(record.authority)}")
    if record.evidence_tier is not None:
        fields.append(
            f":{docs_chrome('docs.legal.record.evidence_tier', language)}: {_rst_literal(record.evidence_tier)}",
        )
    if record.consolidated_as_of is not None:
        fields.append(
            f":{docs_chrome('docs.legal.record.consolidated_as_of', language)}: "
            f"{record.consolidated_as_of.isoformat()}",
        )
    if record.review_status is not None:
        fields.append(
            f":{docs_chrome('docs.legal.record.review_status', language)}: {_rst_literal(record.review_status)}",
        )
    if record.reviewed_at is not None:
        fields.append(f":{docs_chrome('docs.legal.record.reviewed_at', language)}: {record.reviewed_at.isoformat()}")
    if record.reviewed_by is not None:
        fields.append(f":{docs_chrome('docs.legal.record.reviewed_by', language)}: {_rst_escape(record.reviewed_by)}")
    if record.notes is not None:
        fields.append(f":{docs_chrome('docs.legal.record.note', language)}: {_rst_escape(record.notes)}")
    title = docs_chrome("docs.legal.record.title", language)
    return [".. container:: cadrumo-legal-record", "", f"   {title}", "", *(f"   {line}" for line in fields)]


def _headings_by_id(records: tuple[LegalProvisionRecord, ...], instrument: str) -> dict[str, str]:
    """Resolve one unique reader-facing heading per provision on a page.

    A catalogue commonly carries several consolidated versions of the same
    article, each governing a different filing year (``art-52``,
    ``art-52-2015``, ``art-52-2021``).  They share a citation, so the citation
    alone is neither unique nor enough for a reader who needs the version that
    applies to their year: the in-force date is the distinguishing fact, and it
    is authored, not inferred.  Where even that repeats, the catalogue id
    disambiguates, because a heading that silently names two provisions is
    worse than one carrying an identifier.

    ``instrument`` is the page's own heading, which a provision carrying no
    article or section would otherwise duplicate exactly.
    """
    citations: dict[str, list[LegalProvisionRecord]] = {}
    for record in records:
        citations.setdefault(legal_provision_designation(record), []).append(record)

    headings: dict[str, str] = {}
    for citation, group in citations.items():
        if len(group) == 1 and citation != instrument:
            headings[group[0].legal_id] = citation
            continue
        # The bare date is language-neutral: it disambiguates the consolidated
        # versions without splicing a chrome word into a Spanish citation. The
        # in-force line under the heading states what the date means.
        dated = [
            f"{citation} ({record.effective_from.isoformat()})" if record.effective_from is not None else citation
            for record in group
        ]
        distinct = len(set(dated)) == len(dated) and instrument not in dated
        for record, heading in zip(group, dated, strict=True):
            headings[record.legal_id] = heading if distinct else f"{citation} ({record.legal_id})"
    return headings


def _render_entry(record: LegalProvisionRecord, heading: str, language: OutputLanguage) -> tuple[str, str | None, str]:
    """Render one provision: what it says first, where it came from last."""
    anchor = legal_provision_anchor(
        record.legal_id,
        article=record.article,
        section=record.section,
        corpus_ref=record.corpus_ref,
        permalink=record.permalink,
    )
    lines: list[str] = []
    if anchor is not None:
        lines.extend([".. raw:: html", "", f'   <span id="{anchor}"></span>', ""])
    designation = legal_provision_designation(record)
    read_label = docs_chrome("docs.legal.provision.read_on_boe", language, citation=designation)
    lines.extend([_rst_heading(_rst_escape(heading), "-").rstrip("\n"), ""])

    in_force = _in_force_sentence(record, language)
    if in_force is not None:
        lines.extend([".. container:: cadrumo-legal-force", "", f"   {in_force}", ""])

    if record.required_text:
        lines.extend(_official_wording_block(record.required_text, language))

    lines.extend(
        [
            ".. container:: cadrumo-legal-official",
            "",
            f"   `{_rst_escape(read_label)} <{record.permalink}>`__",
            "",
            f"   {_rst_escape(docs_chrome('docs.legal.provision.boe_is_official', language))}",
            "",
        ],
    )
    lines.extend(_catalogue_record_block(record, language))
    lines.append("")
    return "\n".join(lines), anchor, record.permalink


def _render_document_page(
    document_id: str,
    records: tuple[LegalProvisionRecord, ...],
    language: OutputLanguage,
) -> LegalPage:
    header = (
        "..\n"
        "   Generated by dev/docs/legal_reference.py from the registry legal\n"
        "   catalogue. Do not edit by hand; regenerate.\n\n"
    )
    instrument = legal_instrument_designation(records[0].legal_id, records[0].kind) if records else document_id
    intro = _rst_escape(
        docs_chrome("docs.legal.page.intro", language, document=document_id, count=len(records)),
    )
    blocks: list[str] = [header + _rst_heading(_rst_escape(instrument), "="), intro + "\n"]
    anchors: list[str] = []
    targets: dict[str, str] = {}
    anchor_by_id: dict[str, str | None] = {}
    grounding_by_id: dict[str, str] = {}
    seen_anchors: dict[str, str] = {}
    headings = _headings_by_id(records, instrument)
    for record in records:
        entry, anchor, permalink = _render_entry(record, headings[record.legal_id], language)
        if anchor is not None:
            previous = seen_anchors.get(anchor)
            if previous is not None:
                raise LegalReferenceError(
                    f"document {document_id!r}: legal ids {previous!r} and {record.legal_id!r} "
                    f"collide at anchor {anchor!r}",
                )
            seen_anchors[anchor] = record.legal_id
            anchors.append(anchor)
        target = legal_reference_target(
            document_id,
            record.legal_id,
            article=record.article,
            section=record.section,
            corpus_ref=record.corpus_ref,
            permalink=record.permalink,
        )
        targets[record.legal_id] = target
        anchor_by_id[record.legal_id] = anchor
        grounding_by_id[record.legal_id] = permalink
        blocks.append(entry)

    return LegalPage(
        document_id=document_id,
        instrument=instrument,
        output_relpath=legal_page_relpath(document_id).as_posix(),
        rst="\n".join(blocks).rstrip("\n") + "\n",
        anchors=tuple(anchors),
        targets=targets,
        anchor_by_id=anchor_by_id,
        grounding_by_id=grounding_by_id,
    )


def _render_index(pages: tuple[LegalPage, ...], language: OutputLanguage) -> str:
    header = "..\n   Generated by dev/docs/legal_reference.py. Do not edit by hand; regenerate.\n\n"
    lines = [
        header + _rst_heading(_rst_escape(docs_chrome("docs.legal.index.title", language)), "=").rstrip("\n"),
        "",
        _rst_escape(docs_chrome("docs.legal.index.intro", language)),
        "",
        ".. toctree::",
        "   :maxdepth: 1",
        "",
    ]
    for page in sorted(pages, key=lambda page: (page.instrument.casefold(), page.document_id)):
        slug = legal_document_slug(page.document_id)
        lines.append(f"   {_rst_escape(page.instrument)} <{slug}>")
    return "\n".join(lines).rstrip("\n") + "\n"
