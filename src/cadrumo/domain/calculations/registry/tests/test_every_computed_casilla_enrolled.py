"""Completeness gate: every computed casilla is enrolled in a verification contract.

The verification contract reconciles a filed casilla value against the engine.
A computed casilla (``input_kind == "computed"``) that is enrolled in NEITHER a
coverage-gated ``computed_casilla_ids`` contract NOR the exhaustive
``reconcile_when_present_casilla_ids`` class is a silent verification hole: the
operator's relayed value for it is never reconciled. This gate asserts the hole
is closed across every modelo revision and stays closed - a newly-authored
computed casilla must be enrolled (coverage-gated if it is an always-present
final, reconcile-when-present otherwise) or this gate fails.

The reconcile-when-present class is excluded from the coverage denominator
(``RegistryVerificationPolicy``), so enrolling a situational casilla here can
never lower coverage and flip a legitimate filing's verdict - enrollment is
therefore always safe, which is what makes the exhaustive invariant tenable.
"""

from __future__ import annotations

import pytest

from .....tests.registry_tree import bundled_registry_tree
from ..schema_input_kind import InputKind

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


def test_every_computed_casilla_is_enrolled_in_a_verification_contract() -> None:
    modelos, _catalogues = bundled_registry_tree()
    holes: list[str] = []
    checked = 0
    for modelo in modelos:
        for revision in modelo.revisions.values():
            computed = {c.id for c in revision.casillas if c.input_kind == InputKind.COMPUTED}
            if not computed:
                continue
            enrolled: set[str] = set()
            for expectation in revision.verification_expectations:
                enrolled |= set(expectation.computed_casilla_ids)
                enrolled |= set(expectation.reconcile_when_present_casilla_ids)
            missing = sorted(computed - enrolled)
            checked += len(computed)
            if missing:
                holes.append(f"{modelo.id} {revision.id}: {len(missing)} unenrolled: {missing[:8]}")
    assert checked, "no computed casillas were checked"
    assert not holes, "computed casillas unenrolled in any verification contract:\n" + "\n".join(holes)
