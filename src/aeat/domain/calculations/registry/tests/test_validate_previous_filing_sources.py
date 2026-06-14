"""Empty-span coverage for the Modelo 130 casilla-05 expanding-span carry.

Stage 2 flips casilla 05
to a bound ``prior_quarter_expanding_span`` previous_filing carry. The
observation-coverage validator (:func:`previous_filing_observation_requirements`)
must treat an EMPTY span as satisfied: a 1T target (or any first-obligation
quarter) has no same-ejercicio prior quarter, so the carry emits NO required
observation for the casilla-05 binding and a genuine first filer fires no
missing-observation blocker.

The gate reads the real committed registry - no mocks - so a regression that made
the expanding span emit a phantom prior-quarter requirement at 1T would fail here.
"""

from __future__ import annotations

import pytest

from .....core.resources import resources
from .._bindings_previous_filing import (
    RegistryModeloObservationRequirement,
    previous_filing_observation_requirements,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CARRY_BINDING_ID = "modelo-130-pagos-fraccionados-anteriores"
_FILING_YEAR = 2026


def _casilla_05_requirements(period: str) -> tuple[RegistryModeloObservationRequirement, ...]:
    snapshot = resources().modelos.authority.snapshot("130", filing_year=_FILING_YEAR, period=period)
    return tuple(
        requirement
        for requirement in previous_filing_observation_requirements(
            snapshot.revision,
            filing_year=_FILING_YEAR,
            period=period,
        )
        if _CARRY_BINDING_ID in requirement.binding_ids
    )


def test_empty_span_emits_no_casilla_05_requirement_at_first_quarter() -> None:
    """A 1T target emits no casilla-05 observation requirement (empty span satisfied)."""
    assert _casilla_05_requirements("1T") == ()


def test_second_quarter_requires_only_the_single_prior_quarter() -> None:
    """A 2T target requires exactly the 1T prior-quarter casilla-05 observation."""
    requirements = _casilla_05_requirements("2T")
    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.modelo == "130"
    assert requirement.filing_year == _FILING_YEAR
    assert requirement.period == "1T"
    # The carry reads both the positive-part (07) and minoración (16) source
    # casillas; the 1T requirement also bundles the casilla-15 carry's
    # saldo-negativo-fin-periodo because both bindings share the (130, 2026, 1T) key.
    assert {"07", "16"}.issubset(set(requirement.source_casillas))


def test_fourth_quarter_requires_every_prior_same_ejercicio_quarter() -> None:
    """A 4T target requires the 1T, 2T, and 3T prior-quarter casilla-05 observations."""
    requirements = _casilla_05_requirements("4T")
    required_periods = sorted(requirement.period for requirement in requirements)
    assert required_periods == ["1T", "2T", "3T"]
