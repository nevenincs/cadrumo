"""Pure application policy tests for the Modelo 303 simplified-regime scope."""

from __future__ import annotations

import pytest

from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ..action_errors import ModeloProfileReadinessError
from ..m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_scope_for_composition,
    m303_regimen_simplificado_scope_for_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_profile_projection_without_an_iva_block_blocks_m303_scope_resolution() -> None:
    """The refusal is a backstop against a projection the schema cannot produce.

    This seeded a capsule record with no IVA composition and drove the whole
    resolver, which cannot reach the branch: ``iva.regime`` is schema-required,
    and the schema requires ``iva.m303_regime_composition`` "when any IVA
    profile fact claims the IVA block", so EVERY complete profile carries one. A
    record without it is not COMPLETE, and the resolver refuses an incomplete
    profile with ``profile_inactive`` before it ever reads the composition --
    which is the refusal that test actually asserted against.

    So the branch is exercised where it can be: on the projection itself, with
    no IVA block at all. That is the state it defends against -- a projection
    reaching the scope resolver without the block the schema guarantees -- and
    it is reached the same way the sibling composition test reaches its own
    refusal, by calling the function under test directly.
    """
    with pytest.raises(ModeloProfileReadinessError) as raised_1:
        m303_regimen_simplificado_scope_for_profile(
            TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL, iva=None),
        )

    failure_1 = raised_1.value.precondition_failure
    assert failure_1 is not None, "the refusal must carry its declared precondition failure"
    assert failure_1.scenario_id == "modelo.work.calculate.m303_profile_readiness.iva_composition_missing"


def test_raw_unknown_composition_is_refused() -> None:
    raw_composition = "unrecognised"

    with pytest.raises(ModeloProfileReadinessError) as raised_2:
        m303_regimen_simplificado_scope_for_composition(raw_composition)

    failure_2 = raised_2.value.precondition_failure
    assert failure_2 is not None, "the refusal must carry its declared precondition failure"
    assert failure_2.scenario_id == "modelo.work.calculate.m303_profile_readiness.iva_composition_unknown"


def test_profile_without_iva_is_refused_by_the_profile_mapper() -> None:
    profile = TaxpayerProfile(tax_id="00000000T", iva_regime=IVARegime.GENERAL)

    with pytest.raises(ModeloProfileReadinessError) as raised_3:
        m303_regimen_simplificado_scope_for_profile(profile)

    failure_3 = raised_3.value.precondition_failure
    assert failure_3 is not None, "the refusal must carry its declared precondition failure"
    assert failure_3.scenario_id == "modelo.work.calculate.m303_profile_readiness.iva_composition_missing"
