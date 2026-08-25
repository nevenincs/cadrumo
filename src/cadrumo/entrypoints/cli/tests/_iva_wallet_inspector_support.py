"""Shared setup for IVA wallet CLI inspector tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....core import IvaCompensationStateProvenance, Period
from ....domain.iva_compensation import IvaCompensationPeriodState
from ....domain.user_profile.values import ProfileSetupState

_WIZARD_REGISTRATION_MODULES = (_wizard_catalogue, _wizard_persistence)
_NIF = "12345678Z"
#: Guidance-test bucket id, used as both the active bucket and the stored
#: ``profile_id`` (a bucket holds one live profile keyed by its own id).
#: ``UserProfileRecord.profile_id`` requires a UUIDv4, so this is a UUID.
_GUIDANCE_PROFILE = "33333333-3333-4333-8333-333333333333"
_GUIDANCE_NIF = "87654321X"
#: Check letter verified against the standard NIF algorithm
#: (letters = "TRWAGMYFPDXBNJZSQVHLCKE"[87654321 % 23]); "Y" was a typo that
#: only started failing once NIF checksum validation began enforcing it.
#: Bucket id used by the seed/correct/override CLI tests. A bucket holds
#: exactly one live profile keyed by its own id, so the stored profile's
#: ``profile_id`` MUST equal the active bucket id for the verb's
#: active-bucket NIF resolver (``taxpayer_nif_for_bucket`` -> ``.load(bucket_id)``)
#: to find it. ``UserProfileRecord.profile_id`` requires a UUIDv4, so the
#: bucket id is a UUID rather than a free-form label.
_SEED_BUCKET_ID = "21212121-2121-4121-8121-212121212121"


def _state(
    *,
    filing_year: int,
    period: str,
    generated: Decimal = Decimal("0.00"),
    applied: Decimal = Decimal("0.00"),
) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        provenance=IvaCompensationStateProvenance.APP_FILING,
        taxpayer_nif=_NIF,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
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


def _store_profile_with_nif(nif: str, *, bucket_id: str = _SEED_BUCKET_ID) -> None:
    """Persist a minimal UserProfileRecord carrying identity.tax_id.

    The record's ``profile_id`` equals ``bucket_id`` because a bucket holds
    exactly one live profile keyed by its own id; that is the invariant the
    verb's active-bucket NIF resolver relies on. ``bucket_id`` must therefore
    be the same UUIDv4 the paired :func:`isolated_runtime_profile` activates.
    """
    from ....domain.user_profile.values import UserProfileFact, UserProfileRecord
    from ....tests.profile_capsule import seed_test_profile_record

    created_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(UserProfileFact(path="identity.tax_id", value=nif),),
            created_at=created_at,
            updated_at=created_at,
        ),
        label="Test runtime profile",
    )


def _seed_full_autonomo_profile_for_guidance(bucket_id: str) -> None:
    """Persist a minimal autonomo profile sufficient for M303 work-unit applicability."""
    from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
    from ....tests.profile_capsule import seed_test_profile_record

    created_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    seed_test_profile_record(
        UserProfileRecord(
            profile_id=bucket_id,
            setup_state=ProfileSetupState.COMPLETE,
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
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="provenance.source", value="manual_cli"),
            ),
            created_at=created_at,
            updated_at=created_at,
        ),
        label="Guidance Test Autonomo",
    )
