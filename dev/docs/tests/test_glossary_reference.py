"""Real-behaviour tests for the generated glossary reference.

Exercises the generator against the real Terminology Handbook (no mocks): it
renders only approved concepts, excludes drafts, produces a valid Sphinx
``glossary`` directive whose ``:term:`` targets (headwords and admitted
aliases) register without a duplicate-term warning, and resolves legal
grounding links to BOE permalinks.

Testing contract for this generated, localized page: assert only what stays
true when every localized string in the source changes. Legitimate to lock are
(a) the generator's emitted schema (``.. glossary::``, the grounding-line
shape, the 3-space term-line / 6-space body indentation, the output path),
(b) structural shape (one entry per approved concept, term-line count, a body
paragraph under the term lines), and (c) cross-artifact invariants (every
rendered ``:term:`` target is an approved headword, every rendered term
registers in Sphinx, every rendered permalink is one the catalogue maps). A
specific source string (``AEAT``, ``prorrata``, a BOE URL) is never asserted,
and an expected value is never derived by calling the generator's own render
helpers (``_body_text`` / ``_term_lines`` / ``_headword``) -- that re-runs the
code under test as its own oracle. Expected values MAY be derived from the
source handbook, but only as an independent traversal producing a count, a set,
or a shape -- never a rendered string, never through the generator module -- so
the traversal and the render can disagree when the generator is wrong. The
self-check for any assertion here: would it fail if the generator were wrong
while the source stayed fixed?

The Sphinx-parse test builds a throwaway dummy project over the generated
page to prove the directive is well-formed and the ``-n -W`` gate would not
break on it - without running the full multi-minute docs build.
"""

from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..glossary_reference import (
    GlossaryResult,
    generate_glossary_reference,
    render_glossary,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

# dev/docs/tests/test_glossary_reference.py -> parents[3] is the repo root.
_REPO_ROOT = REPO_ROOT


def _load_handbook():
    from ..terminology_handbook.loader import load_terminology_handbook

    return load_terminology_handbook()


def _is_term_line(line: str) -> bool:
    """A glossary term line: 3-space indented, not the 6-space body, not an option.

    Excludes the directive option (``:sorted:``, a 3-space line starting with a
    colon). The leading ``..`` comment block is also 3-space indented, so callers
    must additionally scope to lines after ``.. glossary::`` (see
    :func:`_glossary_body`) to keep it out.
    """
    return (
        line.startswith("   ")
        and not line.startswith("      ")
        and bool(line.strip())
        and not line.lstrip().startswith(":")
    )


def _glossary_body(rst: str) -> list[str]:
    """The lines after the ``.. glossary::`` directive (excludes the header)."""
    lines = rst.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == ".. glossary::"), -1)
    return lines[start + 1 :] if start >= 0 else []


def _rendered_term_lines(rst: str) -> set[str]:
    """The set of term-line labels the page renders inside the glossary directive."""
    return {line[3:] for line in _glossary_body(rst) if _is_term_line(line)}


def test_only_approved_concepts_render_drafts_excluded() -> None:
    """The glossary renders approved concepts and excludes every draft.

    Confirms the approved-only rule: drafts (the bulk of the Handbook) carry
    no curated definition and must never become a glossary entry.
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle

    handbook = _load_handbook()
    approved = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.APPROVED)
    drafts = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.DRAFT)

    _, result = render_glossary(_REPO_ROOT, handbook)

    assert isinstance(result, GlossaryResult)
    assert result.drafts_excluded == drafts
    assert drafts > 0  # the Handbook has a draft backlog to exclude
    assert result.deduplicated_terms == (), (
        "a headword collided during rendering. This field records the terms dropped and "
        "had no reader anywhere in the tree, which matters because a concept whose every "
        f"term collides is skipped entirely and appears in NO count: {result.deduplicated_terms}"
    )
    assert result.approved_rendered == approved, (
        "with nothing deduplicated, every approved concept must reach the page. The bound "
        "here was previously <=, which absorbed a silently dropped concept as a smaller "
        f"number: {result.approved_rendered} rendered against {approved} approved"
    )


def test_term_lines_are_declared_surfaces_and_aliases_share_one_entry() -> None:
    """Rendered term lines are all declared surfaces; aliases share one entry.

    Shape, never content. The set of rendered term lines must be a subset of the
    surfaces the source declares (dedup only removes, so a rendered term absent
    from the source is an invention); and if the source declares any admitted
    alias, some entry must render two or more consecutive term lines -- the
    alias-on-the-same-entry path. No term label is named.
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle

    from ..terminology_handbook.enums import TermStatus

    handbook = _load_handbook()
    rst, _ = render_glossary(_REPO_ROOT, handbook)
    assert ".. glossary::" in rst

    rendered_terms = _rendered_term_lines(rst)
    assert rendered_terms, "the glossary rendered no term lines"

    declared_surfaces = {
        term.label
        for concept in handbook.concepts
        if concept.lifecycle is ConceptLifecycle.APPROVED
        for section in concept.languages
        for term in section.terms
        if term.term_status in (TermStatus.PREFERRED, TermStatus.ADMITTED)
    }
    assert rendered_terms <= declared_surfaces, (
        f"rendered term lines with no declared source surface: {rendered_terms - declared_surfaces!r}"
    )

    # If the source declares an admitted alias distinct from its headword, the
    # generator must render it as an extra term line on the same entry, i.e. a
    # run of 2+ consecutive term lines exists. Guarded on the source so removing
    # every alias does not falsely red this gate.
    source_has_alias = any(
        len({t.label for t in section.terms if t.term_status in (TermStatus.PREFERRED, TermStatus.ADMITTED)}) >= 2
        for concept in handbook.concepts
        if concept.lifecycle is ConceptLifecycle.APPROVED
        for section in concept.languages
    )
    if source_has_alias:
        longest_run = current = 0
        for line in _glossary_body(rst):
            current = current + 1 if _is_term_line(line) else 0
            longest_run = max(longest_run, current)
        assert longest_run >= 2, "no entry renders an alias term line beside its headword"


def test_legal_grounding_links_resolve_to_permalinks() -> None:
    """Concepts with legal_refs render resolved BOE permalink grounding links.

    Count-parity plus membership against an independently read permalink map:
    the number of rendered grounding links equals the generator's own
    ``legal_links`` tally, and every rendered URL is one the legal catalogue
    actually maps. ``_legal_permalinks`` reads the catalogue TOMLs directly, not
    the render path, so it is an independent oracle -- no URL is hardcoded.
    """
    from ..glossary_reference import _legal_permalinks

    rst, result = render_glossary(_REPO_ROOT, _load_handbook())
    assert result.legal_links > 0

    catalogue_permalinks = {grounding.permalink for grounding in _legal_permalinks(_REPO_ROOT).values()}
    # Matched on the line's shape, not its label: the label is localized.
    rendered_links = re.findall(r"^ +\* [^:]+: `[^`]+ <([^>]+)>`__ \(``[^`]+``\)$", rst, re.MULTILINE)
    assert len(rendered_links) == result.legal_links
    assert all(url in catalogue_permalinks for url in rendered_links)


def test_entry_bodies_render_the_build_language_and_no_other() -> None:
    """A root built for one language renders that language's definitions only.

    The page's prose comes from a four-language authority, so the failure to
    guard against is a body rendered in a language the root was not built for.
    For each target language, every rendered body must be the text that
    language's section authors -- read by an independent traversal of the
    handbook, never through the generator -- and no body may be the text of a
    different language whose section says something else.
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle
    from cadrumo.core.external_constants import OutputLanguage

    handbook = _load_handbook()

    def _authored(language: OutputLanguage) -> dict[str, set[str]]:
        """concept_id -> the body strings that language legitimately renders."""
        authored: dict[str, set[str]] = {}
        for concept in handbook.concepts:
            if concept.lifecycle is not ConceptLifecycle.APPROVED:
                continue
            for section in concept.languages:
                if section.language is language:
                    authored[concept.concept_id] = {
                        text for text in (section.definition, section.short_description) if text
                    }
        return authored

    for language in OutputLanguage:
        rst, _ = render_glossary(_REPO_ROOT, handbook, language)
        bodies = {
            line.strip()
            for line in _glossary_body(rst)
            if line.startswith("      ") and line.strip() and not line.strip().startswith("*")
        }
        assert bodies, f"{language.value}: the glossary rendered no entry bodies"

        expected = {text for texts in _authored(language).values() for text in texts}
        # Every body is authored for the build language. Sections are the only
        # source of prose, so a body outside this set came from another one.
        foreign = bodies - expected
        assert not foreign, f"{language.value}: bodies not authored in the build language: {sorted(foreign)[:3]}"

    # The languages must actually differ, or the assertion above holds
    # vacuously for a generator that ignored the argument entirely.
    spanish, _ = render_glossary(_REPO_ROOT, handbook, OutputLanguage.ES)
    english, _ = render_glossary(_REPO_ROOT, handbook, OutputLanguage.EN)
    assert spanish != english, "the es and en renders are identical; the build language is being ignored"


def test_a_concept_without_build_language_prose_never_borrows_another_language() -> None:
    """An unauthored definition degrades to structure, never to other-language prose.

    The rule with teeth: only the curated per-language sections may supply
    prose, so a concept with nothing authored in the build language must say so
    and fall back to compiled structure, never to the Spanish or English text.
    Exercised by rendering the real handbook in a language whose sections are
    stripped from the records, which is the shape partial coverage takes.
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle
    from cadrumo.core.external_constants import OutputLanguage

    handbook = _load_handbook()
    approved = [c for c in handbook.concepts if c.lifecycle is ConceptLifecycle.APPROVED]
    assert approved, "no approved concepts to exercise"

    # Drop the Catalan sections so every approved concept lacks build-language
    # prose, without touching the Spanish/English text that must not leak.
    stripped = handbook.model_copy(
        update={
            "concepts": tuple(
                concept.model_copy(
                    update={"languages": tuple(s for s in concept.languages if s.language is not OutputLanguage.CA)},
                )
                for concept in handbook.concepts
            ),
        },
    )
    rst, _ = render_glossary(_REPO_ROOT, stripped, OutputLanguage.CA)

    other_language_prose = {
        text
        for concept in approved
        for section in concept.languages
        for text in (section.definition, section.short_description)
        if text
    }
    leaked = sorted(text for text in other_language_prose if text in rst)
    assert not leaked, f"other-language prose leaked onto a ca build: {leaked[:2]}"

    # It degrades visibly rather than rendering an empty shell, and the
    # language-safe compiled structure still carries the entry. The expected
    # marker is read from the catalogue, never from the renderer, and never
    # written here as prose.
    from .._locale_chrome import docs_chrome

    assert docs_chrome("docs.glossary.entry.undefined", OutputLanguage.CA) in rst
    assert docs_chrome("docs.glossary.entry.legal_basis", OutputLanguage.CA) in rst


def test_broader_related_relations_render_as_term_cross_references() -> None:
    """Concept relations render as ``:term:`` cross-references to approved targets.

    The Handbook's SKOS ``broader`` / ``related`` relations render as ``:term:``
    links, turning the page into a navigable concept graph. Two invariants, both
    shape-not-content: every ``:term:`` target in a relation line is an approved
    concept's surface (never a dangling reference to a draft), and the count of
    rendered relation edges equals the count of approved-to-approved relations
    the source declares (a dropped or spurious edge fails the count).
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle

    handbook = _load_handbook()
    rst, _ = render_glossary(_REPO_ROOT, handbook)

    approved_ids = {c.concept_id for c in handbook.concepts if c.lifecycle is ConceptLifecycle.APPROVED}
    approved_surfaces = {
        term.label
        for concept in handbook.concepts
        if concept.lifecycle is ConceptLifecycle.APPROVED
        for section in concept.languages
        for term in section.terms
    }

    # No dangling relation: every :term: target rendered in a relation line is an
    # approved concept's surface (drafts never become a :term: anchor).
    # A relation line is identified by its shape -- an indented bullet carrying
    # :term: references -- never by its label, which is localized.
    relation_lines = [line for line in rst.splitlines() if line.lstrip().startswith("*") and ":term:`" in line]
    for line in relation_lines:
        for ref in re.findall(r":term:`([^`]+)`", line):
            assert ref in approved_surfaces, f"relation links to non-approved/unknown term: {ref!r}"

    # Edge-count parity: rendered relation links == approved->approved relations
    # the source declares.
    expected_edges = sum(
        1
        for concept in handbook.concepts
        if concept.lifecycle is ConceptLifecycle.APPROVED
        for ref in (*concept.broader, *concept.related)
        if ref != concept.concept_id and ref in approved_ids
    )
    rendered_edges = sum(len(re.findall(r":term:`[^`]+`", line)) for line in relation_lines)
    assert expected_edges > 0, "no approved->approved relation exists to exercise the renderer"
    assert rendered_edges == expected_edges


def test_generated_glossary_parses_without_duplicate_term_warning() -> None:
    """A throwaway Sphinx build over the page emits no warnings and registers terms.

    Proves the generated directive is well-formed and the nitpicky ``-n -W``
    gate would not break on it: the build is clean (no duplicate-term warning,
    the collision the generator deduplicates) and the set of ``:term:`` targets
    Sphinx registers equals exactly the set of term lines the page renders -
    every headword and alias resolves, nothing extra.
    """
    from sphinx.application import Sphinx

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        docs = tmp / "docs"
        docs.mkdir()
        generate_glossary_reference(docs)
        (docs / "conf.py").write_text('project = "t"\nextensions = []\n', encoding="utf-8")
        (docs / "index.rst").write_text(
            "Test\n====\n\n.. toctree::\n\n   _generated/glossary\n",
            encoding="utf-8",
        )
        warning = io.StringIO()
        app = Sphinx(
            str(docs),
            str(docs),
            str(tmp / "b"),
            str(tmp / "d"),
            "dummy",
            status=io.StringIO(),
            warning=warning,
            freshenv=True,
        )
        app.build()

        # Sphinx registers some docutils nodes/roles process-globally, so a
        # second Sphinx app in the same pytest process re-emits benign
        # "already registered" notices that are not glossary problems. Filter
        # them so this gate asserts only real warnings -- the duplicate-term or
        # unresolved-reference warnings the generated directive could actually
        # provoke.
        real_warnings = [
            line for line in warning.getvalue().splitlines() if line.strip() and "already registered" not in line
        ]
        assert not real_warnings, warning.getvalue()

        # The terms Sphinx registered equal exactly the term lines the page
        # rendered -- the alias-registration invariant, expressed structurally
        # against the generated file rather than a hardcoded term list.
        std = app.env.domains["std"]
        registered_terms = {name for (objtype, name) in std.objects if objtype == "term"}
        generated_rst = (docs / "_generated" / "glossary.rst").read_text(encoding="utf-8")
        rendered_term_lines = _rendered_term_lines(generated_rst)
        assert rendered_term_lines, "the generated glossary rendered no term lines"
        assert registered_terms == rendered_term_lines


def test_generator_writes_to_gitignored_generated_path(tmp_path: Path) -> None:
    """The generator writes the page under docs/_generated/ (gitignored)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    result = generate_glossary_reference(docs)
    assert result.output_relpath == "_generated/glossary.rst"
    written = docs / "_generated" / "glossary.rst"
    assert written.is_file()
    assert ".. glossary::" in written.read_text(encoding="utf-8")


def test_an_absent_legal_catalogue_says_so_instead_of_grounding_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An empty grounding map renders a glossary with no legal citations at all.

    The lookup returned one in silence, so every concept rendered ungrounded and
    read exactly like a corpus that genuinely cites nothing. It stays non-fatal
    because the generator is legitimately driven against synthetic docs roots,
    but it now says which render is ungrounded. Measured live: 64 fragments,
    704 grounding entries, so empty is never the true answer for the real tree.
    """
    from ..glossary_reference import _legal_permalinks

    assert _legal_permalinks(tmp_path) == {}
    assert "no legal catalogue" in capsys.readouterr().err


def test_a_malformed_catalogue_fragment_refuses(tmp_path: Path) -> None:
    """A fragment that does not parse silently dropped every citation it declared.

    Distinguished from a read failure on purpose: broken TOML is a defect, while
    a vanished file is a race, and one handler was treating them alike.
    """
    from ..glossary_reference import _legal_permalinks
    from ..legal_reference import LEGAL_CATALOGUE_RELPATH

    catalogue = tmp_path / LEGAL_CATALOGUE_RELPATH
    catalogue.mkdir(parents=True)
    (catalogue / "broken.toml").write_text("[legal" + chr(10), encoding="utf-8")

    with pytest.raises(SystemExit, match="not valid TOML"):
        _legal_permalinks(tmp_path)


def test_the_live_catalogue_still_grounds_every_reference() -> None:
    """The success path, so the refusals are not satisfied by refusing everything."""
    from ..glossary_reference import _legal_permalinks

    assert len(_legal_permalinks(_REPO_ROOT)) > 0
