"""Ledger-backed registry binding helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG, Modelo
from ....core.aggregation import BindingAggregationOp
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
from ._binding_selector_utils import selector_as_dict as _selector_as_dict
from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition, ModeloRevision

# Ledger-aggregation binding source kinds. Every binding whose ``source``
# matches one of these reads its values from the bucket-scoped ledger
# (transaction-classified IVA aggregation or Renta first-slice expense
# aggregation). Cross-domain consumers route through this frozenset so
# the registry stays the single source of truth for ledger readiness.
LEDGER_BINDING_SOURCE_KINDS: frozenset[str] = frozenset({"ledger_iva_aggregation", "ledger_renta_expense_aggregation"})

__all__ = [
    "LEDGER_BINDING_SOURCE_KINDS",
    "IvaLedgerObservation",
    "OssIossLedgerObservation",
    "RentaExpenseObservationProtocol",
    "RentaIncomeObservationProtocol",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "resolve_ledger_renta_expense_aggregation_binding_values",
    "resolve_ledger_renta_income_aggregation_binding_values",
    "unsupported_ledger_iva_observations",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
    "validate_ledger_renta_expense_aggregation_binding_definition",
    "validate_ledger_renta_income_aggregation_binding_definition",
]

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
) -> dict[str, Decimal]:
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
    resolved: dict[str, Decimal] = {}
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
    fact: Literal["iva_amount_sum", "base_amount_sum"] = "iva_amount_sum"

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

    if selector.fact not in {"iva_amount_sum", "base_amount_sum"}:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_iva_aggregation supports only "
            f"facts {{iva_amount_sum, base_amount_sum}}, got {selector.fact!r}",
        )


def resolve_ledger_iva_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IvaLedgerObservation],
) -> dict[str, Decimal]:
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
    resolved: dict[str, Decimal] = {}
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
_RENTA_100_FIRST_SLICE_CASILLAS: frozenset[str] = frozenset({"0186", "0192", "0199", "0203"})


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
    def target_casilla(self) -> str: ...

    @property
    def deductible_amount(self) -> Decimal: ...


class _RentaLedgerExpenseSelector(BaseModel):
    """Validated form of a ledger_renta_expense_aggregation binding selector."""

    model_config = ConfigDict(strict=False, frozen=True, extra="forbid")

    modelo: Literal[Modelo.M100] = Modelo.M100
    period: Literal["0A"] = "0A"
    target_casilla: str = Field(min_length=4, max_length=4)
    fact: Literal["deductible_amount_sum"] = "deductible_amount_sum"


def _renta_ledger_expense_selector(binding: DataBindingDefinition) -> _RentaLedgerExpenseSelector:
    try:
        return _RentaLedgerExpenseSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_expense_aggregation selector",
        ) from exc


def validate_ledger_renta_expense_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_expense_aggregation`` binding definition."""
    if binding.source != "ledger_renta_expense_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_expense_aggregation source")
    selector = _renta_ledger_expense_selector(binding)
    if selector.target_casilla not in _RENTA_100_FIRST_SLICE_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla {selector.target_casilla!r} "
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
) -> dict[str, Decimal]:
    """Resolve every ``ledger_renta_expense_aggregation`` binding on ``revision``.

    Args:
        revision: The :class:`ModeloRevision` whose renta-expense bindings to resolve.
        observations: Typed renta-expense observations the bindings aggregate
            via their declared ``selector.fact`` and ``aggregation.op``.
    """
    available = tuple(observations)
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_renta_expense_aggregation":
            continue
        selector = _renta_ledger_expense_selector(binding)
        matched = [
            observation
            for observation in available
            if observation.modelo == selector.modelo
            and observation.period == selector.period
            and observation.target_casilla == selector.target_casilla
        ]
        resolved[binding.id] = sum((observation.deductible_amount for observation in matched), Decimal("0"))
    return resolved


class _RentaLedgerIncomeSelector(BaseModel):
    """Validated form of a ledger_renta_income_aggregation binding selector.

    ``modelo`` is the M130 declaration series (the only model that sources
    income via this aggregation path). ``target_casilla`` is the casilla that
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

    modelo: Literal[Modelo.M130] = Modelo.M130
    target_casilla: str = Field(min_length=2, max_length=8)
    fact: Literal["ingresos_integros_sum", "gross_income_sum", "taxable_base_sum"] = "gross_income_sum"


_RENTA_130_INCOME_CASILLAS: frozenset[str] = frozenset({"01", "03"})


def _renta_ledger_income_selector(binding: DataBindingDefinition) -> _RentaLedgerIncomeSelector:
    try:
        return _RentaLedgerIncomeSelector.model_validate(_selector_as_dict(binding))
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_renta_income_aggregation selector",
        ) from exc


_RENTA_130_INCOME_SUPPORTED_FACTS: frozenset[str] = frozenset(
    {"ingresos_integros_sum", "gross_income_sum", "taxable_base_sum"},
)


def validate_ledger_renta_income_aggregation_binding_definition(binding: DataBindingDefinition) -> None:
    """Validate a ``ledger_renta_income_aggregation`` binding definition."""
    if binding.source != "ledger_renta_income_aggregation":
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_renta_income_aggregation source")
    selector = _renta_ledger_income_selector(binding)
    if selector.target_casilla not in _RENTA_130_INCOME_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla {selector.target_casilla!r} "
            "is outside the supported Modelo 130 income casillas",
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
    def target_casilla(self) -> str: ...

    @property
    def gross_amount(self) -> Decimal: ...

    @property
    def taxable_base_amount(self) -> Decimal | None: ...


def resolve_ledger_renta_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[RentaIncomeObservationProtocol],
) -> dict[str, Decimal]:
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
    resolved: dict[str, Decimal] = {}
    for binding in revision.bindings:
        if binding.source != "ledger_renta_income_aggregation":
            continue
        selector = _renta_ledger_income_selector(binding)
        matched = [observation for observation in available if observation.target_casilla == selector.target_casilla]
        if selector.fact == "ingresos_integros_sum":
            resolved[str(binding.id)] = sum(
                (
                    observation.taxable_base_amount
                    if observation.taxable_base_amount is not None
                    else observation.gross_amount
                    for observation in matched
                ),
                Decimal("0"),
            )
        elif selector.fact == "taxable_base_sum":
            resolved[str(binding.id)] = sum(
                (observation.taxable_base_amount or Decimal("0") for observation in matched),
                Decimal("0"),
            )
        else:
            resolved[str(binding.id)] = sum((observation.gross_amount for observation in matched), Decimal("0"))
    return resolved
