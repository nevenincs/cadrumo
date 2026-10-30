"""Reconcile Renta ledger expenses against the activity-asset register."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Protocol

from pydantic import BaseModel, Field

from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.categories.spending_category_catalogue import amortizable_spending_categories
from ...domain.renta.actividad_asset.claims import current_revisions
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision, AssetBasisStage
from . import _shared_issue_reasons
from .source_mesh import CalculationSourceDiagnostic
from .source_resolution_operations import source_diagnostics_for

_NOT_A_DECLARED_EXPENSE_ISSUE_REASONS: Final[frozenset[str]] = frozenset(
    {
        _shared_issue_reasons.OUTSIDE_PERIOD,
        _shared_issue_reasons.UNSUPPORTED_DIRECTION,
        _shared_issue_reasons.PERSONAL_TRANSACTION,
        _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE,
    },
)
"""Refusals saying a row is not this period's business expense, so it declares no amortization here."""


class LedgerRentaExpenseTreatment(BaseModel):
    """One ledger-derived Renta expense row weighed against the activity-asset register.

    ``amortization_labelled`` states whether the row's own Renta destination is
    one of the activity amortization casillas
    (:func:`~domain.calculations.registry.ledger_renta_gastos_estimacion_directa_bindings.activity_asset_amortization_casillas`).
    The two Renta expense projections derive it differently -- the annual
    first-slice observation already carries its resolved target casilla, while
    the quarterly gasto row carries only its ledger category -- so each caller
    resolves the flag and this boundary keeps one meaning for it.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
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
    transaction_id: TransactionId
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int
    purchase_amount: Decimal | None = None


def amortization_labelled_expense_categories(*, effective_date: date) -> frozenset[str]:
    """Return the ledger categories that declare an amortization rather than an ordinary expense.

    The governed spending-category catalogue selected at ``effective_date`` names
    them. They have no first-slice route, so the catalogue is the only place that
    keeps their rows from being read as ordinary expenses.

    Returns:
        The category tokens whose rows belong to the activity-asset register.
    """
    return frozenset(category.value for category in amortizable_spending_categories(effective_date=effective_date))


class UnregisteredAmortizationRow(BaseModel):
    """A ledger row declaring an amortization that no registered element accounts for."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    category: str | None = Field(default=None, min_length=1, max_length=128)
    tax_year: int


@dataclass(frozen=True, slots=True)
class LedgerExpenseRegisterClassification:
    """Which ledger rows the register withholds, and which it will not leave unexplained."""

    withheld: tuple[RegisterOwnedAcquisition, ...]
    unregistered: tuple[UnregisteredAmortizationRow, ...]

    @property
    def excluded_transaction_ids(self) -> frozenset[str]:
        """Return the rows that must not reach an expense total."""
        return frozenset(
            {row.transaction_id for row in self.withheld} | {row.transaction_id for row in self.unregistered},
        )


def classify_ledger_expenses_against_asset_register(
    assets: tuple[ActivityAssetRevision, ...],
    treatments: tuple[LedgerRentaExpenseTreatment, ...],
) -> LedgerExpenseRegisterClassification:
    """Withhold register-owned acquisitions and report unowned amortization rows.

    The activity-asset source owns the activity amortization destinations
    exclusively, in every year and whether or not it holds a claim for that year,
    so no ledger row may route a deductible amount to one:

    - A row on a transaction a registered asset declares as its acquisition IS
      the acquisition. Under LIRPF art. 28.1 the rendimiento neto follows the
      Impuesto sobre Sociedades rules, where LIS art. 12.1 makes the deductible
      item the amortización del inmovilizado and RIS art. 3.2 makes the
      acquisition price the amortizable base, amortised across the element's
      useful life (RIS art. 3.3). The row is withheld and reported, whatever
      category it carries; the transaction and its IVA facts are untouched.
    - Any other row whose own destination is an activity amortization casilla is
      an element the register does not know. It is never deducted, and the
      caller turns it into a non-blocking finding whose remedy is to register the element.

    Returns:
        The withheld rows in asset order and the unregistered rows in ledger order.
    """
    owners = _current_acquisition_owners(assets)
    owned = {transaction_id for _asset_id, transaction_id in owners}
    return LedgerExpenseRegisterClassification(
        withheld=tuple(
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
        ),
        unregistered=tuple(
            UnregisteredAmortizationRow(
                transaction_id=treatment.transaction_id,
                category=treatment.category,
                tax_year=treatment.tax_year,
            )
            for treatment in treatments
            if treatment.amortization_labelled and treatment.transaction_id not in owned
        ),
    )


class RefusedExpenseRow(Protocol):
    """What an aggregation issue says about the ledger row it refused."""

    @property
    def transaction_id(self) -> str:
        """The refused ledger row."""
        ...

    @property
    def category_id(self) -> str | None:
        """The category the row declares."""
        ...

    @property
    def reason(self) -> str:
        """The machine-readable refusal."""
        ...


def refused_amortization_rows(
    issues: Iterable[RefusedExpenseRow],
    *,
    assets: tuple[ActivityAssetRevision, ...],
    tax_year: int,
    effective_date: date,
) -> tuple[UnregisteredAmortizationRow, ...]:
    """Find amortization rows the expense rules refused, which never became observations.

    A row in an amortizable category has no route and no deduction of its own, so
    it is refused before it can be classified. Such a row still declares an
    element the register does not know, so an advisory alone would omit it.

    Returns:
        One row per refused, unowned, amortization-labelled expense of this period.
    """
    declared = tuple(
        issue
        for issue in issues
        if issue.category_id is not None and str(issue.reason) not in _NOT_A_DECLARED_EXPENSE_ISSUE_REASONS
    )
    if not declared:
        return ()
    labelled = amortization_labelled_expense_categories(effective_date=effective_date)
    owned = register_acquisition_transaction_ids(assets)
    return tuple(
        UnregisteredAmortizationRow(
            transaction_id=issue.transaction_id,
            category=issue.category_id,
            tax_year=tax_year,
        )
        for issue in declared
        if issue.category_id in labelled and issue.transaction_id not in owned
    )


def refused_register_owned_rows(
    issues: Iterable[RefusedExpenseRow],
    *,
    assets: tuple[ActivityAssetRevision, ...],
    tax_year: int,
    effective_date: date,
) -> tuple[RegisterOwnedAcquisition, ...]:
    """Find acquisitions the register owns that the expense rules refused outright.

    A row in an amortizable category deducts nothing, so it never becomes an
    observation to withhold. The register still owns it, and the operator is told
    so, without a purchase amount that no observation carries.

    Returns:
        One withheld acquisition per refused, owned, amortization-labelled expense of this period.
    """
    declared = tuple(
        issue
        for issue in issues
        if issue.category_id is not None and str(issue.reason) not in _NOT_A_DECLARED_EXPENSE_ISSUE_REASONS
    )
    if not declared:
        return ()
    labelled = amortization_labelled_expense_categories(effective_date=effective_date)
    owners = {transaction_id: asset_id for asset_id, transaction_id in _current_acquisition_owners(assets)}
    return tuple(
        RegisterOwnedAcquisition(
            asset_id=owners[issue.transaction_id],
            transaction_id=issue.transaction_id,
            category=issue.category_id,
            tax_year=tax_year,
        )
        for issue in declared
        if issue.category_id in labelled and issue.transaction_id in owners
    )


def unregistered_amortization_row_diagnostics(
    rows: Iterable[UnregisteredAmortizationRow],
    *,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project each unowned amortization row into its non-blocking finding.

    Returns:
        One note per row, naming the row and the remedy.
    """
    return source_diagnostics_for(
        tuple({row.transaction_id: row for row in rows}.values()),
        reason="ledger_amortization_row_unregistered",
        source_kind=resolver_id,
        resolver_id=resolver_id,
        source_ref=lambda row: f"transaction:{row.transaction_id}",
        message=lambda row: (
            f"ledger transaction {row.transaction_id!r} (category={row.category!r}, tax_year={row.tax_year}) declares "
            "an amortizable element the activity-asset register does not hold; it deducts nothing"
        ),
        remedy=lambda _row: (
            "register the element in the activity-asset register, naming this transaction as its acquisition, "
            "or reclassify the row if it is not an amortizable element"
        ),
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
            f"tax_year={acquisition.tax_year}); its "
            + (
                "purchase amount"
                if acquisition.purchase_amount is None
                else f"{acquisition.purchase_amount} EUR purchase amount"
            )
            + " is the amortizable base, not a deductible expense of the period, so it is not declared in this "
            "expense total"
        ),
        remedy=lambda _acquisition: (
            "the register owns this asset's Renta deduction: record the year's amortization charge so the "
            "schedule's claim is declared instead of the purchase"
        ),
    )


def _current_acquisition_owners(
    assets: tuple[ActivityAssetRevision, ...],
) -> tuple[tuple[str, str], ...]:
    """Return ``(asset_id, acquisition transaction id)`` for each row of each asset's current revision.

    A superseding revision may restate the acquisition linkage, so only the
    highest revision number of each asset declares which transactions the
    register owns. Pairs are returned rather than a mapping so two assets that
    name the same transaction both keep their disposition instead of one
    silently displacing the other.
    """
    current = current_revisions(assets)
    return tuple(
        (asset_id, transaction_id)
        for asset_id in sorted(current)
        for transaction_id in current[asset_id].acquisition_transaction_ids
    )


def register_acquisition_transaction_ids(assets: tuple[ActivityAssetRevision, ...]) -> frozenset[str]:
    """Return the ledger transactions the register declares as an asset's acquisition.

    Returns:
        Every acquisition transaction id of every asset's current revision.
    """
    return frozenset(transaction_id for _asset_id, transaction_id in _current_acquisition_owners(assets))


def dwelling_ownership_share(assets: tuple[ActivityAssetRevision, ...]) -> Decimal | None:
    """Return the taxpayer's ownership share of the partly affected property the register records.

    A mixed-use property is registered with a whole-property basis, which states
    the taxpayer's direct ownership share of it. That share is the only source
    of the ownership fact the dwelling's own expenses need.

    Returns:
        The share when every registered whole-property asset states the same
        one, or ``None`` when no such asset exists or two state different
        shares, since the ledger rows do not say which property they belong to.
    """
    shares = {
        revision.basis.ownership_share
        for revision in current_revisions(assets).values()
        if revision.basis.stage is AssetBasisStage.WHOLE_PROPERTY and revision.basis.ownership_share is not None
    }
    return next(iter(shares)) if len(shares) == 1 else None
