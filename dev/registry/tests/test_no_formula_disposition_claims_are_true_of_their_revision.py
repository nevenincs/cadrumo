"""A disposition excusing a family "because this revision computes nothing" must be right.

A family disposition is the only record of why a schema family that could have
carried content carries none, and several of them are excused on the strength of
the revision computing nothing at all: a parameter feeds a formula, a
verification predicate guards a calculated result, a verification expectation
reconciles an engine value. Where the revision genuinely declares no formula,
each of those families is empty by construction.

THE DISTINCTION THIS GATE IS BUILT ON, and the wrong version it replaced. A
first attempt matched any disposition claiming the revision "applies none", and
flagged six -- modelos 190, 193, 216 and 322 -- as excusing a family while
declaring formulas. Every one was a FALSE POSITIVE. Those reasons make a
different and legitimate claim: not that the revision has no formula, but that
none of its formulas applies a REGULATORY VALUE. Modelo 216 says so in its own
words -- "all six of its formulas are pure aggregation" -- and measures them.
A modelo may compute plenty and still need no parameter.

So the gate matches only the strictly stronger claim: that the revision declares
no formula, or calculates none. That assertion is checkable against the revision
itself, and a reason making it while formulas sit beside it is simply false.
Measured over the tree: six dispositions make the strong claim and none of them
is wrong.

Deliberately NOT matched: "computes no taxpayer liability of its own", which
sits on the informativa dispositions. An informativa may carry aggregation
formulas and still compute no liability, so reading that sentence as a claim
about formula count would assert more than it says and would red the day one of
those modelos gains a legitimate total.
"""

from __future__ import annotations

import pytest

from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Phrases that assert the REVISION ITSELF derives nothing. Each is a statement
#: about formula count, unlike "applies none", which is about regulatory values.
_COMPUTES_NOTHING = ("declares no formula", "no formula at all", "calculates none")

#: The modelo whose dispositions anchor this gate against a real claim rather
#: than an empty match set. Modelo 840's IAE declaration carries census facts and
#: the administration liquidates from the matrícula (TRLRHL art. 90).
_ANCHOR_MODELO = "840"


def _claims() -> list[tuple[str, str, str, int]]:
    """Return ``(modelo, revision, family, formula count)`` for every strong claim."""
    modelos, _catalogues = _committed_registry_tree()
    found: list[tuple[str, str, str, int]] = []
    for modelo in modelos:
        for revision_id, revision in modelo.revisions.items():
            for family, disposition in revision.family_dispositions.items():
                reason = (disposition.reason or "").lower()
                if any(phrase in reason for phrase in _COMPUTES_NOTHING):
                    found.append((modelo.id, revision_id, family, len(revision.formulas)))
    return found


def test_a_revision_excused_for_computing_nothing_declares_no_formula() -> None:
    claims = _claims()
    assert claims, (
        "no disposition claims its revision computes nothing, so this gate measures "
        "nothing; re-anchor it on the wording that replaced the claim"
    )

    contradicted = [entry for entry in claims if entry[3]]
    assert not contradicted, (
        "these dispositions excuse a family because the revision computes nothing, while "
        f"the revision declares formulas: {contradicted}"
    )


def test_the_anchor_modelo_still_makes_the_claim() -> None:
    """The gate is proven by a real disposition, not by an empty match.

    If modelo 840 stops making the claim -- because it gained a formula, or its
    reasons were reworded -- this says so instead of letting the sibling pass on
    a shrinking population.
    """
    claiming = {(modelo_id, family) for modelo_id, _revision, family, _n in _claims()}
    families = {family for modelo_id, family in claiming if modelo_id == _ANCHOR_MODELO}

    assert families, (
        f"modelo {_ANCHOR_MODELO} no longer excuses any family for computing nothing; "
        "re-anchor this gate on another modelo that does"
    )
    # The families whose whole justification is the absence of a derived value.
    assert {"parameters", "verification_predicates"} <= families, sorted(families)


def test_the_anchor_modelo_really_derives_nothing() -> None:
    """The claim has to be TRUE of the anchor, or the gate anchors on a falsehood.

    Read from the revision rather than from its own prose: no formula, and the
    formulas family itself disposed rather than merely empty.
    """
    modelos, _catalogues = _committed_registry_tree()
    modelo = next(m for m in modelos if m.id == _ANCHOR_MODELO)
    revision = modelo.revisions["2003-y-siguientes"]

    assert not revision.formulas, "the anchor modelo now declares formulas; its claims need re-reading"
    assert "formulas" in revision.family_dispositions, (
        "the anchor's formulas family is empty but undeclared, so the dispositions that "
        "lean on it are resting on an absence rather than on a stated disposition"
    )
