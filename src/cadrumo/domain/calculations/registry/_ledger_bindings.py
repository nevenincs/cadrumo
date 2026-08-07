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
from typing import Literal, NamedTuple, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core import STRICT_FROZEN_CONFIG, Modelo
from ....core.aggregation import (
    LEDGER_BINDING_SOURCE_KINDS,
    BindingAggregationOp,
    BindingSourceKind,
    LedgerIncomeGrounding,
)
from ...iva import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    EUMemberState,
    InputClassification,
    InvoiceKind,
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaRateKind,
    OssIossRegime,
    TransactionKind,
)
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import invariant_diagnostics, selector_against_model
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId, validated_casilla_id
from ._ledger_binding_resolution import (
    resolve_ledger_family_binding_values,
    unsupported_ledger_family_observations,
)
from ._schema import DataBindingDefinition, ModeloRevision

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
    "LEDGER_BINDING_SOURCE_KINDS",
    "IvaLedgerObservation",
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

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    regime: OssIossRegime
    destination_member_state: EUMemberState
    rate_kind: IvaRateKind
    invoice_direction: InvoiceKind
    transaction_kinds: tuple[TransactionKind, ...] = Field(min_length=1)
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
    """Independent criterio-de-caja axis.

    Settlement observations use ``NONE`` and therefore flow through the normal
    Modelo 303 base/cuota bindings. Informational observations for boxes
    62/63/74/75 carry the actual cash-accounting treatment so ordinary
    domestic rows cannot be confused with art. 75 projections.
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

    @model_validator(mode="after")
    def _enforce_exemption_article_category(self) -> IvaLedgerObservation:
        if self.exemption_article is not None and self.category is not IvaCategory.DOMESTIC_EXEMPT:
            raise RegistryValidationError(
                "exemption_article is only valid when category is DOMESTIC_EXEMPT; "
                f"got category {self.category.value!r}",
            )
        return self


class _IvaLedgerSelector(BaseModel):
    """Validated form of a ledger_iva_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    categories: tuple[IvaCategory, ...] = Field(min_length=1)
    exemption_articles: tuple[IvaExemptionArticle, ...] | None = Field(default=None, min_length=1)
    rate_kinds: tuple[IvaRateKind, ...] = Field(min_length=1)
    flow_direction: IvaFlowDirection
    cash_accounting_treatments: tuple[IvaCashAccountingTreatment, ...] = (IvaCashAccountingTreatment.NONE,)
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


def _iva_ledger_selector(binding: DataBindingDefinition) -> _IvaLedgerSelector:
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
    selector = _iva_ledger_selector(binding)

    if binding.aggregation is not None:
        op = binding_aggregation_op(binding)
        if op != BindingAggregationOp.SUM:
            raise RegistryValidationError(
                f"binding {binding.id!r} ledger_iva_aggregation supports only aggregation op 'sum', got {op.value!r}",
            )

    if selector.fact not in {"iva_amount_sum", "base_amount_sum", "recargo_amount_sum"}:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_iva_aggregation supports only "
            f"facts {{iva_amount_sum, base_amount_sum, recargo_amount_sum}}, got {selector.fact!r}",
        )


def _iva_ledger_observation_matches_selector(
    observation: IvaLedgerObservation,
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
    if selector.exemption_articles is None:
        return True
    return observation.exemption_article in set(selector.exemption_articles)


def _iva_build_matcher(selector: _IvaLedgerSelector) -> Callable[[IvaLedgerObservation], bool]:
    categories = set(selector.categories)
    rate_kinds = set(selector.rate_kinds)

    def matcher(observation: IvaLedgerObservation) -> bool:
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
        parse_selector=_iva_ledger_selector,
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
        parse_selector=_iva_ledger_selector,
        build_matcher=_iva_build_matcher,
        is_declarable=lambda observation: True,
        extra_exclusion=lambda observation: observation.category in CUOTA_LESS_M303_IVA_CATEGORIES,
    )


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
    def modelo(self) -> str: ...

    @property
    def period(self) -> str: ...

    @property
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def deductible_amount(self) -> Decimal: ...


class _RentaLedgerGastosEstimacionDirectaSelector(BaseModel):
    """Validated form of a ledger_renta_gastos_estimacion_directa_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

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

    ``modelo`` is the M130 declaration series (the only model that sources
    income via this aggregation path). ``target_casilla_id`` is the casilla id that
    receives the cumulative revenue total.

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

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M130, Modelo.M100] = Modelo.M130
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
_RENTA_INCOME_CASILLAS_BY_MODELO: dict[Modelo, frozenset[CasillaId]] = {
    Modelo.M130: _RENTA_130_INCOME_CASILLAS,
    Modelo.M100: _RENTA_100_INCOME_CASILLAS,
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
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def gross_amount(self) -> Decimal: ...

    @property
    def taxable_base_amount(self) -> Decimal | None: ...

    @property
    def withheld_amount(self) -> Decimal: ...

    @property
    def grounding(self) -> LedgerIncomeGrounding: ...


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
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def deductible_amount(self) -> Decimal: ...


class _RentaLedgerGastosPagoFraccionadoSelector(BaseModel):
    """Validated form of a ledger_renta_gastos_pago_fraccionado_aggregation binding selector.

    ``modelo`` is fixed to the M130 series (the only model sourcing gastos via
    this cumulative path). ``target_casilla_id`` is casilla 02 ("Gastos"). No
    period axis: the cumulative year-to-date window is applied by the
    application aggregator, exactly as for the income sibling.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

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
