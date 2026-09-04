"""Redeclaration conformance gate for the documentation terminology surface.

The terminology sibling of ``test_documented_command_conformance`` and
``test_educational_docs_conformance``: once a term is enrolled and APPROVED in
the Terminology Handbook, the user docs must reference it with ``{term}`` (so
the single canonical definition lives in the generated glossary) and must never
re-declare it inline. No surveyed docs system detects prose redeclaration; this
gate makes "terminology is codebase-state-as-truth" a tested invariant rather
than an author-discipline hope.

What it flags: the inline-glossary SHAPE - an enrolled approved term in emphasis
followed by a definitional clause (``*justificante* - the receipt ...``,
``**casilla**: a numbered box``), or an enrolled term immediately followed by a
parenthetical gloss (``justificante (the official receipt ...)``). These are the
exact shapes the cutover deleted. It deliberately does NOT flag a plain
descriptive sentence (``Modelo 303 is the quarterly VAT return`` on a Modelo-303
page) - that is ambiguous between description and definition, and the gate
chooses precision over recall: a false positive that reds the build on a
legitimate mention is worse than missing a borderline redeclaration.

What it does NOT enforce: the gate drives off the APPROVED enrolled terms only
(the rendered ``:term:`` anchors). A term that is referenced in the docs but not
yet an approved concept (IVA, IRPF, a generic modelo, ...) has no anchor, so its
inline mention is LEGITIMATE until the concept is approved - the gate must not
flag it. As concepts get approved the enforced set widens automatically.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest

from ...._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.docs, pytest.mark.hex_entrypoint]

# Dev tooling runs from a source checkout by definition, so it owns its own
# repo-root anchor. Production code has no repository concept and must never
# export one (see cadrumo.core.config_state_root for the runtime data root).
_REPO_ROOT = REPO_ROOT

# User-docs prose surfaces. The generated glossary (which legitimately DEFINES
# every term) and the generated CLI / API references are excluded - they are
# build-time projections, not hand-authored prose.
_DOC_GLOBS = ("docs/**/*.md", "docs/**/*.rst")
_EXCLUDED_PREFIXES = ("docs/_generated/", "docs/cli/", "docs/api/", "docs/_build/")

# Fenced code blocks and inline code are not prose - an enrolled term inside a
# command example or a code span is not a redeclaration.
_FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
# A {term}`...` / :term:`...` reference is the CORRECT form, never a flag. Strip
# them before scanning so a reference whose display text contains the term word
# is not mistaken for a bare mention.
_TERM_ROLE_RE = re.compile(r"\{term\}`[^`]+`|:term:`[^`]+`")

# Definitional clause: the term is being taught, not used. Kept tight (an
# article-led copula or an explicit "means"/"refers to") to avoid descriptive
# false positives.
_DEFINITION = r"(?:is|are)\s+(?:a|an|the)\b|\bmeans\b|refers to|stands for"


@cache
def _approved_anchor_terms() -> tuple[str, ...]:
    """Return the APPROVED enrolled term labels (the rendered :term: anchors).

    These are the surfaces a doc must reference rather than redefine: the
    preferred + admitted term labels of every approved concept, as the glossary
    generator renders them. Longest-first so a multi-word term is matched before
    a substring (``modelo 100`` before a bare ``modelo`` that is not an anchor).
    """
    from cadrumo.core.concept_lifecycle import ConceptLifecycle

    from ..enums import TermStatus
    from ..loader import load_terminology_handbook

    handbook = load_terminology_handbook()
    labels: set[str] = set()
    for concept in handbook.concepts:
        if concept.lifecycle is not ConceptLifecycle.APPROVED:
            continue
        for section in concept.languages:
            for term in section.terms:
                if term.term_status in (TermStatus.PREFERRED, TermStatus.ADMITTED):
                    labels.add(term.label)
    return tuple(sorted(labels, key=len, reverse=True))


def _redeclaration_patterns(term: str) -> tuple[re.Pattern[str], ...]:
    """Return the inline-glossary-shape redeclaration patterns for one term."""
    escaped = re.escape(term)
    return (
        # *term* - definition  /  **term**: definition  (emphasised + separator)
        re.compile(rf"[*_]{{1,2}}{escaped}[*_]{{1,2}}\s*[—:-]\s+\S", re.IGNORECASE),
        # *term* is a / means ...  (emphasised + definitional clause)
        re.compile(rf"[*_]{{1,2}}{escaped}[*_]{{1,2}}\s+(?:{_DEFINITION})", re.IGNORECASE),
        # term (a/an/the definition...)  (parenthetical gloss right after the term)
        re.compile(rf"(?<![\w-]){escaped}\s*\((?:a|an|the)\s+\w", re.IGNORECASE),
    )


def _strip_non_prose(text: str) -> str:
    """Remove code blocks, inline code, and correct {term}/:term: references."""
    text = _FENCE_RE.sub("\n", text)
    text = _INLINE_CODE_RE.sub(" ", text)
    return _TERM_ROLE_RE.sub(" ", text)


def _user_docs() -> list[Path]:
    docs: list[Path] = []
    for pattern in _DOC_GLOBS:
        for path in sorted(_REPO_ROOT.glob(pattern)):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if not rel.startswith(_EXCLUDED_PREFIXES):
                docs.append(path)
    return docs


def _redeclarations_in(text: str, terms: tuple[str, ...]) -> list[tuple[str, int, str]]:
    """Return ``(term, line, snippet)`` for every inline redeclaration found."""
    prose = _strip_non_prose(text)
    found: list[tuple[str, int, str]] = []
    for term in terms:
        for pattern in _redeclaration_patterns(term):
            for match in pattern.finditer(prose):
                line = prose.count("\n", 0, match.start()) + 1
                found.append((term, line, match.group(0)[:60]))
    return found


def test_approved_terms_are_loaded() -> None:
    """The gate drives off a non-empty approved-term set (guards a silent pass)."""
    terms = _approved_anchor_terms()
    assert terms, "no approved enrolled terms loaded; the gate would never fire"
    # Distinctive Spanish-stem anchors, not generic English words - so a
    # definitional clause adjacent to one is genuinely a redeclaration.
    assert "casilla" in terms
    assert "justificante" in terms


# Anti-tautology fixtures: the detector must FIRE on a real redeclaration and
# stay SILENT on legitimate prose. These exercise the detector directly with an
# explicit term so they do not depend on the live Handbook load.
_FIXTURE_TERMS = ("casilla", "justificante")


def test_positive_fixture_detects_inline_redeclaration() -> None:
    """A doc snippet that inline-redefines an enrolled term is flagged.

    The anti-tautology proof: if this did not fire, the gate could not catch a
    real redeclaration. Covers the three shapes the gate enforces.
    """
    emphasised = "A *casilla* - a numbered box on the form."
    parenthetical = "Download the justificante (the official receipt)."
    means = "A **casilla** means a numbered field."
    for snippet in (emphasised, parenthetical, means):
        found = _redeclarations_in(snippet, _FIXTURE_TERMS)
        assert found, f"detector missed a redeclaration in: {snippet!r}"


def test_negative_fixture_passes_legitimate_prose() -> None:
    """A :term: reference, a non-definitional mention, and an unapproved-term
    inline definition all pass the detector.
    """
    correct_reference = "Open the {term}`casilla` to edit it."
    non_definitional = "Each casilla holds one figure; review every casilla."
    code_example = "Run `aeat modelo show casilla` to inspect it."
    # IVA is NOT in _FIXTURE_TERMS (an unapproved term), so its inline
    # definition is legitimate and must not be flagged by a casilla/justificante
    # gate driven off the approved set.
    unapproved_inline = "IVA is a value-added tax you charge on sales."
    for snippet in (
        correct_reference,
        non_definitional,
        code_example,
        unapproved_inline,
    ):
        found = _redeclarations_in(snippet, _FIXTURE_TERMS)
        assert not found, f"false positive on legitimate prose: {snippet!r} -> {found}"


@pytest.mark.parametrize("doc", _user_docs(), ids=lambda p: str(p.relative_to(_REPO_ROOT)))
def test_no_inline_redeclaration_of_enrolled_terms(doc: Path) -> None:
    """No user-docs prose inline-redefines an approved enrolled term."""
    text = doc.read_text(encoding="utf-8")
    found = _redeclarations_in(text, _approved_anchor_terms())
    messages = [
        f"{doc.relative_to(_REPO_ROOT)}:{line} inline-redefines the enrolled "
        f"term '{term}'; reference it with {{term}}`{term}` instead "
        f"(definitions live in the Handbook). Matched: {snippet!r}"
        for term, line, snippet in found
    ]
    assert not messages, "\n".join(messages)
