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

import pytest

from ..models import IrpfActivityKind, IrpfEstimationRegime, IVARegime, TaxpayerProfile
from ..profiles import taxpayer_profile_from_mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_axis_carries_exactly_the_two_members_the_rate_table_can_consume() -> None:
    """Two members, because art. 95's seven provisions fix only four rates.

    Six of those seven sit in rate-identical pairs -- inicio and the colectivos
    específicos both at 7 %, agrícola/ganadera and forestal both at 2 %, engorde
    and estimación objetiva both at 1 % -- so the only distinction the rate table
    can act on is profesional (15/7) against sectorial (2/1).

    Pinned because a third member is the tempting change, and every candidate
    for one splits a pair that selects the same figure.
    """
    assert {member.value for member in IrpfActivityKind} == {"profesional", "sectorial"}


def test_an_undeclared_activity_kind_is_neither_arm() -> None:
    """Fail-closed: absence must not resolve to a rate arm.

    This is why the field is an optional enum rather than a boolean. A boolean
    would have to spend ``False`` on both "profesional" and "not yet asked", and
    the two arms differ by 15 % against 2 % -- so a consumer reading a defaulted
    value would silently pick a rate the taxpayer never declared.
    """
    profile = TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)

    assert profile.irpf_activity_kind is None
    assert profile.irpf_activity_kind is not IrpfActivityKind.PROFESIONAL
    assert profile.irpf_activity_kind is not IrpfActivityKind.SECTORIAL


@pytest.mark.parametrize("declared", list(IrpfActivityKind))
def test_a_declared_activity_kind_survives_the_projection(declared: IrpfActivityKind) -> None:
    """The operator's declaration reaches the profile the calculation reads.

    Exercised through the production mapping->profile path rather than the raw
    projection helper, so the assertion covers the route a stored profile
    actually takes.
    """
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
        iva_regime=IVARegime.GENERAL,
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
        irpf_activity_kind=IrpfActivityKind.SECTORIAL,
    )

    assert profile.irpf_estimation_regime is IrpfEstimationRegime.DIRECTA_SIMPLIFICADA
    assert profile.irpf_activity_kind is IrpfActivityKind.SECTORIAL
