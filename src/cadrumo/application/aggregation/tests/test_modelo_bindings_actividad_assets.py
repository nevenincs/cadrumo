"""Read-only activity-asset filing composition and collision tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.categories.registry import resolve_category_profiles
from ....domain.renta.actividad_asset.claims import M100_AMORTIZATION_CASILLA_IDS
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
from ....domain.renta.ledger_expenses import renta_first_slice_expense_routing
from ..modelo_bindings_actividad_assets import (
    LedgerRentaExpenseTreatment,
    amortization_labelled_expense_categories,
    classify_ledger_expenses_against_asset_register,
    refused_amortization_rows,
    register_owned_acquisition_diagnostics,
    unregistered_amortization_row_diagnostics,
)
from ..renta_ledger_models import RentaLedgerAggregationIssue, RentaLedgerAggregationIssueReason

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None, "the published authority declares no support envelope"
    return support.years


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
            non_deductible_iva=Decimal("0"),
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
    classification = classify_ledger_expenses_against_asset_register((_asset(year),), ())

    assert classification.withheld == ()
    assert classification.unregistered == ()


@pytest.mark.parametrize("year", _supported_years())
def test_an_unowned_amortization_row_is_reported_with_or_without_a_claim(year: int) -> None:
    """The register is the only route in every year, so a claim changes nothing about the row."""
    row = _treatment(
        transaction_id="a" * 64,
        category="hardware_amortizable",
        amortization_labelled=True,
        tax_year=year,
    )

    unclaimed = classify_ledger_expenses_against_asset_register((_asset(year),), (row,))
    no_assets = classify_ledger_expenses_against_asset_register((), (row,))

    assert [item.transaction_id for item in unclaimed.unregistered] == ["a" * 64]
    assert [item.transaction_id for item in no_assets.unregistered] == ["a" * 64]
    assert unclaimed.excluded_transaction_ids == {"a" * 64}


def test_the_unowned_row_note_names_the_row_and_the_remedy() -> None:
    row = classify_ledger_expenses_against_asset_register(
        (),
        (
            _treatment(
                transaction_id="a" * 64, category="hardware_amortizable", amortization_labelled=True, tax_year=2025
            ),
        ),
    ).unregistered

    diagnostics = unregistered_amortization_row_diagnostics(row, resolver_id="resolver")

    assert [diagnostic.reason for diagnostic in diagnostics] == ["ledger_amortization_row_unregistered"]
    assert diagnostics[0].source_ref == f"transaction:{'a' * 64}"
    assert "hardware_amortizable" in diagnostics[0].message
    assert diagnostics[0].remedy is not None
    assert "register the element" in diagnostics[0].remedy


def _refused(
    reason: RentaLedgerAggregationIssueReason, *, transaction_id: str, category: str
) -> RentaLedgerAggregationIssue:
    return RentaLedgerAggregationIssue(
        transaction_id=transaction_id,
        category_id=category,
        reason=reason,
        detail="refused",
    )


def test_a_row_refused_once_its_route_is_gone_still_counts_as_unowned() -> None:
    """After the category leaves the routing the row never becomes an observation, and must still block."""
    asset = _asset(2025)
    assert asset.acquisition.observed_transaction_id is not None
    with bundled_indexed_authority().operation():
        rows = refused_amortization_rows(
            (
                _refused(
                    RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
                    transaction_id="a" * 64,
                    category="hardware_amortizable",
                ),
                _refused(
                    RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
                    transaction_id=asset.acquisition.observed_transaction_id,
                    category="hardware_amortizable",
                ),
                _refused(
                    RentaLedgerAggregationIssueReason.PERSONAL_TRANSACTION,
                    transaction_id="b" * 64,
                    category="hardware_amortizable",
                ),
                _refused(
                    RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    transaction_id="d" * 64,
                    category="mobiliario_amortizable",
                ),
                _refused(
                    RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
                    transaction_id="e" * 64,
                    category="asesoria_fiscal",
                ),
            ),
            assets=(asset,),
            tax_year=2025,
            effective_date=date(2025, 12, 31),
        )

    assert [row.transaction_id for row in rows] == ["a" * 64]


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
    assert asset.acquisition.observed_transaction_id is not None

    classified = classify_ledger_expenses_against_asset_register(
        (asset,),
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
    withheld = classified.withheld

    assert classified.unregistered == ()

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
    assert asset.acquisition.observed_transaction_id is not None

    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="hardware_amortizable",
                amortization_labelled=True,
                tax_year=year,
            ),
        ),
    ).withheld

    assert tuple(item.purchase_amount for item in withheld) == (Decimal("1000.00"),)


@pytest.mark.parametrize("year", _supported_years())
def test_unrelated_expense_rows_are_outside_the_register_scope(year: int) -> None:
    classified = classify_ledger_expenses_against_asset_register(
        (_asset(year),),
        (
            _treatment(
                transaction_id="e" * 64,
                category="asesoria_fiscal",
                amortization_labelled=False,
                tax_year=year,
            ),
        ),
    )

    assert classified.excluded_transaction_ids == frozenset()


@pytest.mark.parametrize("year", _supported_years())
def test_only_the_current_asset_revision_declares_the_owned_acquisition(year: int) -> None:
    """A superseding revision restates the acquisition linkage; the stale one stops owning it."""
    original = _asset(year)
    superseded_transaction_id = original.acquisition.observed_transaction_id
    assert superseded_transaction_id is not None
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
    ).withheld

    assert tuple(item.transaction_id for item in withheld) == (current_transaction_id,)


@pytest.mark.parametrize("year", _supported_years())
def test_withheld_acquisition_advisory_names_the_asset_and_the_amount(year: int) -> None:
    asset = _asset(year)
    assert asset.acquisition.observed_transaction_id is not None
    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="material_oficina",
                amortization_labelled=False,
                tax_year=year,
                amount=Decimal("2000.00"),
            ),
        ),
    ).withheld

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


@pytest.mark.parametrize("year", _supported_years())
def test_amortization_labelled_categories_come_from_the_governed_catalogue(year: int) -> None:
    """The label is a registry fact: the catalogue names the categories, not a list in code."""
    with bundled_indexed_authority().operation():
        labelled = amortization_labelled_expense_categories(effective_date=date(year, 6, 30))

    assert "hardware_amortizable" in labelled
    assert "mobiliario_amortizable" in labelled
    assert "amortizacion_vivienda_afecto" in labelled
    assert "asesoria_fiscal" not in labelled
    assert "material_oficina" not in labelled


@pytest.mark.parametrize("year", _supported_years())
def test_no_labelled_category_reaches_an_amortization_casilla(year: int) -> None:
    """The register is the only route to 0208 and 0227: no ledger category routes there, and each deducts nothing."""
    effective_date = date(year, 6, 30)
    with bundled_indexed_authority().operation() as operation:
        labelled = amortization_labelled_expense_categories(effective_date=effective_date)
        routing = renta_first_slice_expense_routing(effective_date=effective_date)
        profiles = resolve_category_profiles(year, operation=operation)

    assert labelled
    assert not {category.value for category in routing} & labelled
    assert not {casilla for casilla in routing.values() if casilla in M100_AMORTIZATION_CASILLA_IDS}
    assert {
        category.value for category, profile in profiles.items() if profile.proportionality.kind.is_non_deductible
    } >= labelled
