"""Canonical IVA ledger aggregation binding family."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, NamedTuple, Protocol

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator

from ....core.aggregation import (
    BindingAggregationOp,
    BindingSourceKind,
)
from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.unit_proportion import UnitProportion
from ...iva.deduction_facts import IvaDeductionClassificationProvenance, validate_iva_deduction_fact
from ...iva.flow import IvaFlowDirection, is_deducible_flow
from ...iva.prorrata import InputClassification
from ...iva.schema import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaLedgerObservationRole,
    IvaRateKind,
)
from ._ledger_binding_resolution import (
    UnroutedLedgerQuantity,
    resolve_ledger_family_binding_values,
    unrouted_ledger_family_quantities,
    unsupported_ledger_family_observations,
)
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .quantity_screen_enrolment import assert_quantity_readers_cover_independent_facts, independent_quantity_facts
from .schema import DataBindingDefinition, ModeloRevision
from .schema_base import coerce_decimal_tuple, coerce_enum_member, coerce_enum_tuple


class IvaLedgerObservation(BaseModel):
    """One factual ledger line tagged with the IVA classification triple.

    Modelo 303 / 322 / 353 / 309 / 390 binding selectors filter these
    observations by category, rate kind, and flow direction; the
    runtime aggregates the matched lines through the binding's
    aggregation operator.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place.
        category: Substrate :class:`IvaCategory` resolved by the
            classifier.
        rate_kind: Substrate :class:`IvaRateKind` rate tier.
        flow_direction: Substrate :class:`IvaFlowDirection` (output /
            input / self-assessed reverse charge).
        base_amount: Taxable base in EUR.
        iva_amount: IVA amount in EUR (cuota repercutida or soportada,
            depending on flow direction).
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    category: IvaCategory
    exemption_article: IvaExemptionArticle | None = None
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    base_amount: Decimal
    iva_amount: Decimal
    applied_rate: UnitProportion | None = None
    """The numeric IVA rate this line was charged at, as a fraction, when known.

    Carried ALONGSIDE :attr:`rate_kind` rather than instead of it, because the
    two answer different questions and the annual return asks both. ``rate_kind``
    is the semantic tier (general / reducido / super-reducido / zero); this is the
    rate that tier resolved to on this line's date. One tier can produce several
    rates within a single filing year: the anti-inflation food measures stepped
    the super-reducido tier 4 % to 2 % to 0 % and the reducido tier 10 % to 5 %
    to 7.5 % across successive extensions, which is why Modelo 390 carries one box
    per rate per window where Modelo 303 carries one per tier. Resolving to the
    tier and discarding the value made those boxes unpopulatable, because two
    lines at 4 % and 2 % arrived downstream indistinguishable.

    ``None`` where the rate is genuinely unknown rather than zero — a
    pre-classified candidate supplied without one, or an exempt line that carries
    no rate at all. A caller MUST NOT read ``None`` as 0 %: zero-rated and
    rate-less are different declarations, and :class:`IvaRateKind` already
    distinguishes ``ZERO`` from ``EXEMPT`` for exactly that reason.
    """
    recargo_amount: Decimal = Decimal("0")
    """Recargo de equivalencia cuota the supplier charged on a repercutido sale to
    a recargo-regime retailer, in EUR. ``Decimal("0")`` on every line that carries
    no recargo. Modelo 303 recargo cuota casillas select these via the
    ``recargo_amount_sum`` fact, routed by the line's IVA rate tier."""
    prorrata_reference_id: str | None = Field(default=None, min_length=1, max_length=128)
    """Stable id of the linked :class:`ProrrataLedgerReference` row, when set.

    Populated by the aggregator only on ``SOPORTADO`` (input IVA) flows
    that carry a validated prorrata reference. Downstream Modelo 303 /
    390 binding selectors filter prorrata-linked observations without
    a manual join against the parallel ``prorrata_references`` tuple.
    """
    cash_accounting_treatment: IvaCashAccountingTreatment = IvaCashAccountingTreatment.NONE
    """Independent criterio-de-caja affiliation for this projection."""
    observation_role: IvaLedgerObservationRole
    """Whether this is a monetary settlement or an art. 75 information projection.

    Cash-accounting operation and payment observations retain the same typed
    treatment affiliation.  Registry bindings select this orthogonal role so
    informational boxes cannot consume monetary settlements, and ordinary IVA
    boxes cannot consume the operation-date information projection.
    """
    input_classification: InputClassification | None = None
    """Operator-declared LIVA art. 106 prorrata-especial per-input use class.

    Carried from the source ledger transaction's
    ``input_classification``. Meaningful only for ``SOPORTADO`` (input IVA)
    rows in a bucket under prorrata especial: the regime-aware ledger IVA
    apportionment routes the deducible cuota by this classification (the
    art. 106.Uno reglas 100%/0%/general). ``None`` for every row not under
    especial or carrying no per-input use declaration; the general-regime
    apportionment ignores it.
    """
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    """Operator-declared LIVA arts. 9.1.c / 101 differentiated sector.

    Carried from the source ledger transaction's ``prorrata_sector_id``.
    Meaningful only for ``SOPORTADO`` (input IVA) rows in a sectorized bucket:
    the sector-aware ledger IVA apportionment applies THAT sector's provisional
    percentage to the deducible cuota. ``None`` is a common-use input in a
    sectorized bucket (apportioned by the art. 104.Dos common percentage) and
    the whole-entity default otherwise; the non-sectorized apportionment ignores
    it.
    """
    deduction_fact_kind: IvaDeductionFactKind | None = None
    """Exact, evidence-grounded differentiated-sector deduction family."""
    deduction_provenance: IvaDeductionClassificationProvenance | None = None
    investment_asset_id: str | None = Field(default=None, min_length=1, max_length=128)
    rectifies_ledger_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def _enforce_exemption_article_category(self) -> IvaLedgerObservation:
        if self.exemption_article is not None and self.category is not IvaCategory.DOMESTIC_EXEMPT:
            raise RegistryValidationError(
                "exemption_article is only valid when category is DOMESTIC_EXEMPT; "
                f"got category {self.category.value!r}",
            )
        if not is_deducible_flow(self.flow_direction) or self.category is IvaCategory.RECARGO_EQUIVALENCIA:
            if self.deduction_fact_kind is not None or self.deduction_provenance is not None:
                raise RegistryValidationError("output IVA facts cannot carry deduction authority")
            return self
        if self.deduction_fact_kind is None or self.deduction_provenance is None:
            raise RegistryValidationError("input IVA facts require exact deduction authority")
        validate_iva_deduction_fact(
            kind=self.deduction_fact_kind,
            provenance=self.deduction_provenance,
            category=self.category,
            rate_kind=self.rate_kind,
            flow_direction=self.flow_direction,
            base_amount=self.base_amount,
            iva_amount=self.iva_amount,
            investment_asset_id=self.investment_asset_id,
            rectifies_ledger_id=self.rectifies_ledger_id,
        )
        return self


#: The closed fact vocabulary a ``ledger_iva_aggregation`` selector may declare.
#: Named rather than inlined at each check so the quantity screen below can
#: derive its screened set from the same vocabulary the validator enforces and
#: :func:`_iva_aggregate` dispatches on.
_IVA_SUPPORTED_FACTS: frozenset[str] = frozenset(
    {"iva_amount_sum", "base_amount_sum", "recargo_amount_sum"},
)


class _IvaLedgerSelector(BaseModel):
    """Validated form of a ledger_iva_aggregation binding selector."""

    model_config = STRICT_FROZEN_CONFIG

    categories: Annotated[tuple[IvaCategory, ...], BeforeValidator(coerce_enum_tuple(IvaCategory))] = Field(
        min_length=1,
    )
    exemption_articles: (
        Annotated[tuple[IvaExemptionArticle, ...], BeforeValidator(coerce_enum_tuple(IvaExemptionArticle))] | None
    ) = Field(default=None, min_length=1)
    rate_kinds: Annotated[tuple[IvaRateKind, ...], BeforeValidator(coerce_enum_tuple(IvaRateKind))] = Field(
        min_length=1,
    )
    flow_direction: Annotated[IvaFlowDirection, BeforeValidator(coerce_enum_member(IvaFlowDirection))]
    observation_roles: Annotated[
        tuple[IvaLedgerObservationRole, ...],
        BeforeValidator(coerce_enum_tuple(IvaLedgerObservationRole)),
    ] = Field(min_length=1)
    cash_accounting_treatments: Annotated[
        tuple[IvaCashAccountingTreatment, ...],
        BeforeValidator(coerce_enum_tuple(IvaCashAccountingTreatment)),
    ] = Field(min_length=1)
    applied_rates: Annotated[tuple[Decimal, ...], BeforeValidator(coerce_decimal_tuple)] | None = Field(
        default=None,
        min_length=1,
    )
    """Numeric rates this binding accepts, when the box is rate-specific.

    ``None`` -- the default and the shape every quarterly binding uses -- means
    the binding does not discriminate on the value and matches whatever rates
    its ``rate_kinds`` tiers admit. Set it only where the FORM asks per rate
    rather than per tier: Modelo 390 carries one box per rate per window because
    a tier's rate can change inside a filing year, so its 2 % box must reject a
    4 % line that shares the super-reducido tier with it.

    An observation whose ``applied_rate`` is ``None`` (rate genuinely unknown --
    an invoice-sourced line carries a rate slot, not a number) matches NO
    rate-specific binding. That is deliberate: admitting it would put an
    unmeasured line in a box that asserts a specific rate, and the annual return
    is where that assertion is read.
    """
    fact: Literal["iva_amount_sum", "base_amount_sum", "recargo_amount_sum"] = "iva_amount_sum"

    @field_validator("categories", mode="after")
    @classmethod
    def _categories_unique(cls, value: tuple[IvaCategory, ...]) -> tuple[IvaCategory, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("categories entries must be unique")
        return value

    @field_validator("rate_kinds", mode="after")
    @classmethod
    def _rate_kinds_unique(cls, value: tuple[IvaRateKind, ...]) -> tuple[IvaRateKind, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("rate_kinds entries must be unique")
        return value

    @field_validator("cash_accounting_treatments", mode="after")
    @classmethod
    def _cash_accounting_treatments_unique(
        cls,
        value: tuple[IvaCashAccountingTreatment, ...],
    ) -> tuple[IvaCashAccountingTreatment, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("cash_accounting_treatments entries must be unique")
        return value

    @field_validator("observation_roles", mode="after")
    @classmethod
    def _observation_roles_unique(
        cls,
        value: tuple[IvaLedgerObservationRole, ...],
    ) -> tuple[IvaLedgerObservationRole, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("observation_roles entries must be unique")
        return value

    @field_validator("exemption_articles", mode="after")
    @classmethod
    def _exemption_articles_unique(
        cls,
        value: tuple[IvaExemptionArticle, ...] | None,
    ) -> tuple[IvaExemptionArticle, ...] | None:
        if value is not None and len(set(value)) != len(value):
            raise RegistryValidationError("exemption_articles entries must be unique")
        return value

    @model_validator(mode="after")
    def _exemption_article_filter_requires_domestic_exempt(self) -> _IvaLedgerSelector:
        if self.exemption_articles is not None and IvaCategory.DOMESTIC_EXEMPT not in self.categories:
            raise RegistryValidationError(
                "exemption_articles selector requires DOMESTIC_EXEMPT in categories",
            )
        return self


def iva_ledger_selector(binding: DataBindingDefinition) -> _IvaLedgerSelector:
    """Validate and parse a binding selector into a typed IVA selector."""
    try:
        return _IvaLedgerSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed ledger_iva_aggregation selector") from exc


def validate_ledger_iva_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_iva_aggregation`` binding's selector and aggregation.

    Args:
        binding: The :class:`DataBindingDefinition` to validate. Must
            have ``source == "ledger_iva_aggregation"``.

    Raises:
        RegistryValidationError: If the selector is malformed (unknown
            category / rate kind / flow direction / fact, empty
            tuple), if the aggregation operator is not "sum", or if
            the binding source is not "ledger_iva_aggregation".
    """
    if binding.source != BindingSourceKind.LEDGER_IVA_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_iva_aggregation source")
    selector = iva_ledger_selector(binding)

    if binding.aggregation is not None:
        op = binding_aggregation_op(binding)
        if op != BindingAggregationOp.SUM:
            raise RegistryValidationError(
                f"binding {binding.id!r} ledger_iva_aggregation supports only aggregation op 'sum', got {op.value!r}",
            )

    if selector.fact not in _IVA_SUPPORTED_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_iva_aggregation supports only "
            f"facts {sorted(_IVA_SUPPORTED_FACTS)!r}, got {selector.fact!r}",
        )

    try:
        _iva_reachability_probe(selector)
    except RegistryValidationError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} {exc}") from exc


class IvaSelectorAxesProtocol(Protocol):
    """The six axes the IVA selector matcher reads off an observation.

    Declared so the matcher can state the shape it actually needs instead of
    naming the full :class:`IvaLedgerObservation` record. Both that record and
    the reachability probe below satisfy it structurally, which is what makes
    the probe a legitimate stand-in rather than an unchecked substitution --
    previously the probe was passed where the concrete record was declared and
    only the absence of a checked seam kept that quiet.

    Same shape as :class:`RentaIncomeObservationProtocol` serves for the renta
    side of this module.
    """

    @property
    def category(self) -> IvaCategory:
        """Return the IVA category assigned to the observation."""
        ...

    @property
    def rate_kind(self) -> IvaRateKind:
        """Return the IVA rate tier assigned to the observation."""
        ...

    @property
    def flow_direction(self) -> IvaFlowDirection:
        """Return the observation's IVA flow direction."""
        ...

    @property
    def cash_accounting_treatment(self) -> IvaCashAccountingTreatment:
        """Return the observation's cash-accounting treatment."""
        ...

    @property
    def observation_role(self) -> IvaLedgerObservationRole:
        """Return the ledger observation role used by the selector."""
        ...

    @property
    def exemption_article(self) -> IvaExemptionArticle | None:
        """Return the exemption article when the observation is exempt."""
        ...

    @property
    def applied_rate(self) -> Decimal | None:
        """Return the applied IVA rate as a fraction, when known."""
        ...


class _IvaReachabilityProbeObservation(NamedTuple):
    """Minimal shape carrying only the six axes the IVA matcher reads.

    Stands in for :class:`IvaLedgerObservation` so the probe never needs the
    full record's unrelated required fields (ledger id, dates, amounts). The
    matcher reads exactly these five attributes, which is the seam that makes
    the substitution legitimate.
    """

    category: IvaCategory
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    cash_accounting_treatment: IvaCashAccountingTreatment
    observation_role: IvaLedgerObservationRole
    exemption_article: IvaExemptionArticle | None
    # The probe asks whether a binding is REACHABLE by some observation, so it
    # supplies the rate the binding under test names rather than a fixed value:
    # a rate-specific binding is reachable, just not by a differently-rated line.
    applied_rate: Decimal | None = None


def _iva_reachability_probe(selector: _IvaLedgerSelector) -> None:
    """Assert the selector matches at least one constructible observation shape.

    Builds a synthetic observation from the selector's OWN declared values and
    runs it through the real matcher this family's resolver builds
    (:func:`_iva_build_matcher`), not a reimplementation of the match rule.
    A selector whose matcher accepts no shape assembled from its own
    declarations can never resolve a value: the binding aggregates to zero
    forever, indistinguishable from a taxpayer with no IVA of that kind.

    This family is where a selector-derived probe genuinely bites, and the
    reason is worth stating because it is not true of every family. Every
    multi-value axis is non-empty -- ``categories``, ``rate_kinds``,
    ``observation_roles`` and ``cash_accounting_treatments`` carry
    ``MinLen(1)``, while ``exemption_articles`` is either absent or non-empty
    and ``flow_direction`` is a single enum. The probe therefore confirms the
    declared combination itself can reach the matcher without inventing an
    implicit observation role or cash-accounting policy.

    What this cannot catch, stated so no reader over-trusts it:

    * It never touches real ledger data, so it proves the selector CAN match a
      shape, never that any real row DOES.
    * It cannot catch a matcher that accepts the WRONG rows, only one that
      accepts none.
    * It cannot catch a resolver that aggregates correctly-matched rows
      incorrectly. That residual blind spot needs a data-carrying check, and
      no build-time data-free check can observe it.
    """
    matcher = _iva_build_matcher(selector)
    probe = _IvaReachabilityProbeObservation(
        category=selector.categories[0],
        rate_kind=selector.rate_kinds[0],
        flow_direction=selector.flow_direction,
        # Both role and treatment policies are deliberately explicit and
        # non-empty; reachability may therefore exercise their first declared
        # members without introducing an implicit default.
        cash_accounting_treatment=selector.cash_accounting_treatments[0],
        observation_role=selector.observation_roles[0],
        exemption_article=(selector.exemption_articles[0] if selector.exemption_articles else None),
        # Offer the first rate the selector names, so a rate-specific binding is
        # asked whether ANY line can reach it rather than whether a rate-less one
        # can. A None here would fail every rate-specific binding at build time
        # and read as "unreachable" when the binding is simply particular.
        applied_rate=(selector.applied_rates[0] if selector.applied_rates else None),
    )
    if not matcher(probe):
        raise RegistryValidationError(
            "ledger_iva_aggregation selector matches no constructible observation shape -- "
            "the binding can never resolve a value from any ledger data",
        )


def _iva_ledger_observation_matches_selector(
    observation: IvaSelectorAxesProtocol,
    selector: _IvaLedgerSelector,
    *,
    categories: set[IvaCategory],
    rate_kinds: set[IvaRateKind],
) -> bool:
    if observation.category not in categories:
        return False
    if observation.rate_kind not in rate_kinds:
        return False
    if observation.flow_direction is not selector.flow_direction:
        return False
    if observation.cash_accounting_treatment not in set(selector.cash_accounting_treatments):
        return False
    if observation.observation_role not in set(selector.observation_roles):
        return False
    if selector.applied_rates is not None and observation.applied_rate not in set(selector.applied_rates):
        return False
    if selector.exemption_articles is None:
        return True
    return observation.exemption_article in set(selector.exemption_articles)


def _iva_build_matcher(selector: _IvaLedgerSelector) -> Callable[[IvaSelectorAxesProtocol], bool]:
    categories = set(selector.categories)
    rate_kinds = set(selector.rate_kinds)

    def matcher(observation: IvaSelectorAxesProtocol) -> bool:
        return _iva_ledger_observation_matches_selector(
            observation,
            selector,
            categories=categories,
            rate_kinds=rate_kinds,
        )

    return matcher


def _iva_aggregate(matched: Sequence[IvaLedgerObservation], selector: _IvaLedgerSelector) -> Decimal:
    if selector.fact == "iva_amount_sum":
        return sum((observation.iva_amount for observation in matched), Decimal("0"))
    if selector.fact == "recargo_amount_sum":
        return sum((observation.recargo_amount for observation in matched), Decimal("0"))
    return sum((observation.base_amount for observation in matched), Decimal("0"))


def resolve_ledger_iva_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_iva_aggregation`` binding on ``revision``.

    Filters observations by the three classification axes (category in
    selector.categories, rate_kind in selector.rate_kinds, flow_direction
    matches selector.flow_direction) and aggregates the matched lines'
    iva_amount, recargo_amount, or base_amount per the declared fact.
    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver; the per-selector ``categories`` / ``rate_kinds`` sets
    are built once when the matcher closure is constructed for a binding,
    not once per observation.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: Iterable of substrate-classified ledger lines.

    Returns:
        Mapping of binding id to the aggregated Decimal value. Empty
        match sets resolve to ``Decimal("0")``.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        parse_selector=iva_ledger_selector,
        build_matcher=_iva_build_matcher,
        aggregate=_iva_aggregate,
    )


def unsupported_ledger_iva_observations(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> tuple[IvaLedgerObservation, ...]:
    """Return IVA observations no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family
    carries the campaign's two documented, deliberate asymmetries against
    its six siblings — both load-bearing, neither a gap to "fix":

    1. **``extra_exclusion`` (no sibling has one).** Categories that bear no
       Modelo 303 cuota *by law*
       (:data:`~cadrumo.domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` — exempt,
       zero-rated, not-subject, exempt intra-community supplies/exports,
       triangulation, régimen simplificado) are excluded before the binding
       check: they correctly match no cuota binding, so flagging them would
       be a false positive. After the M303 routing tail (domestic /
       intra-community reverse-charge bindings, the import deducible
       binding) landed, every cuota-bearing declarable category has a
       consuming binding, so the residual unsupported set is empty for the
       known declarable categories; the function still fail-closes on any
       *new* declarable triple that no binding selects.
    2. **``is_declarable`` is ``lambda observation: True`` — this family has
       NO zero-amount false-fire guard, unlike every other ledger family.**
       This is intentional, not an oversight: adding one would SUPPRESS
       real findings the current code fires on
       (``no-silent-under-declaration``). Do not add a zero-amount /
       zero-cuota guard here to "match" the other six families.

    Args:
        revision: The :class:`ModeloRevision` whose bindings define the
            supported IVA classification triples.
        observations: Ledger lines to screen.

    Returns:
        Tuple of :class:`IvaLedgerObservation` instances not matched by any binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        parse_selector=iva_ledger_selector,
        build_matcher=_iva_build_matcher,
        is_declarable=lambda observation: True,
        extra_exclusion=lambda observation: observation.category in CUOTA_LESS_M303_IVA_CATEGORIES,
    )


# The IVA facts excluded from the quantity screen. There are NONE:
# ``base_amount_sum``, ``iva_amount_sum`` and ``recargo_amount_sum`` are three
# INDEPENDENT quantities carried on one line -- the taxable base, the cuota
# charged on it, and the recargo de equivalencia surcharged alongside. No one of
# them stands in for another, so every undrawn one is a real gap.
#
# Contrast the renta side, where three income measures ARE alternatives
# (:data:`_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS`) and screening all three
# would fire on every revision. The emptiness here is a measured property of
# this family, not an unfilled placeholder, and
# ``test_ledger_quantity_screen_partition`` asserts it so the claim is checked
# rather than left as an absence a later author could fill in unnoticed.
_IVA_ALTERNATIVE_MEASURE_FACTS: Mapping[str, str] = dict[str, str]()

#: DERIVED as the complement, exactly as the renta side derives its own, so the
#: two sets cannot drift apart.
_IVA_INDEPENDENT_QUANTITY_FACTS: frozenset[str] = independent_quantity_facts(
    _IVA_SUPPORTED_FACTS,
    _IVA_ALTERNATIVE_MEASURE_FACTS,
)

#: Per-fact readers for the independent quantities. Keyed on the same
#: selector-fact vocabulary :func:`_iva_aggregate` dispatches on, so a fact
#: cannot be screened under one reading and resolved under another.
_IVA_INDEPENDENT_QUANTITY_READERS: dict[str, Callable[[IvaLedgerObservation], Decimal]] = {
    "base_amount_sum": lambda observation: observation.base_amount,
    "iva_amount_sum": lambda observation: observation.iva_amount,
    "recargo_amount_sum": lambda observation: observation.recargo_amount,
}

assert_quantity_readers_cover_independent_facts(
    "ledger-IVA",
    _IVA_INDEPENDENT_QUANTITY_FACTS,
    _IVA_INDEPENDENT_QUANTITY_READERS,
)


def unrouted_ledger_iva_quantities(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> tuple[UnroutedLedgerQuantity[IvaLedgerObservation], ...]:
    """Return IVA quantities the rows carry that no binding on ``revision`` draws.

    The quantity-keyed sibling of :func:`unsupported_ledger_iva_observations`,
    and it watches the axis that screen cannot. That one asks whether a ROW is
    selected by some binding; every IVA row carries three independent
    quantities, so a row selected for its cuota reads as consumed while its
    base imponible reaches nothing at all.

    The gap is live, not hypothetical, and it survives a revision declaring the
    fact. Both Modelo 303 and Modelo 390 declare ``base_amount_sum`` bindings
    covering the domestic tiers, so "is base imponible drawn" answers yes on
    each. Their base bindings nonetheless reach no import or reverse-charge row:
    ``import_third_country``,
    ``intra_community_acquisition_reverse_charge`` and
    ``intra_community_service_acquisition_reverse_charge`` have their CUOTA
    drawn and their base drawn by nothing, on both modelos. The rows are
    consumed for that cuota, so the row screen is silent by construction, and a
    coverage test keyed on the fact alone would be silent too.

    That is why coverage is asked per row and per fact. The earlier worked
    example here — Modelo 390 declaring no base binding at all — was closed by
    the annual-form campaign, and closing it is precisely what would have
    blinded a fact-keyed screen to the three categories above. A screen's value
    is the mechanism, never the instance: this one keeps reporting whatever the
    declared bindings fail to reach, and correctly falls silent on the four
    domestic categories both modelos now cover.

    This function reports; it does not close. Routing an import or
    reverse-charge base imponible is registry work with its own casillas and
    grounding.

    Args:
        revision: The :class:`ModeloRevision` whose IVA bindings decide which
            facts are drawn, and which rows each drawing binding reaches.
        observations: Ledger IVA observations to screen.

    Returns:
        One :class:`UnroutedLedgerQuantity` per fact with uncovered non-zero
        rows, ordered by fact name, each carrying only the rows that fact's
        bindings fail to reach.
    """
    return unrouted_ledger_family_quantities(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        parse_selector=iva_ledger_selector,
        build_matcher=_iva_build_matcher,
        read_fact=lambda selector: selector.fact,
        independent_facts=_IVA_INDEPENDENT_QUANTITY_FACTS,
        readers=_IVA_INDEPENDENT_QUANTITY_READERS,
    )


def structurally_unroutable_iva_base_categories(
    revision: ModeloRevision,
    *,
    out_of_scope: frozenset[IvaCategory] = M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES,
) -> tuple[IvaCategory, ...]:
    """Return :class:`IvaCategory` members no ``base_amount_sum`` binding on ``revision`` could ever reach.

    A fourth axis beside :func:`unsupported_ledger_iva_observations` (is this
    ROW selected) and :func:`unrouted_ledger_iva_quantities` (is this row's
    FACT drawn). Both siblings are OBSERVATION-DEPENDENT: they cannot fire
    until a taxpayer's ledger actually holds a row of the affected category,
    and :func:`unrouted_ledger_iva_quantities` in particular reports only
    *"uncovered non-zero rows"* -- its own docstring states it "must not
    manufacture a finding from" a zero total, which is exactly why it needs no
    category exclusion set: a cuota-less category's cuota is 0.00 BY LAW, so
    it is filtered by the non-zero guard before any exclusion set could matter.

    This screen has no rows to filter on, so it needs the opposite of that
    guard -- an explicit declaration of what is out of scope, because
    "unmentioned" would otherwise mean "unrouted." It answers a question
    neither sibling can: *"could this revision's bindings EVER route this
    category's base, independent of whether any taxpayer has fallen into the
    hole yet?"* True or false from the registry alone, before a single ledger
    row exists. For a filing-grade tool that distinction matters: the first
    taxpayer with an unrouted reverse-charge base should not be the detector.

    Three states result from combining this screen with its siblings, and a
    caller must not collapse two of them into one "no finding":

    - **unroutable**: this screen fires -- no binding on the revision could
      ever draw this category's base, for any observation.
    - **unrouted**: this screen is silent (some binding COULD draw it) but
      :func:`unrouted_ledger_iva_quantities` fires for a real row -- the
      binding exists but a particular row still reached nothing (e.g. a
      binding scoped to one flow direction leaves a row of the same category
      under a different flow direction uncovered).
    - **routed**: both are silent.

    ``out_of_scope`` is deliberately NOT :data:`CUOTA_LESS_M303_IVA_CATEGORIES`.
    That set answers "does this category produce a cuota?"; this screen asks
    "does this category's BASE reach some casilla?", and several by-law
    cuota-less categories DO carry a real base by law --
    :data:`~cadrumo.domain.iva.IvaCategory.DOMESTIC_ZERO` is the proof: zero
    cuota by definition, base-bearing by law. Reusing CUOTA_LESS here would
    suppress exactly the population this screen exists to catch. The default
    is M303's own out-of-scope declaration
    (:data:`~cadrumo.domain.iva.M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES`); no
    generic per-modelo scope mechanism exists in the registry today (a
    registry-expressiveness gap in its own right), so a caller working a
    different modelo must supply its own set rather than default into M303's.

    Uses the real production selector parser (:func:`iva_ledger_selector`)
    and matcher (:func:`_iva_build_matcher`) -- never a re-implementation of
    the match rule. For each ``base_amount_sum`` binding whose declared
    categories include the candidate, a probe observation is assembled from
    values the selector's OWN declared axes already admit (one representative
    rate kind, the declared flow direction, one representative cash-accounting
    treatment, and one representative applied rate / exemption article where
    the selector restricts them) and run through the real matcher. This never
    guesses a value the selector did not itself declare, so it cannot invent a
    false match.

    Args:
        revision: The :class:`ModeloRevision` whose ``ledger_iva_aggregation``
            bindings decide which categories' base is drawn.
        out_of_scope: Categories this screen must not evaluate at all, because
            "unroutable base" is not a meaningful question for them on this
            modelo (see :data:`~cadrumo.domain.iva.M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES`
            for the M303 declaration and the reasoning per member).

    Returns:
        Every :class:`IvaCategory` member not in ``out_of_scope`` for which no
        ``base_amount_sum`` binding on ``revision`` could ever match an
        observation of that category, in enum declaration order.
    """
    base_selectors = [
        iva_ledger_selector(binding)
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IVA_AGGREGATION
    ]
    base_selectors = [selector for selector in base_selectors if selector.fact == "base_amount_sum"]
    matchers = [(selector, _iva_build_matcher(selector)) for selector in base_selectors]

    unroutable: list[IvaCategory] = []
    for category in IvaCategory:
        if category in out_of_scope:
            continue
        reachable = False
        for selector, matcher in matchers:
            if category not in selector.categories:
                continue
            probe = _IvaReachabilityProbeObservation(
                category=category,
                rate_kind=selector.rate_kinds[0],
                flow_direction=selector.flow_direction,
                cash_accounting_treatment=selector.cash_accounting_treatments[0],
                observation_role=selector.observation_roles[0],
                exemption_article=selector.exemption_articles[0] if selector.exemption_articles else None,
                applied_rate=selector.applied_rates[0] if selector.applied_rates else None,
            )
            if matcher(probe):
                reachable = True
                break
        if not reachable:
            unroutable.append(category)
    return tuple(unroutable)


# Ledger Renta estimación directa gastos aggregation source bindings.
#
# These bindings consume first-slice Modelo 100 gastos observations produced
# by the ledger/Renta aggregation layer. They deliberately aggregate already
# evaluated deductible amounts, so proportionality, legal category eligibility,
# invoice reconciliation, and period/date filtering stay outside the registry
# formula runtime.
#
# The registry accesses only four attributes on each observation. A Protocol
# avoids a cross-domain import (domain.calculations -> domain.renta) that
# would violate the hexagonal direction.

# Casilla IDs covered by the first Renta gastos slice (Modelo 100, period 0A).
# These must stay in sync with the binding selectors in the TOML and with
# cadrumo.domain.renta._first_slice_routing.FIRST_SLICE_EXPENSE_CASILLAS (the
# domain-owned SpendingCategory -> casilla routing table this registry-layer
# module cannot import directly without reversing the hexagonal dependency
# direction); they are validated at registry load time so mismatches surface
# before any calculation. Coverage is currently a subset of the full


def validate_ledger_iva_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_iva_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_IvaLedgerSelector`; runs
    the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_iva_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _IvaLedgerSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "ledger_iva_aggregation", validate_ledger_iva_aggregation_binding_definition)


IvaLedgerSelector = _IvaLedgerSelector
