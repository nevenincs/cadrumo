"""Real-behaviour tests for the generated glossary reference.

Exercises the generator against the real Terminology Handbook (no mocks): it
renders only approved concepts, excludes drafts, produces a valid Sphinx
``glossary`` directive whose ``:term:`` targets (headwords and admitted
aliases) register without a duplicate-term warning, and resolves legal
grounding links to BOE permalinks.

Testing contract for this generated, localized page: assert only what stays
true when every localized string in the source changes. Legitimate to lock are
(a) the generator's emitted schema (``.. glossary::``, the ``Legal basis:``
label, the 3-space term-line / 6-space body indentation, the output path),
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

from ..glossary_reference import (
    GlossaryResult,
    generate_glossary_reference,
    render_glossary,
)

# dev/docs/tests/test_glossary_reference.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_handbook():
    from ..terminology_handbook import load_terminology_handbook

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


@pytest.mark.integration
@pytest.mark.hex_core
def test_only_approved_concepts_render_drafts_excluded() -> None:
    """The glossary renders approved concepts and excludes every draft.

    Confirms the approved-only rule: drafts (the bulk of the Handbook) carry
    no curated definition and must never become a glossary entry.
    """
    from ..terminology_handbook._enums import ConceptLifecycle

    handbook = _load_handbook()
    approved = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.APPROVED)
    drafts = sum(1 for c in handbook.concepts if c.lifecycle is ConceptLifecycle.DRAFT)

    _, result = render_glossary(_REPO_ROOT, handbook)

    assert isinstance(result, GlossaryResult)
    assert result.drafts_excluded == drafts
    assert drafts > 0  # the Handbook has a draft backlog to exclude
    # Every rendered entry is an approved concept (minus any fully-deduplicated
    # collisions, which only reduce the count, never raise it).
    assert 0 < result.approved_rendered <= approved


@pytest.mark.integration
@pytest.mark.hex_core
def test_term_lines_are_declared_surfaces_and_aliases_share_one_entry() -> None:
    """Rendered term lines are all declared surfaces; aliases share one entry.

    Shape, never content. The set of rendered term lines must be a subset of the
    surfaces the source declares (dedup only removes, so a rendered term absent
    from the source is an invention); and if the source declares any admitted
    alias, some entry must render two or more consecutive term lines -- the
    alias-on-the-same-entry path. No term label is named.
    """
    from ..terminology_handbook._enums import ConceptLifecycle, TermStatus

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
        len(
            {t.label for t in section.terms if t.term_status in (TermStatus.PREFERRED, TermStatus.ADMITTED)}
        )
        >= 2
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


@pytest.mark.integration
@pytest.mark.hex_core
def test_legal_grounding_links_resolve_to_permalinks() -> None:
    """Concepts with legal_refs render resolved BOE permalink grounding links.

    Count-parity plus membership against an independently read permalink map:
    the number of rendered ``Legal basis:`` links equals the generator's own
    ``legal_links`` tally, and every rendered URL is one the legal catalogue
    actually maps. ``_legal_permalinks`` reads the catalogue TOMLs directly, not
    the render path, so it is an independent oracle -- no URL is hardcoded.
    """
    from ..glossary_reference import _legal_permalinks

    rst, result = render_glossary(_REPO_ROOT, _load_handbook())
    assert result.legal_links > 0
    assert "Legal basis:" in rst

    catalogue_permalinks = set(_legal_permalinks(_REPO_ROOT).values())
    rendered_links = re.findall(r"Legal basis: `[^`]+ <([^>]+)>`__", rst)
    assert len(rendered_links) == result.legal_links
    assert all(url in catalogue_permalinks for url in rendered_links)


@pytest.mark.integration
@pytest.mark.hex_core
def test_broader_related_relations_render_as_term_cross_references() -> None:
    """Concept relations render as ``:term:`` cross-references to approved targets.

    The Handbook's SKOS ``broader`` / ``related`` relations render as ``:term:``
    links, turning the page into a navigable concept graph. Two invariants, both
    shape-not-content: every ``:term:`` target in a relation line is an approved
    concept's surface (never a dangling reference to a draft), and the count of
    rendered relation edges equals the count of approved-to-approved relations
    the source declares (a dropped or spurious edge fails the count).
    """
    from ..terminology_handbook._enums import ConceptLifecycle

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
    for line in rst.splitlines():
        if "Related:" in line or "Broader:" in line:
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
    rendered_edges = sum(
        len(re.findall(r":term:`[^`]+`", line))
        for line in rst.splitlines()
        if "Related:" in line or "Broader:" in line
    )
    assert expected_edges > 0, "no approved->approved relation exists to exercise the renderer"
    assert rendered_edges == expected_edges


@pytest.mark.integration
@pytest.mark.hex_core
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


@pytest.mark.integration
@pytest.mark.hex_core
def test_generator_writes_to_gitignored_generated_path(tmp_path: Path) -> None:
    """The generator writes the page under docs/_generated/ (gitignored)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    result = generate_glossary_reference(docs)
    assert result.output_relpath == "_generated/glossary.rst"
    written = docs / "_generated" / "glossary.rst"
    assert written.is_file()
    assert ".. glossary::" in written.read_text(encoding="utf-8")
