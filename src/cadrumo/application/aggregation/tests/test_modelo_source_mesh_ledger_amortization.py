"""Source mesh parity tests for ledger-backed renta amortization and M130/M100 asset claims."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.categories.spending_category import SpendingCategory
from ....domain.renta.actividad_asset.claims import AmortizationClaim
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
from ....domain.transactions.models import TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...modelo.calculation_notes import GATE_REFUSED_REASONS, UNWORKED_BOX_REASONS, note_attention
from ...modelo.work_form_findings import ModeloFormAttention
from ...modelo.work_profile import ModeloWorkProfile
from ..modelo_bindings_renta_expenses import (
    LedgerRentaGastosEstimacionDirectaAggregationSourceResolver,
    LedgerRentaGastosPagoFraccionadoAggregationSourceResolver,
)
from ..source_mesh import (
    CalculationSourceContext,
)
from .ledger_source_mesh_support import (
    _AMORTIZABLE_CATEGORIES,
    _PRIOR_YEAR_ROW_NOTE,
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    StaticActivityAssetHistoryRepository,
    _empty_catalogue_read_ports,
    _EmptyActivityAssetHistoryRepository,
    _filing_years,
    _free_election,
    _InMemoryInvoiceCatalogueRepository,
    _invoice,
    _m100_revision,
    _m130_binding_id,
    _prior_year_purchase,
    _register_claim,
    _renta_expense_binding_id,
    _revision,
    _UnreadableActivityAssetHistoryRepository,
    catalogue_read_ports,
    empty_invoice_repository,
    empty_prorrata_repository,
    m130_box,
    machine_acquisition_transaction,
    machine_asset,
    machine_claim,
    reasons,
    register_asset,
    resolve_m100,
    resolve_m130,
)
from .ledger_transaction_support import (
    renta_acquisition_row,
    renta_transaction,
)
from .usage_ratio_support import no_stored_usage_ratios

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_renta_source_mesh_resolver_preserves_purchase_invoice_evidence_provenance() -> None:
    revision = _revision("100", "2025")
    tx_repo = InMemoryTransactionCatalogueRepository(
        bucket_id=BUCKET_ID,
    )
    invoice_repo = _InMemoryInvoiceCatalogueRepository()
    initial = renta_transaction("renta-linked", purchase_invoice_evidence_id=None)
    invoice = _invoice(initial.transaction_id)
    linked = renta_transaction("renta-linked", purchase_invoice_evidence_id=invoice.invoice_id)
    tx_repo.save(TransactionCatalogue.from_transactions((linked,)))
    invoice_repo.save(build_invoice_catalogue((invoice,)))

    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=catalogue_read_ports(invoice_repository=invoice_repo, transaction_repository=tx_repo),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=_EmptyActivityAssetHistoryRepository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )

    assert resolution.binding_values  # non-empty: renta expense binding resolved
    assert resolution.source_transaction_ids == (linked.transaction_id,)
    assert resolution.diagnostics == ()
    assert {item.source_ref for item in resolution.provenance} == {
        f"transaction:{linked.transaction_id}",
        f"purchase-invoice-evidence:{invoice.invoice_id}",
    }


def test_renta_source_mesh_blocks_a_separate_depreciation_row_and_never_deducts_it() -> None:
    """A depreciation row the register does not own carries a blocking note and reaches no box."""
    revision = _revision("100", "2025")
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    acquisition = renta_transaction(
        "asset-acquisition",
        purchase_invoice_evidence_id=None,
        amount=Decimal("2000.00"),
        category=SpendingCategory.from_registry("hardware_amortizable"),
    )
    separate_depreciation = renta_transaction(
        "separate-depreciation-row",
        purchase_invoice_evidence_id=None,
        amount=Decimal("250.00"),
        category=SpendingCategory.from_registry("mobiliario_amortizable"),
    )
    tx_repo.save(TransactionCatalogue.from_transactions((acquisition, separate_depreciation)))
    asset = ActivityAssetRevision(
        asset_id="computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id=acquisition.transaction_id,
            invoice_evidence_id="invoice-asset",
            evidence_fingerprint="a" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000.00"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger-business-allocation",
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
    claim = AmortizationClaim(
        asset_id=asset.asset_id,
        asset_revision_id=asset.revision_id,
        asset_kind=asset.asset_kind,
        tax_year=2025,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        amount=Decimal("500.00"),
        schedule_fingerprint="b" * 64,
        authority_generation="published-test-generation",
        source_reference="modelo-100:2025:parameter:computer",
        creating_operation="record-amortization",
    )
    history = ActivityAssetHistory(revisions=(asset,), claims=(claim,))

    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=catalogue_read_ports(
            invoice_repository=_InMemoryInvoiceCatalogueRepository(),
            transaction_repository=tx_repo,
        ),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(history),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )

    notes = [item for item in resolution.diagnostics if item.reason == "ledger_amortization_row_unregistered"]
    assert [note.source_ref for note in notes] == [f"transaction:{separate_depreciation.transaction_id}"]
    assert resolution.binding_values[_renta_expense_binding_id(revision, "0208")] == Decimal("500.00")
    assert separate_depreciation.transaction_id not in resolution.source_transaction_ids


def test_renta_source_mesh_projects_recorded_asset_claim_without_full_cost() -> None:
    revision = _revision("100", "2025")
    asset = ActivityAssetRevision(
        asset_id="computer",
        revision_number=1,
        acquisition=AcquisitionLineageReference(
            observed_transaction_id="c" * 64,
            invoice_evidence_id="invoice-asset",
            evidence_fingerprint="d" * 64,
        ),
        acquisition_shape=AcquisitionShape.PRIMARY_PURCHASE,
        asset_kind=AssetKind.MATERIAL,
        basis=ActivityAssetBasis(
            stage=AssetBasisStage.BUSINESS_ALLOCATED,
            basis_amount=Decimal("2000.00"),
            non_deductible_iva=Decimal("0"),
            prior_allocation_provenance="ledger-business-allocation",
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
    claim = AmortizationClaim(
        asset_id=asset.asset_id,
        asset_revision_id=asset.revision_id,
        asset_kind=asset.asset_kind,
        tax_year=2025,
        covered_from=date(2025, 1, 1),
        covered_until=date(2026, 1, 1),
        amount=Decimal("500.00"),
        schedule_fingerprint="e" * 64,
        authority_generation="published-test-generation",
        source_reference="modelo-100:2025:parameter:computer",
        creating_operation="record-amortization",
    )
    history = ActivityAssetHistory(revisions=(asset,), claims=(claim,))

    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=_empty_catalogue_read_ports(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(history),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )
    target_binding = next(
        binding
        for binding in revision.bindings
        if str(binding.source) == "ledger_renta_gastos_estimacion_directa_aggregation"
        and str(getattr(binding.provider, "target_casilla_id", None)) == "0208"
    )

    assert resolution.binding_values[target_binding.id] == Decimal("500.00")
    assert Decimal("2000.00") not in resolution.binding_values.values()
    assert {item.source_ref for item in resolution.provenance} == {f"activity-asset-claim:{claim.claim_id}"}


def test_renta_source_mesh_declares_only_the_claim_for_a_register_owned_acquisition() -> None:
    """An in-year purchase recorded in the ledger deducts the charge, not the price.

    The machine costs 1.000,00 and its 2025 charge is 120,00. Casilla 0208 must
    carry exactly 120,00: under RIS art. 3.2 the 1.000,00 purchase is the
    amortizable base, so the register's charge is the whole deduction and the
    purchase row the operator tagged ``hardware_amortizable`` yields to it. The
    withholding is reported rather than silent.
    """
    revision = _revision("100", "2025")
    acquisition = machine_acquisition_transaction("hardware_amortizable")
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    tx_repo.save(TransactionCatalogue.from_transactions((acquisition,)))
    asset = machine_asset(acquisition.transaction_id)
    claim = machine_claim(asset)

    resolution = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=catalogue_read_ports(
            invoice_repository=_InMemoryInvoiceCatalogueRepository(),
            transaction_repository=tx_repo,
        ),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(
            ActivityAssetHistory(revisions=(asset,), claims=(claim,)),
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=revision,
        ),
    )

    assert resolution.binding_values[_renta_expense_binding_id(revision, "0208")] == Decimal("120.00")
    assert Decimal("1000.00") not in resolution.binding_values.values()
    assert Decimal("1120.00") not in resolution.binding_values.values()
    assert resolution.source_transaction_ids == ()
    assert {item.source_ref for item in resolution.provenance} == {f"activity-asset-claim:{claim.claim_id}"}
    withheld = [
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "register_owned_capital_acquisition"
    ]
    assert len(withheld) == 1
    assert withheld[0].source_ref == f"transaction:{acquisition.transaction_id}"
    assert asset.asset_id in withheld[0].message


@pytest.mark.parametrize("period", ["1T", "2T"])
def test_renta_gasto_keeps_only_in_window_held_back_identity_as_durable_evidence(period: str) -> None:
    transaction = renta_transaction("missing-base-gasto", purchase_invoice_evidence_id=None)
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    resolution = LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_reader=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        activity_asset_history_repository=_EmptyActivityAssetHistoryRepository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, period),
            revision=_revision("130", "2019-y-siguientes"),
        )
    )
    held_back = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "source_domain_not_ready"]
    if period == "1T":
        assert held_back == []
    else:
        assert len(held_back) == 1
        assert held_back[0].source_ref == f"transaction:{transaction.transaction_id}"
        assert held_back[0].binding_source is BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION


def test_renta_gasto_source_mesh_declares_only_the_claim_for_a_register_owned_acquisition() -> None:
    """Modelo 130 casilla 02 carries the same 120,00 charge and not the 1.000,00 purchase."""
    revision = _revision("130", "2019-y-siguientes")
    acquisition = machine_acquisition_transaction("hardware_amortizable")
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    tx_repo.save(TransactionCatalogue.from_transactions((acquisition,)))
    asset = machine_asset(acquisition.transaction_id)
    claim = machine_claim(asset)

    resolution = LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_reader=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(
            ActivityAssetHistory(revisions=(asset,), claims=(claim,)),
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision=revision,
        ),
    )
    target_binding = next(
        binding
        for binding in revision.bindings
        if str(binding.source) == "ledger_renta_gastos_pago_fraccionado_aggregation"
    )

    assert resolution.binding_values[target_binding.id] == Decimal("120.00")
    assert resolution.source_transaction_ids == ()
    assert [item.contributor_source_kind for item in resolution.provenance] == ["activity_asset_schedule"]
    assert [
        diagnostic.reason
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "register_owned_capital_acquisition"
    ] == ["register_owned_capital_acquisition"]


def test_renta_gasto_source_mesh_reports_a_separate_depreciation_row_without_refusing() -> None:
    """A depreciation row outside the register's own acquisition is a finding and adds nothing to casilla 02."""
    revision = _revision("130", "2019-y-siguientes")
    acquisition = machine_acquisition_transaction("hardware_amortizable")
    separate_depreciation = machine_acquisition_transaction(
        "mobiliario_amortizable",
        provider_id="separate-depreciation-row",
        amount=Decimal("302.50"),
        taxable_base=Decimal("250.00"),
        iva_amount=Decimal("52.50"),
    )
    tx_repo = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    tx_repo.save(TransactionCatalogue.from_transactions((acquisition, separate_depreciation)))
    asset = machine_asset(acquisition.transaction_id)
    claim = machine_claim(asset)

    resolution = LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
        transaction_repository=tx_repo,
        invoice_reader=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        activity_asset_history_repository=StaticActivityAssetHistoryRepository(
            ActivityAssetHistory(revisions=(asset,), claims=(claim,)),
        ),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "4T"),
            revision=revision,
        ),
    )

    notes = [item for item in resolution.diagnostics if item.reason == "ledger_amortization_row_unregistered"]
    assert [note.source_ref for note in notes] == [f"transaction:{separate_depreciation.transaction_id}"]
    assert resolution.binding_values[_m130_binding_id(revision)] == Decimal("120.00")


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        # 12.000 x 10 % x 90 / 365 = 295,890...
        ("1T", Decimal("295.89")),
        # 12.000 x 10 % x 181 / 365 = 595,068...
        ("2T", Decimal("595.07")),
    ],
)
def test_m130_accrues_from_the_schedule_with_no_claim_and_creates_none(period: str, expected: Decimal) -> None:
    """The static repository refuses any write, so reaching a figure proves none was recorded."""
    row = _prior_year_purchase()
    asset = register_asset("furniture", transaction_id=row.transaction_id)

    resolution = resolve_m130(ActivityAssetHistory(revisions=(asset,)), period, rows=(row,))

    assert m130_box(resolution) == expected
    assert [item.contributor_source_kind for item in resolution.provenance] == ["activity_asset_schedule"]
    assert all(item.source_ref.startswith("activity-asset-schedule:") for item in resolution.provenance)
    assert reasons(resolution) == [_PRIOR_YEAR_ROW_NOTE]


def test_m130_accrual_ignores_a_later_years_claim_and_a_claim_inside_the_year() -> None:
    """Recomputing an earlier quarter stays possible, and an in-year claim does not change the accrual."""
    asset = register_asset("furniture", transaction_id="c" * 64)
    in_year = _register_claim(
        asset,
        amount=Decimal("1000.00"),
        covered_from=date(2025, 1, 1),
        covered_until=date(2025, 11, 1),
    )
    later = _register_claim(asset, amount=Decimal("1200.00"), tax_year=2026)

    resolution = resolve_m130(ActivityAssetHistory(revisions=(asset,), claims=(in_year, later)), "1T")

    assert m130_box(resolution) == Decimal("295.89")


def test_m130_excludes_an_agrarian_element_but_keeps_the_same_taxpayers_other_activity() -> None:
    """RIRPF art. 110.1.c filters by activity: 0 from the farm machine, the full accrual from the other."""
    farm_row = renta_acquisition_row("farm-machine", activity="B01")
    office_row = renta_acquisition_row("office-desk", activity="A05")
    farm = register_asset("farm-machine", transaction_id=farm_row.transaction_id)
    office = register_asset("office-desk", transaction_id=office_row.transaction_id)

    resolution = resolve_m130(ActivityAssetHistory(revisions=(farm, office)), "1T", rows=(farm_row, office_row))

    assert m130_box(resolution) == Decimal("295.89")
    excluded = [item for item in resolution.diagnostics if item.reason == "activity_asset_agrarian_excluded"]
    assert [item.source_ref for item in excluded] == ["activity-asset:farm-machine"]


def test_m130_counts_an_element_with_no_declared_activity_and_says_so_only_beside_an_agrarian_one() -> None:
    silent_row = _prior_year_purchase()
    silent = register_asset("unmarked", transaction_id=silent_row.transaction_id)
    farm_row = renta_acquisition_row("farm-machine", activity="B05")
    farm = register_asset("farm-machine", transaction_id=farm_row.transaction_id)

    alone = resolve_m130(ActivityAssetHistory(revisions=(silent,)), "1T", rows=(silent_row,))
    beside = resolve_m130(ActivityAssetHistory(revisions=(silent, farm)), "1T", rows=(silent_row, farm_row))

    assert m130_box(alone) == Decimal("295.89")
    assert reasons(alone) == [_PRIOR_YEAR_ROW_NOTE]
    assert m130_box(beside) == Decimal("295.89")
    assert "activity_asset_activity_undeclared" in reasons(beside)


def test_m130_free_method_contributes_only_its_claims_ending_within_the_span() -> None:
    asset = register_asset("research-lab", transaction_id="c" * 64, election=_free_election())

    unclaimed = resolve_m130(ActivityAssetHistory(revisions=(asset,)), "1T")
    within = _register_claim(
        asset,
        amount=Decimal("700.00"),
        covered_from=date(2025, 1, 1),
        covered_until=date(2025, 4, 1),
    )
    beyond = _register_claim(
        asset,
        amount=Decimal("300.00"),
        covered_from=date(2025, 4, 1),
        covered_until=date(2025, 7, 1),
    )
    claimed = resolve_m130(ActivityAssetHistory(revisions=(asset,), claims=(within, beyond)), "1T")

    assert m130_box(unclaimed) == Decimal("0")
    gap = [item for item in unclaimed.diagnostics if item.reason == "activity_asset_claim_gap"]
    assert [item.source_ref for item in gap] == ["activity-asset:research-lab"]
    assert m130_box(claimed) == Decimal("700.00")
    assert {item.source_ref for item in claimed.provenance} == {f"activity-asset-claim:{within.claim_id}"}
    assert "activity_asset_claim_gap" not in reasons(claimed)


def test_m130_reports_an_element_whose_schedule_cannot_be_worked_out() -> None:
    row = _prior_year_purchase()
    asset = register_asset("furniture", transaction_id=row.transaction_id).model_copy(
        update={"opening_history": OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING)},
    )

    resolution = resolve_m130(ActivityAssetHistory(revisions=(asset,)), "1T", rows=(row,))

    assert m130_box(resolution) == Decimal("0")
    assert reasons(resolution) == [_PRIOR_YEAR_ROW_NOTE, "activity_asset_accrual_unavailable"]


def test_m100_with_no_claims_invents_nothing_and_reports_the_gap_without_refusing() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64)

    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset,)))

    box = _renta_expense_binding_id(_revision("100", "2025"), "0208")
    assert resolution.binding_values.get(box, Decimal("0")) == Decimal("0")
    assert resolution.provenance == ()
    gaps = [item for item in resolution.diagnostics if item.reason == "activity_asset_claim_gap"]
    assert len(gaps) == 1
    assert "furniture" in gaps[0].message
    assert "2025-01-01 to 2026-01-01" in gaps[0].message
    assert "1200.00 EUR accrued" in gaps[0].message
    assert gaps[0].casilla_id == "0208"
    assert "activity_asset_claim_gap" not in GATE_REFUSED_REASONS
    assert "activity_asset_claim_gap" in UNWORKED_BOX_REASONS
    assert note_attention("activity_asset_claim_gap", box="0208") is ModeloFormAttention.CHECK


def test_m100_reports_only_the_uncovered_part_of_the_year_at_its_cumulative_amount() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64)
    first_half = _register_claim(
        asset,
        amount=Decimal("595.07"),
        covered_from=date(2025, 1, 1),
        covered_until=date(2025, 7, 1),
    )

    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset,), claims=(first_half,)))

    gaps = [item for item in resolution.diagnostics if item.reason == "activity_asset_claim_gap"]
    assert len(gaps) == 1
    assert "2025-07-01 to 2026-01-01" in gaps[0].message
    # 1.200,00 less the 595,07 the first half rounds to.
    assert "604.93 EUR accrued" in gaps[0].message
    # A box that does carry a claim keeps its figure rather than reading as unworked.
    assert gaps[0].casilla_id is None
    box = _renta_expense_binding_id(_revision("100", "2025"), "0208")
    assert resolution.binding_values[box] == Decimal("595.07")


def test_a_gap_in_a_past_year_neither_blocks_nor_is_reported_in_a_later_year() -> None:
    asset = register_asset("furniture", transaction_id="c" * 64, in_service=date(2024, 1, 1))
    current_year = _register_claim(asset, amount=Decimal("1200.00"))

    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset,), claims=(current_year,)))

    assert "activity_asset_claim_gap" not in reasons(resolution)
    assert not set(reasons(resolution)) & GATE_REFUSED_REASONS


def test_with_complete_claims_m130_fourth_quarter_equals_0208_plus_0227() -> None:
    """Hand-worked: 12.000 x 10 % = 1.200,00 material; 1.000 x 5 % goodwill = 50,00 intangible."""
    material = register_asset("furniture", transaction_id="c" * 64)
    intangible = register_asset(
        "goodwill",
        transaction_id="f" * 64,
        basis=Decimal("1000.00"),
        kind=AssetKind.INTANGIBLE,
        election=ActivityAssetAmortizationElection(
            regime=DirectEstimationRegime.NORMAL,
            method=AmortizationMethod.GOODWILL,
        ),
    )
    history = ActivityAssetHistory(
        revisions=(material, intangible),
        claims=(
            _register_claim(material, amount=Decimal("1200.00")),
            _register_claim(intangible, amount=Decimal("50.00")),
        ),
    )

    annual = resolve_m100(history)
    quarterly = resolve_m130(history, "4T")

    revision = _revision("100", "2025")
    material_box = annual.binding_values[_renta_expense_binding_id(revision, "0208")]
    assert material_box == Decimal("1200.00")
    assert m130_box(quarterly) == Decimal("1250.00")
    intangible_binding = next(
        (
            binding.id
            for binding in revision.bindings
            if str(binding.source) == "ledger_renta_gastos_estimacion_directa_aggregation"
            and str(getattr(binding.provider, "target_casilla_id", None)) == "0227"
        ),
        None,
    )
    if intangible_binding is None:
        # A published edition with no 0227 binding must say the 50,00 reached no box.
        unrouted = [item for item in annual.diagnostics if item.reason == "unrouted_observation"]
        assert len(unrouted) == 1
        assert "50.00" in unrouted[0].message
    else:
        assert m130_box(quarterly) == material_box + annual.binding_values[intangible_binding]
    assert "activity_asset_claim_gap" not in reasons(annual)


@pytest.mark.parametrize(
    ("amount", "taxable_base", "iva_amount"),
    [
        # Within the low-value limit: the ledger route would have deducted it.
        (Decimal("242.00"), Decimal("200.00"), Decimal("42.00")),
        # Above the limit: the rule refuses it before it can become an observation.
        (Decimal("1210.00"), Decimal("1000.00"), Decimal("210.00")),
    ],
)
def test_an_unowned_amortization_row_is_a_finding_on_both_returns_with_no_register_at_all(
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> None:
    row = machine_acquisition_transaction(
        "hardware_amortizable",
        provider_id="unregistered-machine",
        amount=amount,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
    )

    annual = resolve_m100(ActivityAssetHistory(), rows=(row,))
    quarterly = resolve_m130(ActivityAssetHistory(), "2T", rows=(row,))

    for resolution in (annual, quarterly):
        notes = [item for item in resolution.diagnostics if item.reason == "ledger_amortization_row_unregistered"]
        assert [note.source_ref for note in notes] == [f"transaction:{row.transaction_id}"]
        assert notes[0].reason not in GATE_REFUSED_REASONS
        assert note_attention(notes[0].reason, box=None) is ModeloFormAttention.CHECK
        assert resolution.source_transaction_ids == ()
    assert annual.binding_values.get(_renta_expense_binding_id(_revision("100", "2025"), "0208"), Decimal("0")) == 0
    assert m130_box(quarterly) == Decimal("0")


def test_a_register_owned_row_is_withheld_not_blocked_even_with_no_claim() -> None:
    row = machine_acquisition_transaction("hardware_amortizable")
    asset = register_asset("machine", transaction_id=row.transaction_id, basis=Decimal("1000.00"))

    resolution = resolve_m130(ActivityAssetHistory(revisions=(asset,)), "2T", rows=(row,))

    assert "ledger_amortization_row_unregistered" not in reasons(resolution)
    assert "register_owned_capital_acquisition" in reasons(resolution)


@pytest.mark.parametrize("resolve", [resolve_m100, lambda history, **kwargs: resolve_m130(history, "1T", **kwargs)])
def test_a_foral_period_leaves_registered_assets_out_with_a_finding_and_refuses_nothing(resolve, operation) -> None:
    row = _prior_year_purchase()
    asset = register_asset("furniture", transaction_id=row.transaction_id)
    claim = _register_claim(asset, amount=Decimal("1200.00"))
    profile = ModeloWorkProfile(
        record=_create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X1234567L"),
                UserProfileFact(path="tax_residence.ccaa", value="navarra"),
            ),
            context=_profile_creation_context_for_test(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )

    resolution = resolve(ActivityAssetHistory(revisions=(asset,), claims=(claim,)), rows=(row,), profile=profile)
    no_register = resolve(ActivityAssetHistory(), profile=profile)

    assert reasons(resolution) == [_PRIOR_YEAR_ROW_NOTE, "activity_asset_foral_territory"]
    assert "activity_asset_foral_territory" not in GATE_REFUSED_REASONS
    assert "foral rules" in resolution.diagnostics[1].remedy
    assert sum(resolution.binding_values.values(), Decimal("0")) == Decimal("0")
    assert resolution.provenance == ()
    assert reasons(no_register) == []


@pytest.mark.parametrize("resolve", [resolve_m100, lambda history, **kwargs: resolve_m130(history, "1T", **kwargs)])
def test_an_unreadable_residence_leaves_registered_assets_out_with_a_finding(resolve, operation) -> None:
    row = _prior_year_purchase()
    asset = register_asset("furniture", transaction_id=row.transaction_id)
    claim = _register_claim(asset, amount=Decimal("1200.00"))
    profile = ModeloWorkProfile(
        record=_create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X1234567L"),
                UserProfileFact(path="tax_residence.ccaa", value="not-a-region"),
            ),
            context=_profile_creation_context_for_test(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )

    resolution = resolve(ActivityAssetHistory(revisions=(asset,), claims=(claim,)), rows=(row,), profile=profile)
    no_register = resolve(ActivityAssetHistory(), profile=profile)

    assert reasons(resolution) == [_PRIOR_YEAR_ROW_NOTE, "activity_asset_residence_unresolved"]
    assert "activity_asset_residence_unresolved" not in GATE_REFUSED_REASONS
    assert sum(resolution.binding_values.values(), Decimal("0")) == Decimal("0")
    assert resolution.provenance == ()
    assert reasons(no_register) == []


def test_an_unreadable_history_surfaces_as_a_typed_diagnostic_on_both_resolvers() -> None:
    annual = LedgerRentaGastosEstimacionDirectaAggregationSourceResolver(
        ports=_empty_catalogue_read_ports(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=lambda *, bucket_id, operation: UsageRatioProfile(),
        activity_asset_history_repository=_UnreadableActivityAssetHistoryRepository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=_revision("100", "2025"),
        ),
    )
    quarterly = LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
        transaction_repository=InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID),
        invoice_reader=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        activity_asset_history_repository=_UnreadableActivityAssetHistoryRepository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "1T"),
            revision=_revision("130", "2019-y-siguientes"),
        ),
    )

    assert set(reasons(annual)) == {"storage_degraded"}
    assert set(reasons(quarterly)) == {"storage_degraded"}
    assert annual.binding_values == {}
    assert quarterly.binding_values == {}


@pytest.mark.parametrize("year", _filing_years())
def test_an_intangible_claim_reaches_0227_and_a_material_claim_reaches_0208_in_every_year(year: int) -> None:
    revision = _m100_revision(year)
    material = register_asset("furniture", transaction_id="c" * 64, in_service=date(year, 1, 1))
    intangible = register_asset(
        "licence",
        transaction_id="d" * 64,
        in_service=date(year, 1, 1),
        kind=AssetKind.INTANGIBLE,
    )
    history = ActivityAssetHistory(
        revisions=(material, intangible),
        claims=(
            _register_claim(material, amount=Decimal("1200.00"), tax_year=year),
            _register_claim(intangible, amount=Decimal("700.00"), tax_year=year),
        ),
    )

    resolution = resolve_m100(history, year=year)

    assert resolution.binding_values[_renta_expense_binding_id(revision, "0208")] == Decimal("1200.00")
    assert resolution.binding_values[_renta_expense_binding_id(revision, "0227")] == Decimal("700.00")
    assert "unrouted_observation" not in reasons(resolution)
    assert "activity_asset_claim_gap" not in reasons(resolution)


@pytest.mark.parametrize("category", _AMORTIZABLE_CATEGORIES)
@pytest.mark.parametrize("year", _filing_years())
def test_no_ledger_category_reaches_0208_or_0227_and_the_unowned_row_is_reported(year: int, category: str) -> None:
    revision = _m100_revision(year)
    row = machine_acquisition_transaction(category, provider_id=f"unregistered-{category}", year=year)

    resolution = resolve_m100(ActivityAssetHistory(), rows=(row,), year=year)

    for casilla in ("0208", "0227"):
        assert resolution.binding_values.get(_renta_expense_binding_id(revision, casilla), Decimal("0")) == 0
    assert resolution.source_transaction_ids == ()
    notes = [item for item in resolution.diagnostics if item.reason == "ledger_amortization_row_unregistered"]
    assert [note.source_ref for note in notes] == [f"transaction:{row.transaction_id}"]
    assert "unrouted_observation" not in reasons(resolution)


@pytest.mark.parametrize("category", _AMORTIZABLE_CATEGORIES)
@pytest.mark.parametrize("year", _filing_years())
def test_a_register_owned_row_without_a_claim_yields_a_non_blocking_gap_and_no_deduction(
    year: int,
    category: str,
) -> None:
    revision = _m100_revision(year)
    row = machine_acquisition_transaction(category, provider_id=f"owned-{category}", year=year)
    asset = register_asset(
        "furniture",
        transaction_id=row.transaction_id,
        basis=Decimal("1000.00"),
        in_service=date(year, 1, 1),
    )

    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset,)), rows=(row,), year=year)

    for casilla in ("0208", "0227"):
        assert resolution.binding_values.get(_renta_expense_binding_id(revision, casilla), Decimal("0")) == 0
    assert "ledger_amortization_row_unregistered" not in reasons(resolution)
    gaps = [item for item in resolution.diagnostics if item.reason == "activity_asset_claim_gap"]
    assert len(gaps) == 1
    assert gaps[0].reason not in GATE_REFUSED_REASONS
