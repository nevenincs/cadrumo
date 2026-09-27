"""Read-only Modelo 100/130 projections for effective activity-asset claims."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.renta.actividad_asset.claims import (
    M100_AMORTIZATION_CASILLA_IDS,
    AmortizationClaim,
    effective_claims,
    m100_casilla_id,
)
from ...domain.renta.actividad_asset.errors import ActividadAssetClaimConflictError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetKind
from ...domain.renta.ledger_expenses import renta_first_slice_expense_routing
from ._models import CasillaAggregation
from .source_mesh import CalculationSourceDiagnostic
from .source_resolution_operations import source_diagnostics_for


class ActivityAssetFilingProjection(BaseModel):
    """A non-consuming filing projection retaining effective claim identity."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str
    period: Period
    casilla_values: dict[CasillaId, Decimal]
    claim_ids: tuple[str, ...]


class LedgerRentaExpenseTreatment(BaseModel):
    """One ledger-derived Renta expense row weighed against the activity-asset register.

    ``amortization_labelled`` states whether the row's own Renta destination is
    one of the activity amortization casillas
    (:data:`~domain.renta.actividad_asset.claims.M100_AMORTIZATION_CASILLA_IDS`).
    The two Renta expense projections derive it differently -- the annual
    first-slice observation already carries its resolved target casilla, while
    the quarterly gasto row carries only its ledger category -- so each caller
    resolves the flag and this boundary keeps one meaning for it.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int
    deductible_amount: Decimal
    amortization_labelled: bool


class RegisterOwnedAcquisition(BaseModel):
    """One ledger expense row the activity-asset register owns as a capital acquisition.

    The row stays in the ledger as acquisition evidence; what is withheld is its
    contribution to a Renta deductible-expense total, because the acquisition
    price is the amortizable base rather than a current expense (RIS art. 3.2,
    LIS art. 12.1 through LIRPF art. 28.1).
    """

    model_config = STRICT_FROZEN_CONFIG

    asset_id: str = Field(min_length=1, max_length=128)
    transaction_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int
    purchase_amount: Decimal


class ActivityAssetExpenseObservation(BaseModel):
    """One effective claim projected through an existing Renta expense owner."""

    model_config = STRICT_FROZEN_CONFIG

    claim_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    modelo: str
    period: str = Field(min_length=2, max_length=2)
    target_casilla_id: CasillaId
    deductible_amount: Decimal = Field(ge=Decimal("0"))


def activity_asset_expense_observations(
    claims: tuple[AmortizationClaim, ...],
    *,
    modelo: str,
    period: Period,
) -> tuple[ActivityAssetExpenseObservation, ...]:
    """Project effective claims into the existing M100 or M130 expense family."""
    effective = tuple(claim for claim in effective_claims(claims) if claim.tax_year == period.filing_year)
    if modelo == "130":
        cutoff = period.end_date + timedelta(days=1)
        effective = tuple(claim for claim in effective if claim.covered_until <= cutoff)
        return tuple(
            ActivityAssetExpenseObservation(
                claim_id=claim.claim_id,
                modelo=modelo,
                period=period.registry_token,
                target_casilla_id=validated_casilla_id("02", surface="activity asset M130 observation"),
                deductible_amount=claim.amount,
            )
            for claim in effective
        )
    if modelo == "100":
        return tuple(
            ActivityAssetExpenseObservation(
                claim_id=claim.claim_id,
                modelo=modelo,
                period=period.registry_token,
                target_casilla_id=validated_casilla_id(
                    m100_casilla_id(claim.asset_kind),
                    surface="activity asset M100 observation",
                ),
                deductible_amount=claim.amount,
            )
            for claim in effective
        )
    raise ValueError("activity-asset expense observations support only Modelos 100 and 130")


def project_activity_assets_to_m100(
    claims: tuple[AmortizationClaim, ...],
    *,
    period: Period,
) -> ActivityAssetFilingProjection:
    """Project each effective annual claim once to material/intangible destinations."""
    selected = tuple(claim for claim in effective_claims(claims) if claim.tax_year == period.filing_year)
    values = {
        validated_casilla_id(
            m100_casilla_id(AssetKind.MATERIAL),
            surface="activity asset material projection",
        ): _sum_kind(selected, AssetKind.MATERIAL),
        validated_casilla_id(
            m100_casilla_id(AssetKind.INTANGIBLE),
            surface="activity asset intangible projection",
        ): _sum_kind(selected, AssetKind.INTANGIBLE),
    }
    return ActivityAssetFilingProjection(
        modelo="100",
        period=period,
        casilla_values=values,
        claim_ids=tuple(claim.claim_id for claim in selected),
    )


def add_activity_assets_to_m130_expenses(
    ordinary: CasillaAggregation,
    claims: tuple[AmortizationClaim, ...],
) -> ActivityAssetFilingProjection:
    """Add effective YTD claims to the existing sole casilla-02 expense result."""
    if ordinary.modelo != "130":
        raise ValueError("activity-asset M130 composition requires a Modelo 130 ordinary-expense aggregation")
    end_date = ordinary.period.end_date
    selected = tuple(
        claim
        for claim in effective_claims(claims)
        if claim.tax_year == ordinary.period.filing_year and claim.covered_until <= end_date + timedelta(days=1)
    )
    target = validated_casilla_id("02", surface="activity asset M130 expense projection")
    values = dict(ordinary.casilla_values)
    values[target] = values.get(target, Decimal("0")) + sum((claim.amount for claim in selected), Decimal("0"))
    return ActivityAssetFilingProjection(
        modelo="130",
        period=ordinary.period,
        casilla_values=values,
        claim_ids=tuple(claim.claim_id for claim in selected),
    )


def amortization_labelled_expense_categories(*, effective_date: date) -> frozenset[str]:
    """Return the ledger categories whose Renta destination is an amortization dotación.

    Derived from the governed first-slice expense routing selected at
    ``effective_date``, so the set follows the registry declaration instead of a
    restated category list. A category outside the returned set labels an
    ordinary expense, never a depreciation treatment.

    Returns:
        The category tokens routed to an activity amortization casilla.
    """
    return frozenset(
        category.value
        for category, casilla in renta_first_slice_expense_routing(effective_date=effective_date).items()
        if str(casilla) in M100_AMORTIZATION_CASILLA_IDS
    )


def classify_ledger_expenses_against_asset_register(
    assets: tuple[ActivityAssetRevision, ...],
    claims: tuple[AmortizationClaim, ...],
    treatments: tuple[LedgerRentaExpenseTreatment, ...],
) -> tuple[RegisterOwnedAcquisition, ...]:
    """Withhold register-owned acquisitions and refuse competing depreciation treatments.

    The activity-asset source owns the activity amortization destinations
    exclusively, so no ledger row may route a deductible amount to one. Which of
    the two authorised dispositions applies depends on whether the register
    already accounts for the row:

    - A row on a transaction a registered asset declares as its acquisition IS
      the acquisition. Under LIRPF art. 28.1 the rendimiento neto follows the
      Impuesto sobre Sociedades rules, where LIS art. 12.1 makes the deductible
      item the amortización del inmovilizado and RIS art. 3.2 makes the
      acquisition price the amortizable base, amortised across the element's
      useful life (RIS art. 3.3). The purchase is therefore not an expense of
      the period: the row is withheld from the expense total and reported, and
      the ledger's own depreciation route yields to the register whatever
      category the row carries. The transaction and its IVA facts are untouched,
      so the acquisition stays as evidence exactly as the register requires.
    - Any other row whose own destination is an activity amortization casilla,
      in a tax year the register already charges, declares a second depreciation
      treatment the schedule does not account for. Summing it would deduct the
      same year's depreciation twice, so the calculation refuses and names what
      to reclassify or reverse.

    Withholding is reported rather than silent: the returned rows carry the
    asset, transaction, category, year, and purchase amount the caller turns
    into an operator-visible diagnostic.

    Returns:
        One :class:`RegisterOwnedAcquisition` per withheld row, in asset order.

    Raises:
        ActividadAssetClaimConflictError: When a row outside the register's own
            acquisitions routes a depreciation amount for a charged tax year.
    """
    owners = _current_acquisition_owners(assets)
    owner_by_transaction = {transaction_id: asset_id for asset_id, transaction_id in owners}
    withheld = tuple(
        RegisterOwnedAcquisition(
            asset_id=asset_id,
            transaction_id=treatment.transaction_id,
            category=treatment.category,
            tax_year=treatment.tax_year,
            purchase_amount=treatment.deductible_amount,
        )
        for asset_id, transaction_id in owners
        for treatment in treatments
        if treatment.transaction_id == transaction_id
    )
    _refuse_competing_depreciation_treatments(
        claims,
        tuple(
            treatment
            for treatment in treatments
            if treatment.amortization_labelled and treatment.transaction_id not in owner_by_transaction
        ),
    )
    return withheld


def _refuse_competing_depreciation_treatments(
    claims: tuple[AmortizationClaim, ...],
    amortization_labelled: tuple[LedgerRentaExpenseTreatment, ...],
) -> None:
    """Refuse a ledger depreciation amount for a tax year the register charges."""
    if not amortization_labelled:
        return
    charged_assets: dict[int, list[str]] = {}
    for claim in effective_claims(claims):
        charged_assets.setdefault(claim.tax_year, []).append(claim.asset_id)
    for treatment in amortization_labelled:
        competing_assets = sorted(set(charged_assets.get(treatment.tax_year, ())))
        if not competing_assets:
            continue
        raise ActividadAssetClaimConflictError(
            "competing transaction-ledger depreciation treatment "
            f"asset={competing_assets[0]!r} transaction={treatment.transaction_id!r} "
            f"category={treatment.category!r} tax_year={treatment.tax_year}; retain acquisition evidence and "
            "reclassify or reverse only the competing depreciation treatment",
        )


def register_owned_acquisition_diagnostics(
    withheld: tuple[RegisterOwnedAcquisition, ...],
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project each withheld acquisition into an operator-visible advisory.

    Returns:
        One advisory per withheld row, naming the asset, the transaction, and the
        purchase amount that did not enter the expense total.
    """
    return source_diagnostics_for(
        withheld,
        reason="register_owned_capital_acquisition",
        source_kind=source_kind,
        resolver_id=resolver_id,
        source_ref=lambda acquisition: f"transaction:{acquisition.transaction_id}",
        message=lambda acquisition: (
            f"ledger transaction {acquisition.transaction_id!r} is the activity-asset register's declared "
            f"acquisition of asset {acquisition.asset_id!r} (category={acquisition.category!r}, "
            f"tax_year={acquisition.tax_year}); its {acquisition.purchase_amount} EUR purchase amount is the "
            "amortizable base, not a deductible expense of the period, so it is not declared in this expense total"
        ),
        remedy=lambda _acquisition: (
            "the register owns this asset's Renta deduction: record the year's amortization charge so the "
            "schedule's claim is declared instead of the purchase"
        ),
    )


def _current_acquisition_owners(
    assets: tuple[ActivityAssetRevision, ...],
) -> tuple[tuple[str, str], ...]:
    """Return ``(asset_id, acquisition transaction id)`` for each asset's current revision.

    A superseding revision may restate the acquisition linkage, so only the
    highest revision number of each asset declares which transaction the
    register owns. Pairs are returned rather than a mapping so two assets that
    name the same transaction both keep their disposition instead of one
    silently displacing the other.
    """
    current: dict[str, ActivityAssetRevision] = {}
    for revision in assets:
        held = current.get(revision.asset_id)
        if held is None or revision.revision_number > held.revision_number:
            current[revision.asset_id] = revision
    return tuple((asset_id, current[asset_id].acquisition.observed_transaction_id) for asset_id in sorted(current))


def _sum_kind(claims: tuple[AmortizationClaim, ...], kind: AssetKind) -> Decimal:
    return sum((claim.amount for claim in claims if claim.asset_kind is kind), Decimal("0"))


__all__ = [
    "ActivityAssetExpenseObservation",
    "ActivityAssetFilingProjection",
    "LedgerRentaExpenseTreatment",
    "RegisterOwnedAcquisition",
    "activity_asset_expense_observations",
    "add_activity_assets_to_m130_expenses",
    "amortization_labelled_expense_categories",
    "classify_ledger_expenses_against_asset_register",
    "project_activity_assets_to_m100",
    "register_owned_acquisition_diagnostics",
]
