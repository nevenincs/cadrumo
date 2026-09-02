"""Canonical ledger aggregation binding family."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from ....core.aggregation import (
    BindingAggregationOp,
    BindingSourceKind,
)
from ....core.models import STRICT_FROZEN_CONFIG
from ...iva.classification import InvoiceKind, TransactionKind
from ...iva.oss import OssIossRegime
from ...iva.schema import (
    EUMemberState,
    IvaRateKind,
)
from ._ledger_binding_resolution import (
    resolve_ledger_family_binding_values,
    unsupported_ledger_family_observations,
)
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, selector_against_model
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .ids import BindingId
from .ledger_binding_selector_support import LedgerIvaFact, OssIossLedgerFact
from .schema import DataBindingDefinition, ModeloRevision
from .schema_base import coerce_enum_member, coerce_enum_tuple


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

    model_config = STRICT_FROZEN_CONFIG

    regime: Annotated[OssIossRegime, BeforeValidator(coerce_enum_member(OssIossRegime))]
    destination_member_state: Annotated[EUMemberState, BeforeValidator(coerce_enum_member(EUMemberState))]
    rate_kind: Annotated[IvaRateKind, BeforeValidator(coerce_enum_member(IvaRateKind))]
    invoice_direction: Annotated[InvoiceKind, BeforeValidator(coerce_enum_member(InvoiceKind))]
    transaction_kinds: Annotated[
        tuple[TransactionKind, ...],
        BeforeValidator(coerce_enum_tuple(TransactionKind)),
    ] = Field(min_length=1)
    fact: OssIossLedgerFact = LedgerIvaFact.IVA_AMOUNT_SUM

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


OssIossLedgerSelector = _OssIossLedgerSelector
