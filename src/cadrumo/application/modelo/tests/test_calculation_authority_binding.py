"""A calculated Modelo 202 summary stays on its caller's authority lease."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import IndexedRegistryAuthority, PinnedAuthorityOperation
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    create_user_profile_record,
)
from ..calculate_input import modelo_202_modality_for_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "f377f194-801d-47c2-986e-4f2137a457e4"


def test_modelo_202_summary_uses_supplied_operation_without_bundled_fallback(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corporate modality derives from a real record and pinned schema."""
    period = Period.from_year_and_code(2025, "1P")
    revision_id = operation.snapshot("202", filing_year=2025, period="1P").snapshot_ref.revision_id
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_PROFILE_ID, modelo="202", filing_year=2025, period=period, revision_id=revision_id
        ),
        bucket_id=_PROFILE_ID,
        modelo=ModeloCode("202"),
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name="202 first quarter",
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
        updated_at=datetime(2026, 1, 10, tzinfo=UTC),
    )
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345674"),
            UserProfileFact(path="identity.legal_name", value="Example SL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
        ),
        created_at=datetime(2026, 1, 10, tzinfo=UTC),
        updated_at=datetime(2026, 1, 10, tzinfo=UTC),
    )

    def unexpected_authority(_authority: IndexedRegistryAuthority) -> None:
        raise AssertionError("M202 modality opened another registry authority")

    monkeypatch.setattr(IndexedRegistryAuthority, "operation", unexpected_authority)
    summary = modelo_202_modality_for_record(work_unit, record, operation=operation)
    assert summary is not None
    assert summary.modality
