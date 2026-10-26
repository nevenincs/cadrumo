"""Read-only activity-asset filing composition and collision tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import newest_authored_editions
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.renta.actividad_asset.claims import AmortizationClaim
from ....domain.renta.actividad_asset.election import (
    AcquiredCondition,
    ActivityAssetAmortizationElection,
    AmortizationMethod,
    DirectEstimationRegime,
)
from ....domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
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
from ..modelo_bindings_actividad_assets import (
    LedgerRentaExpenseTreatment,
    activity_asset_expense_observations,
    amortization_labelled_expense_categories,
    classify_ledger_expenses_against_asset_register,
    register_owned_acquisition_diagnostics,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


def _claim(
    year: int,
    *,
    kind: AssetKind = AssetKind.MATERIAL,
    amount: Decimal = Decimal("500.00"),
    covered_until: date | None = None,
) -> AmortizationClaim:
    """A claim covering the first quarter of ``year`` unless told otherwise."""
    return AmortizationClaim(
        asset_id="computer",
        asset_revision_id="a" * 64,
        asset_kind=kind,
        tax_year=year,
        covered_from=date(year, 1, 1),
        covered_until=covered_until or date(year, 4, 1),
        amount=amount,
        schedule_fingerprint="b" * 64,
        authority_generation="published-test-generation",
        source_reference=f"modelo-100:{year}:parameter:test",
        creating_operation="record-amortization",
    )


def _asset(year: int) -> ActivityAssetRevision:
    return ActivityAssetRevision(
        asset_id="computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="c" * 64,
            invoice_evidence_id="invoice-1",
            evidence_fingerprint="d" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000.00"),
            prior_allocation_provenance="canonical-ledger-allocation",
        ),
        in_service_date=date(year, 1, 1),
        opening_history=OpeningAmortizationHistory(
            status=OpeningHistoryStatus.KNOWN,
            accumulated_amount=Decimal("0"),
        ),
        acquired_condition=AcquiredCondition.NEW,
        amortization=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.LINEAR,
            authority_class_key="equipo-proceso-informacion",
        ),
    )


@pytest.mark.parametrize("year", _supported_years())
def test_m130_projects_each_claim_to_the_sole_expense_casilla(year: int) -> None:
    """A claim reaches Modelo 130 as its own observation, never a replaced total."""
    period = Period.from_year_and_code(year, "1T")
    claim = _claim(year)

    observations = activity_asset_expense_observations((claim,), modelo="130", period=period)

    assert [observation.claim_id for observation in observations] == [claim.claim_id]
    assert observations[0].target_casilla_id == validated_casilla_id("02", surface="test M130 target")
    assert observations[0].deductible_amount == Decimal("500.00")


@pytest.mark.parametrize("year", _supported_years())
def test_m130_excludes_a_claim_covered_beyond_the_period_cutoff(year: int) -> None:
    """The year-to-date cutoff is the period end, so a later claim is not declared yet."""
    period = Period.from_year_and_code(year, "1T")

    within = activity_asset_expense_observations((_claim(year),), modelo="130", period=period)
    beyond = activity_asset_expense_observations(
        (_claim(year, covered_until=date(year, 7, 1)),),
        modelo="130",
        period=period,
    )

    assert len(within) == 1
    assert beyond == ()


@pytest.mark.parametrize("year", _supported_years())
def test_m100_keeps_material_and_intangible_destinations_distinct(year: int) -> None:
    """Material and intangible amortization reach distinct Modelo 100 casillas."""
    period = Period.from_year_and_code(year, "0A")
    material = _claim(year)
    intangible = _claim(year, kind=AssetKind.INTANGIBLE, amount=Decimal("125.00"))

    observations = activity_asset_expense_observations((material, intangible), modelo="100", period=period)

    by_claim = {observation.claim_id: observation for observation in observations}
    assert by_claim[material.claim_id].target_casilla_id == validated_casilla_id("0208", surface="test")
    assert by_claim[material.claim_id].deductible_amount == Decimal("500.00")
    assert by_claim[intangible.claim_id].target_casilla_id == validated_casilla_id("0227", surface="test")
    assert by_claim[intangible.claim_id].deductible_amount == Decimal("125.00")


def _treatment(
    *,
    transaction_id: str,
    category: str | None,
    amortization_labelled: bool,
    tax_year: int,
    amount: Decimal = Decimal("1000.00"),
) -> LedgerRentaExpenseTreatment:
    return LedgerRentaExpenseTreatment(
        transaction_id=transaction_id,
        category=category,
        tax_year=tax_year,
        deductible_amount=amount,
        amortization_labelled=amortization_labelled,
    )


@pytest.mark.parametrize("year", _supported_years())
def test_acquisition_evidence_alone_is_valid(year: int) -> None:
    assert classify_ledger_expenses_against_asset_register((_asset(year),), (_claim(year),), ()) == ()


@pytest.mark.parametrize("year", _supported_years())
def test_a_separate_depreciation_row_for_a_charged_year_still_refuses(year: int) -> None:
    """A second depreciation treatment the schedule does not account for refuses.

    The register charges ``year`` for this asset and owns the activity
    amortization destinations exclusively. A ledger row that routes its own
    depreciation amount there would deduct the year's depreciation twice, so the
    calculation names the asset, the transaction, the category, and the year.
    """
    asset = _asset(year)
    claim = _claim(year)

    with pytest.raises(ActividadAssetClaimConflictError, match="retain acquisition evidence"):
        classify_ledger_expenses_against_asset_register(
            (asset,),
            (claim,),
            (
                _treatment(
                    transaction_id="a" * 64,
                    category="hardware_amortizable",
                    amortization_labelled=True,
                    tax_year=year,
                ),
            ),
        )


@pytest.mark.parametrize("year", _supported_years())
def test_a_separate_depreciation_row_for_an_uncharged_year_is_left_alone(year: int) -> None:
    """Without a charge for that year there is no second treatment to collide with."""
    assert (
        classify_ledger_expenses_against_asset_register(
            (_asset(year),),
            (_claim(year),),
            (
                _treatment(
                    transaction_id="a" * 64,
                    category="hardware_amortizable",
                    amortization_labelled=True,
                    tax_year=year - 1,
                ),
            ),
        )
        == ()
    )


@pytest.mark.parametrize("year", _supported_years())
def test_acquisition_purchase_is_withheld_instead_of_deducted_as_a_current_expense(year: int) -> None:
    """The register-owned acquisition is capital, and its own route yields to the register.

    RIS art. 3.2 makes the acquisition price the amortizable base, so the purchase
    is deducted through the register's charge rather than in the year of purchase.
    The row is withheld from the expense total and reported, never refused, and the
    amortization category the operator used for the purchase does not change that:
    the register already accounts for this asset's depreciation.
    """
    asset = _asset(year)
    claim = _claim(year)

    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (claim,),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="hardware_amortizable",
                amortization_labelled=True,
                tax_year=year,
                amount=Decimal("2000.00"),
            ),
        ),
    )

    assert len(withheld) == 1
    assert withheld[0].asset_id == asset.asset_id
    assert withheld[0].transaction_id == asset.acquisition.observed_transaction_id
    assert withheld[0].purchase_amount == Decimal("2000.00")
    assert withheld[0].category == "hardware_amortizable"


@pytest.mark.parametrize("year", _supported_years())
def test_acquisition_purchase_is_withheld_before_any_charge_is_claimed(year: int) -> None:
    """Without a claim the purchase is still capital, and the ledger route still yields.

    A registered asset whose year carries no claim deducts nothing. Declaring the
    full purchase instead would deduct the whole amortizable base at once, which
    is exactly what RIS art. 3.3's useful-life spread forbids.
    """
    asset = _asset(year)

    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="hardware_amortizable",
                amortization_labelled=True,
                tax_year=year,
            ),
        ),
    )

    assert tuple(item.purchase_amount for item in withheld) == (Decimal("1000.00"),)


@pytest.mark.parametrize("year", _supported_years())
def test_unrelated_expense_rows_are_outside_the_register_scope(year: int) -> None:
    asset = _asset(year)
    claim = _claim(year)

    assert (
        classify_ledger_expenses_against_asset_register(
            (asset,),
            (claim,),
            (
                _treatment(
                    transaction_id="e" * 64,
                    category="asesoria_fiscal",
                    amortization_labelled=False,
                    tax_year=year,
                ),
            ),
        )
        == ()
    )


@pytest.mark.parametrize("year", _supported_years())
def test_only_the_current_asset_revision_declares_the_owned_acquisition(year: int) -> None:
    """A superseding revision restates the acquisition linkage; the stale one stops owning it."""
    original = _asset(year)
    superseded_transaction_id = original.acquisition.observed_transaction_id
    current_transaction_id = "f" * 64
    current = original.model_copy(
        update={
            "revision_number": 2,
            "acquisition": AcquisitionLineageReference(
                observed_transaction_id=current_transaction_id,
                invoice_evidence_id="invoice-2",
                evidence_fingerprint="0" * 64,
            ),
        },
    )

    withheld = classify_ledger_expenses_against_asset_register(
        (original, current),
        (),
        (
            _treatment(
                transaction_id=superseded_transaction_id,
                category=None,
                amortization_labelled=False,
                tax_year=year,
            ),
            _treatment(
                transaction_id=current_transaction_id,
                category=None,
                amortization_labelled=False,
                tax_year=year,
            ),
        ),
    )

    assert tuple(item.transaction_id for item in withheld) == (current_transaction_id,)


@pytest.mark.parametrize("year", _supported_years())
def test_withheld_acquisition_advisory_names_the_asset_and_the_amount(year: int) -> None:
    asset = _asset(year)
    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="material_oficina",
                amortization_labelled=False,
                tax_year=year,
                amount=Decimal("2000.00"),
            ),
        ),
    )

    diagnostics = register_owned_acquisition_diagnostics(
        withheld,
        source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
        resolver_id="ledger_renta_gastos_estimacion_directa_aggregation",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].reason == "register_owned_capital_acquisition"
    assert diagnostics[0].source_ref == f"transaction:{asset.acquisition.observed_transaction_id}"
    assert asset.asset_id in diagnostics[0].message
    assert "2000.00" in diagnostics[0].message
    assert diagnostics[0].remedy is not None


# The two newest Modelo 100 editions the registry authors; the first-slice
# expense routing is declared for each of them.
_ROUTING_EDITIONS = newest_authored_editions("100", 2)


@pytest.mark.parametrize("year", _ROUTING_EDITIONS)
def test_amortization_labelled_categories_come_from_the_governed_routing(year: int) -> None:
    """The label is a registry fact: the routed casilla decides, not a category name list."""
    with bundled_indexed_authority().operation():
        labelled = amortization_labelled_expense_categories(effective_date=date(year, 6, 30))

    assert "hardware_amortizable" in labelled
    assert "mobiliario_amortizable" in labelled
    assert "asesoria_fiscal" not in labelled
    assert "material_oficina" not in labelled
