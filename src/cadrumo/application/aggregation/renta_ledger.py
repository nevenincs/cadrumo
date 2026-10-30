"""Repository-backed Modelo 100 Renta expense aggregation.

This is the annual first-slice expense projection behind the
``ledger_renta_gastos_estimacion_directa_aggregation`` source. It loads both a
:class:`~domain.transactions.models.TransactionCatalogue` and a
:class:`~domain.invoices.catalogue.InvoiceCatalogue` from the application-owned catalogue
read capabilities, uses purchase-invoice evidence to validate deductible-expense
facts, and returns
binding-ready :class:`~domain.renta.ledger_expenses.RentaDeductibleExpenseObservation`
records.

The source-mesh resolver in :mod:`~.modelo_bindings` applies the target
:class:`~domain.calculations.registry.schema.ModeloRevision`, resolves registry
bindings, and reports source issues or unrouted expenses on its
:class:`~.source_mesh.CalculationSourceResolution`. The M130 quarterly gasto
projection is separate in :mod:`~.renta_gasto_ledger` (no invoice evidence, a
cumulative window) but evaluates each categorised row through the same
category rules built here by :func:`resolve_category_deduction_rules`.

Related: :mod:`~.iva_ledger` and :mod:`~.renta_income_ledger` for sibling
ledger projections.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, overload

from ...core.casilla_id import CasillaId
from ...core.decimal.constants import ZERO
from ...core.i18n.translatable import Translatable as tr
from ...core.modelo import Modelo
from ...core.period import Period, PeriodKind
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.iva_regime_vocabulary import (
    iva_regime_exento_token,
    require_iva_regime,
)
from ...domain.calculations.registry.prorrata_register_catalogue import regime_apportions_deduction
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.categories.profile import CategoryProfile
from ...domain.categories.registry import resolve_category_profiles
from ...domain.categories.spending_category import SpendingCategory
from ...domain.contribuyente.ccaa import CCAA
from ...domain.contribuyente.errors import ForalRegimeError, TaxResidenceProfileError
from ...domain.contribuyente.seguro_enfermedad_insured import (
    seguro_enfermedad_insured_counts_from_facts,
)
from ...domain.contribuyente.tax_residence import ResidenceTerritory, classify_tax_region, parse_tax_region
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.ledger_expenses import (
    RentaDeductibilityContext,
    RentaDeductibilityResult,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaDeductibleExpenseObservation,
    RentaExpenseDirection,
    StatutoryCapClaim,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
    normalize_spending_category,
    resolve_region_category_profiles,
    select_deductibility_profile,
    statutory_cap_trims,
)
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.values import UserProfileRecord
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import fact_value, profile_fact_index, record_to_path_values
from . import _shared_issue_reasons
from ._models import CasillaAggregation, CasillaProvenance
from ._renta_business_eligibility import (
    exclusive_business_use,
    relies_on_activity_marker,
    renta_expense_business_proportion,
    row_scaling_proportion,
)
from .catalogue_read_binding import require_catalogue_reads_bound_to
from .currency_predicates import (
    effective_eur_amount,
    is_non_eur_without_conversion,
)
from .errors import AggregationPeriodError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

from .renta_ledger_evidence import iva_amount_for, purchase_invoice_evidence_payload, taxable_base_for
from .renta_ledger_models import (
    RentaLedgerAggregationIssue,
    RentaLedgerAggregationIssueReason,
    RentaLedgerExpenseAggregation,
)

_LEDGER_CATALOGUE_ID = "ledger"
_TAX_REGION_PATH = "tax_residence.ccaa"


# Registry authority: selected renta-ledger insurance variants, category-profile
# routing, issue/applicability, and binding declarations are consumed through the dated mapping
def _registry_renta_ledger_declarations(
    *,
    modelo: str,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> dict[str, str]:
    """Resolve the selected renta-ledger declaration mapping without fallbacks."""
    effective_date = date(filing_year, 12, 31)
    directory = operation.modelo_directory(modelo)
    if not any(metadata.contains_date(effective_date) for metadata in directory.revisions):
        raise ValueError(f"{modelo} has no registry revision in force on {effective_date.isoformat()}")
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="renta-ledger-category-variant-routing-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("renta-ledger declarations must resolve as a mapping fact")
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("renta-ledger declaration entries must be string-to-string")
        if entry.key in entries:
            raise ValueError(f"duplicate renta-ledger declaration key {entry.key!r}")
        entries[entry.key] = entry.value
    return entries


def _required_renta_ledger_declaration(entries: Mapping[str, str], key: str) -> str:
    value = entries.get(key)
    if value is None or not value.strip():
        raise ValueError(f"renta-ledger mapping is missing {key!r}")
    return value


def _registry_renta_iva_ratio_declarations(
    *,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> dict[str, str]:
    """Resolve the dated IVA-ratio policy used by the Renta ledger."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="renta-iva-deduction-ratio-policy",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=date(filing_year, 12, 31),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("Renta IVA ratio policy must resolve as a mapping fact")
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("Renta IVA ratio policy entries must be string-to-string")
        if entry.key in entries:
            raise ValueError(f"duplicate Renta IVA ratio policy key {entry.key!r}")
        entries[entry.key] = entry.value
    return entries


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


def _seguro_enfermedad_person_counts(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None,
    filing_year: int,
    modelo: str,
    profile_decode_context: ProfileDecodeContext | None,
    operation: PinnedAuthorityOperation,
) -> dict[str, int]:
    """Resolve insured-person variant counts using selected registry declarations."""
    if profile_decode_context is None:
        profile_decode_context = operation.profile_decode_context()
    declarations = _registry_renta_ledger_declarations(
        modelo=modelo,
        filing_year=filing_year,
        operation=operation,
    )
    general_variant = _required_renta_ledger_declaration(declarations, "insurance.variant.general")
    disability_variant = _required_renta_ledger_declaration(declarations, "insurance.variant.discapacidad")
    general_field = _required_renta_ledger_declaration(declarations, "insurance.count_field.general")
    disability_field = _required_renta_ledger_declaration(declarations, "insurance.count_field.discapacidad")
    record = profile_record
    profile_schema = profile_decode_context.schema
    if record is None:
        try:
            repository = ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=profile_decode_context,
            )
            record = repository.load(bucket_id)
            profile_schema = repository.session.profile_decode_context.schema
        except ProfileNotFoundError:
            return {}
    counts = seguro_enfermedad_insured_counts_from_facts(
        profile_fact_index(record, profile_schema),
        filing_year=filing_year,
    )
    return {
        general_variant: getattr(counts, general_field),
        disability_variant: getattr(counts, disability_field),
    }


def resolve_residence_ccaa(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None = None,
    profile_decode_context: ProfileDecodeContext | None = None,
    operation: PinnedAuthorityOperation,
) -> CCAA | None:
    """Derive the ordinary-residence comunidad autonoma from the bucket's profile.

    Reads the ``tax_residence.ccaa`` fact from the bucket's user profile and
    parses it to the closed :class:`CCAA` enum. Returns ``None`` -- the D4
    fail-closed outcome that falls the aggregation through to the state year
    profile -- when no profile is selected, the fact is absent, or the recorded
    region is a foral regime or otherwise unparseable. The value is inert while
    :func:`resolve_region_category_profiles` returns an empty mapping (general
    expense deductibility is state base-imponible law, invariant across
    comunidades); it is derived here so a future territorial-regime override
    selects by residence with no further caller wiring.

    Args:
        bucket_id: Stable bucket identifier used to load the user profile.
        profile_record: Optional :class:`UserProfileRecord` override for testing;
            when ``None`` the record is loaded from the bucket.
        profile_decode_context: Optional decode context from the caller-held
            authority operation used when the record is loaded.
        operation: Pinned authority operation supplying the profile decode context.
    """
    raw = _recorded_tax_region(
        bucket_id=bucket_id,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        operation=operation,
    )
    if raw is None:
        return None
    try:
        return parse_tax_region(raw)
    except (ForalRegimeError, TaxResidenceProfileError):
        return None


def resident_territory(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None = None,
    profile_decode_context: ProfileDecodeContext | None = None,
    operation: PinnedAuthorityOperation,
    as_of: date | None = None,
) -> ResidenceTerritory:
    """Classify the bucket's recorded tax residence as common, foral or unresolved.

    Reads the same fact as :func:`resolve_residence_ccaa` and asks the same
    parser. An absent reading is common; a recorded one the catalogue cannot
    parse is unresolved, because it established nothing.

    ``as_of`` reads the residence in force on that date, so a later move does not
    reach back over an earlier filing period. When residence is recorded only for
    other dates the answer is :attr:`ResidenceTerritory.PERIOD_UNKNOWN`.
    """
    record = _tax_region_record(
        bucket_id=bucket_id,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        operation=operation,
    )
    reading = record_to_path_values(record, as_of=as_of).get(_TAX_REGION_PATH)
    if reading is None and as_of is not None and fact_value(record, _TAX_REGION_PATH) is not None:
        return ResidenceTerritory.PERIOD_UNKNOWN
    return classify_tax_region(reading)


def _recorded_tax_region(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None,
    profile_decode_context: ProfileDecodeContext | None,
    operation: PinnedAuthorityOperation,
) -> str | None:
    """Return the raw ``tax_residence.ccaa`` fact, or ``None`` with no profile or fact."""
    return fact_value(
        _tax_region_record(
            bucket_id=bucket_id,
            profile_record=profile_record,
            profile_decode_context=profile_decode_context,
            operation=operation,
        ),
        _TAX_REGION_PATH,
    )


def _tax_region_record(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None,
    profile_decode_context: ProfileDecodeContext | None,
    operation: PinnedAuthorityOperation,
) -> UserProfileRecord | None:
    if profile_record is not None:
        return profile_record
    if profile_decode_context is None:
        profile_decode_context = operation.profile_decode_context()
    try:
        return ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=profile_decode_context,
        ).load(bucket_id)
    except ProfileNotFoundError:
        return None


def resolve_iva_deduction_ratio(
    *,
    bucket_id: str,
    ejercicio: int,
    profile_record: UserProfileRecord | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    profile_decode_context: ProfileDecodeContext | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> Decimal | None:
    """Resolve the activity's IVA-deduction fraction for :attr:`RentaDeductibilityContext.iva_deduction_ratio`.

    The selected registry ratio policy supplies the exempt-regime result and
    percentage-unit conversion; the prorrata register supplies the period
    value for all other regimes. An absent or unresolved register value falls
    through to ``None``.

    Returns ``None`` -- the historic base-only fallback -- when neither fact
    resolves a ratio (no profile, an unparseable regime, no register entry, or
    an unresolved percentage). Never fabricates a percentage.

    Args:
        bucket_id: Stable bucket identifier used to load the profile and register.
        ejercicio: Filing year to resolve the register entry for.
        profile_record: Optional :class:`UserProfileRecord` override for testing;
            when ``None`` the record is loaded from the bucket.
        profile_decode_context: Optional decode context from the caller-held
            authority operation used when the record is loaded.
        prorrata_register_repository: Canonical repository for the bucket's
            prorrata register. The caller owns its store selection so a
            non-active bucket cannot be shadowed by a process-global default.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return resolve_iva_deduction_ratio(
                bucket_id=bucket_id,
                ejercicio=ejercicio,
                profile_record=profile_record,
                prorrata_register_repository=prorrata_register_repository,
                profile_decode_context=profile_decode_context,
                operation=indexed_operation,
            )
    if profile_decode_context is None:
        profile_decode_context = operation.profile_decode_context()
    ratio_policy = _registry_renta_iva_ratio_declarations(filing_year=ejercicio, operation=operation)
    exempt_ratio = Decimal(
        _required_renta_ledger_declaration(ratio_policy, "exempt_regime.deduction_ratio"),
    )
    percentage_divisor = Decimal(
        _required_renta_ledger_declaration(ratio_policy, "percentage.unit_divisor"),
    )
    profile_exempt_ratio = _profile_exempt_iva_ratio(
        bucket_id=bucket_id,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        exempt_ratio=exempt_ratio,
    )
    if profile_exempt_ratio is not None:
        return profile_exempt_ratio

    register = require_prorrata_register_coordinates_current(prorrata_register_repository.load(), operation=operation)
    entry = register.entry_for(ejercicio, sector_id=None)
    if entry is None or not regime_apportions_deduction(entry.regime):
        return None
    resolution = register.resolve_provisional(ejercicio, sector_id=None)
    if resolution.percentage is None:
        return None
    return resolution.percentage / percentage_divisor


def _profile_exempt_iva_ratio(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None,
    profile_decode_context: ProfileDecodeContext,
    exempt_ratio: Decimal,
) -> Decimal | None:
    record = profile_record
    if record is None:
        try:
            record = ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=profile_decode_context,
            ).load(bucket_id)
        except ProfileNotFoundError:
            return None
    raw_regime = fact_value(record, "iva.regime")
    if raw_regime is None:
        return None
    regime = require_iva_regime(raw_regime.strip().upper())
    if regime == iva_regime_exento_token():
        return exempt_ratio
    return None


@dataclass(frozen=True, slots=True)
class RentaCategoryDeductionRules:
    """The category rules and evaluation context one Renta expense pipeline runs its rows through.

    The annual Modelo 100 expense pipeline and the Modelo 130 quarterly gasto
    pipeline both decide a row's deductible amount with
    :func:`~cadrumo.domain.renta.ledger_expenses.evaluate_renta_deductibility`
    against these, so the usage ratio, the insured-person counts of the statutory
    cap and the recoverable-IVA share reach both from one construction.
    """

    profile_year: int
    profiles: Mapping[SpendingCategory, CategoryProfile]
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]]
    context: RentaDeductibilityContext


def resolve_category_deduction_rules(
    *,
    bucket_id: str,
    profile_year: int,
    modelo: str,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None,
    residence_ccaa: CCAA | None,
    region_category_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]] | None,
    iva_deduction_ratio: Decimal | None,
    profile_record: UserProfileRecord | None,
    profile_decode_context: ProfileDecodeContext | None,
    operation: PinnedAuthorityOperation,
    ownership_share: Decimal | None = None,
    register_owned_transaction_ids: frozenset[str] = frozenset(),
) -> RentaCategoryDeductionRules:
    """Resolve the category profiles and the deductibility context for one filing year.

    Args:
        bucket_id: Stable bucket identifier used to load the profile when
            ``profile_record`` is absent.
        profile_year: Filing year whose category profiles govern the rows.
        modelo: Modelo identifier receiving the aggregation; it selects the registry
            revision that declares the insured-person count fields.
        usage_ratios: Per-category business-use ratios; the effective ratio the
            usage-ratio rule multiplies by, statutory multiplier included.
        residence_ccaa: Ordinary-residence comunidad, selecting a territorial override.
        region_category_overrides: Per-comunidad override layer; defaults to the
            registry-provisioned (empty) layer.
        iva_deduction_ratio: Activity-wide IVA-deduction fraction, or ``None``.
        profile_record: The :class:`UserProfileRecord` supplying the
            insured-person counts; loaded from the bucket when absent.
        profile_decode_context: Decode context of the caller-held authority operation.
        operation: Generation-pinned authority operation.
        ownership_share: The taxpayer's ownership share of the partly affected
            dwelling, or ``None`` when no source states it.
        register_owned_transaction_ids: The ledger rows the activity-asset
            register declares as an asset's acquisition.

    Returns:
        The rules, ready for :func:`resolve_category_rule` and the evaluator.
    """
    return RentaCategoryDeductionRules(
        profile_year=profile_year,
        profiles=resolve_category_profiles(profile_year, operation=operation),
        region_overrides=(
            region_category_overrides
            if region_category_overrides is not None
            else resolve_region_category_profiles(profile_year)
        ),
        context=RentaDeductibilityContext(
            profile_year=profile_year,
            usage_ratios=dict(usage_ratios or {}),
            residence_ccaa=residence_ccaa,
            iva_deduction_ratio=iva_deduction_ratio,
            ownership_share=ownership_share,
            register_owned_transaction_ids=register_owned_transaction_ids,
            statutory_cap_variant_person_counts=_seguro_enfermedad_person_counts(
                bucket_id=bucket_id,
                profile_record=profile_record,
                filing_year=profile_year,
                modelo=modelo,
                profile_decode_context=profile_decode_context,
                operation=operation,
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class CategoryRuleRefusal:
    """Why a ledger category cannot be evaluated; ``reason`` is a shared issue-reason string."""

    reason: str
    detail: str


def resolve_category_rule(
    category_id: str,
    *,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    profile_year: int,
) -> tuple[SpendingCategory, CategoryProfile] | CategoryRuleRefusal:
    """Resolve a ledger category and the profile selected for the taxpayer's residence.

    Returns:
        The category with its selected profile, or the refusal naming why the
        taxonomy, the year's profiles or the residence comunidad cannot supply one.
    """
    try:
        category = normalize_spending_category(category_id)
    except ValueError:
        return CategoryRuleRefusal(
            _shared_issue_reasons.UNKNOWN_CATEGORY,
            f"ledger category {category_id!r} is not in the spending taxonomy",
        )
    profile = profiles.get(category)
    if profile is None:
        return CategoryRuleRefusal(
            _shared_issue_reasons.MISSING_CATEGORY_PROFILE,
            f"category {category.value!r} has no profile for {profile_year}",
        )
    category_region_overrides = {
        ccaa: overrides[category] for ccaa, overrides in region_overrides.items() if category in overrides
    }
    selected_profile = select_deductibility_profile(
        state_profile=profile,
        region_override_profiles=category_region_overrides,
        context=context,
    )
    if selected_profile is None:
        return CategoryRuleRefusal(
            _shared_issue_reasons.REGION_UNDECLARED_FOR_OVERRIDE,
            (
                f"category {category.value!r} carries a territorial-regime deductibility override for "
                f"{profile_year} but the residence comunidad autonoma is undeclared"
            ),
        )
    return category, selected_profile


def aggregate_renta_ledger_expenses_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    ports: InvoiceCatalogueReadPorts,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
    modelo: str = Modelo("100").value,
    profile_record: UserProfileRecord | None = None,
    region_category_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]] | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    profile_decode_context: ProfileDecodeContext | None = None,
    operation: PinnedAuthorityOperation | None = None,
    ownership_share: Decimal | None = None,
    register_owned_transaction_ids: frozenset[str] = frozenset(),
) -> RentaLedgerExpenseAggregation:
    """Load persisted catalogues and aggregate first-slice Renta expenses.

    Derives the ordinary-residence comunidad autonoma from the bucket's active
    profile (``tax_residence.ccaa``) and threads it into the aggregation so a
    territorial-regime deductibility override selects by residence; the axis is
    fail-closed (an undeclared or unparseable region resolves to the state year
    profile) and byte-identical while the override layer is empty. Pass
    ``profile_record`` to supply the :class:`UserProfileRecord` directly (the
    residence is otherwise loaded from the bucket), and ``region_category_overrides``
    to supply the per-:class:`CCAA` override layer forwarded to
    :func:`aggregate_renta_ledger_expenses` (defaulting to the empty
    registry-provisioned layer, :func:`resolve_region_category_profiles`).

    Also derives the activity's IVA-deduction ratio (:func:`resolve_iva_deduction_ratio`)
    from the bucket's ``iva.regime`` profile fact and its
    :class:`~domain.prorrata_register.register.ProrrataRegister`, so the non-recoverable
    share of input IVA joins the IRPF-deductible cost basis (PGC NRV 12.ª) for
    an exempt or prorrata-rationed activity. ``prorrata_register_repository``
    supplies the canonical register store explicitly.

    Returns a :class:`RentaLedgerExpenseAggregation`.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_renta_ledger_expenses_from_repositories(
                bucket_id=bucket_id,
                period=period,
                ports=ports,
                profile_year=profile_year,
                usage_ratios=usage_ratios,
                activity_key=activity_key,
                modelo=modelo,
                profile_record=profile_record,
                region_category_overrides=region_category_overrides,
                prorrata_register_repository=prorrata_register_repository,
                profile_decode_context=profile_decode_context,
                operation=indexed_operation,
                ownership_share=ownership_share,
                register_owned_transaction_ids=register_owned_transaction_ids,
            )
    if profile_decode_context is None:
        profile_decode_context = operation.profile_decode_context()
    # NOT pre-filtered by date range: a transaction's OWN
    # date can fall outside the requested annual window while its LINKED
    # INVOICE's issue date (the actual ``fact.filing_date`` the classifier
    # below tests) falls inside it, and the reverse — a transaction inside the
    # window whose linked invoice puts it outside. Pre-filtering by the
    # transaction's own date with ``load_for_date_range`` silently drops both
    # shapes before ``_classify_renta_transaction`` ever runs, so the
    # ``OUTSIDE_PERIOD`` diagnostic the operator needs to see never fires for a
    # multi-year catalogue. Mirrors the same revert already applied to
    # ``_iva_ledger`` / ``_renta_income_ledger`` / ``_renta_gasto_ledger`` /
    # ``_impatriado_income_ledger`` for the identical reason.
    require_catalogue_reads_bound_to(ports, bucket_id=bucket_id)
    transactions = ports.transaction_reader.load()
    invoices = ports.invoice_reader.load()
    residence_ccaa = resolve_residence_ccaa(
        bucket_id=bucket_id,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        operation=operation,
    )
    resolved_ejercicio = profile_year if profile_year is not None else period.filing_year
    iva_deduction_ratio = resolve_iva_deduction_ratio(
        bucket_id=bucket_id,
        ejercicio=resolved_ejercicio,
        profile_record=profile_record,
        prorrata_register_repository=prorrata_register_repository,
        profile_decode_context=profile_decode_context,
        operation=operation,
    )
    return aggregate_renta_ledger_expenses(
        transactions,
        invoices,
        bucket_id=bucket_id,
        period=period,
        profile_year=profile_year,
        usage_ratios=usage_ratios,
        activity_key=activity_key,
        modelo=modelo,
        residence_ccaa=residence_ccaa,
        region_category_overrides=region_category_overrides,
        iva_deduction_ratio=iva_deduction_ratio,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        operation=operation,
        ownership_share=ownership_share,
        register_owned_transaction_ids=register_owned_transaction_ids,
    )


def aggregate_renta_ledger_expenses(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    period: Period,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
    modelo: str = Modelo("100").value,
    residence_ccaa: CCAA | None = None,
    region_category_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]] | None = None,
    iva_deduction_ratio: Decimal | None = None,
    profile_record: UserProfileRecord | None = None,
    profile_decode_context: ProfileDecodeContext | None = None,
    operation: PinnedAuthorityOperation | None = None,
    ownership_share: Decimal | None = None,
    register_owned_transaction_ids: frozenset[str] = frozenset(),
) -> RentaLedgerExpenseAggregation:
    """Aggregate classified ledger transactions into Renta expense observations.

    Args:
        transactions: The :class:`TransactionCatalogue` supplying active ledger entries.
        invoices: The :class:`InvoiceCatalogue` used for invoice-linked deductibility checks.
        bucket_id: Activity bucket identifier for scoping the aggregation.
        period: Filing period as a typed :class:`Period` instance.
        profile_year: Optional category-profile year override; defaults to the
            ``period.filing_year`` when ``None``.
        usage_ratios: Optional per-:class:`SpendingCategory` business-use ratio
            overrides applied before deductibility calculation.
        activity_key: Activity identifier carried through to the produced
            observations' provenance; defaults to ``"default"``.
        modelo: Modelo identifier (``"100"`` IRPF or ``"130"`` pagos
            fraccionados) selecting the per-modelo deductibility rules.
        residence_ccaa: Optional ordinary residence comunidad autonoma, used only
            to select a territorial-regime deductibility override; inert while the
            override layer is empty and general expense deductibility is state law.
        region_category_overrides: Optional per-:class:`CCAA` category-profile
            override layer; defaults to :func:`resolve_region_category_profiles`
            (empty) so every fact falls through to the state year profile.
        iva_deduction_ratio: Optional activity-wide IVA-deduction fraction
            (LIVA arts. 94/104), threaded onto :class:`RentaDeductibilityContext`
            so the non-recoverable share of a fact's input IVA joins its
            IRPF-deductible cost basis. ``None`` (the default) preserves the
            historic base-only behaviour.
        profile_record: Optional :class:`UserProfileRecord` override; when ``None``
            the record is loaded from the bucket. Supplies the LIRPF art. 30.2.5.a
            insured-person counts that split the seguro de enfermedad cap across
            its 500 and 1.500 euro limbs.
        profile_decode_context: Optional decode context from the caller-held
            authority operation when ``profile_record`` is supplied directly.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.
        ownership_share: The taxpayer's ownership share of the partly affected
            dwelling, applied by the categories whose rule requires it.
        register_owned_transaction_ids: The ledger rows the activity-asset
            register declares as an asset's acquisition; the register deducts
            them through its amortization schedule.

    Returns a :class:`RentaLedgerExpenseAggregation` containing the accepted
    observations, exclusion issues, and binding-ready casilla totals.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_renta_ledger_expenses(
                transactions,
                invoices,
                bucket_id=bucket_id,
                period=period,
                profile_year=profile_year,
                usage_ratios=usage_ratios,
                activity_key=activity_key,
                modelo=modelo,
                residence_ccaa=residence_ccaa,
                region_category_overrides=region_category_overrides,
                iva_deduction_ratio=iva_deduction_ratio,
                profile_record=profile_record,
                profile_decode_context=profile_decode_context,
                operation=indexed_operation,
                ownership_share=ownership_share,
                register_owned_transaction_ids=register_owned_transaction_ids,
            )
    if profile_decode_context is None:
        profile_decode_context = operation.profile_decode_context()
    resolved_period = _resolve_annual_period(period)
    resolved_profile_year = profile_year if profile_year is not None else resolved_period.filing_year
    rules = resolve_category_deduction_rules(
        bucket_id=bucket_id,
        profile_year=resolved_profile_year,
        modelo=modelo,
        usage_ratios=usage_ratios,
        residence_ccaa=residence_ccaa,
        region_category_overrides=region_category_overrides,
        iva_deduction_ratio=iva_deduction_ratio,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        operation=operation,
        ownership_share=ownership_share,
        register_owned_transaction_ids=register_owned_transaction_ids,
    )
    observations: list[RentaDeductibleExpenseObservation] = []
    issues: list[RentaLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
            # Operator reviewed and deliberately excluded this row from filing
            # (a final disposition): omit it silently, no observation and no
            # advisory-bearing issue.
            continue
        outcome = _classify_renta_transaction(
            transaction,
            invoices=invoices,
            bucket_id=bucket_id,
            resolved_period=resolved_period,
            resolved_profile_year=resolved_profile_year,
            profiles=rules.profiles,
            region_overrides=rules.region_overrides,
            context=rules.context,
            activity_key=activity_key,
        )
        if isinstance(outcome, RentaLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    observations = _apply_statutory_cap_trims(observations, rules=rules)
    casilla_aggregation = _casilla_aggregation(resolved_period, observations, modelo=modelo)
    return RentaLedgerExpenseAggregation(
        modelo=modelo,
        period=resolved_period,
        profile_year=resolved_profile_year,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _classify_renta_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    resolved_period: Period,
    resolved_profile_year: int,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    activity_key: str,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Filter + classify one ledger transaction against the Renta-expense pipeline.

    Returns either a typed :class:`RentaDeductibleExpenseObservation`
    (the transaction survives every gate and is eligible) or a typed
    :class:`RentaLedgerAggregationIssue` (any gate rejects it). The
    twelve original early-return branches each project to a typed
    issue with their dedicated reason code; the eligible path returns
    the constructed observation.
    """
    direction = _renta_direction_for(transaction.direction, transaction.purchase_invoice_evidence_id)
    if direction is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
            f"transaction direction {transaction.direction.value!r} is not a Renta expense flow",
        )
    if is_non_eur_without_conversion(transaction):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            f"transaction currency {transaction.raw.currency!r} is not supported for Renta expenses",
        )
    # Use the EUR projection after rejecting unconverted non-EUR rows, so converted
    # rows contribute their EUR equivalent while EUR rows retain their raw amount.
    eur_amount = effective_eur_amount(transaction)
    proportion = _renta_business_proportion_or_issue(transaction)
    if isinstance(proportion, RentaLedgerAggregationIssue):
        return proportion
    category_profile = _renta_category_profile_or_issue(
        transaction,
        profiles=profiles,
        region_overrides=region_overrides,
        context=context,
        profile_year=resolved_profile_year,
    )
    if isinstance(category_profile, RentaLedgerAggregationIssue):
        return category_profile
    category, profile = category_profile
    proportion = row_scaling_proportion(transaction, proportion, profile.proportionality)
    fact = _renta_expense_fact_or_issue(
        transaction,
        invoices=invoices,
        bucket_id=bucket_id,
        direction=direction,
        category=category,
        activity_key=activity_key,
        eur_amount=eur_amount,
        proportion=proportion,
    )
    if isinstance(fact, RentaLedgerAggregationIssue):
        return fact
    return _renta_observation_or_issue(
        transaction,
        fact=fact,
        profile=profile,
        context=context,
        period=resolved_period,
    )


def _renta_business_proportion_or_issue(
    transaction: Transaction,
) -> Decimal | RentaLedgerAggregationIssue:
    """Return the annual filing business proportion or its precise refusal."""
    # Annual filing deliberately refuses the actividad marker that quarterly M130
    # accepts, through the shared predicate rather than a second policy copy.
    proportion = renta_expense_business_proportion(transaction, accept_activity_marker=False)
    if proportion is not None:
        return proportion
    if relies_on_activity_marker(transaction):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.ACTIVITY_MARKED_PENDING_ANNUAL_REVIEW,
            "actividad-marked expense needs business-classification review before the annual declaration",
        )
    reason = (
        RentaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
        if transaction.business_classification is BusinessClassification.PERSONAL
        else RentaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
    )
    return _renta_transaction_issue(
        transaction,
        reason,
        f"business classification {transaction.business_classification.value!r} cannot feed Renta expenses",
    )


def _renta_category_profile_or_issue(
    transaction: Transaction,
    *,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    profile_year: int,
) -> tuple[SpendingCategory, CategoryProfile] | RentaLedgerAggregationIssue:
    """Resolve the first-slice category and the profile selected for residence."""
    category_id = transaction.category_id
    if category_id is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.MISSING_CATEGORY,
            "classified expense transaction has no ledger category",
        )
    resolved = resolve_category_rule(
        category_id,
        profiles=profiles,
        region_overrides=region_overrides,
        context=context,
        profile_year=profile_year,
    )
    if isinstance(resolved, CategoryRuleRefusal):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason(resolved.reason),
            resolved.detail,
        )
    return resolved


def _renta_expense_fact_or_issue(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    direction: RentaExpenseDirection,
    category: SpendingCategory,
    activity_key: str,
    eur_amount: Decimal,
    proportion: Decimal,
) -> RentaDeductibleExpenseFact | RentaLedgerAggregationIssue:
    """Enrich a transaction with invoice evidence and construct its expense fact."""
    evidence_payload = purchase_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction_id=transaction.transaction_id,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        category_id=transaction.category_id,
        transaction_amount=eur_amount,
    )
    if isinstance(evidence_payload, RentaLedgerAggregationIssue):
        return evidence_payload
    try:
        return RentaDeductibleExpenseFact(
            transaction_id=transaction.transaction_id,
            invoice_id=transaction.purchase_invoice_evidence_id,
            catalogue_id=_LEDGER_CATALOGUE_ID,
            operation_date=transaction.raw.value_date or transaction.raw.booked_date,
            invoice_issue_date=evidence_payload.invoice_issue_date,
            posting_date=transaction.raw.booked_date,
            gross_amount=_business_fact_amount(eur_amount, proportion),
            taxable_base=_business_fact_amount(taxable_base_for(transaction, evidence_payload), proportion),
            iva_amount=_business_fact_amount(iva_amount_for(transaction, evidence_payload), proportion),
            direction=direction,
            category=category,
            activity_key=activity_key,
            exclusive_business_use=exclusive_business_use(transaction),
        )
    except ValueError as exc:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            str(exc),
        )


def _renta_observation_or_issue(
    transaction: Transaction,
    *,
    fact: RentaDeductibleExpenseFact,
    profile: CategoryProfile,
    context: RentaDeductibilityContext,
    period: Period,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Apply filing-period and deductibility gates to one validated fact."""
    if not period.contains(fact.filing_date):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            f"filing date {fact.filing_date.isoformat()} is outside {period}",
        )
    result = evaluate_renta_deductibility(fact, profile, context)
    if result.status is not RentaDeductibilityStatus.ELIGIBLE:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason(refusal_issue_reason(result)),
            result.reason,
        )
    try:
        return build_renta_deductible_expense_observation(fact, result, tax_year=period.filing_year)
    except ValueError as exc:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            str(exc),
        )


def refusal_issue_reason(result: RentaDeductibilityResult) -> str:
    """Return the shared issue reason a refused deductibility result reports.

    A refusal that asks the operator for one specific fact keeps its own
    reason; every other refusal is the generic ineligible-deductibility reason.
    """
    if result.refusal is not None:
        return result.refusal.value
    return _shared_issue_reasons.INELIGIBLE_DEDUCTIBILITY


def _apply_statutory_cap_trims(
    observations: list[RentaDeductibleExpenseObservation],
    *,
    rules: RentaCategoryDeductionRules,
) -> list[RentaDeductibleExpenseObservation]:
    """Hold the observations that share one statutory cap to that cap together."""
    trims = statutory_cap_trims(
        tuple(
            StatutoryCapClaim(
                claim_id=observation.observation_id,
                transaction_id=observation.transaction_id,
                category=observation.category,
                claim_date=observation.operation_date,
                deductible_amount=observation.deductible_amount,
            )
            for observation in observations
        ),
        profiles=rules.profiles,
        context=rules.context,
    )
    if not trims:
        return observations
    return [
        _trimmed_observation(observation, trims[observation.observation_id])
        if observation.observation_id in trims
        else observation
        for observation in observations
    ]


def _trimmed_observation(
    observation: RentaDeductibleExpenseObservation,
    deductible_amount: Decimal,
) -> RentaDeductibleExpenseObservation:
    gross = observation.gross_amount
    return observation.model_copy(
        update={
            "deductible_amount": deductible_amount,
            "non_deductible_amount": gross - deductible_amount,
            "applied_ratio": Decimal("0") if gross == Decimal("0") else deductible_amount / gross,
        },
    )


def _renta_transaction_issue(
    transaction: Transaction,
    reason: RentaLedgerAggregationIssueReason,
    detail: str,
) -> RentaLedgerAggregationIssue:
    return RentaLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        category_id=transaction.category_id,
        reason=reason,
        detail=detail,
    )


def _resolve_annual_period(period: Period) -> Period:
    resolved = period
    if resolved.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            tr("aggregation.renta_ledger.errors.annual_period_required"),
            context={"period": str(resolved)},
        )
    return resolved


def _renta_direction_for(
    direction: TransactionDirection,
    purchase_invoice_evidence_id: str | None,
) -> RentaExpenseDirection | None:
    if direction is TransactionDirection.OUTGOING:
        return RentaExpenseDirection.OUTGOING_EXPENSE
    if direction is TransactionDirection.INCOMING and purchase_invoice_evidence_id is not None:
        return RentaExpenseDirection.REFUND
    return None


@overload
def _business_fact_amount(amount: None, proportion: Decimal) -> None: ...
@overload
def _business_fact_amount(amount: Decimal, proportion: Decimal) -> Decimal: ...
def _business_fact_amount(amount: Decimal | None, proportion: Decimal) -> Decimal | None:
    if amount is None:
        return None
    if amount < ZERO:
        raise ValueError("ledger amount must be a non-negative magnitude")
    return amount * proportion


def _casilla_aggregation(
    period: Period,
    observations: Sequence[RentaDeductibleExpenseObservation],
    *,
    modelo: str,
) -> CasillaAggregation:
    totals: dict[CasillaId, Decimal] = {}
    provenance_rows: list[CasillaProvenance] = []
    grouped: dict[tuple[CasillaId, SpendingCategory], list[RentaDeductibleExpenseObservation]] = {}
    for observation in observations:
        totals[observation.target_casilla_id] = (
            totals.get(observation.target_casilla_id, Decimal("0")) + observation.deductible_amount
        )
        grouped.setdefault((observation.target_casilla_id, observation.category), []).append(observation)
    for (casilla, category), rows in sorted(grouped.items()):
        provenance_rows.append(
            CasillaProvenance(
                casilla_id=casilla,
                category_id=category,
                transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
                subtotal=sum((row.deductible_amount for row in rows), start=Decimal("0")),
            ),
        )
    return CasillaAggregation(
        modelo=modelo,
        period=period,
        casilla_values=totals,
        provenance=tuple(provenance_rows),
    )


__all__ = [
    "CategoryRuleRefusal",
    "RentaCategoryDeductionRules",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
    "resolve_category_deduction_rules",
    "resolve_category_rule",
    "resolve_residence_ccaa",
]
