"""Read-only activity-asset filing composition and collision tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
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
from .._models import CasillaAggregation
from ..modelo_bindings_actividad_assets import (
    LedgerRentaExpenseTreatment,
    add_activity_assets_to_m130_expenses,
    amortization_labelled_expense_categories,
    classify_ledger_expenses_against_asset_register,
    project_activity_assets_to_m100,
    register_owned_acquisition_diagnostics,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _claim(*, kind: AssetKind = AssetKind.MATERIAL, amount: Decimal = Decimal("500.00")) -> AmortizationClaim:
    return AmortizationClaim(
        asset_id="computer",
        asset_revision_id="a" * 64,
        asset_kind=kind,
        tax_year=2025,
        covered_from=date(2025, 1, 1),
        covered_until=date(2025, 4, 1),
        amount=amount,
        schedule_fingerprint="b" * 64,
        authority_generation="published-test-generation",
        source_reference="modelo-100:2025:parameter:test",
        creating_operation="record-amortization",
    )


def _asset() -> ActivityAssetRevision:
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
        in_service_date=date(2025, 1, 1),
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


def test_m130_adds_claim_to_ordinary_expenses_without_replacing_them() -> None:
    period = Period.from_year_and_code(2025, "1T")
    target = validated_casilla_id("02", surface="test M130 target")
    ordinary = CasillaAggregation(modelo="130", period=period, casilla_values={target: Decimal("300.00")})
    claim = _claim()

    result = add_activity_assets_to_m130_expenses(ordinary, (claim,))

    assert result.casilla_values[target] == Decimal("800.00")
    assert result.claim_ids == (claim.claim_id,)
    assert ordinary.casilla_values[target] == Decimal("300.00")


def test_m100_keeps_material_and_intangible_destinations_distinct() -> None:
    period = Period.from_year_and_code(2025, "0A")
    material = _claim()
    intangible = _claim(kind=AssetKind.INTANGIBLE, amount=Decimal("125.00"))

    result = project_activity_assets_to_m100((material, intangible), period=period)

    assert result.casilla_values[validated_casilla_id("0208", surface="test")] == Decimal("500.00")
    assert result.casilla_values[validated_casilla_id("0227", surface="test")] == Decimal("125.00")
    assert set(result.claim_ids) == {material.claim_id, intangible.claim_id}


def _treatment(
    *,
    transaction_id: str,
    category: str | None,
    amortization_labelled: bool,
    amount: Decimal = Decimal("1000.00"),
    tax_year: int = 2025,
) -> LedgerRentaExpenseTreatment:
    return LedgerRentaExpenseTreatment(
        transaction_id=transaction_id,
        category=category,
        tax_year=tax_year,
        deductible_amount=amount,
        amortization_labelled=amortization_labelled,
    )


def test_acquisition_evidence_alone_is_valid() -> None:
    assert classify_ledger_expenses_against_asset_register((_asset(),), (_claim(),), ()) == ()


def test_a_separate_depreciation_row_for_a_charged_year_still_refuses() -> None:
    """A second depreciation treatment the schedule does not account for refuses.

    The register charges 2025 for this asset and owns the activity amortization
    destinations exclusively. A ledger row that routes its own depreciation
    amount there would deduct the year's depreciation twice, so the calculation
    names the asset, the transaction, the category, and the year.
    """
    asset = _asset()
    claim = _claim()

    with pytest.raises(ActividadAssetClaimConflictError, match="retain acquisition evidence"):
        classify_ledger_expenses_against_asset_register(
            (asset,),
            (claim,),
            (
                _treatment(
                    transaction_id="a" * 64,
                    category="hardware_amortizable",
                    amortization_labelled=True,
                ),
            ),
        )


def test_a_separate_depreciation_row_for_an_uncharged_year_is_left_alone() -> None:
    """Without a charge for that year there is no second treatment to collide with."""
    assert (
        classify_ledger_expenses_against_asset_register(
            (_asset(),),
            (_claim(),),
            (
                _treatment(
                    transaction_id="a" * 64,
                    category="hardware_amortizable",
                    amortization_labelled=True,
                    tax_year=2024,
                ),
            ),
        )
        == ()
    )


def test_acquisition_purchase_is_withheld_instead_of_deducted_as_a_current_expense() -> None:
    """The register-owned acquisition is capital, and its own route yields to the register.

    RIS art. 3.2 makes the acquisition price the amortizable base, so the purchase
    is deducted through the register's charge rather than in the year of purchase.
    The row is withheld from the expense total and reported, never refused, and the
    amortization category the operator used for the purchase does not change that:
    the register already accounts for this asset's depreciation.
    """
    asset = _asset()
    claim = _claim()

    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (claim,),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="hardware_amortizable",
                amortization_labelled=True,
                amount=Decimal("2000.00"),
            ),
        ),
    )

    assert len(withheld) == 1
    assert withheld[0].asset_id == asset.asset_id
    assert withheld[0].transaction_id == asset.acquisition.observed_transaction_id
    assert withheld[0].purchase_amount == Decimal("2000.00")
    assert withheld[0].category == "hardware_amortizable"


def test_acquisition_purchase_is_withheld_before_any_charge_is_claimed() -> None:
    """Without a claim the purchase is still capital, and the ledger route still yields.

    A registered asset whose year carries no claim deducts nothing. Declaring the
    full purchase instead would deduct the whole amortizable base at once, which
    is exactly what RIS art. 3.3's useful-life spread forbids.
    """
    asset = _asset()

    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="hardware_amortizable",
                amortization_labelled=True,
            ),
        ),
    )

    assert tuple(item.purchase_amount for item in withheld) == (Decimal("1000.00"),)


def test_unrelated_expense_rows_are_outside_the_register_scope() -> None:
    asset = _asset()
    claim = _claim()

    assert (
        classify_ledger_expenses_against_asset_register(
            (asset,),
            (claim,),
            (_treatment(transaction_id="e" * 64, category="asesoria_fiscal", amortization_labelled=False),),
        )
        == ()
    )


def test_only_the_current_asset_revision_declares_the_owned_acquisition() -> None:
    """A superseding revision restates the acquisition linkage; the stale one stops owning it."""
    original = _asset()
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
            _treatment(transaction_id=superseded_transaction_id, category=None, amortization_labelled=False),
            _treatment(transaction_id=current_transaction_id, category=None, amortization_labelled=False),
        ),
    )

    assert tuple(item.transaction_id for item in withheld) == (current_transaction_id,)


def test_withheld_acquisition_advisory_names_the_asset_and_the_amount() -> None:
    asset = _asset()
    withheld = classify_ledger_expenses_against_asset_register(
        (asset,),
        (),
        (
            _treatment(
                transaction_id=asset.acquisition.observed_transaction_id,
                category="material_oficina",
                amortization_labelled=False,
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


def test_amortization_labelled_categories_come_from_the_governed_routing() -> None:
    """The label is a registry fact: the routed casilla decides, not a category name list."""
    with bundled_indexed_authority().operation():
        labelled = amortization_labelled_expense_categories(effective_date=date(2025, 6, 30))

    assert "hardware_amortizable" in labelled
    assert "mobiliario_amortizable" in labelled
    assert "asesoria_fiscal" not in labelled
    assert "material_oficina" not in labelled
