"""The agreement threshold for a casilla reconcile belongs to the registry, not the code.

How close two casilla values must be before they count as agreeing is a
regulatory question, versioned by filing year and revision. The registry
publishes it per verification expectation and folds the STRICTEST across a
revision's expectations. A reconcile that carries its own constant instead is
wrong for every revision whose published value differs from that constant — and
wrong in the silent direction, because too generous a threshold absorbs a
divergence rather than surfacing one.

These tests are written over two real bundled modelos chosen because they
disagree, which is what makes them able to fail. Modelo 303 publishes
expectations at both ``0.00`` and ``0.01``, so the strictest-wins fold resolves
it to EXACT equality; modelo 131 publishes ``0.01`` on every expectation and
resolves to one cent. A hardcoded constant cannot satisfy both assertions at
once, so the pair pins "the value is read from the registry" rather than merely
"the value is currently right".

The behavioural case is the one that matters: one and the same one-cent delta
must surface as a mismatch under the first modelo's published tolerance and stay
silent under the second's. Nothing in these tests computes a money figure, so
none of them can be satisfied by re-deriving the formula under test.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from ....core.resources import resources
from .._reconcile_casilla import (
    CasillaDivergenceKind,
    detect_casilla_divergences,
)

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FILING_YEAR = 2026
_PERIOD = "1T"

#: Publishes verification expectations at BOTH ``0.00`` and ``0.01``; the policy
#: fold takes the strictest, so this modelo reconciles on exact equality.
_EXACT_MODELO = "303"

#: Publishes ``0.01`` on every expectation, so this modelo tolerates one cent.
_CENT_MODELO = "131"

_CASILLA = "01"
_COMPUTED = Decimal("1000.00")
#: Exactly one cent above the computed value: inside modelo 131's published
#: tolerance and outside modelo 303's. The whole point is that one delta gets
#: two different verdicts, decided by registry data alone.
_FILED_ONE_CENT_HIGH = Decimal("1000.01")


def _snapshot(modelo_id: str) -> RegistrySnapshot:
    """Resolve a real bundled snapshot through the registry authority."""
    return resources().modelos.authority.snapshot(modelo_id, filing_year=_FILING_YEAR, period=_PERIOD)


def _published_tolerance(modelo_id: str) -> Decimal:
    """Return the tolerance the registry publishes for this modelo's revision.

    Deliberately reads the authority directly rather than any one consumer's
    helper: what these tests pin is the CONTRACT that the threshold comes from
    the registry, which every reconcile consumer must honour. Binding them to a
    single private helper would make the guard follow that helper around instead
    of guarding the rule.
    """
    return _snapshot(modelo_id).verification_policy().tolerance


def test_resolved_tolerance_differs_between_two_real_modelos() -> None:
    """The threshold tracks the registry, so two modelos must not share one answer.

    A constant — whether one cent or exact — would fail one of these three
    assertions. That is the property being pinned; the individual values are
    only how it is observed.
    """
    exact = _published_tolerance(_EXACT_MODELO)
    cent = _published_tolerance(_CENT_MODELO)

    assert exact == Decimal("0.00")
    assert cent == Decimal("0.01")
    assert exact != cent


def test_strictest_expectation_wins_when_a_modelo_publishes_several() -> None:
    """The fold is a minimum, not a first- or last-one-wins pick.

    Read off the loaded snapshot rather than the authoring files, so this
    asserts what the runtime actually resolved.
    """
    snapshot = _snapshot(_EXACT_MODELO)
    published = {expectation.tolerance for expectation in snapshot.verification_expectations.values()}

    assert len(published) > 1, "this modelo must publish differing tolerances or the fold is untested"
    assert snapshot.verification_policy().tolerance == min(published)


def test_one_cent_divergence_surfaces_under_an_exact_tolerance_modelo() -> None:
    """The defect this pins: a one-cent delta must not be silently absorbed.

    Modelo 303 publishes exact equality. Reconciling it under a hardcoded cent
    granted agreement here and reported nothing, which is a silent one-cent
    under-declaration per casilla on the most-filed modelo in the system.
    """
    divergences = detect_casilla_divergences(
        computed={_CASILLA: _COMPUTED},
        filed={_CASILLA: _FILED_ONE_CENT_HIGH},
        tolerance=_published_tolerance(_EXACT_MODELO),
    )

    assert [row.casilla_id for row in divergences] == [_CASILLA]
    assert divergences[0].kind is CasillaDivergenceKind.VALUE_MISMATCH
    assert divergences[0].delta == Decimal("0.01")


def test_the_same_delta_stays_silent_under_a_cent_tolerance_modelo() -> None:
    """The other direction, so the test above is not passing for a trivial reason.

    Without this the suite could not distinguish "the tolerance is honoured"
    from "every delta is reported regardless of tolerance".
    """
    divergences = detect_casilla_divergences(
        computed={_CASILLA: _COMPUTED},
        filed={_CASILLA: _FILED_ONE_CENT_HIGH},
        tolerance=_published_tolerance(_CENT_MODELO),
    )

    assert divergences == ()


def test_the_comparison_default_is_exact_rather_than_a_cent() -> None:
    """A caller that omits the tolerance gets the strictest reading, never a looser one.

    The default cannot consult the registry, so the only safe value is the one
    that absorbs nothing. A permissive default is the shape that let a caller
    skip the authority and still look correct.
    """
    divergences = detect_casilla_divergences(
        computed={_CASILLA: _COMPUTED},
        filed={_CASILLA: _FILED_ONE_CENT_HIGH},
    )

    assert [row.casilla_id for row in divergences] == [_CASILLA]
    assert divergences[0].kind is CasillaDivergenceKind.VALUE_MISMATCH
