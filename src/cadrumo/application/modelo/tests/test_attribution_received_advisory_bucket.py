"""Inward policy coverage for the attribution-received advisory profile branch.

The persistence-backed profile loading seam belongs to the profile adapter tests.
These cases keep the advisory policy inward by supplying explicit profile facts,
so application tests do not reach a private persistence implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.tests.profile_schema_support import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._attribution_received_advisory import _attribution_received_omission_advisory_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "20000000-0000-4000-8000-000000000184"
_CLOCK = datetime(2026, 7, 9, tzinfo=UTC)
_FILING_YEAR = 2024


def _work_unit() -> WorkUnit:
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    revision_id = "r" + "0" * 63
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET,
            modelo=ModeloCode(Modelo("100").value),
            filing_year=_FILING_YEAR,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode(Modelo("100").value),
        filing_year=_FILING_YEAR,
        period=period,
        revision_id=revision_id,
        name="100-2024",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _received_facts() -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="attribution_received.0.entity_nif", value="B12345678"),
        UserProfileFact(path="attribution_received.0.entity_name", value="Sociedad Civil Ejemplo"),
        UserProfileFact(path="attribution_received.0.share_pct", value=Decimal("50")),
        UserProfileFact(path="attribution_received.0.base_imponible_attributed", value=Decimal("58100.00")),
        UserProfileFact(path="attribution_received.0.filing_year", value=str(_FILING_YEAR)),
    )


def _profile_record(*facts: UserProfileFact) -> UserProfileRecord:
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=facts,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )


def test_advisory_reads_attribution_facts_from_profile_record() -> None:
    snapshot = compiled_bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A")
    findings = _attribution_received_omission_advisory_findings(
        work_unit=_work_unit(),
        snapshot=snapshot,
        casilla_values={},
        profile_record=_profile_record(*_received_facts()),
    )

    assert len(findings) == 1
    assert findings[0].message_facts["total_base"] == Decimal("58100.00")


def test_advisory_with_no_received_profile_facts_returns_no_finding() -> None:
    snapshot = compiled_bundled_authority().snapshot("100", filing_year=_FILING_YEAR, period="0A")
    findings = _attribution_received_omission_advisory_findings(
        work_unit=_work_unit(),
        snapshot=snapshot,
        casilla_values={},
        profile_record=_profile_record(),
    )

    assert findings == ()
