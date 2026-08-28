"""The one spelling of "does this prorrata regime apportion the deducible cuotas".

Prorrata governs what fraction of input IVA a taxpayer may deduct, so two
surfaces disagreeing about whether a register entry apportions would change the
same taxpayer's deduction according to which one asked. The question is
therefore asked in exactly one place,
:func:`~core.regime_apportions_deduction`, and these tests bind both its answer
and the enum membership that answer depends on.
"""

from __future__ import annotations

import pytest

from .. import ProrrataRegisterRegime, regime_apportions_deduction

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_general_and_especial_apportion() -> None:
    """Both rationing regimes ration: LIVA art. 104 and art. 106."""
    assert regime_apportions_deduction(ProrrataRegisterRegime.GENERAL)
    assert regime_apportions_deduction(ProrrataRegisterRegime.ESPECIAL)


def test_ninguna_does_not_apportion() -> None:
    """``NINGUNA`` leaves the LIVA art. 94 full-deduction default standing.

    The negative case is the load-bearing one: were it to answer ``True``, every
    call site would go looking for a provisional percentage that no entry
    records, and the taxpayer's deduction would silently follow whatever the
    unresolved path falls back to.
    """
    assert not regime_apportions_deduction(ProrrataRegisterRegime.NINGUNA)


def test_every_regime_is_ruled_on() -> None:
    """No enum member may be left without an answer.

    The predicate states its apportioning set rather than deriving it as "not
    ``NINGUNA``", so a newly added regime would default to non-apportioning --
    which is the over-deduction direction. This test makes that silent default
    impossible: adding a member reds it until someone rules on which side the
    new regime falls.
    """
    assert {member.name for member in ProrrataRegisterRegime} == {"GENERAL", "ESPECIAL", "NINGUNA"}


def test_the_apportioning_set_is_exactly_the_non_ninguna_members() -> None:
    """Pins the equivalence the three former spellings silently relied on.

    ``regime not in (GENERAL, ESPECIAL)`` and ``regime is not NINGUNA`` were
    both in the tree and agree only while the enum has exactly these three
    members. This asserts that equivalence explicitly, so it is a checked
    property rather than a coincidence nobody wrote down.
    """
    apportioning = {member for member in ProrrataRegisterRegime if regime_apportions_deduction(member)}
    non_ninguna = {member for member in ProrrataRegisterRegime if member is not ProrrataRegisterRegime.NINGUNA}

    assert apportioning == non_ninguna
