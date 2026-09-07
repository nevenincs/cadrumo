"""Does a review identity NAME a surface, or is it only well-formed text?

The sibling inventory module proves that every concrete interface carries a
review identity, that the identity is slug-shaped, and that no two screens
claim one. Those are claims about the identity's FORM. This module is the
claim about what it REFERS to, and it is kept apart because it is the only
check here that leaves the process: the answer comes from the running
harness, which is the sole reading of the production surface registry a
package barred from importing the TUI can obtain.
"""

from __future__ import annotations

import pytest

from .. import _coverage, _harness

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _live_harness_surface_registry() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    """Ask the running harness which surfaces exist and what each one paints.

    Two subprocess calls into the production surface registry. This package
    is barred from importing the TUI at all, so the harness is not merely a
    convenient reading of that registry -- it is the only one available here,
    which is exactly what makes it an INDEPENDENT root rather than a second
    hand-written copy of the table under test.

    Workbench surfaces are named ``<surface-id>--<scenario>``; the scenario is
    a state of one surface, not a separate identity, so both readings are
    keyed on the identity before the separator.
    """
    drivable = frozenset(surface.name.partition("--")[0] for surface in _harness.surfaces())
    painted: dict[str, set[str]] = {}
    for name, qualnames in _harness.coverage().items():
        painted.setdefault(name.partition("--")[0], set()).update(qualnames)
    return drivable, {base: frozenset(qualnames) for base, qualnames in painted.items()}


def test_a_review_identity_resolves_to_the_surface_it_names() -> None:
    """A surface id must NAME something, not merely be unique and well formed.

    The three sibling gates above prove that every concrete interface HAS an
    id, that the id is slug-shaped, and that no two screens share one. All
    three range over the id's FORM. None of them reads the id against anything
    outside this package, so renaming ONE identity to another value that is
    still unique and still a slug leaves the whole module green: renaming
    ``ledger-evidence`` to ``ledger-evidence-review`` passed 52 of 52. The
    identity stops naming the screen a reviewer would open, and nothing says so.

    ``_coverage.check`` looks like it closes this for the covered five, but
    ``fixture_needed`` calls it with ``tuple(RENDERED_BY)`` -- the table's own
    keys -- so in this suite that assertion joins the table to itself and holds
    for any rename that moves both sides together. Renaming ``status`` to
    ``status-page`` in the classification AND in ``RENDERED_BY`` also passed 52
    of 52, against a harness that offers no such surface.

    Both joins below are keyed on the QUALNAME, never on the id, so neither can
    be satisfied by editing the identity being checked:

    - a COVERED id must be a surface the harness will actually drive;
    - where the registry declares which classes a surface paints, a class it
      names must not be classified under a DIFFERENT id.

    Contradiction, not coverage. An interface the registry says nothing about
    stays unconstrained rather than being exempted by name, because a list of
    exempt identities would be one more hand-maintained table and would make
    this gate a closed loop. That residue is real and sized. Of the 49 concrete
    identities, 27 are bound here -- 22 by declared interfaces and the covered 5
    by drivability. Of the remaining 22, eleven are declared only by the modelo
    fixture registry, which this package cannot read because the harness does
    not expose those surfaces yet, and eleven are declared nowhere at all. A
    rename inside that 22 is still invisible, and stays so until a surface
    exists to name.
    """
    drivable, painted = _live_harness_surface_registry()
    # Vacuity floor on the root itself: a harness that answered with an empty
    # or truncated registry would satisfy every claim below by having nothing
    # to contradict. Live: 29 drivable identities, 23 declaring interfaces.
    assert len(drivable) >= 20, (
        f"the harness offered only {len(drivable)} identities; the joins below range over almost nothing"
    )
    assert len(painted) >= 15, (
        f"only {len(painted)} harness surface(s) declare interfaces; the contradiction check is nearly vacuous"
    )

    concrete = {
        qualname: classification.surface_id
        for qualname, classification in _coverage.CLASSIFICATIONS.items()
        if classification.disposition
        in {_coverage.InventoryDisposition.COVERED, _coverage.InventoryDisposition.FIXTURE_NEEDED}
    }
    unreachable = sorted(
        f"{qualname} claims {classification.surface_id!r}"
        for qualname, classification in _coverage.CLASSIFICATIONS.items()
        if classification.disposition is _coverage.InventoryDisposition.COVERED
        and classification.surface_id not in drivable
    )
    assert unreachable == [], (
        "an interface is reported as covered by a surface the harness cannot "
        "drive, so the coverage claim names nothing: " + "; ".join(unreachable)
    )

    resolved = 0
    contradictions = []
    for base, qualnames in sorted(painted.items()):
        for qualname in sorted(qualnames):
            declared = concrete.get(qualname)
            if declared is None:
                continue
            if declared == base:
                resolved += 1
            else:
                contradictions.append(f"{qualname}: registry paints it under {base!r}, classified {declared!r}")
    # Vacuity floor on the join: the contradiction loop is a claim about
    # identities that actually met the registry, and it reads clean when none
    # did. Live: 22 of the 49 concrete identities resolve this way.
    assert resolved >= 18, (
        f"only {resolved} review identit(ies) met the surface registry, so the "
        "contradiction check below is bound to almost none of the census"
    )
    assert contradictions == [], (
        "a review identity disagrees with the registry about which surface "
        "paints the screen, so opening the named surface reviews a different "
        "screen than the classification claims: " + "; ".join(contradictions)
    )
