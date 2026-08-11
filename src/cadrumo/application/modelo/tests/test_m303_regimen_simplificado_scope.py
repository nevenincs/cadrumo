"""Secure-profile resolution of the Modelo 303 simplified-regime scope."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....core import Period
from ....domain.deadlines import M303RegimeComposition
from ....domain.iva import M303RegimenSimplificadoScope
from ....domain.modelos import WorkUnit, derive_work_unit_id
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .._action_errors import ModeloProfileReadinessError
from .._m303_regimen_simplificado_scope import resolve_m303_regimen_simplificado_scope

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


def _store_profile(*, composition: M303RegimeComposition | None) -> None:
    facts = ()
    if composition is not None:
        facts = (
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value=composition.value),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="M303 scope profile",
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
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile(composition=composition)

        decision = resolve_m303_regimen_simplificado_scope(_work_unit())

    assert decision is not None
    assert decision.scope is expected_scope


def test_secure_profile_without_iva_composition_blocks_m303_scope_resolution(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile(composition=None)

        with pytest.raises(ModeloProfileReadinessError, match="complete IVA profile composition"):
            resolve_m303_regimen_simplificado_scope(_work_unit())
