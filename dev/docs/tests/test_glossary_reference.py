"""Real-behaviour tests for the generated glossary reference.

Exercises the generator against the real Terminology Handbook (no mocks): it
renders only approved concepts, excludes drafts, produces a valid Sphinx
``glossary`` directive whose ``:term:`` targets (headwords and admitted
aliases) register without a duplicate-term warning, and resolves legal
grounding links to BOE permalinks.

The Sphinx-parse test builds a throwaway dummy project over the generated
page to prove the directive is well-formed and the ``-n -W`` gate would not
break on it - without running the full multi-minute docs build.
"""

from __future__ import annotations

import io
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
    from aeat.terminology import load_terminology_handbook

    return load_terminology_handbook()


@pytest.mark.integration
@pytest.mark.hex_core
def test_only_approved_concepts_render_drafts_excluded() -> None:
    """The glossary renders approved concepts and excludes every draft.

    Confirms the approved-only rule: drafts (the bulk of the Handbook) carry
    no curated definition and must never become a glossary entry.
    """
    from aeat.terminology._enums import ConceptLifecycle

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
def test_headword_and_alias_term_lines_present() -> None:
    """The page carries Spanish headwords plus admitted-alias term lines.

    The AEAT concept renders its preferred term ``AEAT`` as the headword and
    its admitted alias ``Agencia Tributaria`` as an additional term line on the
    same entry, so a ``:term:`` to either resolves to one definition.
    """
    rst, _ = render_glossary(_REPO_ROOT, _load_handbook())
    assert ".. glossary::" in rst
    # Headword and alias both appear as term lines (3-space indented).
    assert "\n   AEAT\n" in rst
    assert "\n   Agencia Tributaria\n" in rst
    # The English definition body is present (6-space indented).
    assert "The Spanish Tax Agency" in rst


@pytest.mark.integration
@pytest.mark.hex_core
def test_legal_grounding_links_resolve_to_permalinks() -> None:
    """Concepts with legal_refs render resolved BOE permalink grounding links."""
    rst, result = render_glossary(_REPO_ROOT, _load_handbook())
    assert result.legal_links > 0
    # The autoliquidacion concept grounds in LGT art. 120 with a BOE permalink.
    assert "Legal basis:" in rst
    assert "boe.es/buscar/act.php" in rst


@pytest.mark.integration
@pytest.mark.hex_core
def test_broader_related_relations_render_as_term_cross_references() -> None:
    """Concept relations render as ``:term:`` cross-references to approved targets.

    The Handbook's SKOS ``broader`` / ``related`` relations were invisible to
    the reader; the glossary now renders them as ``:term:`` links, turning the
    page into a navigable concept graph. A relation to a draft (non-rendered)
    concept is skipped so no unresolvable reference reaches the ``-n -W`` build.
    """
    from aeat.terminology._enums import ConceptLifecycle

    handbook = _load_handbook()
    rst, _ = render_glossary(_REPO_ROOT, handbook)

    # The modelo-303 concept declares related = iva/casilla/autoliquidacion/...,
    # which must surface as a Related cross-reference line of :term: links.
    assert "* Related: :term:`IVA`" in rst or "* Related: :term:`casilla`" in rst
    assert ":term:`prorrata`" in rst

    # Every :term: target rendered in a relation line is an approved concept's
    # headword (drafts never become a :term: target -- they have no anchor).
    approved_headwords = set()
    for concept in handbook.concepts:
        if concept.lifecycle is ConceptLifecycle.APPROVED:
            for section in concept.languages:
                for term in section.terms:
                    approved_headwords.add(term.label)
    import re

    for line in rst.splitlines():
        if "Related:" in line or "Broader:" in line:
            for ref in re.findall(r":term:`([^`]+)`", line):
                assert ref in approved_headwords, f"relation links to non-approved/unknown term: {ref!r}"


@pytest.mark.integration
@pytest.mark.hex_core
def test_generated_glossary_parses_without_duplicate_term_warning() -> None:
    """A throwaway Sphinx build over the page emits no warnings and registers terms.

    Proves the generated directive is well-formed and the nitpicky ``-n -W``
    gate would not break on it: the build is clean (no duplicate-term warning,
    the collision the generator deduplicates) and the ``:term:`` targets -
    headwords and aliases - are registered in the std domain.
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

        assert not warning.getvalue().strip(), warning.getvalue()
        std = app.env.domains["std"]
        terms = [name for (objtype, name) in std.objects if objtype == "term"]
        assert "AEAT" in terms
        assert "Agencia Tributaria" in terms  # the alias resolves too
        assert len(terms) >= 30


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
