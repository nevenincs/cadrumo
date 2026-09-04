"""Generated glossary page from the approved Terminology Handbook concepts.

The sibling of ``cli_reference.py``: a build-time projection rendered from a
typed authority (here the Terminology Handbook) into an uncommitted page the
docs build emits, regenerated on every build so it can never drift from the
source. ``cli_reference`` projects the live command tree; this projects the
Handbook concepts into a Sphinx ``glossary`` directive, giving every approved
concept a stable ``:term:`` anchor and a single canonical definition - the
hook the nitpicky ``-n -W`` build then leans on to enforce enrolment (an
undefined ``:term:`` breaks the build) and single declaration (a duplicate
glossary entry warns) for free.

Approved-only rule (decided): ONLY concepts whose lifecycle is ``approved``
render as glossary entries. The ``draft`` concepts (the bulk of the Handbook)
carry no curated definition - they are search-only, surfaced through the
compiled search index, never as a glossary entry. Rendering a draft would
either ship a blank/placeholder entry (misleading the reader) or red the
build; both are wrong, so drafts are excluded here and the count of excluded
drafts is reported.

Term lines and anchors: each entry's headword is the concept's Spanish
preferred term (the canonical surface), and its admitted aliases render as
additional term lines on the SAME entry, so a ``:term:`AEAT``` /
``:term:`Agencia Tributaria``` cross-reference resolves any declared surface
to one definition. One concept = one glossary entry (the sphinx-hoverxref
shared-entry rendering bug forbids many terms sharing one definition block via
separate entries; the multi-term-line form is the supported way to alias).

Output language: the entry body follows the language the docs root is being
built in (``CADRUMO_DOCS_LANGUAGE``, resolved through the single build-language
authority :func:`~dev.docs.build.docs_build_language`), so a Spanish root
renders Spanish definitions and a Hungarian root Hungarian ones. A page built
for one language renders that language's prose and no other's. The headword
stays the Spanish preferred term in every root: it is the term a Spanish-tax
reader looks up, it is the surface the AEAT publishes, and it is the anchor
authority the injected search records deep-link to. Legal grounding links
render where the concept carries ``legal_refs`` that resolve to a BOE
permalink in the legal catalogue.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from cadrumo.core.concept_lifecycle import ConceptLifecycle
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import OutputLanguage

from .._paths import UTF_8
from ._locale_chrome import docs_chrome
from .build import docs_build_language
from .legal_reference import LEGAL_CATALOGUE_RELPATH, legal_citation
from .terminology_handbook import load_terminology_handbook
from .terminology_handbook.enums import TermStatus
from .terminology_handbook.loader import TerminologyHandbook
from .terminology_handbook.schema import ConceptRecord, LanguageSection

_UTF_8 = UTF_8

#: Generated glossary path, relative to the docs root. Uncommitted and
#: regenerated every build, like ``docs/cli/`` - the hand-written
#: ``docs/glossary.md`` stays in place until the cutover step swaps to this.
_GENERATED_RELPATH = Path("_generated") / "glossary.rst"


@dataclass(frozen=True)
class LegalGrounding:
    """The catalogue facts one ``legal_refs`` entry resolves to.

    ``kind`` rides alongside the permalink because the reader-facing citation
    is derived from the id stem and the instrument kind together; resolving
    both in one catalogue read keeps the glossary from reading the same TOMLs
    twice for one grounding line.
    """

    permalink: str
    kind: str
    article: str | None = None
    section: str | None = None


@dataclass(frozen=True)
class GlossaryResult:
    """Outcome of a glossary generation pass."""

    output_relpath: str
    approved_rendered: int
    drafts_excluded: int
    legal_links: int
    deduplicated_terms: tuple[str, ...] = ()


def _legal_permalinks(repo_root: Path) -> dict[str, LegalGrounding]:
    """Build the ``legal-ref-id -> grounding`` map from the catalogue TOMLs.

    Reads the ``[legal."<id>"]`` tables directly (a lightweight read, not the
    full registry-catalogue machinery): the concept ``legal_refs`` ids match
    the catalogue keys verbatim, so the map resolves a concept's grounding to
    its published BOE permalink and the instrument kind its citation is
    derived from.
    """
    catalogue = repo_root / LEGAL_CATALOGUE_RELPATH
    grounding: dict[str, LegalGrounding] = {}
    if not catalogue.is_dir():
        return grounding
    for fragment in scan_directory(catalogue, pattern="*.toml"):
        try:
            data = cast(dict[str, object], tomllib.loads(fragment.read_text(encoding=_UTF_8)))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        legal = data.get("legal")
        if not isinstance(legal, dict):
            continue
        legal_tables = cast(dict[object, object], legal)
        for ref_id, body in legal_tables.items():
            if not isinstance(ref_id, str) or not isinstance(body, dict):
                continue
            table = cast(dict[str, object], body)
            permalink = table.get("permalink")
            kind = table.get("kind")
            article = table.get("article")
            section = table.get("section")
            if isinstance(permalink, str) and permalink:
                grounding[ref_id] = LegalGrounding(
                    permalink=permalink,
                    kind=kind if isinstance(kind, str) else "",
                    article=article if isinstance(article, str) else None,
                    section=section if isinstance(section, str) else None,
                )
    return grounding


def _approved_concepts(handbook: TerminologyHandbook) -> tuple[ConceptRecord, ...]:
    """Return the approved concepts, ordered by their headword for the page."""
    approved = tuple(concept for concept in handbook.concepts if concept.lifecycle is ConceptLifecycle.APPROVED)
    return tuple(sorted(approved, key=_headword))


def _primary_section(concept: ConceptRecord) -> LanguageSection | None:
    """Return the Spanish section (the headword + term source), or None."""
    for section in concept.languages:
        if section.language is OutputLanguage.ES:
            return section
    return None


def _section_for(concept: ConceptRecord, language: OutputLanguage) -> LanguageSection | None:
    """Return the concept's section in one language, or None when unauthored."""
    for section in concept.languages:
        if section.language is language:
            return section
    return None


def _headword(concept: ConceptRecord) -> str:
    """The concept's headword: the Spanish preferred term, else the id."""
    section = _primary_section(concept)
    if section is not None:
        for term in section.terms:
            if term.term_status is TermStatus.PREFERRED:
                return term.label
        if section.terms:
            return section.terms[0].label
    return concept.concept_id


def _term_lines(concept: ConceptRecord) -> list[str]:
    """The headword plus admitted-alias term lines for one glossary entry.

    The preferred term is the headword; admitted terms become additional term
    lines on the same entry so any declared surface resolves via ``:term:``.
    Deprecated and forbidden terms are not enrolled as resolvable anchors.
    """
    head = _headword(concept)
    lines = [head]
    section = _primary_section(concept)
    if section is not None:
        for term in section.terms:
            if term.term_status is TermStatus.ADMITTED and term.label != head:
                lines.append(term.label)
    return lines


def _body_text(concept: ConceptRecord, language: OutputLanguage) -> str:
    """The entry body in the build language, or empty when none is authored.

    Both fields are curated, taxpayer-general prose. The full ``definition`` is
    preferred when authored; ``short_description`` is the shorter authored
    form of the same language.

    There is deliberately NO cross-language fallback. Only the four locale
    catalogues and these curated per-language sections are sanctioned sources
    of localized text, and prose the reader cannot read is worse than no prose:
    it looks like an answer, is silently in another language, and cannot be
    translated by this layer without authoring meaning. A concept with nothing
    authored in the build language renders its compiled structure instead (see
    :func:`_render_entry`).
    """
    section = _section_for(concept, language)
    if section is None:
        return ""
    return section.definition or section.short_description


def _related_lines(
    concept: ConceptRecord,
    headwords: dict[str, str],
    body_indent: str,
    language: OutputLanguage,
) -> list[str]:
    """Render the concept's broader/related SKOS relations as ``:term:`` links.

    The Handbook declares shallow SKOS relations (``broader`` / ``related``)
    between concepts, but they were invisible to the reader -- they rode on the
    search-record metadata and nowhere else. Rendering them here as ``:term:``
    cross-references turns the glossary into a navigable concept graph: a reader
    on the prorrata entry jumps straight to the casilla and IVA entries.

    Only relations whose target is an APPROVED concept (one that renders as a
    glossary entry, so its ``:term:`` anchor exists) are linked; a relation to a
    draft or self is skipped, because a ``:term:`` to a non-existent anchor would
    red the nitpicky ``-n -W`` build. The link text is the target's headword,
    the exact surface the glossary entry claims.
    """
    relation_lines: list[str] = []
    # Spelled out at the call, not passed through a variable: the locale
    # scanner reads call sites, and a key it cannot see is a key scaffold prunes.
    for label, ids in (
        (docs_chrome("docs.glossary.entry.broader", language), concept.broader),
        (docs_chrome("docs.glossary.entry.related", language), concept.related),
    ):
        refs = [f":term:`{headwords[ref]}`" for ref in ids if ref != concept.concept_id and ref in headwords]
        if refs:
            relation_lines.append(f"{body_indent}* {label}: {', '.join(refs)}")
    return relation_lines


def _render_entry(
    concept: ConceptRecord,
    permalinks: dict[str, LegalGrounding],
    claimed: set[str],
    headwords: dict[str, str],
    language: OutputLanguage,
) -> tuple[str, int, list[str]]:
    """Render one ``glossary`` entry and return ``(rst, legal_count, dropped)``.

    A Sphinx ``glossary`` requires every term to be globally unique - a label
    already claimed by an earlier entry would red the ``-n -W`` build with a
    duplicate-term warning. So a term line whose label was already claimed is
    DROPPED from this entry (and recorded in ``dropped``), keeping the anchor
    on its first concept. Two concepts legitimately sharing a surface form is a
    Handbook-curation question for the redeclaration gate, surfaced here rather
    than silently merged.

    The block is the surviving term lines (headword + admitted aliases), then a
    6-space-indented definition paragraph, then any resolvable BOE grounding
    links and broader/related concept cross-references as an indented bullet list.
    """
    dropped: list[str] = []
    term_lines: list[str] = []
    for term in _term_lines(concept):
        if term in claimed:
            dropped.append(term)
            continue
        claimed.add(term)
        term_lines.append(term)
    body_indent = "      "
    lines = [f"   {term}" for term in term_lines]
    body = _body_text(concept, language)
    # A Sphinx glossary entry must carry a body, so an unauthored definition
    # cannot simply be omitted. It says so plainly and then leans on the
    # compiled record, which is language-safe: the domain, the legal grounding
    # and the concept relations are structure, not prose, and stay true in
    # every build language.
    undefined = docs_chrome("docs.glossary.entry.undefined", language)
    block = [*lines, f"{body_indent}{body}" if body else f"{body_indent}{undefined}"]
    legal_count = 0
    grounding: list[str] = []
    if not body:
        domain_label = docs_chrome("docs.glossary.entry.domain", language)
        grounding.append(f"{body_indent}* {domain_label}: {concept.domain.value}")
    for ref in concept.legal_refs:
        resolved = permalinks.get(ref)
        if resolved:
            # The link reads as the citation a taxpayer would recognise; the
            # catalogue id stays visible behind it so the grounding remains
            # traceable to the exact row it came from.
            citation = legal_citation(ref, resolved.kind, article=resolved.article, section=resolved.section)
            basis = docs_chrome("docs.glossary.entry.legal_basis", language)
            grounding.append(f"{body_indent}* {basis}: `{citation} <{resolved.permalink}>`__ (``{ref}``)")
            legal_count += 1
    grounding.extend(_related_lines(concept, headwords, body_indent, language))
    if grounding:
        block.append("")
        block.extend(grounding)
    return "\n".join(block), legal_count, dropped


def render_glossary(
    repo_root: Path,
    handbook: TerminologyHandbook,
    language: OutputLanguage | None = None,
) -> tuple[str, GlossaryResult]:
    """Render the generated glossary RST and its result summary.

    Args:
        repo_root: Repository root (for the legal-catalogue read).
        handbook: The compiled Terminology Handbook.
        language: The language to render definitions in. Defaults to the
            language this docs root is being built for, read from the
            environment through the single build-language authority.

    Returns:
        ``(rst_text, result)`` - the page content and a summary of how many
        approved concepts rendered, how many drafts were excluded, and how
        many legal grounding links resolved.
    """
    resolved_language = language if language is not None else docs_build_language(os.environ)
    permalinks = _legal_permalinks(repo_root)
    approved = _approved_concepts(handbook)
    # concept_id -> headword for every approved concept, so broader/related
    # relations can be rendered as resolvable ``:term:`` cross-references to the
    # target's glossary anchor (a relation to a draft/non-rendered concept is
    # skipped, never emitting an unresolvable reference).
    headwords = {concept.concept_id: _headword(concept) for concept in approved}
    drafts = sum(1 for concept in handbook.concepts if concept.lifecycle is ConceptLifecycle.DRAFT)

    title = docs_chrome("docs.glossary.title", resolved_language)
    header = (
        "..\n"
        "   Generated by dev/docs/glossary_reference.py from the approved\n"
        "   Terminology Handbook concepts. Do not edit by hand; regenerate.\n\n"
        f"{title}\n"
        f"{'=' * max(len(title), 3)}\n\n"
        f"{docs_chrome('docs.glossary.intro', resolved_language)}\n\n"
        ".. glossary::\n"
        "   :sorted:\n\n"
    )
    entries: list[str] = []
    legal_links = 0
    claimed: set[str] = set()
    deduplicated: list[str] = []
    rendered = 0
    for concept in approved:
        entry, count, dropped = _render_entry(concept, permalinks, claimed, headwords, resolved_language)
        deduplicated.extend(dropped)
        # A concept whose every term collided with an earlier entry has no
        # surviving headword; skip it rather than emit a term-less block.
        if not any(line.startswith("   ") and not line.startswith("      ") for line in entry.splitlines()):
            continue
        entries.append(entry)
        legal_links += count
        rendered += 1
    rst = header + "\n\n".join(entries) + "\n"
    result = GlossaryResult(
        output_relpath=str(_GENERATED_RELPATH).replace("\\", "/"),
        approved_rendered=rendered,
        drafts_excluded=drafts,
        legal_links=legal_links,
        deduplicated_terms=tuple(deduplicated),
    )
    return rst, result


def generate_glossary_reference(docs_root: Path, *, language: OutputLanguage | None = None) -> GlossaryResult:
    """Materialise the generated glossary page under ``docs_root/_generated/``.

    Mirrors :func:`~dev.docs.cli_reference.generate_cli_reference`: it loads
    the typed authority, renders the page, and writes it to the generated
    (gitignored, uncommitted) location, returning a summary. Wired at the
    ``builder-inited`` seam so the page exists before Sphinx reads the source
    tree.

    Args:
        docs_root: The documentation root (the directory holding ``index.md``).
        language: The language to render in. Defaults to the language this
            docs root is being built for.

    Returns:
        A :class:`GlossaryResult` summarising the render.
    """
    repo_root = docs_root.resolve().parent
    handbook = load_terminology_handbook()
    rst, result = render_glossary(repo_root, handbook, language)
    output_path = docs_root / _GENERATED_RELPATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not (output_path.is_file() and output_path.read_text(encoding=_UTF_8) == rst):
        # Force LF so the generated page is byte-identical across platforms; the
        # default newline translation emits CRLF on Windows, which doc8's
        # CheckCarriageReturn (D004) then flags on every regeneration.
        output_path.write_text(rst, encoding=_UTF_8, newline="\n")
    return result
