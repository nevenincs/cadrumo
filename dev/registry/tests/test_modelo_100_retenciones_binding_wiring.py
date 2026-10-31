"""Wiring contract for the Modelo 100 withholding credit casillas 0596 and 0597.

The credit belongs to the perceptor. Casilla 0596 (retenciones del trabajo) is
therefore bound to the payee's own salary-certificate figure, and casilla 0597
(retenciones de capital mobiliario) is keyed by the declarant until a typed
per-payer evidence family carries it. Neither is fed by a withholding-agent
return the declarant files for other people.

Binding-to-casilla plumbing contract (not a formula derivation):
  - binding ``renta-certificado-trabajo-retenciones`` -> casilla 0596
  - casilla 0597 takes a keyed manual amount

The certificate binding is an operator-keyed source, so its value reaches the
engine the way every calculate path sends it: through
``resolve_available_bound_inputs_by_casilla_id``, which projects a binding value
onto the casilla the registry binds it to. Asserting 0596 == the certificate
amount is therefore not tautological: a casilla that lost its
``input_kind``/``binding`` pair would earn no projection and silently stay at
zero. The formula 0609 = sum of the credit operands gives the independent
confirmation that the wired value propagates, and 0610 gives the sign.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.tests import modelo_100_retenciones_binding_wiring_scenarios as scenarios

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture
def prior_edition_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """The prior edition at calculation grade: these tests assert wiring, never filing eligibility."""
    return registry_snapshot("100", scenarios.PRIOR_EDITION, "0A", grade=RegistryAuthorityGrade.CALCULATION)


@pytest.fixture
def reviewed_edition_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """The reviewed edition at calculation grade: these tests assert wiring, never filing eligibility."""
    return registry_snapshot("100", scenarios.REVIEWED_EDITION, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def test_salary_certificate_retenciones_binding_populates_prior_edition_casilla_0596(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_salary_certificate_retenciones_binding_populates_prior_edition_casilla_0596(prior_edition_snapshot)


def test_salary_certificate_retenciones_binding_populates_reviewed_edition_casilla_0596(
    reviewed_edition_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_salary_certificate_retenciones_binding_populates_reviewed_edition_casilla_0596(
        reviewed_edition_snapshot
    )


def test_zero_salary_certificate_retenciones_gives_zero_0596(prior_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_zero_salary_certificate_retenciones_gives_zero_0596(prior_edition_snapshot)


def test_keyed_capital_mobiliario_retenciones_reach_0609(prior_edition_snapshot: RegistrySnapshot) -> None:
    scenarios.check_keyed_capital_mobiliario_retenciones_reach_0609(prior_edition_snapshot)


def test_salary_certificate_retenciones_change_reflects_proportionally_in_0610(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_salary_certificate_retenciones_change_reflects_proportionally_in_0610(prior_edition_snapshot)


def test_conflicting_equivalent_binding_values_refuse_before_projection(
    prior_edition_snapshot: RegistrySnapshot,
) -> None:
    scenarios.check_conflicting_equivalent_binding_values_refuse_before_projection(prior_edition_snapshot)
