"""A bien de inversión reaches its own deducible boxes on Modelo 303 and 390.

Every Modelo 303 diseño de registro from 2022 onwards asks for the cuota
soportada in pairs split by what was acquired: operaciones interiores corrientes
[28]/[29] against bienes de inversión [30]/[31], importaciones [32]/[33] against
[34]/[35], adquisiciones intracomunitarias [36]/[37] against [38]/[39], and box
[45] adds the cuotas. Modelo 390 restates the year in [48]/[49] against
[50]/[51] and [52]/[53] against [54]/[55]. The rows of a pair share category,
rate and flow; only their fact-0085 deduction kind, backed by a reciprocal
bienes-inversión register record, tells them apart.

The quarter below is the second trimester of the Manual práctico de IVA worked
example (chapter 9, "La declaración-resumen anual. Modelo 390"): its interior
purchases split into 11.970 euros of corrientes cuota and the 1.050 euros of a
bien de inversión, 13.020 euros in all, its import is 7.560 euros of corrientes
cuota and its intra-community acquisitions 4.410 euros. The investment import
and the intra-community bien de inversión are synthetic, chosen so no two boxes
share a figure. Every expected value is stated from that arithmetic, never read
back from the implementation.

Real rows go through the real ledger aggregation, the published registry's
``ledger_iva_aggregation`` resolver and the registry formula runtime.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionValidationError,
)
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import aggregate_iva_ledger_observations, resolve_iva_ledger_binding_values
from .ledger_transaction_support import ledger_raw_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "bienes-inversion-box-routing"
_DOMESTIC = IvaCategory("domestic_general")
_IMPORT = IvaCategory("import_third_country")
_AIC = IvaCategory("intra_community_acquisition_reverse_charge")
_SELF_ASSESSED = frozenset({_IMPORT, _AIC})
_EVIDENCE_BY_CATEGORY = {
    _DOMESTIC: "invoice_evidence",
    _IMPORT: "customs_declaration",
    _AIC: "intra_eu_self_assessment",
}


@dataclass(frozen=True, slots=True)
class _Purchase:
    """One received operation: its base, its 21 % cuota and its deduction kind."""

    label: str
    category: IvaCategory
    kind: str
    base: Decimal
    cuota: Decimal
    asset_id: str | None = None


def _transaction(purchase: _Purchase, booked: date) -> Transaction:
    # An import or intra-community cuota is not paid to the supplier, so the
    # movement is the base alone; a domestic purchase pays base plus cuota.
    gross = purchase.base if purchase.category in _SELF_ASSESSED else purchase.base + purchase.cuota
    fields: dict[str, object] = {
        "raw": ledger_raw_transaction(f"{purchase.label}-{booked.isoformat()}", booked_date=booked, amount=gross),
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "material_oficina",
        "taxable_base": purchase.base,
        "iva_rate": Decimal("0.21"),
        "iva_amount": purchase.cuota,
        "iva_category": purchase.category,
        "deduction_fact_kind": IvaDeductionFactKind.from_registry(purchase.kind),
        "deduction_provenance": IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry(_EVIDENCE_BY_CATEGORY[purchase.category]),
            source_locator=f"evidence:{purchase.label}",
            evidence_digest="b" * 64,
        ),
        "investment_asset_id": purchase.asset_id,
        "classified_at": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        "classified_by": "manual",
    }
    if purchase.category == _AIC:
        fields["counterparty_country"] = "DE"
        fields["counterparty_identification_state"] = "DE"
    return Transaction.model_validate(fields)


def _register(transactions: Iterable[tuple[_Purchase, Transaction]], *, year: int) -> BienesInversionIvaRegister:
    """The reciprocal register records every investment row names, and nothing else."""
    return BienesInversionIvaRegister(
        records=tuple(
            BienInversionIvaRecord(
                identifier=purchase.asset_id,
                description=f"Bien de inversión {purchase.label}",
                acquisition_year=year,
                cuota_soportada=purchase.cuota,
                prorrata_inicial_pct=Decimal("100"),
                kind=BienInversionKind.from_registry("mueble"),
                acquisition_ledger_id=transaction.transaction_id,
            )
            for purchase, transaction in transactions
            if purchase.asset_id is not None
        ),
    )


def _observations(
    dated: Iterable[tuple[_Purchase, date]],
    *,
    period: Period,
    register_year: int,
    operation: PinnedAuthorityOperation,
) -> Sequence[IvaLedgerObservation]:
    pairs = tuple((purchase, _transaction(purchase, booked)) for purchase, booked in dated)
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(tuple(transaction for _, transaction in pairs)),
        period=period,
        ledger_profile_id=_PROFILE_ID,
        investment_asset_register=_register(pairs, year=register_year),
        investment_asset_profile_id=_PROFILE_ID,
        operation=operation,
    )
    assert aggregation.issues == (), aggregation.issues
    return aggregation.observations


def _calculate(
    snapshot: RegistrySnapshot,
    observations: Iterable[IvaLedgerObservation],
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[CasillaId, Decimal]:
    """Resolve the ledger bindings onto their casillas and run the revision's formulas.

    Every other binding -- the prior-period compensación, profile facts,
    operator inputs, the 303 fold-ins of the annual return, and the prorrata
    and bienes-inversión regularisations, none of which this ledger carries --
    is supplied as zero so the formula chain can run.
    """
    ledger_values = resolve_iva_ledger_binding_values(
        snapshot.revision,
        tuple(observations),
        prorrata_apportionment=None,
        operation=operation,
    )
    others: dict[BindingId, Decimal] = {
        binding.id: Decimal("0") for binding in snapshot.revision.bindings if binding.id not in ledger_values
    }
    calculation = calculate_registry_snapshot(
        snapshot,
        inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, ledger_values),
        date_context={},
        binding_values=others,
    )
    return calculation.values


def _box(values: Mapping[CasillaId, Decimal], casilla_id: str) -> Decimal:
    return values[validated_casilla_id(casilla_id)]


# The Manual práctico's second-trimester purchases, numbered as the manual numbers them.
_MANUAL_QUARTER = (
    _Purchase("compras-15", _DOMESTIC, "domestic_current", Decimal("1800.00"), Decimal("378.00")),
    _Purchase("servicios-13", _DOMESTIC, "domestic_current", Decimal("30000.00"), Decimal("6300.00")),
    _Purchase("servicios-18", _DOMESTIC, "domestic_current", Decimal("1200.00"), Decimal("252.00")),
    _Purchase("servicios-24", _DOMESTIC, "domestic_current", Decimal("24000.00"), Decimal("5040.00")),
    _Purchase("bien-inversion-22", _DOMESTIC, "domestic_investment", Decimal("5000.00"), Decimal("1050.00"), "BI-22"),
    _Purchase("importacion-11", _IMPORT, "import_current", Decimal("36000.00"), Decimal("7560.00")),
    _Purchase("importacion-bi", _IMPORT, "import_investment", Decimal("10000.00"), Decimal("2100.00"), "BI-IMP"),
    _Purchase("aic-corriente", _AIC, "intra_eu_current", Decimal("21000.00"), Decimal("4410.00")),
    _Purchase("aic-bi", _AIC, "intra_eu_investment", Decimal("8000.00"), Decimal("1680.00"), "BI-AIC"),
)

# Each supported filing year, at a quarter inside it; 2024 carries two editions.
_QUARTERS = (
    (2022, "2T", 5),
    (2023, "2T", 5),
    (2024, "2T", 5),
    (2024, "4T", 11),
    (2025, "2T", 5),
    (2026, "2T", 5),
)


@pytest.mark.parametrize(("filing_year", "period", "month"), _QUARTERS)
def test_each_deducible_pair_splits_corrientes_from_bienes_de_inversion(
    filing_year: int,
    period: str,
    month: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    booked = date(filing_year, month, 10)
    observations = _observations(
        ((purchase, booked) for purchase in _MANUAL_QUARTER),
        period=Period.from_year_and_code(filing_year, period),
        register_year=filing_year,
        operation=operation,
    )

    values = _calculate(
        operation.snapshot("303", filing_year=filing_year, period=period), observations, operation=operation
    )

    # Interiores: 1.800 + 30.000 + 1.200 + 24.000 of corrientes base carrying
    # 378 + 11.592 = 11.970 of cuota; the bien de inversión alone in [30]/[31].
    assert _box(values, "28") == Decimal("57000.00")
    assert _box(values, "iva.soportado.interiores") == Decimal("11970.00")
    assert _box(values, "30") == Decimal("5000.00")
    assert _box(values, "31") == Decimal("1050.00")
    # The manual's "Total cuotas soportadas en operaciones interiores".
    assert _box(values, "iva.soportado.interiores") + _box(values, "31") == Decimal("13020.00")
    # Importaciones: the manual's 36.000 x 21 % in the corrientes cuota, the
    # investment import alone in [34]/[35].
    assert _box(values, "iva.soportado.importaciones") == Decimal("7560.00")
    assert _box(values, "34") == Decimal("10000.00")
    assert _box(values, "35") == Decimal("2100.00")
    # Adquisiciones intracomunitarias, deducible side.
    assert _box(values, "iva.autorepercutido.intracomunitaria.deducible") == Decimal("4410.00")
    assert _box(values, "38") == Decimal("8000.00")
    assert _box(values, "39") == Decimal("1680.00")
    # Box [45]: 11.970 + 1.050 + 7.560 + 2.100 + (4.410 + 1.680) = 28.770. The
    # intra-community pair enters once, through its self-assessed total.
    assert _box(values, "iva.cuota-deducible-total") == Decimal("28770.00")


@pytest.mark.parametrize(("filing_year", "period", "month"), [row for row in _QUARTERS if row[0] >= 2023])
def test_the_numbered_corrientes_boxes_carry_only_the_corrientes_cuota(
    filing_year: int,
    period: str,
    month: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """From 2023 the numbered cuota boxes project their sources, and [45] projects the total."""
    booked = date(filing_year, month, 10)
    observations = _observations(
        ((purchase, booked) for purchase in _MANUAL_QUARTER),
        period=Period.from_year_and_code(filing_year, period),
        register_year=filing_year,
        operation=operation,
    )

    values = _calculate(
        operation.snapshot("303", filing_year=filing_year, period=period), observations, operation=operation
    )

    assert _box(values, "29") == Decimal("11970.00")
    assert _box(values, "33") == Decimal("7560.00")
    assert _box(values, "37") == Decimal("4410.00")
    assert _box(values, "45") == Decimal("28770.00")


def test_an_investment_row_without_its_register_record_reaches_no_box(*, operation: PinnedAuthorityOperation) -> None:
    """The split cannot become a way to claim a bien de inversión the register does not hold."""
    orphan = _Purchase("orphan", _DOMESTIC, "domestic_investment", Decimal("4000.00"), Decimal("840.00"), "BI-ORPHAN")
    transaction = _transaction(orphan, date(2025, 5, 10))

    with pytest.raises(BienInversionValidationError, match="no reciprocal bienes-inversion record"):
        aggregate_iva_ledger_observations(
            TransactionCatalogue.from_transactions((transaction,)),
            period=Period.from_year_and_code(2025, "2T"),
            ledger_profile_id=_PROFILE_ID,
            investment_asset_register=BienesInversionIvaRegister(),
            investment_asset_profile_id=_PROFILE_ID,
            operation=operation,
        )


# One year of purchases spread over the four quarters, every figure distinct.
_YEAR_ROWS = (
    ("1T", 2, _Purchase("q1-corriente", _DOMESTIC, "domestic_current", Decimal("1000.00"), Decimal("210.00"))),
    ("1T", 2, _Purchase("q1-bi", _DOMESTIC, "domestic_investment", Decimal("4000.00"), Decimal("840.00"), "BI-Q1")),
    ("2T", 5, _Purchase("q2-corriente", _DOMESTIC, "domestic_current", Decimal("2000.00"), Decimal("420.00"))),
    ("2T", 5, _Purchase("q2-importacion", _IMPORT, "import_current", Decimal("3000.00"), Decimal("630.00"))),
    ("3T", 8, _Purchase("q3-bi", _DOMESTIC, "domestic_investment", Decimal("6000.00"), Decimal("1260.00"), "BI-Q3")),
    ("3T", 8, _Purchase("q3-imp-bi", _IMPORT, "import_investment", Decimal("7000.00"), Decimal("1470.00"), "BI-IQ3")),
    ("4T", 11, _Purchase("q4-corriente", _DOMESTIC, "domestic_current", Decimal("500.00"), Decimal("105.00"))),
    ("4T", 11, _Purchase("q4-bi", _DOMESTIC, "domestic_investment", Decimal("2500.00"), Decimal("525.00"), "BI-Q4")),
)

# Each annual 390 box and the quarterly 303 box whose four values it restates.
_ANNUAL_TO_QUARTERLY = (
    ("iva.anual.soportado.interiores.base", "28"),
    ("iva.anual.soportado.interiores", "iva.soportado.interiores"),
    ("iva.anual.deducible.interiores-inversion.total.base", "30"),
    ("iva.anual.deducible.interiores-inversion.total.cuota", "31"),
    ("iva.anual.soportado.importaciones", "iva.soportado.importaciones"),
    ("iva.anual.deducible.importaciones-inversion.total.base", "34"),
    ("iva.anual.deducible.importaciones-inversion.total.cuota", "35"),
    ("iva.anual.cuota-deducible-total", "iva.cuota-deducible-total"),
)


@pytest.mark.parametrize("filing_year", [2022, 2023, 2024, 2025])
def test_the_annual_boxes_equal_the_sum_of_the_four_quarters(
    filing_year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 390 restates each quarterly pair box by box.

    The year is aggregated once, against the register holding every asset the
    year acquired, and each quarter's 303 is resolved from the rows dated in
    that quarter. The quarterly and annual revisions read the same observations,
    so a figure that differs can only come from how each routes them.
    """
    annual = _observations(
        ((purchase, date(filing_year, month, 10)) for _, month, purchase in _YEAR_ROWS),
        period=Period.from_year_and_code(filing_year, "0A"),
        register_year=filing_year,
        operation=operation,
    )
    quarters = {
        quarter: _calculate(
            operation.snapshot("303", filing_year=filing_year, period=quarter),
            (row for row in annual if Period.from_year_and_code(filing_year, quarter).contains(row.transaction_date)),
            operation=operation,
        )
        for quarter in ("1T", "2T", "3T", "4T")
    }
    year = _calculate(operation.snapshot("390", filing_year=filing_year, period="0A"), annual, operation=operation)

    for annual_box, quarterly_box in _ANNUAL_TO_QUARTERLY:
        quarterly_sum = sum((_box(values, quarterly_box) for values in quarters.values()), Decimal("0"))
        assert _box(year, annual_box) == quarterly_sum, annual_box
    # And the sums themselves, by hand: corrientes 1.000 + 2.000 + 500 of base
    # and 210 + 420 + 105 of cuota; bienes de inversión 4.000 + 6.000 + 2.500 of
    # base and 840 + 1.260 + 525 of cuota; one import of each kind.
    assert _box(year, "iva.anual.soportado.interiores.base") == Decimal("3500.00")
    assert _box(year, "iva.anual.soportado.interiores") == Decimal("735.00")
    assert _box(year, "iva.anual.deducible.interiores-inversion.total.base") == Decimal("12500.00")
    assert _box(year, "iva.anual.deducible.interiores-inversion.total.cuota") == Decimal("2625.00")
    assert _box(year, "iva.anual.soportado.importaciones") == Decimal("630.00")
    assert _box(year, "iva.anual.deducible.importaciones-inversion.total.base") == Decimal("7000.00")
    assert _box(year, "iva.anual.deducible.importaciones-inversion.total.cuota") == Decimal("1470.00")
    # 735 + 2.625 + 630 + 1.470.
    assert _box(year, "iva.anual.cuota-deducible-total") == Decimal("5460.00")
