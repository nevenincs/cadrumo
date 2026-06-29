"""Shared setup for IVA wallet CLI inspector tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....core import Period
from ....domain.iva_compensation._carry_forward import IvaCompensationPeriodState

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_NIF = "12345678Z"
_GUIDANCE_PROFILE = "guidance-test"
_GUIDANCE_NIF = "87654321Y"


def _unwrap_envelope(payload: object) -> dict[str, object]:
    """Return the inner ``result`` payload from a CLI emit envelope."""
    if not isinstance(payload, dict):
        raise AssertionError(f"unexpected JSON shape: {type(payload).__name__}")
    if "result" not in payload or "schema_version" not in payload:
        raise AssertionError(f"missing CLI output envelope keys: {sorted(payload)}")
    result_obj = payload["result"]
    if isinstance(result_obj, dict):
        return cast(dict[str, object], result_obj)
    raise AssertionError(f"result field is not a dict: {type(result_obj).__name__}")


def _state(
    *,
    filing_year: int,
    period: str,
    generated: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        taxpayer_nif=_NIF,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        expediente_id=f"EXP-{filing_year}-{period}",
        status="filed",
        presented_at=datetime(filing_year + 1, 1, 20, 12, 0, tzinfo=UTC),
        prior_pending_amount=None,
        applied_amount=applied,
        pending_for_later_amount=None,
        period_result_amount=None,
        final_result_amount=None,
        generated_amount=generated,
        available_end_amount=generated,
        source_observation_key=f"303:{filing_year}:{period}:EXP",
    )


def _store_profile_with_nif(nif: str) -> None:
    """Persist a minimal UserProfileRecord carrying identity.tax_id."""
    from ....application.user_profile import UserProfileLifecycleRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord

    created_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id="seed-test").save(
        UserProfileRecord(
            profile_id="seed-test",
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value=nif),),
            created_at=created_at,
            updated_at=created_at,
        ),
    )


def _seed_full_autonomo_profile_for_guidance(bucket_id: str) -> None:
    """Persist a minimal autonomo profile sufficient for M303 work-unit applicability."""
    from ....application.user_profile import UserProfileLifecycleRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus

    created_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Test runtime profile",
            status=UserProfileStatus.ACTIVE,
            facts=(
                UserProfileFact(path="identity.name", value="Guidance Test Autonomo"),
                UserProfileFact(path="identity.surnames", value="Guidance Tester"),
                UserProfileFact(path="identity.tax_id", value=_GUIDANCE_NIF),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(
                    path="taxpayer_type.irpf_income_categories",
                    value="actividad_economica",
                ),
                UserProfileFact(path="censo.activity_start_date", value="2024-01-01"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
            created_at=created_at,
            updated_at=created_at,
        ),
    )
