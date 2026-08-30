"""Ledger-backed registry binding helpers.

Each ledger source family carries three collaborators. The registered
``validate_ledger_<family>_aggregation_binding`` is the accumulating
``list[str]`` validator the registry-build section validator dispatches to; it
checks the selector shape, then runs the family's op/fact cross-invariant
through :func:`invariant_diagnostics`. The raise-style
``validate_ledger_<family>_aggregation_binding_definition`` is that invariant's
body, and the accumulating validator is its only caller: these op/fact
invariants are enforced at registry-build time only. The
``resolve_ledger_<family>_aggregation_binding_values`` resolvers do not call
the invariant body — each re-parses the selector independently through its own
private ``_<family>_selector`` helper, which raises on a malformed selector but
re-checks no op/fact invariant.

Each resolver delegates its filter/aggregate skeleton to
:func:`~.registry._ledger_binding_resolution.resolve_ledger_family_binding_values`,
the shape shared by every ledger family (this module's five plus IRNR and
impatriado in their own family modules); the family supplies only its
selector parser, match predicate, and fact-dispatch aggregation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, NamedTuple, Protocol

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, IvaDeductionFactKind, Modelo
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.aggregation import (
    BindingAggregationOp,
    BindingSourceKind,
    LedgerIncomeGrounding,
)
from ....core.unit_proportion import UnitProportion
from ...iva.classification import InvoiceKind, TransactionKind
from ...iva.deduction_facts import IvaDeductionClassificationProvenance, validate_iva_deduction_fact
from ...iva.flow import IvaFlowDirection, is_deducible_flow
from ...iva.oss import OssIossRegime
from ...iva.prorrata import InputClassification
from ...iva.schema import CUOTA_LESS_M303_IVA_CATEGORIES, EUMemberState, IvaCashAccountingTreatment, IvaCategory, IvaExemptionArticle, IvaLedgerObservationRole, IvaRateKind, M303_BASE_OUT_OF_SCOPE_IVA_CATEGORIES
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

# Ledger-aggregation binding source kinds. Re-exported from
# :data:`cadrumo.core.aggregation.LEDGER_BINDING_SOURCE_KINDS`, which derives the
# set from :class:`~cadrumo.core.BindingSourceKind` (the single source-kind
# taxonomy). Every binding whose ``source`` is a member reads its values from
# the bucket-scoped ledger (transaction-classified IVA / OSS aggregation, Renta
# first-slice income and estimación directa gastos aggregation, the M130
# pago-fraccionado gastos cumulative aggregation,
# the M151 impatriado Spanish-source base aggregation, or the M210 explicit
# IRNR income projection). Cross-domain consumers route through this name so the
# registry stays the single source of truth for ledger readiness.
__all__ = [
    "IvaLedgerObservation",
    "IvaSelectorAxesProtocol",
    "OssIossLedgerObservation",
    "RentaGastosEstimacionDirectaObservationProtocol",
    "RentaGastosPagoFraccionadoObservationProtocol",
    "RentaIncomeObservationProtocol",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values",
    "resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values",
    "resolve_ledger_renta_income_aggregation_binding_values",
    "unsupported_ledger_iva_observations",
    "unsupported_ledger_oss_observations",
    "unsupported_ledger_renta_gastos_estimacion_directa_observations",
    "unsupported_ledger_renta_gastos_pago_fraccionado_observations",
    "unsupported_ledger_renta_income_observations",
    "validate_ledger_iva_aggregation_binding",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_gastos_estimacion_directa_aggregation_binding",
    "validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition",
    "validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding",
    "validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition",
    "validate_ledger_renta_income_aggregation_binding",
    "validate_ledger_renta_income_aggregation_binding_definition",
]


def _mapping_lacks_fact(value: object) -> bool:
    """Whether *value* is a mapping with no ``fact`` key.

    Extracted so the ``isinstance`` narrowing stays local. Inline, it widened
    the enclosing validator's inferred return to include an unparameterised
    mapping, which said less than the declared type it replaced.
    """
    return isinstance(value, Mapping) and "fact" not in value


def _casilla_id_set(surface: str, *values: object) -> frozenset[CasillaId]:
    return frozenset(validated_casilla_id(value, surface=surface) for value in values)


casilla_id_set = _casilla_id_set


# Ledger OSS / IOSS aggregation source bindings.
#
# These bindings aggregate ledger lines whose IVA classification matches a
# regime + destination Member State + rate tier + invoice direction selector.
# The classification axes come from :mod:`cadrumo.domain.iva`; the binding source
# is the registry's ledger-driven aggregation kind for Modelo 369.
#
# The selector keys are validated against the substrate's closed enums at
# binding-definition time; the runtime resolver then consumes
# :class:`OssIossLedgerObservation` instances (per-line ledger facts already
# tagged with the substrate classification) and returns the aggregated value.


class OssIossLedgerObservation(BaseModel):
    """One factual ledger line tagged with substrate-grounded classification.

    Modelo 369 binding selectors filter these observations by the four
    classification axes (regime, destination Member State, rate tier,
    invoice direction) plus the optional transaction kind set; the
    runtime aggregates the matched lines through the binding's
    aggregation operator.

    Attributes:
        ledger_id: Stable id of the source ledger line.
        transaction_date: When the supply takes place.
        regime: OSS / IOSS Esquema the line is filed under.
        destination_member_state: Member State of consumption (the
            destination MS for the supply, which determines the
            applicable IVA rate per the OSS / IOSS rules).
        rate_kind: Substrate rate tier (general / reduced / etc.).
        invoice_direction: Whether the autónomo issued or received
            the invoice.
        transaction_kind: Substrate :class:`cadrumo.domain.iva.TransactionKind`
            the line resolves to.
        base_amount: Taxable base in EUR.
        iva_amount: IVA amount in EUR (already applied at the
            destination MS rate per OSS / IOSS rules).
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: IvaRateKind
    invoice_direction: InvoiceKind
    transaction_kind: TransactionKind
    base_amount: Decimal
    iva_amount: Decimal


class _OssIossLedgerSelector(BaseModel):
    """Validated form of a ledger_oss_aggregation binding selector.

    The selector is expressed in TOML as a mapping of string-valued
    keys (the registry binding selector contract); this record coerces
    those strings into substrate enum members at validation time so
    downstream consumers see typed values.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    regime: Annotated[OssIossRegime, BeforeValidator(coerce_enum_member(OssIossRegime))]
    destination_member_state: Annotated[EUMemberState, BeforeValidator(coerce_enum_member(EUMemberState))]
    rate_kind: Annotated[IvaRateKind, BeforeValidator(coerce_enum_member(IvaRateKind))]
    invoice_direction: Annotated[InvoiceKind, BeforeValidator(coerce_enum_member(InvoiceKind))]
    transaction_kinds: Annotated[
        tuple[TransactionKind, ...],
        BeforeValidator(coerce_enum_tuple(TransactionKind)),
    ] = Field(min_length=1)
    fact: Literal["iva_amount_sum", "base_amount_sum"] = "iva_amount_sum"

    @field_validator("transaction_kinds", mode="after")
    @classmethod
    def _kinds_unique(cls, value: tuple[TransactionKind, ...]) -> tuple[TransactionKind, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("transaction_kinds entries must be unique")
        return value


def _ledger_oss_selector(binding: DataBindingDefinition) -> _OssIossLedgerSelector:
    """Validate and parse a binding selector into a typed OSS / IOSS selector."""
    try:
        return _OssIossLedgerSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed ledger_oss_aggregation selector") from exc


def validate_ledger_oss_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_oss_aggregation`` binding's selector and aggregation.

    Args:
        binding: The :class:`DataBindingDefinition` to validate. Must
            have ``source == "ledger_oss_aggregation"``.

    Raises:
        RegistryValidationError: If the selector is malformed (unknown
            regime / member state / rate kind / invoice direction /
            transaction kind), or if the aggregation operator is
            inconsistent with the declared fact.
    """
    if binding.source != BindingSourceKind.LEDGER_OSS_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_oss_aggregation source")
    selector = _ledger_oss_selector(binding)

    if binding.aggregation is not None:
        op = binding_aggregation_op(binding)
        if op != BindingAggregationOp.SUM:
            raise RegistryValidationError(
                f"binding {binding.id!r} ledger_oss_aggregation supports only aggregation op 'sum', got {op.value!r}",
            )

    if selector.fact not in {"iva_amount_sum", "base_amount_sum"}:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_oss_aggregation supports only "
            f"facts {{iva_amount_sum, base_amount_sum}}, got {selector.fact!r}",
        )


def _oss_build_matcher(
    selector: _OssIossLedgerSelector,
) -> Callable[[OssIossLedgerObservation], bool]:
    regime, destination, rate_kind, direction = (
        selector.regime,
        selector.destination_member_state,
        selector.rate_kind,
        selector.invoice_direction,
    )
    kinds = set(selector.transaction_kinds)

    def matcher(observation: OssIossLedgerObservation) -> bool:
        return (
            observation.regime is regime
            and observation.destination_member_state is destination
            and observation.rate_kind is rate_kind
            and observation.invoice_direction is direction
            and observation.transaction_kind in kinds
        )

    return matcher


def _oss_aggregate(
    matched: Sequence[OssIossLedgerObservation],
    selector: _OssIossLedgerSelector,
) -> Decimal:
    if selector.fact == "iva_amount_sum":
        return sum((observation.iva_amount for observation in matched), Decimal("0"))
    return sum((observation.base_amount for observation in matched), Decimal("0"))


def resolve_ledger_oss_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_oss_aggregation`` binding on ``revision``.

    For each binding, observations are filtered by the four
    classification axes plus the transaction-kind set; matched
    observations are aggregated through the binding's declared fact
    (``iva_amount_sum`` defaults; ``base_amount_sum`` selects the base).
    The resolver is deterministic and side-effect-free. Delegates the
    filter/aggregate skeleton to :func:`resolve_ledger_family_binding_values`,
    shared by every ledger family resolver; the per-selector
    ``transaction_kinds`` set is built once when the matcher closure is
    constructed for a binding, not once per observation.

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
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        parse_selector=_ledger_oss_selector,
        build_matcher=_oss_build_matcher,
        aggregate=_oss_aggregate,
    )


def _oss_is_declarable(observation: OssIossLedgerObservation) -> bool:
    return observation.base_amount != Decimal("0") or observation.iva_amount != Decimal("0")


def unsupported_ledger_oss_observations(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> tuple[OssIossLedgerObservation, ...]:
    """Return the :class:`OssIossLedgerObservation` rows no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the compound regime/destination/rate/
    direction/transaction-kind match predicate (reused from the resolver's
    ``_oss_build_matcher``, so the ``transaction_kinds`` set is built once
    per binding rather than once per (observation, binding) pair) and a
    false-fire guard excluding an observation carrying neither base nor IVA
    (both zero). No ``extra_exclusion``.

    Args:
        revision: The :class:`ModeloRevision` whose OSS bindings define the
            supported classification tuples.
        observations: Validated OSS/IOSS observations to screen.

    Returns:
        Tuple of observations whose non-zero base/cuota is selected by no
        ``ledger_oss_aggregation`` binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_OSS_AGGREGATION,
        parse_selector=_ledger_oss_selector,
        build_matcher=_oss_build_matcher,
        is_declarable=_oss_is_declarable,
    )


# Ledger IVA aggregation source bindings (cross-modelo IVA roll-out).
#
# Generic counterpart to :func:`resolve_ledger_oss_aggregation_binding_values`
# for the standard IVA modelos (303 autoliquidación trimestral, 322 grupos
# individual, 353 grupos agregado, 309 no periódica, 390 resumen anual).
# Aggregates ledger lines by the canonical IVA classification triple
# (IvaCategory + IvaRateKind + IvaFlowDirection).
#
# OSS / IOSS bindings keep their dedicated source kind because they
# additionally carry the regime + destination Member State axes; this
# generic source covers domestic IVA, intra-community supplies /
# acquisitions, exports, imports, recargo de equivalencia, and
# domestic-reverse-charge operations.


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

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
# SpendingCategory routing table.
_RENTA_100_FIRST_SLICE_CASILLAS: frozenset[CasillaId] = _casilla_id_set(
    "_RENTA_100_FIRST_SLICE_CASILLAS",
    "0183",
    "0186",
    "0191",
    "0192",
    "0193",
    "0194",
    "0195",
    "0199",
    "0200",
    "0202",
    "0203",
    "0206",
    "0208",
    "0217",
)


class RentaGastosEstimacionDirectaObservationProtocol(Protocol):
    """Structural protocol for first-slice Renta estimación directa gastos observations.

    The registry only needs these four attributes to resolve
    ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings; the full
    :class:`~cadrumo.domain.renta.RentaDeductibleExpenseObservation` satisfies
    this protocol without any explicit declaration.

    Properties are declared read-only so that Literal-typed concrete attributes
    (e.g. ``modelo: Literal[Modelo.M100]``) satisfy the protocol under strict
    covariant checking.
    """

    @property
    def modelo(self) -> str:
        """Return the Modelo series associated with the gasto observation."""
        ...

    @property
    def period(self) -> str:
        """Return the filing period associated with the gasto observation."""
        ...

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the declaration casilla receiving the deductible amount."""
        ...

    @property
    def deductible_amount(self) -> Decimal:
        """Return the deductible amount carried by the observation."""
        ...


class _RentaLedgerGastosEstimacionDirectaSelector(BaseModel):
    """Validated form of a ledger_renta_gastos_estimacion_directa_aggregation binding selector."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M100] = Modelo.M100
    period: Literal["0A"] = "0A"
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_gastos_estimacion_directa_selector(
    binding: DataBindingDefinition,
) -> _RentaLedgerGastosEstimacionDirectaSelector:
    try:
        return _RentaLedgerGastosEstimacionDirectaSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_gastos_estimacion_directa_aggregation selector: {exc}",
        ) from exc


def validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_renta_gastos_estimacion_directa_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION:
        raise RegistryValidationError(
            f"binding {binding.id!r} is not a ledger_renta_gastos_estimacion_directa_aggregation source"
        )
    selector = _renta_ledger_gastos_estimacion_directa_selector(binding)
    if selector.target_casilla_id not in _RENTA_100_FIRST_SLICE_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            "is outside the first Modelo 100 Renta ledger gastos slice",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_estimacion_directa_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_estimacion_directa_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}",
        )


def _renta_gastos_estimacion_directa_build_matcher(
    selector: _RentaLedgerGastosEstimacionDirectaSelector,
) -> Callable[[RentaGastosEstimacionDirectaObservationProtocol], bool]:
    modelo, period, target_casilla_id = selector.modelo, selector.period, selector.target_casilla_id

    def matcher(observation: RentaGastosEstimacionDirectaObservationProtocol) -> bool:
        return (
            observation.modelo == modelo
            and observation.period == period
            and observation.target_casilla_id == target_casilla_id
        )

    return matcher


def _renta_gastos_estimacion_directa_aggregate(
    matched: Sequence[RentaGastosEstimacionDirectaObservationProtocol],
    selector: _RentaLedgerGastosEstimacionDirectaSelector,
) -> Decimal:
    del selector  # single declared fact (deductible_amount_sum); nothing to dispatch on
    return sum((observation.deductible_amount for observation in matched), Decimal("0"))


def resolve_ledger_renta_gastos_estimacion_directa_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosEstimacionDirectaObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_gastos_estimacion_directa_aggregation`` binding on ``revision``.

    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose gastos bindings to resolve.
        observations: Typed gastos observations the bindings aggregate
            via their declared ``selector.fact`` and ``aggregation.op``.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        parse_selector=_renta_ledger_gastos_estimacion_directa_selector,
        build_matcher=_renta_gastos_estimacion_directa_build_matcher,
        aggregate=_renta_gastos_estimacion_directa_aggregate,
    )


def unsupported_ledger_renta_gastos_estimacion_directa_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosEstimacionDirectaObservationProtocol],
) -> tuple[RentaGastosEstimacionDirectaObservationProtocol, ...]:
    """Return the :class:`RentaGastosEstimacionDirectaObservationProtocol` rows no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the (modelo, period, target_casilla_id)
    match predicate (reused from the resolver's
    ``_renta_gastos_estimacion_directa_build_matcher``) and a
    zero-``deductible_amount`` false-fire guard. No ``extra_exclusion``.

    Args:
        revision: The :class:`ModeloRevision` whose gastos bindings define
            the supported (modelo, period, target_casilla_id) triples.
        observations: First-slice gastos observations to screen.

    Returns:
        Tuple of observations whose non-zero deductible amount is selected by no
        ``ledger_renta_gastos_estimacion_directa_aggregation`` binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
        parse_selector=_renta_ledger_gastos_estimacion_directa_selector,
        build_matcher=_renta_gastos_estimacion_directa_build_matcher,
        is_declarable=lambda observation: observation.deductible_amount != Decimal("0"),
    )


def renta_first_slice_binding_target_casillas(revision: ModeloRevision) -> frozenset[CasillaId]:
    """Return the ``target_casilla_id`` set this revision's own bindings route to.

    Unlike :data:`cadrumo.domain.renta._first_slice_routing.FIRST_SLICE_EXPENSE_CASILLAS`
    (the universal BOE-prescribed routing table spanning every filing year the
    application supports), this returns only the casillas a
    ``ledger_renta_gastos_estimacion_directa_aggregation`` binding on THIS revision actually
    targets. Older Modelo 100 revisions (2020-2023) declare no such bindings
    at all -- the first-slice ledger-aggregation mechanism did not yet exist
    for them -- so their required set is legitimately empty even though the
    universal routing table's codomain is wider. The snapshot-time
    referential-integrity gate
    (:mod:`cadrumo.domain.renta._first_slice_routing_integrity`) uses this
    per-revision set rather than the universal table so it only fails when a
    binding THIS revision actually declares points at a casilla absent from
    that same revision -- the real defect class the gate exists to catch,
    not "does every filing year's estimación directa casilla exist on every
    other filing year's revision" (it does not, by BOE design: casillas are
    added, split, and renumbered across years).

    Args:
        revision: The :class:`ModeloRevision` whose own
            ``ledger_renta_gastos_estimacion_directa_aggregation`` binding selectors are
            inspected.
    """
    return frozenset(
        _renta_ledger_gastos_estimacion_directa_selector(binding).target_casilla_id
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION
    )


class _RentaLedgerIncomeSelector(BaseModel):
    """Validated form of a ledger_renta_income_aggregation binding selector.

    ``modelo`` names the declaration series the aggregation feeds: M130's
    cumulative quarter, M100's annual ejercicio, or M131's agrarian quarterly
    volumen de ingresos. ``target_casilla_id`` is the casilla that receives the
    total. The M131 leg is NOT cumulative -- art. 110.1.c) fixes its payment on
    *el volumen de ingresos del trimestre* -- and its projection applies two
    filters the others do not: the art. 110.1.c) activity set, and the exclusion
    of subvenciones de capital and indemnizaciones. Both live in the projection
    rather than in this selector because they decide which rows EXIST as
    observations, not which observations a binding claims.

    ``fact`` is REQUIRED and carries no default. Each accepted value names a
    different legal measure of the same rows, so a default would silently pick
    a legal claim on the taxpayer's behalf: ``cash_received_sum`` is the raw
    bank-credited amount — net of any retención practicada and possibly
    IVA-inclusive — while ``ingresos_integros_sum`` is the ingresos íntegros
    the M130 instructions actually ask for. An omitting binding fails registry
    validation naming the accepted set rather than inheriting the weakest
    measure.

    ``fact`` controls which aggregation path is applied:

    - ``"ingresos_integros_sum"`` sums the fiscally computable ingreso per
      observation: ``taxable_base_amount`` (the IVA-exclusive base
      imponible) when the transaction carries an explicit IVA tagging,
      falling back to ``gross_amount`` when no base is declared — the
      canonical ingresos-íntegros path feeding casilla ``"01"``. The AEAT
      M130 instructions define casilla 01 as the "ingresos íntegros
      fiscalmente computables"; IVA repercutido is collected on behalf of
      Hacienda and is not computable income, so a tagged invoice
      contributes its base, never its IVA-inclusive gross.
    - ``"cash_received_sum"`` sums ``RentaIncomeObservation.gross_amount``
      (``raw.amount`` or its business fraction) across the window,
      ignoring any declared taxable base. Named for what it computes: the
      cash the bank credited, which is neither gross of retención nor
      IVA-exclusive and is therefore NOT the ingresos-íntegros measure.
    - ``"taxable_base_sum"`` sums ``RentaIncomeObservation.taxable_base_amount``
      (the IVA-exclusive base imponible).  Observations whose
      ``taxable_base_amount`` is ``None`` declare no base and contribute
      nothing to this sum;
      :func:`ungrounded_ledger_renta_income_observations` surfaces every such
      row so the omission is visible rather than silent.
    - ``"withheld_amount_sum"`` sums the IRPF amount withheld at source from
      net-paid professional receipts.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M130, Modelo.M100, Modelo.M131] = Modelo.M130
    target_casilla_id: CasillaId
    fact: Literal["ingresos_integros_sum", "cash_received_sum", "taxable_base_sum", "withheld_amount_sum"]

    @model_validator(mode="before")
    @classmethod
    def _require_explicit_fact(cls, value: object) -> object:
        """Refuse an omitted ``fact``, naming the accepted set in the message.

        Pydantic's own "Field required" names the field but not its accepted
        values; a wrong value already enumerates the ``Literal`` members. This
        closes the missing-value half so a binding author reads the choice
        instead of guessing it.
        """
        if _mapping_lacks_fact(value):
            raise ValueError(
                "ledger_renta_income_aggregation selector requires an explicit 'fact'; "
                f"accepted facts are {sorted(_RENTA_INCOME_SUPPORTED_FACTS)!r}",
            )
        return value


# Per-modelo income casillas this aggregation may feed. M130 (pago fraccionado)
# feeds the cumulative-quarter ingresos casillas; M100 (annual IRPF) feeds the
# estimación-directa "Ingresos de explotación" leaf (0171). Validated at registry
# load so a binding targeting any other casilla surfaces before any calculation.
_RENTA_130_INCOME_CASILLAS: frozenset[CasillaId] = _casilla_id_set("_RENTA_130_INCOME_CASILLAS", "01", "03")
_RENTA_100_INCOME_CASILLAS: frozenset[CasillaId] = _casilla_id_set("_RENTA_100_INCOME_CASILLAS", "0171")
# One casilla, and the narrowness is the point. Modelo 131 casilla 01 is the sum
# of modulos-computed rendimientos -- derived from signos and indices correctores,
# not from receipts -- so no ledger sum may target it. Only casilla 05, the
# agrarian volumen de ingresos del trimestre, is a real ledger aggregation.
_RENTA_131_INCOME_CASILLAS: frozenset[CasillaId] = _casilla_id_set("_RENTA_131_INCOME_CASILLAS", "05")
_RENTA_INCOME_CASILLAS_BY_MODELO: dict[Modelo, frozenset[CasillaId]] = {
    Modelo.M130: _RENTA_130_INCOME_CASILLAS,
    Modelo.M100: _RENTA_100_INCOME_CASILLAS,
    Modelo.M131: _RENTA_131_INCOME_CASILLAS,
}


def _renta_ledger_income_selector(binding: DataBindingDefinition) -> _RentaLedgerIncomeSelector:
    try:
        return _RentaLedgerIncomeSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_income_aggregation selector: {exc}",
        ) from exc


# The complete accepted ``fact`` set for this family, shared by the
# missing-``fact`` refusal message and the build-time invariant so the two can
# never name different sets. Covers both M130 and M100, which is why the name
# carries no modelo segment.
_RENTA_INCOME_SUPPORTED_FACTS: frozenset[str] = frozenset(
    {"ingresos_integros_sum", "cash_received_sum", "taxable_base_sum", "withheld_amount_sum"},
)


def validate_ledger_renta_income_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_income_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_income_aggregation source")
    selector = _renta_ledger_income_selector(binding)
    allowed = _RENTA_INCOME_CASILLAS_BY_MODELO.get(selector.modelo, frozenset())
    if selector.target_casilla_id not in allowed:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            f"is outside the supported {selector.modelo.value} income casillas {sorted(allowed)!r}",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_income_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact not in _RENTA_INCOME_SUPPORTED_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_income_aggregation supports only "
            f"facts {sorted(_RENTA_INCOME_SUPPORTED_FACTS)!r}, got {selector.fact!r}",
        )


class RentaIncomeObservationProtocol(Protocol):
    """Structural protocol for actividad-económica income observations.

    The registry only needs these attributes to resolve
    ``ledger_renta_income_aggregation`` bindings; the full
    :class:`~cadrumo.application.aggregation._renta_income_ledger.RentaIncomeObservation`
    satisfies this protocol without any explicit declaration.
    """

    @property
    def transaction_id(self) -> str:
        """Return the ledger row this observation was projected from.

        Declared because a consumer samples these ids to name the offending
        rows in an ungrounded-income diagnostic. Leaving it off the protocol
        let a conforming implementation omit it and fail there at runtime.
        """
        ...

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the declaration casilla receiving the income aggregate."""
        ...

    @property
    def gross_amount(self) -> Decimal:
        """Return the observation's gross or cash-received amount."""
        ...

    @property
    def taxable_base_amount(self) -> Decimal | None:
        """Return the declared IVA-exclusive taxable base, when available."""
        ...

    @property
    def withheld_amount(self) -> Decimal:
        """Return the IRPF amount withheld at source for the observation."""
        ...

    @property
    def grounding(self) -> LedgerIncomeGrounding:
        """Return the substrate-grounding marker for the income observation."""
        ...


def _renta_income_build_matcher(
    selector: _RentaLedgerIncomeSelector,
) -> Callable[[RentaIncomeObservationProtocol], bool]:
    target_casilla_id = selector.target_casilla_id

    def matcher(observation: RentaIncomeObservationProtocol) -> bool:
        return observation.target_casilla_id == target_casilla_id

    return matcher


def _renta_income_aggregate(
    matched: Sequence[RentaIncomeObservationProtocol],
    selector: _RentaLedgerIncomeSelector,
) -> Decimal:
    if selector.fact == "ingresos_integros_sum":
        return sum(
            (
                observation.taxable_base_amount
                if observation.taxable_base_amount is not None
                else observation.gross_amount
                for observation in matched
            ),
            Decimal("0"),
        )
    if selector.fact == "taxable_base_sum":
        # A row that declares no base contributes nothing: this fact sums
        # DECLARED bases, and inventing one from cash would fabricate a legal
        # figure. Written as an explicit ``is not None`` filter rather than
        # ``or Decimal("0")`` so a genuinely-zero declared base and an absent
        # one stop sharing a branch.
        return sum(
            (observation.taxable_base_amount for observation in matched if observation.taxable_base_amount is not None),
            Decimal("0"),
        )
    if selector.fact == "withheld_amount_sum":
        return sum((observation.withheld_amount for observation in matched), Decimal("0"))
    # cash_received_sum: the raw bank-credited magnitude, ignoring any declared
    # base. ``fact`` is a required closed Literal, so this is that member alone.
    return sum((observation.gross_amount for observation in matched), Decimal("0"))


def resolve_ledger_renta_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_income_aggregation`` binding on ``revision``.

    The ``fact`` declared in the binding selector controls which field is
    summed: ``"ingresos_integros_sum"`` → ``observation.taxable_base_amount``
    when declared, else ``observation.gross_amount`` (per-observation
    fallback); ``"cash_received_sum"`` → ``observation.gross_amount``;
    ``"taxable_base_sum"`` → ``observation.taxable_base_amount`` (a base-less
    row contributes nothing); ``"withheld_amount_sum"`` →
    ``observation.withheld_amount``. Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are resolved.
        observations: Renta income ledger lines to aggregate over.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        parse_selector=_renta_ledger_income_selector,
        build_matcher=_renta_income_build_matcher,
        aggregate=_renta_income_aggregate,
    )


def _renta_income_is_declarable(observation: RentaIncomeObservationProtocol) -> bool:
    declarable = observation.gross_amount
    if observation.taxable_base_amount is not None:
        declarable = max(declarable, observation.taxable_base_amount)
    return declarable != Decimal("0")


def unsupported_ledger_renta_income_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> tuple[RentaIncomeObservationProtocol, ...]:
    """Return the :class:`RentaIncomeObservationProtocol` rows no binding on ``revision`` can consume.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the ``target_casilla_id`` match predicate
    (reused from the resolver's ``_renta_income_build_matcher``) and a
    false-fire guard that excludes an observation whose declarable amount —
    ``max(gross_amount, taxable_base_amount)`` when a base is declared,
    ``gross_amount`` otherwise — is zero. No ``extra_exclusion``.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings define
            the supported ``target_casilla_id`` set.
        observations: Actividad-económica income observations to screen.

    Returns:
        Tuple of observations whose non-zero income is selected by no
        ``ledger_renta_income_aggregation`` binding.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        parse_selector=_renta_ledger_income_selector,
        build_matcher=_renta_income_build_matcher,
        is_declarable=_renta_income_is_declarable,
    )


# The facts that read a row's DECLARED taxable_base. Both mis-handle a row that
# declares none, in opposite directions, which is why one screen serves both:
# ``ingresos_integros_sum`` substitutes the raw bank cash (net of retención,
# possibly IVA-inclusive — wrong in a direction that depends on the invoice),
# and ``taxable_base_sum`` contributes nothing at all (always under-declares).
# ``cash_received_sum`` and ``withheld_amount_sum`` never read the base, so a
# base-less row is not an ungrounded contribution for them.
_RENTA_INCOME_BASE_READING_FACTS: frozenset[str] = frozenset({"ingresos_integros_sum", "taxable_base_sum"})


class UngroundedRentaIncome(NamedTuple):
    """Base-less income rows that a base-reading binding still consumes.

    ``facts`` is the set of base-reading facts the revision actually declares,
    so a caller can describe the consequence precisely rather than guessing:
    ``ingresos_integros_sum`` means the listed rows contributed bank cash in
    place of a base, ``taxable_base_sum`` means they contributed nothing.
    ``observations`` are the contributing rows, in input order.

    Empty ``observations`` means every consumed row declared its substrate;
    empty ``facts`` means the revision declares no base-reading income binding,
    in which case ``observations`` is empty too.
    """

    facts: frozenset[str]
    observations: tuple[RentaIncomeObservationProtocol, ...]


def ungrounded_ledger_renta_income_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> UngroundedRentaIncome:
    """Return the base-less rows a base-reading income binding on ``revision`` consumes.

    The companion to :func:`unsupported_ledger_renta_income_observations`, for
    the opposite failure: that screen catches a row NO binding consumes, this
    one catches a row a binding DOES consume but without the substrate the
    binding's fact assumes. Both are ``no-silent-under-declaration`` screens;
    neither changes a value.

    A row reaches an income casilla through declared substrate or through the
    cash fallback, and only the row's :class:`LedgerIncomeGrounding` marker
    distinguishes them — this screen keys on that marker, never on
    ``taxable_base_amount is None``, so the grounding fact has exactly one
    definition. Rows are screened against the ``target_casilla_id`` of the
    base-reading bindings only, so a revision whose income bindings all read
    cash or withholdings reports nothing.

    The caller surfaces the result as a NON-BLOCKING advisory: the fallback is
    deliberately kept (dropping an untagged income row would under-declare by
    the whole row, strictly worse than mis-measuring it), so what this screen
    buys is visibility, not exclusion.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings
            decide which casillas and facts are in play.
        observations: Actividad-económica income observations to screen.

    Returns:
        An :class:`UngroundedRentaIncome` pairing the declared base-reading
        facts with the base-less rows those bindings consume.
    """
    matchers: list[Callable[[RentaIncomeObservationProtocol], bool]] = []
    facts: set[str] = set()
    for binding in revision.bindings:
        if binding.source != BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION:
            continue
        selector = _renta_ledger_income_selector(binding)
        if selector.fact not in _RENTA_INCOME_BASE_READING_FACTS:
            continue
        facts.add(selector.fact)
        matchers.append(_renta_income_build_matcher(selector))
    if not matchers:
        return UngroundedRentaIncome(facts=frozenset(), observations=())
    ungrounded = tuple(
        observation
        for observation in observations
        if observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK
        and any(matcher(observation) for matcher in matchers)
    )
    return UngroundedRentaIncome(facts=frozenset(facts), observations=ungrounded)


# The renta-income facts excluded from the quantity screen, each with the reason
# it re-measures a quantity another fact already carries. These are DECLARATIONS
# a reviewer can check against the form, not proofs: excluding a fact narrows the
# screen, so the claim is written at the site rather than inferred from an
# absence.
#
# ``withheld_amount_sum`` is deliberately absent from this mapping, and that is
# the whole point: the retención a taxpayer suffered is an INDEPENDENT quantity
# carried on the same observation, not an alternative measure of its income.
# Nothing else can stand in for it.
_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS: Mapping[str, str] = {
    "ingresos_integros_sum": (
        "measures the row's income as its declared taxable base, falling back to bank cash; "
        "one of three income measures a revision picks between"
    ),
    "taxable_base_sum": (
        "measures the same income as the declared taxable base only, contributing nothing for a "
        "base-less row; the stricter sibling of ingresos_integros_sum"
    ),
    "cash_received_sum": (
        "measures the same income as the raw bank credit, net of retención and possibly "
        "IVA-inclusive; the loosest of the three measures"
    ),
}

#: The independent quantities, DERIVED as the complement so the two sets cannot
#: drift apart. A new fact added to the closed set is screened by default and
#: must be classified deliberately as an alternative measure to be excluded --
#: the safe direction, since forgetting to classify one surfaces an advisory
#: rather than silently dropping a quantity.
_RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS: frozenset[str] = independent_quantity_facts(
    _RENTA_INCOME_SUPPORTED_FACTS,
    _RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS,
)


#: Per-fact readers for the independent quantities. Keyed on the same
#: selector-fact vocabulary the resolver dispatches on
#: (:func:`_renta_income_aggregate`), so a fact cannot be screened under one
#: reading and resolved under another.
_RENTA_INDEPENDENT_QUANTITY_READERS: dict[str, Callable[[RentaIncomeObservationProtocol], Decimal]] = {
    "withheld_amount_sum": lambda observation: observation.withheld_amount,
}

assert_quantity_readers_cover_independent_facts(
    "renta-income",
    _RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS,
    _RENTA_INDEPENDENT_QUANTITY_READERS,
)


def unrouted_ledger_renta_income_quantities(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> tuple[UnroutedLedgerQuantity[RentaIncomeObservationProtocol], ...]:
    """Return independent quantities the rows carry that no binding on ``revision`` draws.

    The third renta-income screen, and it watches an axis the other two cannot
    see. :func:`unsupported_ledger_renta_income_observations` asks whether a ROW
    is selected by some binding; :func:`ungrounded_ledger_renta_income_observations`
    asks whether a consumed row carried the substrate its binding's fact assumes.
    Both key on the row. This one keys on the QUANTITY.

    The distinction is load-bearing because every ``RentaIncomeObservation`` is
    built with ``target_casilla_id = "01"`` regardless of which fact a binding
    reads off it (see the note in the M130 ``0003-m130-income-cumulative.toml``
    bindings fragment). A row therefore matches the income bindings on that key
    and counts as consumed — while a SECOND, independent quantity it carries,
    the retención suffered, reaches nothing at all. Drop the
    ``withheld_amount_sum`` binding from a revision and the row-level screen
    stays silent: every row is still consumed, for its income. The taxpayer's
    whole retención credit disappears with a clean screen on both sides, which
    is precisely the silent under-declaration the screens exist to prevent.

    Alternative MEASURES of one quantity are excluded
    (:data:`_RENTA_INCOME_ALTERNATIVE_MEASURE_FACTS`): a revision picks one
    income measure and omitting the other two is correct, so demanding all three
    would fire on every revision and train the operator to ignore the advisory.
    Only a genuinely independent quantity is screened.

    Reports nothing when the rows carry nothing: a taxpayer who suffered no
    retención has a zero total, which is a legitimate zero rather than a
    modelling gap, and this screen must not manufacture a finding from it.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings
            decide which facts are drawn.
        observations: Actividad-económica income observations to screen.

    Returns:
        One :class:`UnroutedLedgerQuantity` per uncovered non-zero quantity,
        ordered by fact name. Empty when every quantity the rows carry is drawn.
    """
    return unrouted_ledger_family_quantities(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION,
        parse_selector=_renta_ledger_income_selector,
        build_matcher=_renta_income_build_matcher,
        read_fact=lambda selector: selector.fact,
        independent_facts=_RENTA_INCOME_INDEPENDENT_QUANTITY_FACTS,
        readers=_RENTA_INDEPENDENT_QUANTITY_READERS,
    )


# Casilla IDs that the M130 gastos cumulative aggregation may feed. Validated at
# registry load time so a binding targeting any other casilla surfaces before
# any calculation runs.
_RENTA_130_GASTO_CASILLAS: frozenset[CasillaId] = _casilla_id_set("_RENTA_130_GASTO_CASILLAS", "02")


class RentaGastosPagoFraccionadoObservationProtocol(Protocol):
    """Structural protocol for M130 pago-fraccionado gastos observations.

    The registry only needs these two attributes to resolve
    ``ledger_renta_gastos_pago_fraccionado_aggregation`` bindings; the full
    :class:`~cadrumo.application.aggregation._renta_gasto_ledger.RentaGastoObservation`
    satisfies this protocol without any explicit declaration. Mirrors
    :class:`RentaIncomeObservationProtocol` for the gastos dimension.
    """

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the declaration casilla receiving the deductible amount."""
        ...

    @property
    def deductible_amount(self) -> Decimal:
        """Return the deductible amount carried by the observation."""
        ...


class _RentaLedgerGastosPagoFraccionadoSelector(BaseModel):
    """Validated form of a ledger_renta_gastos_pago_fraccionado_aggregation binding selector.

    ``modelo`` is fixed to the M130 series (the only model sourcing gastos via
    this cumulative path). ``target_casilla_id`` is casilla 02 ("Gastos"). No
    period axis: the cumulative year-to-date window is applied by the
    application aggregator, exactly as for the income sibling.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M130] = Modelo.M130
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_gastos_pago_fraccionado_selector(
    binding: DataBindingDefinition,
) -> _RentaLedgerGastosPagoFraccionadoSelector:
    try:
        return _RentaLedgerGastosPagoFraccionadoSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_gastos_pago_fraccionado_aggregation selector: {exc}",
        ) from exc


class _ReachabilityProbeObservation(NamedTuple):
    """Minimal structural instance of :class:`RentaGastosPagoFraccionadoObservationProtocol`.

    Not a test double: this is production code, called at registry-build
    time, constructing the smallest object that satisfies the registry's
    own declared Protocol. It exists so the reachability probe below never
    needs to import the concrete
    :class:`~cadrumo.application.aggregation._renta_gasto_ledger.RentaGastoObservation`
    -- doing so would have domain code depend on the application layer,
    the wrong hexagonal direction (`aeat-architecture-boundaries`). The
    Protocol is exactly the seam that makes this substitution legitimate:
    the resolver's matcher only ever reads the two declared attributes.
    """

    target_casilla_id: CasillaId
    deductible_amount: Decimal


def _renta_gastos_pago_fraccionado_reachability_probe(
    selector: _RentaLedgerGastosPagoFraccionadoSelector,
) -> None:
    """Assert the selector matches at least one constructible observation shape.

    Constructs a synthetic minimal observation from the selector's own
    declared ``target_casilla_id`` and runs it through the real matcher this
    family's resolver builds
    (:func:`_renta_gastos_pago_fraccionado_build_matcher`) -- not a
    reimplementation of the match rule, the same one production calculate
    and this probe both call. A selector whose matcher accepts no
    constructible shape is a defect no runtime ledger data can ever
    surface: the binding would aggregate to zero forever, indistinguishable
    from a taxpayer with no gasto deducible that period.

    This is a REACHABILITY probe only, and deliberately narrow. It proves
    the selector CAN match a shape built from its own declared fields; it
    never touches real ledger data and so cannot prove real data DOES
    match, and it cannot catch a matcher that accepts the wrong rows or a
    resolver that aggregates matched rows incorrectly -- both are outside
    what a build-time, data-free check can observe.

    **It also cannot fail as this family is currently matched, and saying so
    is the point.** The matcher tests
    ``observation.target_casilla_id == selector.target_casilla_id`` while the
    probe builds the observation from that same field, so the comparison is
    ``x == x`` for every selector, including a nonsense casilla id. Read
    without this paragraph the probe looks like coverage of a defect class it
    cannot reach, which is worse than no probe at all.

    It is kept rather than deleted because it costs nothing and becomes live
    the moment this family's matcher tests anything the selector declares as a
    SET -- the shape that makes the sibling
    :func:`_iva_reachability_probe` genuinely bite. The tautology is pinned by
    ``test_a_casilla_keyed_selector_probe_is_structurally_unable_to_fail``,
    which reddens if the match rule changes, forcing this paragraph to be
    rewritten instead of quietly outliving its truth.

    The reachability guarantee this family actually has is elsewhere and is
    real: ``target_casilla_id`` is validated against
    :data:`_RENTA_130_GASTO_CASILLAS` by the caller below, and the revision's
    own casilla set is cross-checked at snapshot build.
    """
    matcher = _renta_gastos_pago_fraccionado_build_matcher(selector)
    probe = _ReachabilityProbeObservation(
        target_casilla_id=selector.target_casilla_id,
        deductible_amount=Decimal("1.00"),
    )
    if not matcher(probe):
        raise RegistryValidationError(
            f"ledger_renta_gastos_pago_fraccionado_aggregation binding target_casilla_id "
            f"{selector.target_casilla_id!r} matches no constructible observation shape -- "
            "the binding can never resolve a value from any ledger data",
        )


def validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition(
    binding: DataBindingDefinition,
) -> None:
    """Validate a ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION:
        raise RegistryValidationError(
            f"binding {binding.id!r} is not a ledger_renta_gastos_pago_fraccionado_aggregation source"
        )
    selector = _renta_ledger_gastos_pago_fraccionado_selector(binding)
    if selector.target_casilla_id not in _RENTA_130_GASTO_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            "is outside the supported Modelo 130 gasto casillas",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_pago_fraccionado_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gastos_pago_fraccionado_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}",
        )
    try:
        _renta_gastos_pago_fraccionado_reachability_probe(selector)
    except RegistryValidationError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} {exc}") from exc


def _renta_gastos_pago_fraccionado_build_matcher(
    selector: _RentaLedgerGastosPagoFraccionadoSelector,
) -> Callable[[RentaGastosPagoFraccionadoObservationProtocol], bool]:
    target_casilla_id = selector.target_casilla_id

    def matcher(observation: RentaGastosPagoFraccionadoObservationProtocol) -> bool:
        return observation.target_casilla_id == target_casilla_id

    return matcher


def _renta_gastos_pago_fraccionado_aggregate(
    matched: Sequence[RentaGastosPagoFraccionadoObservationProtocol],
    selector: _RentaLedgerGastosPagoFraccionadoSelector,
) -> Decimal:
    del selector  # single declared fact (deductible_amount_sum); nothing to dispatch on
    return sum((observation.deductible_amount for observation in matched), Decimal("0"))


def resolve_ledger_renta_gastos_pago_fraccionado_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosPagoFraccionadoObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding on ``revision``.

    Matches observations by ``target_casilla_id`` and sums their
    ``deductible_amount``, mirroring the income resolver's casilla-keyed fold.
    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` whose gasto bindings are resolved.
        observations: M130 deductible gastos observations to aggregate over.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        parse_selector=_renta_ledger_gastos_pago_fraccionado_selector,
        build_matcher=_renta_gastos_pago_fraccionado_build_matcher,
        aggregate=_renta_gastos_pago_fraccionado_aggregate,
    )


def unsupported_ledger_renta_gastos_pago_fraccionado_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaGastosPagoFraccionadoObservationProtocol],
) -> tuple[RentaGastosPagoFraccionadoObservationProtocol, ...]:
    """Return the gasto observations no ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding can consume.

    ``revision`` is the :class:`ModeloRevision` whose declared bindings define
    what is consumable.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the ``target_casilla_id`` match predicate
    (reused from the resolver's ``_renta_gastos_pago_fraccionado_build_matcher``)
    and a zero-``deductible_amount`` false-fire guard — a gasto that
    contributes nothing declarable is excluded whether or not it is routed.
    No ``extra_exclusion``; unlike the IVA family this family has no
    category-level carve-out.

    Returns:
        Unsupported :class:`RentaGastosPagoFraccionadoObservationProtocol` observations.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_RENTA_GASTOS_PAGO_FRACCIONADO_AGGREGATION,
        parse_selector=_renta_ledger_gastos_pago_fraccionado_selector,
        build_matcher=_renta_gastos_pago_fraccionado_build_matcher,
        is_declarable=lambda observation: observation.deductible_amount != Decimal("0"),
    )


def validate_ledger_oss_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_oss_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector shape against
    :class:`_OssIossLedgerSelector` (preserving the underlying pydantic field
    error) then runs the fact/aggregation-op invariant through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_oss_aggregation_binding_definition`. This validator is
    that body's only caller, so the invariant is enforced at registry-build time
    only; :func:`resolve_ledger_oss_aggregation_binding_values` re-parses the
    selector independently through :func:`_ledger_oss_selector`.
    """
    failures = selector_against_model(binding, _OssIossLedgerSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "ledger_oss_aggregation", validate_ledger_oss_aggregation_binding_definition)


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


def validate_ledger_renta_gastos_estimacion_directa_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_gastos_estimacion_directa_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerGastosEstimacionDirectaSelector`;
    runs the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerGastosEstimacionDirectaSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_gastos_estimacion_directa_aggregation",
        validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition,
    )


def validate_ledger_renta_income_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_income_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerIncomeSelector`;
    runs the fact/aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_income_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerIncomeSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_income_aggregation",
        validate_ledger_renta_income_aggregation_binding_definition,
    )


def validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_gastos_pago_fraccionado_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerGastosPagoFraccionadoSelector`;
    runs the casilla / fact / aggregation-op invariant at build time through
    :func:`invariant_diagnostics`, whose raise-style body is
    :func:`validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerGastosPagoFraccionadoSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_gastos_pago_fraccionado_aggregation",
        validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition,
    )


IvaLedgerSelector = _IvaLedgerSelector
OssIossLedgerSelector = _OssIossLedgerSelector
RentaLedgerGastosEstimacionDirectaSelector = _RentaLedgerGastosEstimacionDirectaSelector
RentaLedgerGastosPagoFraccionadoSelector = _RentaLedgerGastosPagoFraccionadoSelector
RentaLedgerIncomeSelector = _RentaLedgerIncomeSelector
