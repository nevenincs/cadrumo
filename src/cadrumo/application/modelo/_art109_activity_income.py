"""Period-scoped Art. 109 activity-income coverage from ledger evidence.

The coverage helper derives the RIRPF Art. 109 70 percent withholding fact from
current-period ledger rows in a
:class:`~domain.transactions.TransactionCatalogue`. Work-unit consumers use
a bucket-scoped :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
to load that catalogue before applying the same pure calculation.

The result is intentionally evidence-scoped: the denominator and withholding
status must be proven from invoice-substrate ledger facts, so gross-only bank
movements fail closed instead of fabricating an activity-income ratio.

See Also:
    :func:`derive_art109_activity_income_coverage`
        Pure catalogue-level derivation for already-loaded ledger rows.
    :func:`derive_art109_activity_income_coverage_for_work_unit`
        Work-unit adapter that resolves the matching bucket repository.
    :mod:`application.modelo._verification_actions`
        Verification path that folds a proven coverage fact into the workflow
        profile used for M130 verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.decimal.constants import ZERO
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.irpf_categories import has_activity_irpf_category, has_employment_irpf_category
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ...domain.transactions.volumen_ingresos import counts_toward_art_109_activity_income

# Registry-owned ratio, activity entity sets, category applicability, and source
# references remain in canonical versioned registry/facts TOML.  The selected
# declarations are resolved below; evidence folding mechanics remain local.


def _art109_registry_declarations(
    *,
    filing_year: int,
    period: Period,
) -> tuple[object, str, str]:
    """Resolve the selected Art. 109 ratio and activity selectors."""
    authority = bundled_authority()
    query_service = RegistryQueryService(authority)
    context = query_service._resolve_revision_for_scope(
        str(Modelo.M130),
        filing_year=filing_year,
        period=period.registry_token,
    )
    ratio_parameters = tuple(
        parameter
        for parameter in context.revision.parameters
        if parameter.data_type == "ratio" and any("109" in str(legal_ref) for legal_ref in parameter.legal_refs)
    )
    if len(ratio_parameters) != 1:
        raise RegistryValidationError(
            f"selected Modelo 130 revision {context.revision.id} does not declare one Art. 109 ratio parameter",
        )

    resolved_catalogue = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="m036-activity-selector-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=period.end_date,
        ),
    )
    if not isinstance(resolved_catalogue, ResolvedMappingFact):
        raise RegistryValidationError("the activity selector catalogue is not a mapping fact")
    selector_ids: dict[str, str] = {}
    for entry in resolved_catalogue.payload.entries:
        key = str(entry.key)
        if not key.endswith(".entity_set_fact_id") or "art-109" not in key:
            continue
        selector_ids["exempt" if "exencion" in key else "net"] = str(entry.value)
    if set(selector_ids) != {"exempt", "net"}:
        raise RegistryValidationError("the activity selector catalogue has no complete Art. 109 selector pair")
    return ratio_parameters[0], selector_ids["exempt"], selector_ids["net"]


#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#


class Art109ActivityIncomeCoverageStatus(StrEnum):
    """Whether current-period ledger evidence proves the Art. 109 threshold."""

    PROVEN = "proven"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class Art109ActivityIncomeCoverage:
    """Period-scoped Art. 109 70 percent activity-income coverage result."""

    status: Art109ActivityIncomeCoverageStatus
    meets_threshold: bool | None
    numerator: Decimal
    denominator: Decimal
    reason: str

    @property
    def is_proven(self) -> bool:
        """Return whether ``meets_threshold`` is backed by sufficient evidence."""
        return self.status is Art109ActivityIncomeCoverageStatus.PROVEN


def derive_art109_activity_income_coverage_for_work_unit(
    work_unit: WorkUnit,
    *,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
) -> Art109ActivityIncomeCoverage:
    """Derive the Art. 109 current-payment-period coverage fact for an M130 work unit.

    The returned :class:`Art109ActivityIncomeCoverage` is proven only from
    current-period ledger rows, not from M130 output casillas. A row proves
    the denominator and withholding status only when it carries invoice
    substrate (``taxable_base`` and ``iva_amount``); gross-only bank
    movements fail closed because they cannot prove whether the receipt was
    subject to withholding.
    """
    if str(work_unit.modelo) != Modelo.M130.value:
        return _insufficient("not_modelo_130")
    period = work_unit.period
    if not period.has_date_span():
        return _insufficient("period_without_date_span")
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    if repository.bucket_id != work_unit.bucket_id:
        return _insufficient("repository_bucket_mismatch")
    return derive_art109_activity_income_coverage(repository.load(), period=period)


def art_109_retained_income_threshold(*, filing_year: int, period: Period) -> Decimal:
    """Return the Art. 109 retained-income ratio selected for this filing.

    The ratio is regulatory data, versioned by filing year plus revision, so it
    is read from the Modelo 130 revision that governs ``(filing_year, period)``
    rather than inlined here. The selected registry declaration carries its
    legal and source grounding.

    Args:
        filing_year: The filing year whose revision declares the parameter.
        period: The filing period, used to resolve the governing revision and
            to date-resolve the parameter value.

    Returns:
        The threshold as a fraction (0.70 for the 70 per 100 the article states).

    Raises:
        RegistryValidationError: When the governing revision declares no Art. 109
            threshold parameter. Refusing is correct: answering from a default
            would apply an ungrounded ratio to a real filing decision.
    """
    parameter, _exempt_selector, _net_selector = _art109_registry_declarations(
        filing_year=filing_year,
        period=period,
    )
    return resolve_parameter(parameter, {"filing_period": period.end_date})


def derive_art109_activity_income_coverage(
    catalogue: TransactionCatalogue,
    *,
    period: Period,
) -> Art109ActivityIncomeCoverage:
    """Derive Art. 109 current-period coverage from a transaction catalogue.

    Args:
        catalogue: :class:`~domain.transactions.TransactionCatalogue`
            containing the ledger rows to classify for the target period.
        period: Filing period whose date span selects the current-payment rows.

    Returns:
        The proven or insufficient :class:`Art109ActivityIncomeCoverage`.
    """
    if not period.has_date_span():
        return _insufficient("period_without_date_span")

    parameter, exempt_selector, net_selector = _art109_registry_declarations(
        filing_year=period.filing_year,
        period=period,
    )
    threshold = resolve_parameter(parameter, {"filing_period": period.end_date})
    authority = bundled_authority()
    exempt_activities = tipo_actividad_code_set(
        exempt_selector,
        effective_date=period.end_date,
        authority=authority,
    )
    net_of_subvenciones_activities = tipo_actividad_code_set(
        net_selector,
        effective_date=period.end_date,
        authority=authority,
    )
    numerator = ZERO
    denominator = ZERO
    for transaction in catalogue.values():
        computable_income, insufficient_reason = _current_period_income_contribution(
            transaction,
            period=period,
            exempt_activities=exempt_activities,
            net_of_subvenciones_activities=net_of_subvenciones_activities,
        )
        if insufficient_reason is not None:
            return _insufficient(insufficient_reason)
        if computable_income is None:
            continue
        denominator += computable_income
        if _proved_withheld_income(transaction):
            numerator += computable_income

    if denominator <= ZERO:
        return _insufficient("current_period_activity_income_absent")

    return Art109ActivityIncomeCoverage(
        status=Art109ActivityIncomeCoverageStatus.PROVEN,
        meets_threshold=(numerator / denominator) >= threshold,
        numerator=numerator,
        denominator=denominator,
        reason="current_period_activity_income_ratio_proven",
    )


class _RowKind(StrEnum):
    IGNORE = "ignore"
    ACTIVITY_INCOME = "activity_income"
    INSUFFICIENT = "insufficient"


def _is_current_period_candidate(transaction: Transaction, *, period: Period) -> bool:
    """Return whether lifecycle, direction, and filing date admit a row."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        return False
    if transaction.direction is not TransactionDirection.INCOMING:
        return False
    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    return period.contains(filing_date)


def _classify_current_period_row(transaction: Transaction, *, period: Period) -> _RowKind:
    if not _is_current_period_candidate(transaction, period=period):
        return _RowKind.IGNORE
    if has_employment_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return _RowKind.IGNORE
    if has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return _RowKind.ACTIVITY_INCOME
    if transaction.business_classification is BusinessClassification.PERSONAL:
        return _RowKind.IGNORE
    if transaction.business_classification in _PROVEN_ACTIVITY_STATES:
        return _RowKind.ACTIVITY_INCOME
    if transaction.business_classification in _UNRESOLVED_ACTIVITY_STATES:
        return _RowKind.INSUFFICIENT
    return _RowKind.INSUFFICIENT


def _current_period_income_contribution(
    transaction: Transaction,
    *,
    period: Period,
    exempt_activities: frozenset[TipoActividad],
    net_of_subvenciones_activities: frozenset[TipoActividad],
) -> tuple[Decimal | None, str | None]:
    """Return one row's computable income or its fail-closed reason."""
    row = _classify_current_period_row(transaction, period=period)
    if row is _RowKind.IGNORE:
        return None, None
    if row is _RowKind.INSUFFICIENT:
        return None, "current_period_activity_income_unresolved"
    activity = transaction.tipo_actividad
    if activity is None:
        # Art. 109 exempts an activity CLASS, so a row that does not say which
        # activity it belongs to cannot be placed on either side of the rule.
        # Guessing would either invent an exemption or deny a real one, and this
        # module's contract is to fail closed rather than fabricate a ratio.
        return None, "current_period_activity_class_undeclared"
    if activity not in exempt_activities:
        # A different activity of the same taxpayer. The exemption is granted
        # "en relacion con las mismas", so an empresarial row neither claims it
        # nor dilutes the class that does.
        return None, None
    if activity in net_of_subvenciones_activities and not counts_toward_art_109_activity_income(
        transaction.concepto_ingreso,
        effective_date=period.end_date,
    ):
        # Apartados 3 and 4 measure the 70 per cent net of subvenciones and
        # indemnizaciones. A subsidy carries no retencion, so leaving it in the
        # base depresses the ratio and denies an exemption the reglamento grants.
        return None, None

    computable_income = _proved_computable_income(transaction)
    if computable_income is None or computable_income <= ZERO:
        return None, "current_period_activity_income_substrate_incomplete"
    return computable_income, None


def _proved_computable_income(transaction: Transaction) -> Decimal | None:
    if transaction.raw.currency != "EUR":
        return None
    if transaction.taxable_base is None or transaction.iva_amount is None:
        return None
    amount = transaction.taxable_base
    if transaction.business_classification is BusinessClassification.MIXED:
        if transaction.business_pct is None:
            return None
        amount *= transaction.business_pct
    return amount


def _proved_withheld_income(transaction: Transaction) -> bool:
    if transaction.taxable_base is None or transaction.iva_amount is None:
        return False
    invoice_gross = transaction.taxable_base + transaction.iva_amount
    cash_received = abs(transaction.raw.amount)
    return invoice_gross > cash_received


def _insufficient(reason: str) -> Art109ActivityIncomeCoverage:
    return Art109ActivityIncomeCoverage(
        status=Art109ActivityIncomeCoverageStatus.INSUFFICIENT,
        meets_threshold=None,
        numerator=ZERO,
        denominator=ZERO,
        reason=reason,
    )


__all__ = [
    "Art109ActivityIncomeCoverage",
    "Art109ActivityIncomeCoverageStatus",
    "derive_art109_activity_income_coverage",
    "derive_art109_activity_income_coverage_for_work_unit",
]
