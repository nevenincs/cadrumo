"""Ledger-backed registry binding helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG, Modelo
from ....core.aggregation import LEDGER_BINDING_SOURCE_KINDS, BindingAggregationOp
from ...iva import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    EUMemberState,
    InvoiceKind,
    IvaCategory,
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
from ._schema import DataBindingDefinition, ModeloRevision

# Ledger-aggregation binding source kinds (all four). Re-exported from
# :data:`aeat.core.aggregation.LEDGER_BINDING_SOURCE_KINDS`, which derives the
# set from :class:`~aeat.core.BindingSourceKind` (the single source-kind
# taxonomy). Every binding whose ``source`` is a member reads its values from
# the bucket-scoped ledger (transaction-classified IVA / OSS aggregation or
# Renta first-slice income/expense aggregation). Cross-domain consumers route
# through this name so the registry stays the single source of truth for ledger
# readiness.
__all__ = [
    "LEDGER_BINDING_SOURCE_KINDS",
    "IvaLedgerObservation",
    "OssIossLedgerObservation",
    "RentaExpenseObservationProtocol",
    "RentaGastoObservationProtocol",
    "RentaIncomeObservationProtocol",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_expense_aggregation_binding_values",
    "resolve_ledger_renta_gasto_aggregation_binding_values",
    "resolve_ledger_renta_income_aggregation_binding_values",
    "unsupported_ledger_iva_observations",
    "unsupported_ledger_oss_observations",
    "unsupported_ledger_renta_expense_observations",
    "unsupported_ledger_renta_gasto_observations",
    "unsupported_ledger_renta_income_observations",
    "validate_ledger_iva_aggregation_binding",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_expense_aggregation_binding",
    "validate_ledger_renta_expense_aggregation_binding_definition",
    "validate_ledger_renta_gasto_aggregation_binding",
    "validate_ledger_renta_gasto_aggregation_binding_definition",
    "validate_ledger_renta_income_aggregation_binding",
    "validate_ledger_renta_income_aggregation_binding_definition",
]


def _casilla_id_set(surface: str, *values: object) -> frozenset[CasillaId]:
    return frozenset(validated_casilla_id(value, surface=surface) for value in values)

# Ledger OSS / IOSS aggregation source bindings.
#
# These bindings aggregate ledger lines whose IVA classification matches a
# regime + destination Member State + rate tier + invoice direction selector.
# The classification axes come from :mod:`aeat.domain.iva`; the binding source
# is the registry's ledger-driven aggregation kind for Modelo 369.
#
# The selector keys are validated against the substrate's closed enums at
# binding-definition time; the runtime resolver then consumes
# :class:`OssIossLedgerObservation` instances (per-line ledger facts already
# tagged with the substrate classification) and returns the aggregated value.
# ---------------------------------------------------------------------------


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
        transaction_kind: Substrate :class:`aeat.domain.iva.TransactionKind`
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
    if binding.source != "ledger_oss_aggregation":
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


def resolve_ledger_oss_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_oss_aggregation`` binding on ``revision``.

    For each binding, observations are filtered by the four
    classification axes plus the transaction-kind set; matched
    observations are aggregated through the binding's declared fact
    (``iva_amount_sum`` defaults; ``base_amount_sum`` selects the base).
    The resolver is deterministic and side-effect-free.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: Iterable of substrate-classified ledger lines.

    Returns:
        Mapping of binding id to the aggregated Decimal value. Empty
        match sets resolve to ``Decimal("0")``.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_oss_aggregation":
            continue
        selector = _ledger_oss_selector(binding)
        kinds = set(selector.transaction_kinds)
        matched = [
            observation
            for observation in available
            if observation.regime is selector.regime
            and observation.destination_member_state is selector.destination_member_state
            and observation.rate_kind is selector.rate_kind
            and observation.invoice_direction is selector.invoice_direction
            and observation.transaction_kind in kinds
        ]
        if selector.fact == "iva_amount_sum":
            total = sum((observation.iva_amount for observation in matched), Decimal("0"))
        else:
            total = sum((observation.base_amount for observation in matched), Decimal("0"))
        resolved[binding.id] = total
    return resolved


def unsupported_ledger_oss_observations(
    revision: ModeloRevision,
    observations: Iterable[OssIossLedgerObservation],
) -> tuple[OssIossLedgerObservation, ...]:
    """Return the :class:`OssIossLedgerObservation` rows no binding on ``revision`` can consume.

    Fail-closed counterpart to
    :func:`resolve_ledger_oss_aggregation_binding_values`, mirroring
    :func:`unsupported_ledger_iva_observations`. An observation whose
    regime/destination/rate/direction/transaction-kind tuple matches no
    ``ledger_oss_aggregation`` binding has its base/cuota silently dropped — a
    modelling gap, not a legitimate zero.

    False-fire guard: an observation carrying neither base nor IVA (both zero)
    contributes nothing whether or not it is routed and is excluded; only a
    non-zero declarable OSS line reaching no binding is surfaced.

    Args:
        revision: The :class:`ModeloRevision` whose OSS bindings define the
            supported classification tuples.
        observations: Validated OSS/IOSS observations to screen.

    Returns:
        Tuple of observations whose non-zero base/cuota is selected by no
        ``ledger_oss_aggregation`` binding.
    """
    selectors = tuple(
        _ledger_oss_selector(binding) for binding in revision.bindings if binding.source == "ledger_oss_aggregation"
    )
    unsupported: list[OssIossLedgerObservation] = []
    for observation in observations:
        if observation.base_amount == Decimal("0") and observation.iva_amount == Decimal("0"):
            continue
        if not any(
            observation.regime is selector.regime
            and observation.destination_member_state is selector.destination_member_state
            and observation.rate_kind is selector.rate_kind
            and observation.invoice_direction is selector.invoice_direction
            and observation.transaction_kind in set(selector.transaction_kinds)
            for selector in selectors
        ):
            unsupported.append(observation)
    return tuple(unsupported)


# ---------------------------------------------------------------------------
# Ledger IVA aggregation source bindings (cross-modelo IVA roll-out).
#
# Generic counterpart to :func:`resolve_ledger_oss_aggregation_binding_values`
# for the standard IVA modelos (303 autoliquidación trimestral, 322 grupos
# individual, 353 grupos agregado, 309 no periódica, 390 resumen anual).
# Aggregates ledger lines by the canonical IVA classification triple
# (IvaCategory + IvaRateKind + IvaFlowDirection) introduced by the
# IvaFlowDirection codification slice.
#
# OSS / IOSS bindings keep their dedicated source kind because they
# additionally carry the regime + destination Member State axes; this
# generic source covers domestic IVA, intra-community supplies /
# acquisitions, exports, imports, recargo de equivalencia, and
# domestic-reverse-charge operations.
# ---------------------------------------------------------------------------


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


class _IvaLedgerSelector(BaseModel):
    """Validated form of a ledger_iva_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    categories: tuple[IvaCategory, ...] = Field(min_length=1)
    rate_kinds: tuple[IvaRateKind, ...] = Field(min_length=1)
    flow_direction: IvaFlowDirection
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
    if binding.source != "ledger_iva_aggregation":
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


def resolve_ledger_iva_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_iva_aggregation`` binding on ``revision``.

    Filters observations by the three classification axes (category in
    selector.categories, rate_kind in selector.rate_kinds, flow_direction
    matches selector.flow_direction) and aggregates the matched lines'
    iva_amount or base_amount per the declared fact.

    Args:
        revision: The :class:`ModeloRevision` whose bindings to resolve.
        observations: Iterable of substrate-classified ledger lines.

    Returns:
        Mapping of binding id to the aggregated Decimal value. Empty
        match sets resolve to ``Decimal("0")``.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_iva_aggregation":
            continue
        selector = _iva_ledger_selector(binding)
        cat_set = set(selector.categories)
        kind_set = set(selector.rate_kinds)
        matched = [
            observation
            for observation in available
            if observation.category in cat_set
            and observation.rate_kind in kind_set
            and observation.flow_direction is selector.flow_direction
        ]
        if selector.fact == "iva_amount_sum":
            total = sum((observation.iva_amount for observation in matched), Decimal("0"))
        elif selector.fact == "recargo_amount_sum":
            total = sum((observation.recargo_amount for observation in matched), Decimal("0"))
        else:
            total = sum((observation.base_amount for observation in matched), Decimal("0"))
        resolved[binding.id] = total
    return resolved


def unsupported_ledger_iva_observations(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> tuple[IvaLedgerObservation, ...]:
    """Return IVA observations no binding on ``revision`` can consume.

    Args:
        revision: The :class:`ModeloRevision` whose bindings define the
            supported IVA classification triples.
        observations: Ledger lines to screen.

    Returns:
        Tuple of :class:`IvaLedgerObservation` instances not matched by any binding.

    This is the fail-closed counterpart to
    :func:`resolve_ledger_iva_aggregation_binding_values`. Empty match
    sets on supported bindings still resolve to zero, but a concrete
    observation whose category/rate/flow triple is not selected by any
    ``ledger_iva_aggregation`` binding is a modelling gap and must not
    be silently inferred into an annual or periodic form.

    Categories that bear no Modelo 303 cuota *by law*
    (:data:`~aeat.domain.iva.CUOTA_LESS_M303_IVA_CATEGORIES` — exempt,
    zero-rated, not-subject, exempt intra-community supplies/exports,
    triangulation, and régimen simplificado) are excluded: they
    correctly match no cuota binding, so flagging them would be a false
    positive. After the M303 routing tail (domestic / intra-community
    reverse-charge bindings, the import deducible binding) landed, every
    cuota-bearing declarable category has a consuming binding, so the
    residual unsupported set is empty for the known declarable categories;
    the function still fail-closes on any *new* declarable triple that no
    binding selects.
    """
    selectors = tuple(
        _iva_ledger_selector(binding) for binding in revision.bindings if binding.source == "ledger_iva_aggregation"
    )
    unsupported: list[IvaLedgerObservation] = []
    for observation in observations:
        if observation.category in CUOTA_LESS_M303_IVA_CATEGORIES:
            continue
        if not any(
            observation.category in selector.categories
            and observation.rate_kind in selector.rate_kinds
            and observation.flow_direction is selector.flow_direction
            for selector in selectors
        ):
            unsupported.append(observation)
    return tuple(unsupported)


# ---------------------------------------------------------------------------
# Ledger Renta deductible-expense aggregation source bindings.
#
# These bindings consume first-slice Modelo 100 expense observations produced
# by the ledger/Renta aggregation layer. They deliberately aggregate already
# evaluated deductible amounts, so proportionality, legal category eligibility,
# invoice reconciliation, and period/date filtering stay outside the registry
# formula runtime.
#
# The registry accesses only four attributes on each observation. A Protocol
# avoids a cross-domain import (domain.calculations -> domain.renta) that
# would violate the hexagonal direction.
# ---------------------------------------------------------------------------

# Casilla IDs covered by the first Renta expense slice (Modelo 100, period 0A).
# These must stay in sync with the binding selectors in the TOML; they are
# validated at registry load time so mismatches surface before any calculation.
_RENTA_100_FIRST_SLICE_CASILLAS: frozenset[CasillaId] = _casilla_id_set(
    "_RENTA_100_FIRST_SLICE_CASILLAS",
    "0186",
    "0192",
    "0199",
    "0203",
)


class RentaExpenseObservationProtocol(Protocol):
    """Structural protocol for first-slice Renta expense observations.

    The registry only needs these four attributes to resolve
    ``ledger_renta_expense_aggregation`` bindings; the full
    :class:`~aeat.domain.renta.RentaDeductibleExpenseObservation` satisfies
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


class _RentaLedgerExpenseSelector(BaseModel):
    """Validated form of a ledger_renta_expense_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M100] = Modelo.M100
    period: Literal["0A"] = "0A"
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_expense_selector(binding: DataBindingDefinition) -> _RentaLedgerExpenseSelector:
    try:
        return _RentaLedgerExpenseSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_expense_aggregation selector: {exc}",
        ) from exc


def validate_ledger_renta_expense_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_expense_aggregation`` binding definition."""
    if binding.source != "ledger_renta_expense_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_expense_aggregation source")
    selector = _renta_ledger_expense_selector(binding)
    if selector.target_casilla_id not in _RENTA_100_FIRST_SLICE_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            "is outside the first Modelo 100 Renta ledger expense slice",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_expense_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_expense_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}",
        )


def resolve_ledger_renta_expense_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaExpenseObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_expense_aggregation`` binding on ``revision``.

    Args:
        revision: The :class:`ModeloRevision` whose renta-expense bindings to resolve.
        observations: Typed renta-expense observations the bindings aggregate
            via their declared ``selector.fact`` and ``aggregation.op``.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_renta_expense_aggregation":
            continue
        selector = _renta_ledger_expense_selector(binding)
        matched = [
            observation
            for observation in available
            if observation.modelo == selector.modelo
            and observation.period == selector.period
            and observation.target_casilla_id == selector.target_casilla_id
        ]
        resolved[binding.id] = sum((observation.deductible_amount for observation in matched), Decimal("0"))
    return resolved


def unsupported_ledger_renta_expense_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaExpenseObservationProtocol],
) -> tuple[RentaExpenseObservationProtocol, ...]:
    """Return the :class:`RentaExpenseObservationProtocol` rows no binding on ``revision`` can consume.

    Fail-closed counterpart to
    :func:`resolve_ledger_renta_expense_aggregation_binding_values`, mirroring
    :func:`unsupported_ledger_iva_observations`. An observation whose
    modelo/period/target_casilla_id triple matches no
    ``ledger_renta_expense_aggregation`` binding has its deductible amount
    silently dropped from the filing — a modelling gap, not a legitimate zero.

    False-fire guard (``ledger-iva-advisory-only-on-cuota-bearing-categories``
    precedent): an observation that carries a zero ``deductible_amount`` contributes
    nothing whether or not it is routed, so it is excluded — only a non-zero
    declarable expense that reaches no casilla is surfaced.

    Args:
        revision: The :class:`ModeloRevision` whose renta-expense bindings define
            the supported (modelo, period, target_casilla_id) triples.
        observations: First-slice renta-expense observations to screen.

    Returns:
        Tuple of observations whose non-zero deductible amount is selected by no
        ``ledger_renta_expense_aggregation`` binding.
    """
    selectors = tuple(
        _renta_ledger_expense_selector(binding)
        for binding in revision.bindings
        if binding.source == "ledger_renta_expense_aggregation"
    )
    unsupported: list[RentaExpenseObservationProtocol] = []
    for observation in observations:
        if observation.deductible_amount == Decimal("0"):
            continue
        if not any(
            observation.modelo == selector.modelo
            and observation.period == selector.period
            and observation.target_casilla_id == selector.target_casilla_id
            for selector in selectors
        ):
            unsupported.append(observation)
    return tuple(unsupported)


class _RentaLedgerIncomeSelector(BaseModel):
    """Validated form of a ledger_renta_income_aggregation binding selector.

    ``modelo`` is the M130 declaration series (the only model that sources
    income via this aggregation path). ``target_casilla_id`` is the casilla id that
    receives the cumulative revenue total.

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
    - ``"gross_income_sum"`` sums ``RentaIncomeObservation.gross_amount``
      (``raw.amount`` or its business fraction) across the window,
      ignoring any declared taxable base.
    - ``"taxable_base_sum"`` sums ``RentaIncomeObservation.taxable_base_amount``
      (the IVA-exclusive base imponible).  Observations whose
      ``taxable_base_amount`` is ``None`` contribute zero to this sum.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M130, Modelo.M100] = Modelo.M130
    target_casilla_id: CasillaId
    fact: Literal["ingresos_integros_sum", "gross_income_sum", "taxable_base_sum"] = "gross_income_sum"


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


_RENTA_130_INCOME_SUPPORTED_FACTS: frozenset[str] = frozenset(
    {"ingresos_integros_sum", "gross_income_sum", "taxable_base_sum"},
)


def validate_ledger_renta_income_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_income_aggregation`` binding definition."""
    if binding.source != "ledger_renta_income_aggregation":
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
    if selector.fact not in _RENTA_130_INCOME_SUPPORTED_FACTS:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_income_aggregation supports only "
            f"facts {sorted(_RENTA_130_INCOME_SUPPORTED_FACTS)!r}, got {selector.fact!r}",
        )


class RentaIncomeObservationProtocol(Protocol):
    """Structural protocol for actividad-económica income observations.

    The registry only needs these attributes to resolve
    ``ledger_renta_income_aggregation`` bindings; the full
    :class:`~aeat.application.aggregation._renta_income_ledger.RentaIncomeObservation`
    satisfies this protocol without any explicit declaration.
    """

    @property
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def gross_amount(self) -> Decimal: ...

    @property
    def taxable_base_amount(self) -> Decimal | None: ...


def resolve_ledger_renta_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_income_aggregation`` binding on ``revision``.

    The ``fact`` declared in the binding selector controls which field is
    summed: ``"ingresos_integros_sum"`` → ``observation.taxable_base_amount``
    when declared, else ``observation.gross_amount`` (per-observation
    fallback); ``"gross_income_sum"`` → ``observation.gross_amount``;
    ``"taxable_base_sum"`` → ``observation.taxable_base_amount`` (zero when
    ``None``).

    Args:
        revision: The :class:`ModeloRevision` whose bindings are resolved.
        observations: Renta income ledger lines to aggregate over.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_renta_income_aggregation":
            continue
        selector = _renta_ledger_income_selector(binding)
        matched = [
            observation for observation in available if observation.target_casilla_id == selector.target_casilla_id
        ]
        if selector.fact == "ingresos_integros_sum":
            resolved[binding.id] = sum(
                (
                    observation.taxable_base_amount
                    if observation.taxable_base_amount is not None
                    else observation.gross_amount
                    for observation in matched
                ),
                Decimal("0"),
            )
        elif selector.fact == "taxable_base_sum":
            resolved[binding.id] = sum(
                (observation.taxable_base_amount or Decimal("0") for observation in matched),
                Decimal("0"),
            )
        else:
            resolved[binding.id] = sum((observation.gross_amount for observation in matched), Decimal("0"))
    return resolved


def unsupported_ledger_renta_income_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> tuple[RentaIncomeObservationProtocol, ...]:
    """Return the :class:`RentaIncomeObservationProtocol` rows no binding on ``revision`` can consume.

    Fail-closed counterpart to
    :func:`resolve_ledger_renta_income_aggregation_binding_values`, mirroring
    :func:`unsupported_ledger_iva_observations`. An observation whose
    ``target_casilla_id`` matches no ``ledger_renta_income_aggregation`` binding has
    its income silently dropped from the filing — a modelling gap, not a
    legitimate zero.

    False-fire guard: an observation whose declarable income is zero (both
    ``gross_amount`` and any declared ``taxable_base_amount`` are zero) contributes
    nothing whether or not it is routed and is excluded; only a non-zero income
    reaching no casilla is surfaced.

    Args:
        revision: The :class:`ModeloRevision` whose renta-income bindings define
            the supported ``target_casilla_id`` set.
        observations: Actividad-económica income observations to screen.

    Returns:
        Tuple of observations whose non-zero income is selected by no
        ``ledger_renta_income_aggregation`` binding.
    """
    supported_casillas = frozenset(
        _renta_ledger_income_selector(binding).target_casilla_id
        for binding in revision.bindings
        if binding.source == "ledger_renta_income_aggregation"
    )
    unsupported: list[RentaIncomeObservationProtocol] = []
    for observation in observations:
        declarable = observation.gross_amount
        if observation.taxable_base_amount is not None:
            declarable = max(declarable, observation.taxable_base_amount)
        if declarable == Decimal("0"):
            continue
        if observation.target_casilla_id not in supported_casillas:
            unsupported.append(observation)
    return tuple(unsupported)


# ---------------------------------------------------------------------------
# Ledger Renta Modelo 130 deductible-expense (gasto) aggregation source bindings.
#
# The OUTGOING sibling of ``ledger_renta_income_aggregation``: M130 casilla 02
# ("Gastos") accumulates deductible business-expense bases over the same
# cumulative year-to-date quarterly window the income path uses (RD 439/2007
# art. 110.2). Mirrors the income resolver exactly — a minimal observation
# protocol matched only by ``target_casilla_id`` (the revision is M130, so all of
# its gasto bindings are M130). Deliberately distinct from the M100 first-slice
# ``ledger_renta_expense_aggregation`` source, whose annual / invoice-evidence /
# category-profile machinery is constraint-shape-divergent from this simple
# cumulative sum.
# ---------------------------------------------------------------------------

# Casilla IDs that the M130 gasto cumulative aggregation may feed. Validated at
# registry load time so a binding targeting any other casilla surfaces before
# any calculation runs.
_RENTA_130_GASTO_CASILLAS: frozenset[CasillaId] = _casilla_id_set("_RENTA_130_GASTO_CASILLAS", "02")


class RentaGastoObservationProtocol(Protocol):
    """Structural protocol for M130 deductible-expense (gasto) observations.

    The registry only needs these two attributes to resolve
    ``ledger_renta_gasto_aggregation`` bindings; the full
    :class:`~aeat.application.aggregation._renta_gasto_ledger.RentaGastoObservation`
    satisfies this protocol without any explicit declaration. Mirrors
    :class:`RentaIncomeObservationProtocol` for the expense dimension.
    """

    @property
    def target_casilla_id(self) -> CasillaId: ...

    @property
    def deductible_amount(self) -> Decimal: ...


class _RentaLedgerGastoSelector(BaseModel):
    """Validated form of a ledger_renta_gasto_aggregation binding selector.

    ``modelo`` is fixed to the M130 series (the only model sourcing gastos via
    this cumulative path). ``target_casilla_id`` is casilla 02 ("Gastos"). No
    period axis: the cumulative year-to-date window is applied by the
    application aggregator, exactly as for the income sibling.
    """

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M130] = Modelo.M130
    target_casilla_id: CasillaId
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_gasto_selector(binding: DataBindingDefinition) -> _RentaLedgerGastoSelector:
    try:
        return _RentaLedgerGastoSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_gasto_aggregation selector: {exc}",
        ) from exc


def validate_ledger_renta_gasto_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_gasto_aggregation`` binding definition."""
    if binding.source != "ledger_renta_gasto_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_gasto_aggregation source")
    selector = _renta_ledger_gasto_selector(binding)
    if selector.target_casilla_id not in _RENTA_130_GASTO_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            "is outside the supported Modelo 130 gasto casillas",
        )
    op = binding_aggregation_op(binding)
    if op != BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gasto_aggregation supports only "
            f"aggregation op 'sum', got {op.value!r}",
        )
    if selector.fact != "deductible_amount_sum":
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_renta_gasto_aggregation supports only "
            f"fact 'deductible_amount_sum', got {selector.fact!r}",
        )


def resolve_ledger_renta_gasto_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaGastoObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve every ``ledger_renta_gasto_aggregation`` binding on ``revision``.

    Matches observations by ``target_casilla_id`` and sums their
    ``deductible_amount``, mirroring the income resolver's casilla-keyed fold.

    Args:
        revision: The :class:`ModeloRevision` whose gasto bindings are resolved.
        observations: M130 deductible-expense observations to aggregate over.
    """
    available = tuple(observations)
    resolved: dict[BindingId, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_renta_gasto_aggregation":
            continue
        selector = _renta_ledger_gasto_selector(binding)
        matched = [
            observation for observation in available if observation.target_casilla_id == selector.target_casilla_id
        ]
        resolved[binding.id] = sum((observation.deductible_amount for observation in matched), Decimal("0"))
    return resolved


def unsupported_ledger_renta_gasto_observations(
    revision: ModeloRevision,
    observations: Iterable[RentaGastoObservationProtocol],
) -> tuple[RentaGastoObservationProtocol, ...]:
    """Return the gasto observations no binding on the :class:`ModeloRevision` ``revision`` can consume.

    Fail-closed counterpart to
    :func:`resolve_ledger_renta_gasto_aggregation_binding_values`, mirroring
    :func:`unsupported_ledger_renta_income_observations`. An observation whose
    ``target_casilla_id`` matches no ``ledger_renta_gasto_aggregation`` binding has
    its deductible expense silently dropped — a modelling gap, not a legitimate
    zero (no-silent-under-declaration).

    False-fire guard: a zero-``deductible_amount`` observation contributes
    nothing whether or not it is routed and is excluded; only a non-zero
    declarable gasto reaching no casilla is surfaced.
    """
    supported_casillas = frozenset(
        _renta_ledger_gasto_selector(binding).target_casilla_id
        for binding in revision.bindings
        if binding.source == "ledger_renta_gasto_aggregation"
    )
    unsupported: list[RentaGastoObservationProtocol] = []
    for observation in observations:
        if observation.deductible_amount == Decimal("0"):
            continue
        if observation.target_casilla_id not in supported_casillas:
            unsupported.append(observation)
    return tuple(unsupported)


def validate_ledger_oss_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_oss_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector shape against
    :class:`_OssIossLedgerSelector` (preserving the underlying pydantic field
    error) then lifts the fact/aggregation-op invariant to build time via the
    raise-style :func:`validate_ledger_oss_aggregation_binding_definition`, which
    stays as a defence-in-depth resolve-time re-check.
    """
    failures = selector_against_model(binding, _OssIossLedgerSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "ledger_oss_aggregation", validate_ledger_oss_aggregation_binding_definition)


def validate_ledger_iva_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_iva_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_IvaLedgerSelector`; lifts
    the fact/aggregation-op invariant via the raise-style
    :func:`validate_ledger_iva_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _IvaLedgerSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "ledger_iva_aggregation", validate_ledger_iva_aggregation_binding_definition)


def validate_ledger_renta_expense_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_expense_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerExpenseSelector`;
    lifts the fact/aggregation-op invariant via the raise-style
    :func:`validate_ledger_renta_expense_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerExpenseSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_expense_aggregation",
        validate_ledger_renta_expense_aggregation_binding_definition,
    )


def validate_ledger_renta_income_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_income_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerIncomeSelector`;
    lifts the fact/aggregation-op invariant via the raise-style
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


def validate_ledger_renta_gasto_aggregation_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a ``ledger_renta_gasto_aggregation`` binding at registry-build time.

    Accumulating ``list[str]`` validator over :class:`_RentaLedgerGastoSelector`;
    lifts the casilla / fact / aggregation-op invariant via the raise-style
    :func:`validate_ledger_renta_gasto_aggregation_binding_definition`.
    """
    failures = selector_against_model(binding, _RentaLedgerGastoSelector)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_renta_gasto_aggregation",
        validate_ledger_renta_gasto_aggregation_binding_definition,
    )
