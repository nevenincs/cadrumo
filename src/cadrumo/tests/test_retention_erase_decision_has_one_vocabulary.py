"""No retention condition can reach one erase decision and not the others.

Whether a profile's records may be destroyed is a LEGAL question: the
Administration's right to review a filed self-assessment prescribes four years
(Ley 58/2003 LGT art. 66/67) and the supporting documentation must be conserved
for the same window (art. 70.2). Getting it wrong destroys records the taxpayer
is required to keep.

That decision is not written once. It is expressed at several production sites
in different shapes -- some admit a recorded override, and the ``delete`` verb
deliberately does not, because it offers no override to record. The shapes
differing is fine. What is not fine is the failure mode the delete verb's own
docstring names and then accepts as a known cost: **a third condition added to
the retention contract would reach one site and not the other.**

This gate makes that impossible to do quietly. It does not require the sites to
agree on their expression -- that would fight a deliberate difference. It
requires them to draw from one declared VOCABULARY: every attribute read while
deciding whether an erase may proceed must be a term this test names. A new term
appearing at any single site fails here and lists every site, so whoever adds it
must decide, deliberately, which of them it belongs to.

The real remedy is the one that docstring proposes -- promote the decision to a
single shared function -- and that belongs to whoever owns the config-reset
surface. Until then this converts a known cost into a detected divergence, which
is the difference between prose and a gate.
"""

from __future__ import annotations

import ast

import pytest

from ._inventory import SRC_CADRUMO, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The attributes that mark an expression as an erase decision.
#:
#: ``blocks_erase`` is the reset's own retention backstop. ``filing_hold`` is
#: the SAME legal question asked at the custody transaction, which reaches it
#: through the hold assessment rather than the floor assessment -- both compute
#: from one ``assess_retention_floor``. Keying on the floor term alone left the
#: custody gates outside this gate's site population entirely, which is how a
#: third condition reached them without arriving here.
_DECISION_MARKERS = frozenset({"blocks_erase", "filing_hold"})

#: Every term an erase decision is currently entitled to read.
#:
#: ``blocks_erase`` is the floor itself; ``override_approved`` is the recorded
#: operator override that some surfaces admit and the delete verb does not.
#: A term outside this pair means the retention contract grew a condition, and
#: the gate's whole purpose is to make that arrive at every site at once.
_DECLARED_VOCABULARY = frozenset(
    {
        "blocks_erase",
        "override_approved",
        # The custody expression of the same decision. ``legal_hold`` is the
        # one term no operator authorisation clears; ``retention_override`` is
        # that authorisation, weighed only against the filing half.
        "filing_hold",
        "legal_hold",
        "retention_override",
        # NOT a retention condition: the custody re-validation compares the
        # recorded and current assessments and reads the identity to prove it
        # is comparing one profile against itself. Declared so the gate keeps
        # its teeth for terms that ARE conditions, rather than reddening on an
        # identity guard.
        "profile_id",
    }
)

#: Source carrying a third condition at a single site.
_WIDENED_SAMPLE = (
    "def may_erase(retention):\n"
    "    return not retention.blocks_erase or retention.override_approved or retention.legal_hold_lifted\n"
)

#: The same decision drawing only on the declared vocabulary.
_DECLARED_SAMPLE = (
    "def may_erase(retention):\n"
    "    return not retention.blocks_erase or retention.override_approved\n"
)


def _decision_expressions(tree: ast.AST) -> list[ast.expr]:
    """Return the boolean expressions that decide whether an erase may proceed.

    A decision is a boolean test over the floor, not a mention of it, and two
    shapes name the marker without deciding anything:

    - Building a ``RetentionFloorAssessment(blocks_erase=..., retained=...)``
      passes it as a keyword; a constructor keyword never sits inside a boolean
      operator, so requiring ``BoolOp``/``UnaryOp``/``Compare`` excludes it.
    - The assessment model's own validator checks ``self.blocks_erase`` against
      ``self.retained_record_count`` to prove the record is internally
      consistent. That is the floor checking itself, not a surface deciding an
      erase, so a marker read off ``self`` is excluded. Every real decision
      reads the floor from an assessment handed to it.
    """
    found: list[ast.expr] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp | ast.UnaryOp | ast.Compare):
            continue
        if any(
            isinstance(inner, ast.Attribute)
            and inner.attr in _DECISION_MARKERS
            and not (isinstance(inner.value, ast.Name) and inner.value.id == "self")
            for inner in ast.walk(node)
        ):
            found.append(node)
    # Keep only the outermost expression of each nest, so one decision reports once.
    outermost: list[ast.expr] = []
    for candidate in found:
        nested = any(candidate is not other and candidate in set(ast.walk(other)) for other in found)
        if not nested:
            outermost.append(candidate)
    return outermost


def _terms_read(expression: ast.expr) -> set[str]:
    """Return the attribute names one erase decision reads."""
    return {inner.attr for inner in ast.walk(expression) if isinstance(inner, ast.Attribute)}


def _undeclared_terms(tree: ast.AST) -> list[tuple[int, list[str]]]:
    """Return ``(line, terms)`` for decisions reaching outside the vocabulary."""
    offenders: list[tuple[int, list[str]]] = []
    for expression in _decision_expressions(tree):
        surplus = sorted(_terms_read(expression) - _DECLARED_VOCABULARY)
        if surplus:
            offenders.append((expression.lineno, surplus))
    return offenders


def _production_modules() -> list:
    """Return the package's production modules."""
    return [
        path
        for path in SRC_CADRUMO.rglob("*.py")
        if "tests" not in path.parts and path.name != "conftest.py"
    ]


def _decision_sites() -> list[str]:
    """Return every production site that decides an erase."""
    sites: list[str] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        sites.extend(f"{repo_relative(path)}:{expression.lineno}" for expression in _decision_expressions(tree))
    return sites


def test_no_erase_decision_reads_an_undeclared_term() -> None:
    """DISCRIMINATING: a new retention condition must not land at one site alone."""
    offenders = [
        f"{repo_relative(path)}:{line}: reads {terms}"
        for path in _production_modules()
        for line, terms in _undeclared_terms(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert not offenders, (
        "these erase decisions read a retention term this gate does not declare:\n  "
        + "\n  ".join(sorted(offenders))
        + "\n\nA condition governing whether legally retained records may be destroyed has "
        "to reach EVERY decision site, not the one being edited. Add the term here and "
        "apply it at each site below, deciding for each whether it belongs:\n  "
        + "\n  ".join(sorted(_decision_sites()))
    )


def test_the_decision_is_expressed_at_several_sites() -> None:
    """ANTI-VACUITY: a scan that found nothing would clear the tree for free.

    The gate's value is that a new term reaches an existing population. If the
    marker were renamed and the population dropped to zero, every assertion here
    would pass while nothing was checked.
    """
    sites = _decision_sites()

    assert len(sites) >= 4, f"expected the erase decision at several sites, found {sites}"
    assert any("_profile_delete.py" in site for site in sites), (
        "the delete verb's decision is no longer recognised; the marker or the verb moved"
    )


def test_the_detector_reports_a_widened_decision() -> None:
    """ANTI-TAUTOLOGY: proven on source carrying the shape, no tracked file touched."""
    assert _undeclared_terms(ast.parse(_WIDENED_SAMPLE)) == [(2, ["legal_hold_lifted"])]


def test_the_detector_accepts_the_declared_vocabulary() -> None:
    """The other direction: the shapes in the tree today must not be reported.

    The sites differ deliberately -- the delete verb admits no override -- and a
    detector that demanded identical expressions would fight that difference
    instead of guarding it.
    """
    assert _undeclared_terms(ast.parse(_DECLARED_SAMPLE)) == []
