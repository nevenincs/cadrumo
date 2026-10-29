"""Classify IVA ledger evidence and calculate annual deductible totals."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.external_constants import DEFAULT_CURRENCY
from ...core.i18n.render import tr as render_tr
from ...core.period import Period
from ...core.time.clock import today_madrid
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.iva_category_catalogue import require_iva_category
from ...domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    especial_prorrata_register_regime,
    general_prorrata_register_regime,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.categories.proportionality import IvaMixedUseRule, IvaMixedUseShare
from ...domain.categories.registry import resolve_category_profile
from ...domain.categories.spending_category_catalogue import require_spending_category
from ...domain.iva.classification import territorial_scope_alias
from ...domain.iva.errors import ProrrataInputError
from ...domain.iva.establishment import (
    StatedCountryCodeStatus,
    stated_country_code_status,
    territorial_scope_for_country,
)
from ...domain.iva.lookup import unique_rate_kind_for_declared_rate
from ...domain.iva.prorrata import (
    ProrrataReference,
    validate_prorrata_reference,
)
from ...domain.iva.schema import (
    EUMemberState,
    IvaCategory,
    IvaRateKind,
    spanish_eu_member_state,
)
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.enums import BusinessClassification
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .business_proportion import business_proportion
from .currency_predicates import effective_eur_taxable_base
from .iva_ledger import (
    AnnualDeducibleTotalsByRegime,
    IvaLedgerAggregationIssue,
    IvaLedgerAggregationIssueReason,
    aggregate_iva_ledger_observations_from_repositories,
)
from .iva_ledger_apportionment import deducible_cuota_binding_ids, resolve_iva_ledger_binding_values


def _unclassified_deducible_soportado_count(
    revision: ModeloRevision,
    observations: Sequence[IvaLedgerObservation],
    deducible_binding_ids: frozenset[BindingId],
    *,
    operation: PinnedAuthorityOperation,
) -> int:
    """Count deducible-cuota observations that carry no ``input_classification``.

    A deducible soportado observation is one whose own canonically-resolved
    contribution lands on at least one deducible cuota binding (the registry
    selector decides membership; no category is hard-coded here). An observation
    with no declared ``input_classification`` is one the art. 106 especial total
    cannot honestly route, so the general filer must classify it before the art. 103.Dos.2.º
    check can run. The signal drives the CHECK-vs-PROMPT branch in the settlement
    collector.
    """
    count = 0
    for observation in observations:
        if observation.input_classification is not None:
            continue
        single = resolve_ledger_iva_aggregation_binding_values(revision, (observation,))
        if any(single.get(binding_id, Decimal("0")) != Decimal("0") for binding_id in deducible_binding_ids):
            count += 1
    return count


def compute_annual_deducible_totals_by_regime(
    *,
    bucket_id: str,
    ejercicio: int,
    revision: ModeloRevision,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    investment_asset_register: BienesInversionIvaRegister,
    investment_asset_profile_id: str,
    operation: PinnedAuthorityOperation,
) -> AnnualDeducibleTotalsByRegime | None:
    """Compute the ejercicio's deducible IVA cuota under both prorrata regimes.

    The plumbing for the LIVA art. 103.Dos.2.º mandatory-especial settlement
    check. Aggregates the ejercicio's annual IVA observations ONCE
    (:func:`aggregate_iva_ledger_observations_from_repositories` over the
    canonical ``0A`` annual :class:`~core.period.Period`), then resolves
    :func:`resolve_iva_ledger_binding_values` TWICE over the same observations —
    once with a GENERAL-stamped and once with an ESPECIAL-stamped
    :class:`IvaLedgerProrrataApportionment` at the register's resolved percentage
    — and sums the deducible-cuota binding ids under each. One aggregation, two
    apportionment passes through the one canonical resolver
    (``aeat-calculation-aggregation``); no second aggregation
    implementation is introduced.

    Returns ``None`` when no register apportionment resolves for the ejercicio
    (prorrata inapplicable), when the register is sectorized (LIVA arts. 9.1.c /
    101 — the art-103.Dos.2.º comparison composes per sector, a named v1 deferral),
    or when the revision declares no deducible cuota bindings. A negative
    deducible total (an adjustment-heavy degenerate case the art-103.Dos.2
    comparison is undefined over) also returns ``None`` so the check stays silent
    rather than crashing on a non-comparable input.

    Args:
        bucket_id: Active bucket whose annual ledger and prorrata register are
            read.
        ejercicio: The filing year whose annual deducible totals are computed.
        revision: The target :class:`ModeloRevision` whose deducible cuota
            bindings are summed.
        transaction_repository: Required bucket-bound catalogue capability.
        prorrata_register_repository: Canonical register repository for the
            same bucket as the transaction catalogue.
        investment_asset_register: Bienes-inversion authority the year's
            investment acquisitions are reciprocal to; a year that acquired a
            bien de inversión cannot aggregate without it.
        investment_asset_profile_id: Profile that owns that register.
        operation: Caller-owned pinned authority operation retained through the
            annual aggregation.

    See Also:
        :class:`AnnualDeducibleTotalsByRegime`
            The frozen record returned.
        :func:`~application.calculations.prorrata_especial_advisory.build_prorrata_especial_mandatory_advisory`
            Consumes the two totals to build the mandatory-especial advisory.
    """
    period = Period.from_year_and_code(ejercicio, "0A")
    aggregation = aggregate_iva_ledger_observations_from_repositories(
        bucket_id=bucket_id,
        period=period,
        transaction_repository=transaction_repository,
        investment_asset_register=investment_asset_register,
        investment_asset_profile_id=investment_asset_profile_id,
        operation=operation,
        prorrata_register_repository=prorrata_register_repository,
    )
    apportionment = aggregation.prorrata_apportionment
    if apportionment is None:
        return None
    if apportionment.sector_apportionments:
        # Sectorized register: the art-103.Dos.2.º comparison composes per sector,
        # a named v1 deferral (LIVA arts. 9.1.c / 101). No branch in v1.
        return None
    deducible_binding_ids = deducible_cuota_binding_ids(revision)
    if not deducible_binding_ids:
        return None
    observations = tuple(aggregation.observations)
    general_apportionment = apportionment.model_copy(
        update={"regime": general_prorrata_register_regime(authority=operation)},
    )
    especial_apportionment = apportionment.model_copy(
        update={"regime": especial_prorrata_register_regime(authority=operation)},
    )
    general_values = resolve_iva_ledger_binding_values(
        revision,
        observations,
        prorrata_apportionment=general_apportionment,
        operation=operation,
    )
    especial_values = resolve_iva_ledger_binding_values(
        revision,
        observations,
        prorrata_apportionment=especial_apportionment,
        operation=operation,
    )
    deduction_under_general = sum(
        (general_values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids),
        Decimal("0"),
    )
    deduction_under_especial = sum(
        (especial_values.get(binding_id, Decimal("0")) for binding_id in deducible_binding_ids),
        Decimal("0"),
    )
    if deduction_under_general < Decimal("0") or deduction_under_especial < Decimal("0"):
        return None
    return AnnualDeducibleTotalsByRegime(
        deduction_under_general=deduction_under_general,
        deduction_under_especial=deduction_under_especial,
        unclassified_deducible_count=_unclassified_deducible_soportado_count(
            revision,
            observations,
            deducible_binding_ids,
            operation=operation,
        ),
        regime=apportionment.regime,
    )


#: The registry-declared categories whose exemption rests on the operation
#: leaving the Union.  The category membership is filing law, not aggregation
#: mechanics, so the ledger reads the dated classification catalogue rather
#: than maintaining a second Python list beside the invoice classifier.
def _registry_export_categories(
    *,
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> frozenset[IvaCategory]:
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-invoice-classification-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("IVA classification catalogue must resolve as a mapping fact")
    entries = _unique_iva_classification_entries(resolved)
    raw_categories = entries.get("counterparty.export_categories")
    if raw_categories is None:
        raise ValueError("IVA classification catalogue is missing counterparty.export_categories")
    return _parse_export_categories(raw_categories, operation=operation)


def _unique_iva_classification_entries(resolved: ResolvedMappingFact) -> dict[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("IVA classification entries must be string-to-string")
        if entry.key in entries:
            raise ValueError(f"duplicate IVA classification entry {entry.key!r}")
        entries[entry.key] = entry.value

    return entries


def _parse_export_categories(raw_categories: str, *, operation: PinnedAuthorityOperation) -> frozenset[IvaCategory]:
    try:
        categories = frozenset(
            require_iva_category(token.strip(), authority=operation)
            for token in raw_categories.split(",")
            if token.strip()
        )
    except ValueError as exc:
        raise ValueError("IVA classification catalogue contains an unknown export category") from exc
    if not categories:
        raise ValueError("IVA classification catalogue declares no export categories")
    return categories


def _export_establishment_is_answerable(
    counterparty_country: str | None,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether this country evidence may carry an export exemption.

    Two different situations are allowed through, and collapsing them would be
    wrong in opposite directions.

    A code the vocabulary places in a third country answers the question
    outright -- that is the exemption's actual premise.

    A code the vocabulary does NOT carry is also allowed through, and that
    carve-out is what separates a guard from a trap. The scope resolver answers
    from a closed table, so a well-formed code naming a real jurisdiction it
    does not list resolves to nothing, and such jurisdictions exist at any
    moment because the table is a bounded subset that grows. The establishment
    is then a gap in OUR data rather than in the operator's, and refusing there
    would reject a legitimate export over a row nobody has written. A refusal an
    operator cannot act on is how they learn to skip refusals, which costs more
    than the case it catches. The ingestion path's
    declared-relief guard spares the same status on the same authority, so the
    two surfaces cannot disagree about what evidence an export needs.

    Everything else is refused: an absent code, a malformed one, and an
    ISO-unassigned pair, each of which genuinely establishes nothing about
    where the party is.
    """
    if territorial_scope_for_country(counterparty_country, operation=operation) == territorial_scope_alias(
        "third_country",
        operation=operation,
    ):
        return True
    return stated_country_code_status(counterparty_country, operation=operation) is StatedCountryCodeStatus.UNCATALOGUED


def validate_intracom_export_counterparty(
    *,
    transaction_id: str,
    category: IvaCategory,
    counterparty_country: str | None,
    eu_member_state: EUMemberState | None,
    identification_state: EUMemberState | None,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Return a gate issue when the counterparty/category coupling is violated.

    Rules:

    - ``INTRA_COMMUNITY_SUPPLY`` requires a non-ES ``identification_state``.
    - Export and export-assimilated categories require the counterparty to be
      POSITIVELY established in a third country, and must carry no
      ``EUMemberState``.

    The two rules read DIFFERENT facts, deliberately. Ley 37/1992 art. 25
    exempts on the acquirer holding an IVA identification assigned by another
    Member State and says nothing about where it has its sede, so the
    intra-community rule reads identification and establishment does not enter
    it at all. The export rule is the one genuinely about place -- an export
    leaves the Union -- so it keeps reading establishment.

    Absent identification refuses rather than falling back to
    ``eu_member_state``. That fallback is precisely the defect this shape
    replaced: it read an address fact as a registration fact, over-declaring a
    Spanish-established acquirer holding a German IVA number and silently
    under-declaring a German-established acquirer purchasing under a Spanish
    NIF-IVA.
    """
    if category == require_iva_category("intra_community_supply", authority=operation):
        if identification_state is None:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
                detail=render_tr(
                    "aggregation.iva_ledger.errors.missing_counterparty_identification_state",
                ),
            )
        if identification_state == spanish_eu_member_state(authority=operation):
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
                detail=render_tr(
                    "aggregation.iva_ledger.errors.domestic_identification_on_intra_community_transaction",
                ),
            )
    if category in _registry_export_categories(
        effective_date=effective_date or today_madrid(),
        operation=operation,
    ):
        if eu_member_state is not None:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
                detail=render_tr(
                    "aggregation.iva_ledger.errors.eu_member_state_on_export_transaction",
                    member_state=eu_member_state.value,
                ),
            )
        # Only NOW is absence reached, and it is refused rather than read as
        # third-country establishment. That inference is the defect this branch
        # closes: an export leaves the Union, so the exemption turns on where
        # the counterparty IS, and "no country recorded" is not a place. Read
        # as one it zero-rated a supply from a fact nobody had stated, which is
        # the under-declaration direction on the issued side.
        if not _export_establishment_is_answerable(counterparty_country, operation=operation):
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT,
                detail=render_tr(
                    "aggregation.iva_ledger.errors.missing_counterparty_establishment_on_export",
                ),
            )
    return None


def validate_iva_ledger_counterparty_category(
    transaction: Transaction,
    *,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Return the D5 counterparty/category gate :class:`IvaLedgerAggregationIssue` for a ledger transaction."""
    category = transaction.iva_category
    if category is None:
        return None
    return validate_intracom_export_counterparty(
        transaction_id=transaction.transaction_id,
        category=category,
        counterparty_country=transaction.counterparty_country,
        eu_member_state=transaction.counterparty_eu_member_state,
        identification_state=transaction.counterparty_identification_state,
        effective_date=transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date,
        operation=operation,
    )


def validate_iva_ledger_deduction_classification(
    transaction: Transaction,
    *,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> IvaLedgerAggregationIssue | None:
    """Return the deduction-admissibility gate issue for a ledger row, or ``None``.

    The readiness layer's entry into the per-transaction IVA pipeline. It runs
    the real pre-observation gates in their real order and reports only the
    deduction verdict, so a readiness finding cannot contradict what calculation
    will do with the row: a row an earlier gate excludes yields nothing here,
    exactly as it contributes nothing there. Deriving the same facts a second
    time in this layer would have produced the opposite failure -- a readiness
    report blocking a filing over a row the projection path had already
    excluded for an unrelated reason.

    Scoped to rows that actually carry deduction authority. A row with neither a
    kind nor a provenance cannot be inadmissible on this axis, and skipping it
    keeps the readiness pass off the classification pipeline for the ordinary
    majority of a ledger.
    """
    if transaction.deduction_fact_kind is None and transaction.deduction_provenance is None:
        return None
    from ._iva_transaction import iva_transaction_gate_issue

    issue = iva_transaction_gate_issue(transaction, resolved_period=period, operation=operation)
    if issue is None or issue.reason not in IVA_LEDGER_DEDUCTION_GATE_REASONS:
        return None
    return issue


def business_proportionality_for(transaction: Transaction) -> Decimal | None:
    """Return the transaction’s reviewed business proportion."""
    return business_proportion(transaction.business_classification, transaction.business_pct)


def iva_category_deductible_proportion(
    transaction: Transaction,
    proportion: Decimal,
    *,
    operation_date: date,
    year: int,
    operation: PinnedAuthorityOperation,
) -> Decimal | None:
    """Return the share of a received row's cuota its category lets it deduct, or ``None`` for none.

    ``proportion`` is the row's business share: ``1`` for a BUSINESS row, the
    stated degree of use for a MIXED one. The category's IVA treatment decides
    what that share is worth (LIVA art. 95):

    - ``not_deductible``: a MIXED row deducts nothing; a BUSINESS row keeps its share.
    - ``degree_of_use``: the row's share.
    - ``bien_inversion_degree_of_use``: a MIXED row deducts its share only when
      the good's value makes it a bien de inversión (LIVA art. 108.Dos.5.º).
    - ``vehicle_presumption``: the presumed share of LIVA art. 95.Tres.2.ª,
      for a BUSINESS row as well, because booking the vehicle in the activity
      is no proof of a higher degree of use (LIVA art. 95.Tres.4.ª).

    A row without a category, or whose category the pinned authority does not
    declare, keeps its own share.

    Args:
        transaction: The received ledger row.
        proportion: The row's business share.
        operation_date: The date the bien de inversión threshold is read for.
        year: The filing year whose category profiles apply.
        operation: The caller-owned authority generation.

    Returns:
        The deductible share, or ``None`` when the category grants no deduction
        for the row's use.
    """
    rule = _category_iva_mixed_use_rule(transaction, year=year, operation=operation)
    if rule is None:
        return proportion
    mixed = transaction.business_classification is BusinessClassification.MIXED
    if rule.share is IvaMixedUseShare.VEHICLE_PRESUMPTION:
        return rule.presumed_share
    if not mixed or rule.share is IvaMixedUseShare.DEGREE_OF_USE:
        return proportion
    if rule.share is IvaMixedUseShare.BIEN_INVERSION_DEGREE_OF_USE:
        base = effective_eur_taxable_base(transaction)
        threshold = _bien_inversion_threshold(operation_date=operation_date, operation=operation)
        return proportion if base is not None and base >= threshold else None
    return None


def _category_iva_mixed_use_rule(
    transaction: Transaction,
    *,
    year: int,
    operation: PinnedAuthorityOperation,
) -> IvaMixedUseRule | None:
    """Return the IVA treatment the row's category declares, or ``None``."""
    if transaction.category_id is None:
        return None
    try:
        category = require_spending_category(
            transaction.category_id,
            effective_date=date(year, 12, 31),
            authority=operation,
        )
    except RegistryValidationError:
        return None
    return resolve_category_profile(category, year, operation=operation).proportionality.iva_mixed_use


_BIEN_INVERSION_THRESHOLD_FACT_ID: Final = "iva-bien-inversion-escaso-valor-threshold"


def _bien_inversion_threshold(*, operation_date: date, operation: PinnedAuthorityOperation) -> Decimal:
    """Return the acquisition value below which a good is not a bien de inversión (LIVA art. 108.Dos.5.º)."""
    resolved = operation.resolve_governed_fact(
        ScalarFactQuery(
            fact_id=_BIEN_INVERSION_THRESHOLD_FACT_ID,
            date_axis=DateAxis.TRANSACTION_DATE,
            effective_date=operation_date,
        )
    )
    if not isinstance(resolved, ResolvedScalarFact) or not isinstance(resolved.payload.value, Decimal):
        raise RegistryValidationError(f"{_BIEN_INVERSION_THRESHOLD_FACT_ID} must resolve to one decimal amount")
    return resolved.payload.value


def has_converted_non_eur_amount(transaction: Transaction) -> bool:
    """Report whether a foreign-currency amount has a EUR conversion."""
    return transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is not None


def missing_tax_fact_reason(transaction: Transaction) -> IvaLedgerAggregationIssueReason | None:
    """Return the first missing tax fact, if any."""
    reasons = iva_ledger_missing_fact_reasons(transaction)
    return reasons[0] if reasons else None


#: The required IVA tax fact behind each missing-fact reason, in report order.
#:
#: Read as the single source of both the probe and the emission set, so
#: :data:`IVA_LEDGER_MISSING_FACT_REASONS` cannot fall out of step with what
#: :func:`iva_ledger_missing_fact_reasons` actually emits. A hand-listed
#: companion set would drift the moment a fourth required fact is added, and
#: the readiness layer downstream keys its operator-facing mapping on that set.
_MISSING_FACT_REASON_BY_FIELD: Final[Mapping[str, IvaLedgerAggregationIssueReason]] = {
    "taxable_base": IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
    "iva_amount": IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT,
    "iva_rate": IvaLedgerAggregationIssueReason.MISSING_IVA_RATE,
}

#: Every reason :func:`iva_ledger_missing_fact_reasons` can emit, derived.
IVA_LEDGER_MISSING_FACT_REASONS: Final[frozenset[IvaLedgerAggregationIssueReason]] = frozenset(
    _MISSING_FACT_REASON_BY_FIELD.values(),
)

#: Every reason :func:`validate_iva_ledger_counterparty_category` can emit.
#:
#: Declared rather than derived because the three branches read three different
#: counterparty facts and collapsing them into one table would erase the legal
#: distinction between identification and establishment the gate turns on. A
#: behavioural gate exercises the real screen across the category matrix and
#: asserts the observed emissions equal this set, so the declaration is pinned
#: to behaviour rather than trusted.
IVA_LEDGER_COUNTERPARTY_GATE_REASONS: Final[frozenset[IvaLedgerAggregationIssueReason]] = frozenset(
    {
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE,
        IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
        IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT,
    },
)

#: Every reason :func:`validate_iva_ledger_deduction_classification` can emit.
#:
#: One member, and still declared as a set for the same reason its two siblings
#: are: the readiness layer derives its own mapped domain from the union of the
#: screens it runs, so a screen that gains a second reason has to move this set
#: rather than arrive at a bare subscript with no entry.
IVA_LEDGER_DEDUCTION_GATE_REASONS: Final[frozenset[IvaLedgerAggregationIssueReason]] = frozenset(
    {IvaLedgerAggregationIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION},
)


def iva_ledger_missing_fact_reasons(transaction: Transaction) -> tuple[IvaLedgerAggregationIssueReason, ...]:
    """Return missing IVA fact reasons for a transaction without projecting it.

    Each element is an :class:`IvaLedgerAggregationIssueReason` describing
    one absent required tax fact.
    """
    return tuple(
        reason for field, reason in _MISSING_FACT_REASON_BY_FIELD.items() if getattr(transaction, field) is None
    )


def missing_tax_fact_detail(reason: IvaLedgerAggregationIssueReason) -> str:
    """Describe the missing fact represented by a reason."""
    field = reason.value.removeprefix("missing_")
    return f"transaction has no {field} fact"


def prorrata_reference_for(
    reference_id: str | None,
    *,
    transaction_id: str,
) -> ProrrataReference | IvaLedgerAggregationIssue | None:
    """Validate a prorrata reference or return its issue."""
    if reference_id is None:
        return None
    try:
        return validate_prorrata_reference(reference_id)
    except ProrrataInputError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
            detail=str(exc),
        )


def iva_rate_kind_for(
    rate: Decimal,
    *,
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> IvaRateKind | None:
    """Return the tier a declared rate belongs to, or ``None`` if it is not one.

    Delegates to the domain's exact-one projection of the registry-owned
    value-to-tier direction. Multiple numeric rates can belong to one tier;
    only multiple distinct matching tiers make this declared rate ambiguous.
    Without a published discriminator that settles that ambiguity, this path
    refuses by returning ``None``.
    """
    return unique_rate_kind_for_declared_rate(
        spanish_eu_member_state(effective_date=on_date, authority=operation),
        rate,
        on_date,
        operation=operation,
    )
