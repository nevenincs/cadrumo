"""Real profile-backed coverage for M303 simplified-regime scope resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.m303_regimen_simplificado_scope import (
    active_taxpayer_profile,
    m303_regimen_simplificado_scope_for_composition,
    m303_regimen_simplificado_scope_for_profile,
)
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.iva_schema_vocabulary import m303_regime_composition_simplified_scope
from cadrumo.domain.deadlines.models import M303RegimeComposition
from cadrumo.domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

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
#: missing any of them cannot be COMPLETE, and this test needs a COMPLETE one.
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
            m303_regime_composition_simplified_scope("general", authority=compiled_bundled_authority()),
        ),
        (
            M303RegimeComposition.SIMPLIFIED,
            m303_regime_composition_simplified_scope("simplified", authority=compiled_bundled_authority()),
        ),
        (
            M303RegimeComposition.MIXED,
            m303_regime_composition_simplified_scope("mixed", authority=compiled_bundled_authority()),
        ),
    ),
)
def test_secure_profile_composition_derives_the_closed_m303_scope(
    tmp_path: Path,
    composition: M303RegimeComposition,
    expected_scope: M303RegimenSimplificadoScope,
) -> None:
    assert m303_regimen_simplificado_scope_for_composition(composition).scope == expected_scope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile(composition=composition)

        decision = m303_regimen_simplificado_scope_for_profile(active_taxpayer_profile(_work_unit()))

    assert decision.scope == expected_scope
