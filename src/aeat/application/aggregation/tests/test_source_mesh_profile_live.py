"""Source mesh coverage for profile-backed calculation sources."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    IVA_COMPENSATION_WALLET_URL,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ....core import Period
from ....core.resources import resources
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionSourceResolver, reconcile_iva_compensation_wallet
from ...modelo._profile_binding import resolve_profile_sourced_bindings
from ...user_profile import UserProfileLifecycleRepository
from .. import CalculationSourceContext, ProfileSourceResolver

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_PROFILE_ID = "10010010-0100-4100-8100-100100100100"
_BUCKET_ID = _PROFILE_ID
_CCAA_BINDING = "renta-2025-profile-tax-residence-ccaa"
_PROFILE_FINGERPRINT = "sha256:e43c88edad4d98897cc610aad74834a0ef1711f53a635269846e54069237b207"


@pytest.fixture
def secure_profile_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


def _modelo_100_snapshot():
    return resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_PROFILE_ID,
        display_name="Renta perfil Ñandú",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Ñ"),
            UserProfileFact(path="tax_residence.ccaa", value=ccaa),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _wallet(amount: Decimal) -> IvaCompensationWalletObservation:
    return IvaCompensationWalletObservation(
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        rows=(
            IvaCompensationWalletRow(
                generation_year=2026,
                generation_period=Period.from_year_and_code(2026, "1T"),
                generated_amount=amount,
                applied_amount=Decimal("0"),
                pending_amount=amount,
                raw_label="2026 1T",
            ),
        ),
        total_pending=amount,
        source_url=AnyHttpUrl(IVA_COMPENSATION_WALLET_URL),
        captured_at=_CLOCK,
        raw_sha256="a" * 64,
    )


def test_profile_source_resolver_matches_existing_profile_binding_resolution() -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("madrid")

    legacy = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=profile_record,
    )
    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=profile_record,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values == legacy.binding_values
    assert resolution.enum_binding_values == legacy.enum_binding_values
    assert resolution.source_transaction_ids == ()
    assert resolution.provenance
    assert {item.source_ref for item in resolution.provenance if item.source_kind == "profile"} == {
        f"profile:{_BUCKET_ID}:binding:{_CCAA_BINDING}",
    }
    assert {item.fingerprint for item in resolution.provenance if item.source_kind == "profile"} == {
        _PROFILE_FINGERPRINT,
    }


def test_profile_source_resolver_fingerprints_storage_loaded_profile(
    secure_profile_backend: None,
) -> None:
    snapshot = _modelo_100_snapshot()
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(_profile_with_ccaa("madrid"))

    resolution = ProfileSourceResolver(registry_snapshot=snapshot).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.enum_binding_values[_CCAA_BINDING] == "madrid"
    assert {item.fingerprint for item in resolution.provenance if item.source_kind == "profile"} == {
        _PROFILE_FINGERPRINT,
    }


def test_profile_source_resolver_respects_caller_owned_precedence() -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("cataluna")

    resolution = ProfileSourceResolver(
        registry_snapshot=snapshot,
        profile_record=profile_record,
        caller_binding_ids=(_CCAA_BINDING,),
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert _CCAA_BINDING not in resolution.binding_values
    assert _CCAA_BINDING not in resolution.enum_binding_values
    assert resolution.provenance == ()


def test_live_iva_wallet_source_resolution_carries_decision_fingerprint() -> None:
    decision = reconcile_iva_compensation_wallet(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "2T"),
        wallet=_wallet(Decimal("1200")),
        local_recurrence_amount=Decimal("1200"),
        decided_at=_CLOCK,
    )
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")

    resolution = IvaWalletDecisionSourceResolver(decision).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "2T"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200")}
    assert resolution.provenance
    assert all(item.fingerprint for item in resolution.provenance)
    assert {item.fingerprint for item in resolution.provenance} == {resolution.provenance[0].fingerprint}
