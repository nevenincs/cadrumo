"""Real profile-backed coverage for M303 simplified-regime scope resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.modelo.m303_regimen_simplificado_scope import (
    active_taxpayer_profile,
    m303_regimen_simplificado_scope_for_composition,
    m303_regimen_simplificado_scope_for_profile,
)
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.period import Period
from cadrumo.domain.deadlines.models import M303RegimeComposition
from cadrumo.domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

from .....domain.calculations.registry.m303_schema_vocabulary import (
    m303_regime_composition_simplified_scope,
)
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_YEAR = filing_year_envelope().horizon
_REVISION_ID = str(open_ended_revision("303").id)

_BUCKET_ID = "e3030000-0000-4000-8000-000000000059"
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_CLOCK = datetime(_YEAR, 4, 1, tzinfo=UTC)


def _work_unit() -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=_PERIOD,
            revision_id=_REVISION_ID,
        ),
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=_PERIOD,
        revision_id=_REVISION_ID,
        name=f"303-{_YEAR}-1T",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _store_profile(*, composition: M303RegimeComposition) -> None:
    facts = persona_facts_beneath(
        (
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.m303_regime_composition", value=composition.value),
        )
    )
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=facts,
            created_at=_CLOCK,
            updated_at=_CLOCK,
            context=profile_creation_context_for_test(),
        )
    )


@pytest.mark.parametrize("composition_token", ("general", "simplified", "mixed"))
def test_secure_profile_composition_derives_the_closed_m303_scope(
    tmp_path: Path,
    composition_token: str,
) -> None:
    composition = M303RegimeComposition.from_registry(composition_token)
    # The authority compiles inside the test, not at collection.
    expected_scope: M303RegimenSimplificadoScope = m303_regime_composition_simplified_scope(
        composition_token, authority=published_authority_operation()
    )
    assert m303_regimen_simplificado_scope_for_composition(composition).scope == expected_scope

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _store_profile(composition=composition)

        decision = m303_regimen_simplificado_scope_for_profile(active_taxpayer_profile(_work_unit()))

    assert decision.scope == expected_scope
