"""The RIRPF art. 95 activity axis: two members, and undeclared stays undeclared.

The axis exists because the retención rate turns on whether an activity is
profesional or sectorial, and nothing else on the profile establishes it: a
farmer may file estimación directa and sit in IVA general, so neither the
estimation regime nor the IVA regime is a proxy.

What these gates defend is the SHAPE rather than any rate arithmetic. The rate
selection itself is a legal determination the application deliberately does not
make, so there is no computed figure here to assert; what must hold is that the
axis stays two-membered, that an undeclared profile resolves to neither arm, and
that the value survives the projection.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from ...calculations.registry.activity_kind_catalogue import resolve_irpf_activity_kind_catalogue
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ..models import IrpfActivityKind, IrpfEstimationRegime, IVARegime, TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _authority_scope(operation: PinnedAuthorityOperation) -> Iterator[None]:
    with validating_governed_facts(operation):
        yield


def test_the_axis_carries_exactly_the_two_members_the_rate_table_can_consume(
    operation: PinnedAuthorityOperation,
) -> None:
    """Two members, because art. 95's seven provisions fix only four rates.

    Six of those seven sit in rate-identical pairs -- inicio and the colectivos
    específicos both at 7 %, agrícola/ganadera and forestal both at 2 %, engorde
    and estimación objetiva both at 1 % -- so the only distinction the rate table
    can act on is profesional (15/7) against sectorial (2/1).

    Pinned because a third member is the tempting change, and every candidate
    for one splits a pair that selects the same figure.
    """
    catalogue = resolve_irpf_activity_kind_catalogue(effective_date=date(2025, 1, 1), authority=operation)
    assert len(catalogue.all_activity_kinds) == 2


def test_an_undeclared_activity_kind_is_neither_arm() -> None:
    """Fail-closed: absence must not resolve to a rate arm.

    This is why the field is an optional enum rather than a boolean. A boolean
    would have to spend ``False`` on both "profesional" and "not yet asked", and
    the two arms differ by 15 % against 2 % -- so a consumer reading a defaulted
    value would silently pick a rate the taxpayer never declared.
    """
    profile = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime("GENERAL"))

    assert profile.irpf_activity_kind is None
    assert profile.irpf_activity_kind is not IrpfActivityKind.from_registry("profesional")
    assert profile.irpf_activity_kind is not IrpfActivityKind.from_registry("sectorial")


def test_a_declared_activity_kind_survives_the_projection(operation: PinnedAuthorityOperation) -> None:
    """The operator's declaration reaches the profile the calculation reads.

    Exercised through the production mapping->profile path rather than the raw
    projection helper, so the assertion covers the route a stored profile
    actually takes.
    """
    catalogue = resolve_irpf_activity_kind_catalogue(effective_date=date(2025, 1, 1), authority=operation)
    for declared in catalogue.all_activity_kinds:
        profile = taxpayer_profile_from_mapping(
            {"irpf.activity_kind": declared.value},
            tax_id_default="12345678Z",
        )

        assert profile.irpf_activity_kind is declared


def test_the_activity_axis_is_independent_of_the_estimation_regime() -> None:
    """The reason the axis had to be added rather than derived.

    A sectorial taxpayer in estimación directa is the case that defeats every
    proxy: the regime says directa, the activity is still sectorial, and the
    rate follows the activity. If this pairing were ever made unrepresentable,
    the axis would have collapsed back into the regime it exists to be
    independent of.
    """
    profile = TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime("GENERAL"),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_simplificada"),
        irpf_activity_kind=IrpfActivityKind.from_registry("sectorial"),
    )

    assert profile.irpf_estimation_regime is IrpfEstimationRegime.from_registry("directa_simplificada")
    assert profile.irpf_activity_kind is IrpfActivityKind.from_registry("sectorial")
