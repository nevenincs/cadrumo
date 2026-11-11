"""A MIXED ledger row deducts what the law grants, whichever door the calculation came through.

Every figure below is worked by hand from a 100.00 base and a 21.00 cuota, or a
4,000.00 base and an 840.00 cuota for a good worth a bien de inversión:

- IVA (LIVA art. 95): simultaneous use deducts nothing, except a bien de inversión
  at its degree of use (Tres.1.ª), a vehicle at the presumed 50 per cent (Tres.2.ª),
  and what follows one of them (Cuatro).
- Renta: a share of the base, except a home-office suministro at the operator's
  usage ratio (LIRPF art. 30.2.5.ª b, 0.20 here) and an indivisible element, which
  admits no partial affectation (RIRPF art. 22.3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.categories.spending_category_catalogue import require_spending_category
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.history import ActivityAssetHistory
from ...ledger.preflight import OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE
from ...modelo.work_profile import ModeloWorkProfile
from ..iva_ledger import IvaLedgerAggregationIssueReason, aggregate_iva_ledger_observations
from ..modelo_bindings_renta_expenses import LedgerRentaGastosPagoFraccionadoAggregationSourceResolver
from ..renta_business_eligibility import RentaExpenseAdvisoryReason
from ..renta_gasto_ledger import (
    RentaGastoLedgerAggregation,
    RentaGastoLedgerAggregationIssueReason,
    aggregate_renta_gasto_ledger,
)
from ..renta_ledger import aggregate_renta_ledger_expenses
from ..renta_ledger_models import RentaLedgerAggregationIssueReason, RentaLedgerExpenseAggregation
from ..source_mesh import CalculationSourceContext
from .ledger_source_mesh_support import (
    BUCKET_ID,
    EmptyActivityAssetHistoryRepository,
    InMemoryTransactionCatalogueRepository,
    cash_criterion_profile,
    empty_invoice_repository,
    empty_prorrata_repository,
    ledger_iva_resolver,
    ledger_source_mesh_revision,
    m130_box,
    resolve_m100,
)
from .ledger_transaction_support import iva_transaction
from .usage_ratio_support import no_stored_usage_ratios

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = 2025
_QUARTER = Period.from_year_and_code(_YEAR, "1T")
_ANNUAL = Period.from_year_and_code(_YEAR, "0A")
_USAGE_RATIO = Decimal("0.20")
_MIXED = BusinessClassification.MIXED
_BUSINESS = BusinessClassification.BUSINESS


def _row(
    category: str | None,
    *,
    classification: BusinessClassification = _MIXED,
    share: Decimal | None = Decimal("0.50"),
    base: Decimal = Decimal("100.00"),
    cuota: Decimal = Decimal("21.00"),
) -> Transaction:
    return iva_transaction(
        "mixed-use",
        direction=TransactionDirection.OUTGOING,
        amount=base + cuota,
        taxable_base=base,
        iva_amount=cuota,
        booked_date=date(_YEAR, 2, 10),
    ).model_copy(
        update={
            "business_classification": classification,
            "business_pct": share if classification is _MIXED else None,
            "category_id": category,
        }
    )


def _iva(row: Transaction, operation: PinnedAuthorityOperation) -> list[object]:
    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((row,)),
        period=_QUARTER,
        ledger_profile_id="mixed-use",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="mixed-use",
        operation=operation,
    )
    return [*(o.iva_amount for o in result.observations), *(i.reason for i in result.issues)]


def _ratios(operation: PinnedAuthorityOperation) -> dict[SpendingCategory, Decimal]:
    return {
        require_spending_category(token, authority=operation): _USAGE_RATIO
        for token in ("suministros_home_office_luz", "telefonia_fija")
    }


def _gasto(row: Transaction, operation: PinnedAuthorityOperation) -> RentaGastoLedgerAggregation:
    return aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions((row,)),
        bucket_id=BUCKET_ID,
        period=_QUARTER,
        modelo="130",
        target_casilla_id="02",
        accept_activity_marker=True,
        usage_ratios=_ratios(operation),
        operation=operation,
    )


def _annual(row: Transaction, operation: PinnedAuthorityOperation) -> RentaLedgerExpenseAggregation:
    return aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((row,)),
        InvoiceCatalogue(),
        bucket_id=BUCKET_ID,
        period=_ANNUAL,
        profile_year=_YEAR,
        usage_ratios=_ratios(operation),
        operation=operation,
    )


_NOTHING = IvaLedgerAggregationIssueReason.NON_DEDUCTIBLE_MIXED_USE
_LARGE = {"base": Decimal("4000.00"), "cuota": Decimal("840.00")}


@pytest.mark.parametrize(
    ("category", "classification", "amounts", "expected"),
    [
        # The degree of use, on a lease and a repair of a bien de inversión and on suministros.
        ("arrendamiento_local", _MIXED, {}, Decimal("10.50")),
        ("reparaciones_conservacion", _MIXED, {}, Decimal("10.50")),
        ("suministros_local_afecto", _MIXED, {}, Decimal("10.50")),
        ("suministros_home_office_luz", _MIXED, {}, Decimal("10.50")),
        ("telefonia_fija", _MIXED, {}, Decimal("10.50")),
        # A bien de inversión only from the art. 108.Dos.5.º value: half of 840.00.
        ("hardware_amortizable", _MIXED, _LARGE, Decimal("420.00")),
        ("mobiliario_amortizable", _MIXED, _LARGE, Decimal("420.00")),
        ("hardware_amortizable", _MIXED, {}, _NOTHING),
        # The vehicle presumption, whatever the row states.
        ("vehiculo_combustible", _MIXED, {}, Decimal("10.50")),
        ("vehiculo_peaje", _MIXED, {}, Decimal("10.50")),
        ("vehiculo_combustible", _BUSINESS, {}, Decimal("10.50")),
        # Simultaneous use of anything else deducts nothing.
        ("telefonia_movil", _MIXED, {}, _NOTHING),
        ("asesoria_fiscal", _MIXED, {}, _NOTHING),
        ("material_oficina", _MIXED, {}, _NOTHING),
        ("vehiculo_seguro", _MIXED, {}, _NOTHING),
        # Exclusive use deducts in full, with or without a category.
        ("asesoria_fiscal", _BUSINESS, {}, Decimal("21.00")),
        (None, _BUSINESS, {}, Decimal("21.00")),
        # Only the category can say which of these a mixed row is.
        (None, _MIXED, {}, IvaLedgerAggregationIssueReason.UNDETERMINED_MIXED_USE_TREATMENT),
        ("no_such_category", _MIXED, {}, IvaLedgerAggregationIssueReason.UNDETERMINED_MIXED_USE_TREATMENT),
    ],
)
def test_iva_deducts_what_the_category_grants(
    category: str | None,
    classification: BusinessClassification,
    amounts: dict[str, Decimal],
    expected: object,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    assert _iva(_row(category, classification=classification, **amounts), operation) == [expected]


_NOT_SCALED_FURTHER = Decimal("20.00")


@pytest.mark.parametrize(
    ("category", "classification", "quarterly", "annual", "advisory"),
    [
        # An eligible usage-ratio category applies the operator's ratio once.
        ("suministros_home_office_luz", _MIXED, _NOT_SCALED_FURTHER, _NOT_SCALED_FURTHER, None),
        # Outside one, the share of the base stands and the question is reported.
        (
            "asesoria_fiscal",
            _MIXED,
            Decimal("50.00"),
            Decimal("50.00"),
            RentaExpenseAdvisoryReason.MIXED_SHARE_OUTSIDE_USAGE_RATIO,
        ),
        (
            "arrendamiento_local",
            _MIXED,
            Decimal("50.00"),
            Decimal("50.00"),
            RentaExpenseAdvisoryReason.MIXED_SHARE_OUTSIDE_USAGE_RATIO,
        ),
        # A row wholly business is no question of share.
        ("asesoria_fiscal", _BUSINESS, Decimal("100.00"), Decimal("100.00"), None),
    ],
)
def test_renta_figures_stand_and_only_the_open_reading_is_reported(
    category: str,
    classification: BusinessClassification,
    quarterly: Decimal,
    annual: Decimal,
    advisory: RentaExpenseAdvisoryReason | None,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    row = _row(category, classification=classification)
    expected = [advisory] if advisory is not None else []

    gasto = _gasto(row, operation)
    assert [o.deductible_amount for o in gasto.observations] == [quarterly]
    assert [a.reason for a in gasto.advisories] == expected

    first_slice = _annual(row, operation)
    assert [o.deductible_amount for o in first_slice.observations] == [annual]
    assert [a.reason for a in first_slice.advisories] == expected


@pytest.mark.parametrize("category", ["telefonia_movil", "vehiculo_combustible"])
def test_an_indivisible_element_still_admits_no_share_in_renta(
    category: str, *, operation: PinnedAuthorityOperation
) -> None:
    gasto = _gasto(_row(category), operation)
    assert gasto.observations == ()
    assert [issue.reason for issue in gasto.issues] == [RentaGastoLedgerAggregationIssueReason.EXCLUSIVE_USE_REQUIRED]
    assert gasto.advisories == ()


def test_an_uncategorized_mixed_gasto_is_held_rather_than_counted_at_its_share(
    *, operation: PinnedAuthorityOperation
) -> None:
    gasto = _gasto(_row(None), operation)
    assert gasto.observations == ()
    assert [issue.reason for issue in gasto.issues] == [RentaGastoLedgerAggregationIssueReason.MISSING_CATEGORY]
    assert gasto.advisories == ()


def test_an_uncategorized_whole_business_gasto_is_held_as_the_annual_expense_is(
    *, operation: PinnedAuthorityOperation
) -> None:
    row = _row(None, classification=_BUSINESS)
    gasto = _gasto(row, operation)
    assert gasto.observations == ()
    assert gasto.advisories == ()
    assert [issue.reason.value for issue in gasto.issues] == [
        issue.reason.value for issue in _annual(row, operation).issues
    ]
    assert [issue.reason for issue in gasto.issues] == [RentaGastoLedgerAggregationIssueReason.MISSING_CATEGORY]
    resolution = _gasto_resolution(row)
    assert [diagnostic.source_ref for diagnostic in resolution.diagnostics] == [f"transaction:{row.transaction_id}"]
    assert resolution.diagnostics[0].reason == "source_domain_not_ready"
    assert row.transaction_id not in resolution.source_transaction_ids


@pytest.mark.parametrize("classification", [_MIXED, _BUSINESS])
def test_an_unknown_category_is_a_typed_finding_in_both_renta_pipelines(
    classification: BusinessClassification, *, operation: PinnedAuthorityOperation
) -> None:
    row = _row("gastos_sin_catalogo", classification=classification)
    gasto = _gasto(row, operation)
    annual = _annual(row, operation)
    assert gasto.observations == ()
    assert annual.observations == ()
    assert [issue.reason for issue in gasto.issues] == [RentaGastoLedgerAggregationIssueReason.UNKNOWN_CATEGORY]
    assert [issue.reason for issue in annual.issues] == [RentaLedgerAggregationIssueReason.UNKNOWN_CATEGORY]
    assert "gastos_sin_catalogo" in gasto.issues[0].detail


def test_an_unknown_category_blocks_the_payment_and_the_annual_declaration_through_the_source_mesh() -> None:
    row = _row("gastos_sin_catalogo", classification=_BUSINESS)
    for resolution in (_gasto_resolution(row), resolve_m100(ActivityAssetHistory(), rows=(row,))):
        held_back = [d for d in resolution.diagnostics if d.reason == "source_domain_not_ready"]
        assert [d.source_ref for d in held_back] == [f"transaction:{row.transaction_id}"]
        assert "gastos_sin_catalogo" in held_back[0].message


@pytest.mark.parametrize("classification", [_MIXED, _BUSINESS])
def test_the_annual_expense_still_refuses_any_uncategorized_row(
    classification: BusinessClassification, *, operation: PinnedAuthorityOperation
) -> None:
    annual = _annual(_row(None, classification=classification), operation)
    assert annual.observations == ()
    assert [issue.reason for issue in annual.issues] == [RentaLedgerAggregationIssueReason.MISSING_CATEGORY]


def test_the_undetermined_iva_row_asks_the_operator_for_a_fact() -> None:
    assert (
        OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE[
            IvaLedgerAggregationIssueReason.UNDETERMINED_MIXED_USE_TREATMENT
        ].value
        == "supply_manual_input"
    )


def _repository(row: Transaction) -> InMemoryTransactionCatalogueRepository:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions((row,)))
    return repository


def test_the_iva_refusal_blocks_through_the_source_mesh_without_any_preflight() -> None:
    row = _row(None)
    resolution = ledger_iva_resolver(
        transaction_repository=_repository(row),
        invoice_repository=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=_QUARTER,
            revision=ledger_source_mesh_revision("303", "2022"),
        ),
    )
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["iva_selected_scope_evidence_failure"]
    assert resolution.diagnostics[0].source_ref == f"transaction:{row.transaction_id}"
    assert "undetermined_mixed_use_treatment" in resolution.diagnostics[0].message
    assert row.transaction_id not in resolution.source_transaction_ids


def _gasto_resolution(row: Transaction, *, profile: ModeloWorkProfile | None = None):
    return LedgerRentaGastosPagoFraccionadoAggregationSourceResolver(
        transaction_repository=_repository(row),
        invoice_reader=empty_invoice_repository(),
        prorrata_register_repository=empty_prorrata_repository(),
        usage_ratio_profile_loader=no_stored_usage_ratios,
        activity_asset_history_repository=EmptyActivityAssetHistoryRepository(),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="130",
            filing_year=_YEAR,
            period=_QUARTER,
            revision=ledger_source_mesh_revision("130", "2019-y-siguientes"),
            profile=profile,
        ),
    )


def test_the_gasto_refusal_blocks_through_the_source_mesh_without_any_preflight() -> None:
    row = _row(None)
    resolution = _gasto_resolution(row)
    held_back = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "source_domain_not_ready"]
    assert [diagnostic.source_ref for diagnostic in held_back] == [f"transaction:{row.transaction_id}"]
    assert held_back[0].binding_source is BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION


def test_a_kept_share_reaches_the_calculation_as_an_advisory_and_not_a_blocker() -> None:
    row = _row("asesoria_fiscal")
    resolution = _gasto_resolution(row, profile=cash_criterion_profile(_YEAR))
    assert [diagnostic.reason for diagnostic in resolution.diagnostics] == ["source_issue"]
    assert "art. 29.2" in resolution.diagnostics[0].message
    assert row.transaction_id in resolution.source_transaction_ids


def test_a_kept_share_in_a_year_with_no_criterion_cannot_be_placed() -> None:
    """RIRPF art. 7 picks the year, and no default stands in for an undeclared election."""
    row = _row("asesoria_fiscal")
    resolution = _gasto_resolution(row)
    assert {diagnostic.reason for diagnostic in resolution.diagnostics} == {"unresolved_binding"}
    assert row.transaction_id not in resolution.source_transaction_ids


def _accrual_profile() -> ModeloWorkProfile:
    cash = cash_criterion_profile(_YEAR)
    facts = tuple(
        UserProfileFact.model_validate(
            {"path": fact.path, "value": "devengo", "valid_from": fact.valid_from, "valid_to": fact.valid_to}
        )
        if fact.path == "irpf.activity_income_imputation_criterion"
        else fact
        for fact in cash.record.facts
    )
    return replace(cash, record=cash.record.model_copy(update={"facts": facts}))


@pytest.mark.parametrize("classification", [_MIXED, _BUSINESS])
@pytest.mark.parametrize("profile_of", [lambda: None, lambda: cash_criterion_profile(_YEAR), _accrual_profile])
def test_a_row_with_no_category_is_held_for_its_category_under_every_criterion(
    classification: BusinessClassification, profile_of: Callable[[], ModeloWorkProfile | None]
) -> None:
    """Undeclared, cash, and accrual with no document all name the category, as the annual declaration does."""
    row = _row(None, classification=classification)
    resolution = _gasto_resolution(row, profile=profile_of())
    held_back = [d for d in resolution.diagnostics if d.reason == "source_domain_not_ready"]
    assert [d.source_ref for d in held_back] == [f"transaction:{row.transaction_id}"]
    assert "spending category" in held_back[0].message
    assert row.transaction_id not in resolution.source_transaction_ids
    assert m130_box(resolution) == Decimal("0")
