"""Shared setup for IVA wallet CLI inspector tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from ....application.wizard import _catalogue as _wizard_catalogue
from ....application.wizard import _persistence as _wizard_persistence
from ....core import IvaCompensationStateProvenance, Period
from ....domain.iva_compensation import IvaCompensationPeriodState

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


def _unwrap_envelope(payload: object) -> dict[str, object]:
    """Return the inner ``result`` payload from a CLI emit envelope."""
    if not isinstance(payload, dict):
        raise AssertionError(f"unexpected JSON shape: {type(payload).__name__}")
    # ``isinstance(payload, dict)`` only proves *some* dict — this is always
    # parsed JSON envelope output, so re-keying with ``str(k)`` gives an
    # honestly-typed ``dict[str, object]`` rather than casting the bare dict.
    typed_payload = {str(k): v for k, v in payload.items()}
    if "result" not in typed_payload or "schema_version" not in typed_payload:
        raise AssertionError(f"missing CLI output envelope keys: {sorted(typed_payload)}")
    result_obj = typed_payload["result"]
    if isinstance(result_obj, dict):
        return {str(k): v for k, v in result_obj.items()}
    raise AssertionError(f"result field is not a dict: {type(result_obj).__name__}")


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
    from ....application.user_profile import ProfileRecordRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord

    created_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    ProfileRecordRepository(bucket_id=bucket_id).save(
        UserProfileRecord(
            profile_id=bucket_id,
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value=nif),),
            created_at=created_at,
            updated_at=created_at,
        ),
    )


def _seed_full_autonomo_profile_for_guidance(bucket_id: str) -> None:
    """Persist a minimal autonomo profile sufficient for M303 work-unit applicability."""
    from ....application.user_profile import ProfileRecordRepository
    from ....domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus

    created_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    ProfileRecordRepository(bucket_id=bucket_id).save(
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
    )
