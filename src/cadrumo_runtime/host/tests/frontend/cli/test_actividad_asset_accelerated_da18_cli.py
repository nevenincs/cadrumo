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

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.errors.error_codes import ErrorCategory, get_error_exit_code
from cadrumo.core.i18n.render import tr
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, manual_editions_printing
from cadrumo.domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
)
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionLineageReference,
    AcquisitionShape,
    ActivityAssetBasis,
    ActivityAssetRevision,
    AssetBasisStage,
    AssetKind,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.renta.actividad_asset.vehicle_affectation import (
    ElectricPropulsion,
    VehicleAffectation,
    VehicleCategory,
    VehiclePrivateUse,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from .cli_runner import invoke_cached_cli
from .runtime_profile_backend import runtime_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_T0 = datetime(1980, 2, 1, 9, 0, tzinfo=UTC)
BASIS = Decimal("30000.00")
_ACCELERATED_CODE = "REFUSED_ACTIVIDAD_ASSET_ACCELERATED_DA18_DEPRECIATION_NOT_COMPUTED"
_ACCELERATED_MESSAGE_KEY = "errors.refused.refused_actividad_asset_accelerated_da18_depreciation_not_computed"
LANGUAGES = ("en", "es", "ca", "hu")

_ACCELERATED_REGIME_HEADING = "amortizacion acelerada de determinados vehiculos"
_FREE_REGIME_HEADING = "libertad de amortizacion en determinados vehiculos"
#: The exercise whose bundled manual edition gives LIS DA 18 as accelerated
#: depreciation and not as free depreciation, and the first exercise whose edition
#: gives it as free depreciation.
_ACCELERATED_EXERCISE = max(
    set(manual_editions_printing("renta", _ACCELERATED_REGIME_HEADING))
    - set(manual_editions_printing("renta", _FREE_REGIME_HEADING))
)
_FREE_EXERCISE = min(manual_editions_printing("renta", _FREE_REGIME_HEADING))
_ACCELERATED_ASSET = f"van-{_ACCELERATED_EXERCISE}"
_FREE_ASSET = f"van-{_FREE_EXERCISE}"


def seed_direct_normal_profile(root: Path, profile_id: str, *, residence: str = "madrid") -> None:
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile_id,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Autonoma"),
                    UserProfileFact(path="identity.surnames", value="Sintetica"),
                    UserProfileFact(path="activities.description", value="reparto sintetico"),
                    UserProfileFact(path="tax_residence.ccaa", value=residence),
                    UserProfileFact(
                        path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                        value=False,
                    ),
                    UserProfileFact(path="censo.activity_start_date", value=date(filing_year_envelope().floor, 1, 1)),
                    UserProfileFact(path="renta_filing.declaration_type", value="1"),
                    UserProfileFact(path="renta_taxpayer.sex", value="M"),
                    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                    UserProfileFact(path="withholding.colegio_concertado", value=False),
                )
            ),
            created_at=_T0,
            updated_at=_T0,
            context=leased_profile_create_context(),
        ),
        root=root,
        label="accelerated electric mobility",
    )


def van_payment(asset_id: str, in_service: date) -> str:
    """Record the bank payment of the van, 30,000.00 base plus 6,300.00 IVA, and return its ledger id."""
    invoked = invoke_cached_cli(
        [
            *("--format", "json", "app", "ledger", "add"),
            *("--date", in_service.isoformat(), "--amount", "36300.00", "--direction", "OUTGOING"),
            *("--description", f"Compra de furgoneta {asset_id}", "--classification", "BUSINESS"),
            *("--taxable-base", str(BASIS), "--iva-rate", "0.21", "--iva-amount", "6300.00"),
        ],
    )
    assert invoked.exit_code == 0, invoked.output
    payload = unwrap_schema_envelope(invoked.output)
    assert isinstance(payload, dict)
    transaction = payload["transaction"]
    assert isinstance(transaction, dict)
    return str(transaction["transaction_id"])


def electric_van(asset_id: str, in_service: date, transaction_id: str) -> str:
    """Return the create-command JSON of a new battery-electric van used only for the activity."""
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=transaction_id,
            invoice_evidence_id=f"factura-{asset_id}",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=BASIS,
            non_deductible_iva=Decimal("0"),
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
            *("--free-depreciation-amount", str(BASIS)),
        ],
    )


def test_an_electric_vehicle_under_the_accelerated_regime_refuses_in_every_language(tmp_path: Path) -> None:
    with runtime_cli_profile(tmp_path=tmp_path, label="accelerated da18") as profile:
        seed_direct_normal_profile(profile.storage_root, profile.bucket_id)
        for asset_id, in_service in (
            (_ACCELERATED_ASSET, date(_ACCELERATED_EXERCISE, 3, 1)),
            (_FREE_ASSET, date(_FREE_EXERCISE, 3, 1)),
        ):
            payment = van_payment(asset_id, in_service)
            created = invoke_cached_cli(
                [
                    *("--format", "json", "app", "ledger", "actividad-asset", "create"),
                    *("--name", asset_id),
                    electric_van(asset_id, in_service, payment),
                ],
            )
            assert created.exit_code == 0, created.output
        refusals = {
            language: _forecast(_ACCELERATED_ASSET, _ACCELERATED_EXERCISE, language=language) for language in LANGUAGES
        }
        admitted = _forecast(_FREE_ASSET, _FREE_EXERCISE)

    messages: set[str] = set()
    for language, refused in refusals.items():
        assert refused.exit_code == get_error_exit_code(ErrorCategory.REFUSED), refused.output
        error = json.loads(refused.output)["error"]
        assert error["code"] == _ACCELERATED_CODE, error
        assert error["message"] == tr(_ACCELERATED_MESSAGE_KEY, locale=language)
        assert error["context"]["legal_reference"] == "ley-27-2014:da-18"
        assert error["context"]["tax_year"] == str(_ACCELERATED_EXERCISE)
        assert error["context"]["asset_id"] == _ACCELERATED_ASSET
        messages.add(error["message"])
    # Each supported language renders its own translation, not a shared fallback text.
    assert len(messages) == len(LANGUAGES)

    assert admitted.exit_code == 0, admitted.output
    forecast = unwrap_schema_envelope(admitted.output)
    assert isinstance(forecast, dict)
    assert forecast["method"] == AmortizationMethod.ELECTRIC_VEHICLE_FREE.value
    assert Decimal(str(forecast["amount"])) == BASIS
