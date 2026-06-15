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

Output language: the docs build pins ``AEAT_OUTPUT_LANGUAGE=en`` (conf.py), so
the entry body is the English definition (or the English short description
when no full definition is authored), with the Spanish term as the headword -
the term a Spanish-tax reader looks up, defined in the docs' English prose.
Legal grounding links render where the concept carries ``legal_refs`` that
resolve to a BOE permalink in the legal catalogue.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from aeat.core.external_constants import OutputLanguage

from .terminology_handbook import load_terminology_handbook
from .terminology_handbook._enums import ConceptLifecycle, TermStatus
from .terminology_handbook._loader import TerminologyHandbook
from .terminology_handbook._schema import ConceptRecord, LanguageSection

_UTF_8 = "utf-8"

#: Generated glossary path, relative to the docs root. Uncommitted and
#: regenerated every build, like ``docs/cli/`` - the hand-written
#: ``docs/glossary.md`` stays in place until the cutover step swaps to this.
_GENERATED_RELPATH = Path("_generated") / "glossary.rst"

#: The legal catalogue tree (id -> permalink) for grounding-link resolution.
_LEGAL_CATALOGUE_RELPATH = Path("src") / "aeat" / "_data" / "registry" / "aeat" / "legal"


@dataclass(frozen=True)
class GlossaryResult:
    """Outcome of a glossary generation pass."""

    output_relpath: str
    approved_rendered: int
    drafts_excluded: int
    legal_links: int
    deduplicated_terms: tuple[str, ...] = ()


def _legal_permalinks(repo_root: Path) -> dict[str, str]:
    """Build the ``legal-ref-id -> BOE permalink`` map from the catalogue TOMLs.

    Reads the ``[legal."<id>"]`` tables directly (a lightweight read, not the
    full registry-catalogue machinery): the concept ``legal_refs`` ids match
    the catalogue keys verbatim, so the map resolves a concept's grounding to
    its published BOE permalink.
    """
    catalogue = repo_root / _LEGAL_CATALOGUE_RELPATH
    permalinks: dict[str, str] = {}
    if not catalogue.is_dir():
        return permalinks
    for fragment in sorted(catalogue.glob("*.toml")):
        try:
            data = tomllib.loads(fragment.read_text(encoding=_UTF_8))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        legal = data.get("legal")
        if not isinstance(legal, dict):
            continue
        for ref_id, body in legal.items():
            if isinstance(body, dict):
                permalink = body.get("permalink")
                if isinstance(permalink, str) and permalink:
                    permalinks[str(ref_id)] = permalink
    return permalinks


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


def _english_section(concept: ConceptRecord) -> LanguageSection | None:
    """Return the English section (the entry body text), or None."""
    for section in concept.languages:
        if section.language is OutputLanguage.EN:
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


def _body_text(concept: ConceptRecord) -> str:
    """The entry body: the English definition, else the English short description.

    Both are curated, taxpayer-general prose. The full ``definition`` is
    preferred when authored; the required ``short_description`` is the
    guaranteed fallback (every approved concept has one).
    """
    section = _english_section(concept) or _primary_section(concept)
    if section is None:  # pragma: no cover - approved concepts always have a section
        return ""
    return section.definition or section.short_description


def _related_lines(
    concept: ConceptRecord,
    headwords: dict[str, str],
    body_indent: str,
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
    for label, ids in (("Broader", concept.broader), ("Related", concept.related)):
        refs = [f":term:`{headwords[ref]}`" for ref in ids if ref != concept.concept_id and ref in headwords]
        if refs:
            relation_lines.append(f"{body_indent}* {label}: {', '.join(refs)}")
    return relation_lines


def _render_entry(
    concept: ConceptRecord,
    permalinks: dict[str, str],
    claimed: set[str],
    headwords: dict[str, str],
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
    block = [*lines, f"{body_indent}{_body_text(concept)}"]
    legal_count = 0
    grounding: list[str] = []
    for ref in concept.legal_refs:
        permalink = permalinks.get(ref)
        if permalink:
            grounding.append(f"{body_indent}* Legal basis: `{ref} <{permalink}>`__")
            legal_count += 1
    grounding.extend(_related_lines(concept, headwords, body_indent))
    if grounding:
        block.append("")
        block.extend(grounding)
    return "\n".join(block), legal_count, dropped


def render_glossary(repo_root: Path, handbook: TerminologyHandbook) -> tuple[str, GlossaryResult]:
    """Render the generated glossary RST and its result summary.

    Args:
        repo_root: Repository root (for the legal-catalogue read).
        handbook: The compiled Terminology Handbook.

    Returns:
        ``(rst_text, result)`` - the page content and a summary of how many
        approved concepts rendered, how many drafts were excluded, and how
        many legal grounding links resolved.
    """
    permalinks = _legal_permalinks(repo_root)
    approved = _approved_concepts(handbook)
    # concept_id -> headword for every approved concept, so broader/related
    # relations can be rendered as resolvable ``:term:`` cross-references to the
    # target's glossary anchor (a relation to a draft/non-rendered concept is
    # skipped, never emitting an unresolvable reference).
    headwords = {concept.concept_id: _headword(concept) for concept in approved}
    drafts = sum(1 for concept in handbook.concepts if concept.lifecycle is ConceptLifecycle.DRAFT)

    header = (
        "..\n"
        "   Generated by dev/docs/glossary_reference.py from the approved\n"
        "   Terminology Handbook concepts. Do not edit by hand; regenerate.\n\n"
        "Glossary\n"
        "========\n\n"
        "Spanish tax terms used across the documentation. Each term links to\n"
        "its legal basis where one applies. Look a term up; the definition is\n"
        "the same wherever the term is referenced.\n\n"
        ".. glossary::\n"
        "   :sorted:\n\n"
    )
    entries: list[str] = []
    legal_links = 0
    claimed: set[str] = set()
    deduplicated: list[str] = []
    rendered = 0
    for concept in approved:
        entry, count, dropped = _render_entry(concept, permalinks, claimed, headwords)
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


def generate_glossary_reference(docs_root: Path) -> GlossaryResult:
    """Materialise the generated glossary page under ``docs_root/_generated/``.

    Mirrors :func:`~dev.docs.cli_reference.generate_cli_reference`: it loads
    the typed authority, renders the page, and writes it to the generated
    (gitignored, uncommitted) location, returning a summary. Wired at the
    ``builder-inited`` seam so the page exists before Sphinx reads the source
    tree.

    Args:
        docs_root: The documentation root (the directory holding ``index.md``).

    Returns:
        A :class:`GlossaryResult` summarising the render.
    """
    repo_root = docs_root.resolve().parent
    handbook = load_terminology_handbook()
    rst, result = render_glossary(repo_root, handbook)
    output_path = docs_root / _GENERATED_RELPATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not (output_path.is_file() and output_path.read_text(encoding=_UTF_8) == rst):
        # Force LF so the generated page is byte-identical across platforms; the
        # default newline translation emits CRLF on Windows, which doc8's
        # CheckCarriageReturn (D004) then flags on every regeneration.
        output_path.write_text(rst, encoding=_UTF_8, newline="\n")
    return result
