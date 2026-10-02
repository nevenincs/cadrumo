"""An electric-vehicle claim under the accelerated LIS DA 18 regime refuses through the live command tree.

The Manual practico de Renta 2023 (capitulo 7, "Amortizacion acelerada de
determinados vehiculos y de nuevas infraestructuras de recarga") gives LIS DA 18
for that exercise as depreciation at twice the maximum linear coefficient; the
2024 manual gives it as free depreciation ("Libertad de amortizacion en
determinados vehiculos"). The product computes only the free regime, so the
2023 forecast refuses with its own registered code and the catalogue message
in each supported language, while a vehicle entering service in 2024 is still
charged its elected free amount. Both assets are registered with
``aeat app ledger actividad-asset create`` and forecast against the published
authority.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_cli_runtime_profile
from ....core.errors.error_codes import ErrorCategory, get_error_exit_code
from ....core.i18n.render import tr
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from ....domain.renta.actividad_asset.vehicle_affectation import (
    ElectricPropulsion,
    VehicleAffectation,
    VehicleCategory,
    VehiclePrivateUse,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from ....tests.cli_envelope import unwrap_schema_envelope
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "00000000-0000-4000-8000-000000000618"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_BASIS = Decimal("30000.00")
_ACCELERATED_CODE = "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED"
_ACCELERATED_MESSAGE_KEY = "errors.refused.refused_actividad_asset_accelerated_da18_depreciation_not_computed"
_LANGUAGES = ("en", "es", "ca", "hu")


def _seed_direct_normal_profile(root: Path) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Autonoma"),
                UserProfileFact(path="identity.surnames", value="Sintetica"),
                UserProfileFact(path="activities.description", value="reparto sintetico"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_taxpayer.sex", value="M"),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
        root=root,
        label="accelerated electric mobility",
    )


def _electric_van(asset_id: str, in_service: date) -> str:
    """Return the create-command JSON of a new battery-electric van used only for the activity."""
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="a" * 64,
            invoice_evidence_id=f"factura-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=_BASIS,
            prior_allocation_provenance="furgoneta afecta al 100% a la actividad",
        ),
        residual_value=Decimal("0"),
        in_service_date=in_service,
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.ELECTRIC_VEHICLE_FREE,
            authority_class_key="transporte-externo",
        ),
        vehicle_affectation=VehicleAffectation(
            category=VehicleCategory.OTHER_VEHICLE,
            private_use=VehiclePrivateUse.NONE,
            recorded_in_activity_books=True,
            evidence_reference="libro-registro-bienes-inversion",
            electric_propulsion=ElectricPropulsion.BEV,
        ),
    ).model_dump_json()


def _forecast(asset_id: str, year: int, *, language: str = "es") -> Result:
    return invoke_cached_cli(
        [
            *("--format", "json", "--language", language),
            *("app", "ledger", "actividad-asset", "forecast", asset_id),
            *("--covered-from", date(year, 1, 1).isoformat(), "--covered-until", date(year + 1, 1, 1).isoformat()),
            *("--free-depreciation-amount", str(_BASIS)),
        ],
    )


def test_an_electric_vehicle_under_the_accelerated_regime_refuses_in_every_language(tmp_path: Path) -> None:
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="accelerated da18") as profile:
        _seed_direct_normal_profile(profile.storage_root)
        for asset_id, in_service in (("van-2023", date(2023, 3, 1)), ("van-2024", date(2024, 3, 1))):
            created = invoke_cached_cli(
                ["--format", "json", "app", "ledger", "actividad-asset", "create", _electric_van(asset_id, in_service)],
            )
            assert created.exit_code == 0, created.output
        refusals = {language: _forecast("van-2023", 2023, language=language) for language in _LANGUAGES}
        admitted = _forecast("van-2024", 2024)

    messages: set[str] = set()
    for language, refused in refusals.items():
        assert refused.exit_code == get_error_exit_code(ErrorCategory.REFUSED), refused.output
        error = json.loads(refused.output)["error"]
        assert error["code"] == _ACCELERATED_CODE, error
        assert error["message"] == tr(_ACCELERATED_MESSAGE_KEY, locale=language)
        assert error["context"]["legal_reference"] == "ley-27-2014:da-18"
        assert error["context"]["tax_year"] == "2023"
        assert error["context"]["asset_id"] == "van-2023"
        messages.add(error["message"])
    # Each supported language renders its own translation, not a shared fallback text.
    assert len(messages) == len(_LANGUAGES)

    assert admitted.exit_code == 0, admitted.output
    forecast = unwrap_schema_envelope(admitted.output)
    assert isinstance(forecast, dict)
    assert forecast["method"] == AmortizationMethod.ELECTRIC_VEHICLE_FREE.value
    assert Decimal(str(forecast["amount"])) == _BASIS
