from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.application.actividad_asset.modality import direct_estimation_modality
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
    LowValueElection,
)
from cadrumo.domain.renta.actividad_asset.errors import (
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
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
from cadrumo.domain.renta.actividad_asset.schedule import (
    AssetScheduleHistory,
    ScheduleAuthority,
    ScheduledAmortizationCharge,
    schedule_charge,
)
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction

from .ledger_support import MemoryLedger, acquisition_transaction
from .register_support import MemoryRepository as _MemoryRepository
from .register_support import describing, memory_register_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LINEAR = ActivityAssetAmortizationElection(
    regime=DirectEstimationRegime.SIMPLIFIED,
    method=AmortizationMethod.LINEAR,
    authority_class_key="equipo-informacion-software",
)


@cache
def _acquisition() -> Transaction:
    return acquisition_transaction()


def _ledger() -> MemoryLedger:
    return MemoryLedger(_acquisition())


def _simplified() -> DirectEstimationRegime:
    return DirectEstimationRegime.SIMPLIFIED


def _normal() -> DirectEstimationRegime:
    return DirectEstimationRegime.NORMAL


def _revision(
    *,
    asset_id: str = "laptop-1",
    basis_amount: Decimal = Decimal("2000"),
    non_deductible_iva: Decimal = Decimal("0"),
    acquisition_id: str | None = None,
    number: int = 1,
    supersedes: str | None = None,
    election: ActivityAssetAmortizationElection = _LINEAR,
) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id=asset_id,
        revision_number=number,
        supersedes_revision_id=supersedes,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=acquisition_id or _acquisition().transaction_id,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="b" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=basis_amount,
            non_deductible_iva=non_deductible_iva,
            prior_allocation_provenance="ledger allocation allocation-1",
        ),
        in_service_date=date(2025, 1, 1),
        opening_history=OpeningAmortizationHistory(status=OpeningHistoryStatus.KNOWN, accumulated_amount=Decimal("0")),
        acquired_condition=AcquiredCondition.NEW,
        amortization=election,
    )


def _linear_forecast(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    return schedule_charge(
        revision,
        ScheduleAuthority(
            tax_year=2025,
            asset_kind=AssetKind.MATERIAL,
            method=AmortizationMethod.LINEAR,
            election_fingerprint=revision.amortization.fingerprint,
            annual_rate=Decimal("0.26"),
            authority_generation="irpf-2025-assets-test-v1",
            source_reference="AEAT simplified direct-estimation table 2025",
        ),
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_frontend_operations_share_one_create_forecast_claim_and_projection_path() -> None:
    repository = _MemoryRepository()
    operations = ActivityAssetOperations(
        repository=repository,
        ledger=_ledger(),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_simplified,
        register_authority=memory_register_authority(),
    )
    revision = _revision()

    operations.create(revision, describing(revision))
    forecast = operations.forecast(
        asset_id=revision.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
    )
    assert forecast.amount == Decimal("520.00")
    assert repository.history.claims == ()

    first = operations.record_claim(forecast, creating_operation="actividad_asset.claim")
    retry = operations.record_claim(forecast, creating_operation="actividad_asset.claim")
    assert retry.reused_existing_claim is True
    assert retry.claim.claim_id == first.claim.claim_id
    assert len(repository.history.claims) == 1

    handoff = operations.filing_handoff(
        tax_year=2025,
        m130_period=Period.from_year_and_code(2025, "4T"),
    )
    assert handoff.material_m100.amount == Decimal("520.00")
    assert handoff.material_m130.amount == Decimal("520.00")
    assert handoff.material_m100.claim_ids == (first.claim.claim_id,)
    assert [item.schedule_fingerprint for item in handoff.material_m130.contributions] == [forecast.schedule_fingerprint]
    assert handoff.intangible_m100.amount == Decimal("0.00")


def test_forecast_passes_effective_history_split_at_the_tax_year() -> None:
    repository = _MemoryRepository()
    seen: list[AssetScheduleHistory] = []

    def recording_forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        seen.append(history)
        return _linear_forecast(
            revision,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    operations = ActivityAssetOperations(
        repository=repository,
        ledger=_ledger(),
        forecast_operation=recording_forecast,
        taxpayer_modality=_simplified,
        register_authority=memory_register_authority(),
    )
    revision = _revision()
    operations.create(revision, describing(revision))
    first_quarter = operations.forecast(
        asset_id=revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2025, 4, 1)
    )
    operations.record_claim(first_quarter, creating_operation="test.q1")
    operations.forecast(asset_id=revision.asset_id, covered_from=date(2025, 4, 1), covered_until=date(2025, 7, 1))

    assert seen[-1].accumulated_in_tax_year == first_quarter.amount
    assert seen[-1].accumulated_before_tax_year == Decimal("0")
    assert seen[-1].election_fingerprints_in_tax_year == (revision.amortization.fingerprint,)


def test_correction_must_supersede_the_current_revision() -> None:
    operations = ActivityAssetOperations(
        repository=_MemoryRepository(),
        ledger=_ledger(),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_simplified,
        register_authority=memory_register_authority(),
    )
    first = _revision()
    operations.create(first, describing(first))

    with pytest.raises(ActividadAssetValidationError, match="correction_must_supersede_current"):
        operations.correct(_revision(number=2, supersedes="c" * 64))

    corrected = _revision(number=2, supersedes=first.revision_id)
    history = operations.correct(corrected)
    assert operations.inspect(first.asset_id) == (first, corrected)
    assert history.revisions[-1] == corrected


def test_operations_use_effective_profile_history_for_the_free_depreciation_cap_without_forecast_consumption() -> None:
    repository = _MemoryRepository()

    def free_forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        return schedule_charge(
            revision,
            ScheduleAuthority(
                tax_year=2025,
                asset_kind=AssetKind.MATERIAL,
                method=AmortizationMethod.LOW_VALUE_FREE,
                election_fingerprint=revision.amortization.fingerprint,
                authority_generation="irpf-2025-published-test",
                source_reference="modelo-100:2025:low-value-free",
                free_depreciation_unit_threshold=Decimal("300.00"),
                free_depreciation_annual_cap=Decimal("500.00"),
                low_value=revision.amortization.low_value,
            ),
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            requested_free_amount=requested_free_amount,
        )

    def low_value(asset_id: str) -> ActivityAssetRevision:
        return _revision(
            asset_id=asset_id,
            basis_amount=Decimal("300.00"),
            election=ActivityAssetAmortizationElection(
                regime=DirectEstimationRegime.NORMAL,
                method=AmortizationMethod.LOW_VALUE_FREE,
                authority_class_key="mobiliario",
                low_value=LowValueElection(
                    election_reference=f"election-{asset_id}",
                    new_material_evidence_reference="canonical-new-material-evidence",
                ),
            ),
        )

    operations = ActivityAssetOperations(
        repository=repository,
        ledger=_ledger(),
        forecast_operation=free_forecast,
        taxpayer_modality=_normal,
        register_authority=memory_register_authority(),
    )
    first_asset = low_value("low-value-first")
    second_asset = low_value("low-value-second")
    operations.create(first_asset, describing(first_asset))
    operations.create(second_asset, describing(second_asset))

    forecast = operations.forecast(
        asset_id=first_asset.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        requested_free_amount=Decimal("300.00"),
    )
    assert repository.history.claims == ()
    operations.record_claim(forecast, creating_operation="test.free-depreciation")

    with pytest.raises(ActividadAssetUnsupportedError, match="free_amount_exceeds_annual_cap"):
        operations.forecast(
            asset_id=second_asset.asset_id,
            covered_from=date(2025, 1, 1),
            covered_until=date(2026, 1, 1),
            requested_free_amount=Decimal("300.00"),
        )
    exact_cap_forecast = operations.forecast(
        asset_id=second_asset.asset_id,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        requested_free_amount=Decimal("200.00"),
    )
    operations.record_claim(exact_cap_forecast, creating_operation="test.free-depreciation")
    assert sum((claim.amount for claim in repository.history.claims), Decimal("0")) == Decimal("500.00")


def test_forecast_refuses_an_election_the_taxpayer_modality_does_not_declare() -> None:
    operations = ActivityAssetOperations(
        repository=_MemoryRepository(),
        ledger=_ledger(),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_normal,
        register_authority=memory_register_authority(),
    )
    revision = _revision()
    operations.create(revision, describing(revision))

    with pytest.raises(ActividadAssetValidationError, match="profile_modality_mismatch"):
        operations.forecast(asset_id=revision.asset_id, covered_from=date(2025, 1, 1), covered_until=date(2026, 1, 1))


@pytest.mark.parametrize(
    ("profile_token", "expected"),
    [("directa_normal", DirectEstimationRegime.NORMAL), ("directa_simplificada", DirectEstimationRegime.SIMPLIFIED)],
)
def test_profile_direct_estimation_tokens_resolve_through_governed_authority(
    profile_token: str,
    expected: DirectEstimationRegime,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    assert direct_estimation_modality(profile_token, authority=authority_operation) is expected


@pytest.mark.parametrize(
    ("profile_token", "error", "key"),
    [
        (None, ActividadAssetIncompleteError, "modality_not_declared"),
        ("objetiva", ActividadAssetUnsupportedError, "modality_not_direct_estimation"),
    ],
)
def test_absent_or_objective_profile_regime_refuses(
    profile_token: str | None,
    error: type[Exception],
    key: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(error) as refused:
        direct_estimation_modality(profile_token, authority=authority_operation)
    assert getattr(refused.value, "translated_message", None) == f"ledger.actividad_asset.errors.{key}"


def _operations(*transactions: Transaction) -> ActivityAssetOperations:
    return ActivityAssetOperations(
        repository=_MemoryRepository(),
        ledger=MemoryLedger(*transactions),
        forecast_operation=_linear_forecast,
        taxpayer_modality=_simplified,
        register_authority=memory_register_authority(),
    )


def test_creation_refuses_an_acquisition_the_ledger_does_not_hold() -> None:
    operations = _operations()

    with pytest.raises(ActividadAssetValidationError, match="acquisition_transaction_missing"):
        operations.create(_revision(), describing(_revision()))
    with pytest.raises(ActividadAssetValidationError, match="asset_not_found"):
        operations.inspect("laptop-1")


def test_creation_refuses_an_acquisition_that_is_not_a_payment() -> None:
    received = acquisition_transaction(provider_id="refund-1", direction=TransactionDirection.INCOMING)

    with pytest.raises(ActividadAssetValidationError, match="acquisition_transaction_not_payment"):
        _operations(received).create(_revision(acquisition_id=received.transaction_id), describing())


def test_price_and_non_deductible_iva_are_bounded_by_what_the_transaction_paid() -> None:
    operations = _operations(_acquisition())

    # The row paid 2,420.00 = 2,000.00 base + 420.00 IVA, so 2,000.00 + 420.00 is exactly admissible.
    exact = _revision(non_deductible_iva=Decimal("420.00"))
    assert operations.create(exact, describing(exact)).revisions == (exact,)

    with pytest.raises(ActividadAssetValidationError, match="acquisition_cost_exceeds_payment"):
        _operations(_acquisition()).create(
            _revision(asset_id="over-paid", non_deductible_iva=Decimal("500.00")),
            describing(),
        )
    with pytest.raises(ActividadAssetValidationError, match="acquisition_price_exceeds_base"):
        _operations(_acquisition()).create(
            _revision(asset_id="over-base", basis_amount=Decimal("2000.01")),
            describing(),
        )
    with pytest.raises(ActividadAssetValidationError, match="acquisition_iva_exceeds_transaction_iva"):
        _operations(_acquisition()).create(
            _revision(asset_id="over-iva", basis_amount=Decimal("1500.00"), non_deductible_iva=Decimal("421.00")),
            describing(),
        )


def test_a_foreign_currency_acquisition_is_compared_by_its_euro_value() -> None:
    dollars = acquisition_transaction(
        provider_id="usd-1",
        amount=Decimal("100.00"),
        taxable_base=None,
        iva_amount=None,
        currency="USD",
        value_in_eur=Decimal("92.00"),
    )
    unconverted = acquisition_transaction(
        provider_id="usd-2",
        amount=Decimal("100.00"),
        taxable_base=None,
        iva_amount=None,
        currency="USD",
    )

    accepted = _revision(basis_amount=Decimal("92.00"), acquisition_id=dollars.transaction_id)
    assert _operations(dollars).create(accepted, describing()).revisions == (accepted,)
    with pytest.raises(ActividadAssetValidationError, match="acquisition_cost_exceeds_payment"):
        _operations(dollars).create(
            _revision(basis_amount=Decimal("92.01"), acquisition_id=dollars.transaction_id),
            describing(),
        )
    with pytest.raises(ActividadAssetValidationError, match="acquisition_currency_unconverted"):
        _operations(unconverted).create(
            _revision(basis_amount=Decimal("92.00"), acquisition_id=unconverted.transaction_id),
            describing(),
        )


def test_a_correction_is_checked_against_the_ledger_like_a_creation() -> None:
    operations = _operations(_acquisition())
    first = _revision()
    operations.create(first, describing(first))

    with pytest.raises(ActividadAssetValidationError, match="acquisition_transaction_missing"):
        operations.correct(_revision(number=2, supersedes=first.revision_id, acquisition_id="d" * 64))
    with pytest.raises(ActividadAssetValidationError, match="acquisition_cost_exceeds_payment"):
        operations.correct(
            _revision(number=2, supersedes=first.revision_id, non_deductible_iva=Decimal("500.00")),
        )
    corrected = _revision(number=2, supersedes=first.revision_id, non_deductible_iva=Decimal("100.00"))
    assert operations.correct(corrected).revisions == (first, corrected)


def test_a_refused_cost_names_the_exact_figures_in_its_context() -> None:
    with pytest.raises(ActividadAssetValidationError) as refused:
        _operations(_acquisition()).create(_revision(non_deductible_iva=Decimal("500.00")), describing())

    assert refused.value.context == {
        "cost": "2500.00",
        "price": "2000",
        "non_deductible_iva": "500.00",
        "paid": "2420.00",
    }
