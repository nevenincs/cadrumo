"""Secure-profile resolution of the Modelo 303 simplified-regime scope."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.deadlines.models import IVARegime, M303RegimeComposition, TaxpayerProfile
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ..action_errors import ModeloProfileReadinessError
from ..m303_regimen_simplificado_scope import (
    m303_regimen_simplificado_scope_for_composition,
    m303_regimen_simplificado_scope_for_profile,
    resolve_m303_regimen_simplificado_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "e3030000-0000-4000-8000-000000000059"
_PERIOD = Period.from_year_and_code(2026, "1T")
_CLOCK = datetime(2026, 4, 1, tzinfo=UTC)


def _work_unit() -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=_PERIOD,
            revision_id="2026-y-siguientes",
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        revision_id="2026-y-siguientes",
        name="303-2026-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


#: The three facts the profile schema requires of every record. A profile
#: missing any of them cannot be COMPLETE, and these tests need a COMPLETE one:
#: the scope resolver refuses an incomplete profile with ``profile_inactive``
#: before it ever reads the IVA composition, so seeding without the baseline
#: made every case here refuse for the wrong reason -- including the one whose
#: whole subject is an absent composition on an otherwise ready profile.
_SCHEMA_REQUIRED_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
)


def _store_profile(*, composition: M303RegimeComposition) -> None:
    facts = (
        *_SCHEMA_REQUIRED_FACTS,
        UserProfileFact(path="iva.m303_regime_composition", value=composition.value),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    )
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=facts,
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )
    )


@pytest.mark.parametrize(
    ("composition", "expected_scope"),
    (
        (
            M303RegimeComposition.GENERAL,
            M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
        ),
        (
            M303RegimeComposition.SIMPLIFIED,
            M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
        ),
        (
            M303RegimeComposition.MIXED,
            M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_EVIDENCE_REQUIRED,
        ),
    ),
)
def test_secure_profile_composition_derives_the_closed_m303_scope(
    tmp_path: Path,
    composition: M303RegimeComposition,
    expected_scope: M303RegimenSimplificadoScope,
) -> None:
    assert m303_regimen_simplificado_scope_for_composition(composition).scope is expected_scope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile(composition=composition)

        decision = resolve_m303_regimen_simplificado_scope(_work_unit())

    assert decision is not None
    assert decision.scope is expected_scope


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
