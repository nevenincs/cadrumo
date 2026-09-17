"""Modelo 210 explicit-IRNR ledger binding contract.

The selected :class:`ModeloRevision` declares the bindings this module
validates and resolves. The resolver and its fail-closed screen delegate
their filter/aggregate skeleton to
:func:`~.registry._ledger_binding_resolution.resolve_ledger_family_binding_values`
and :func:`~.registry._ledger_binding_resolution.unsupported_ledger_family_observations`,
the shape shared by every ledger-aggregation family; this module supplies
only the M210 selector, its ``target_casilla_id`` match predicate, the
single-fact ``gross_income_amount`` aggregation, and the zero-amount
false-fire guard.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.country_code import CountryCodeAlpha2
from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from ._ledger_binding_resolution import resolve_ledger_family_binding_values, unsupported_ledger_family_observations
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, provider_member, selector_against_model
from .errors import RegistryValidationError
from .ids import BindingId

if TYPE_CHECKING:
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "IrnrIncomeObservationProtocol",
    "LedgerIrnrIncomeProvider",
    "ledger_irnr_income_source_jurisdictions",
    "resolve_ledger_irnr_income_aggregation_binding_values",
    "unsupported_ledger_irnr_income_observations",
    "validate_ledger_irnr_income_aggregation_binding",
    "validate_ledger_irnr_income_aggregation_binding_definition",
]


class LedgerIrnrIncomeProvider(BaseModel):
    """Validated selector for a Modelo 210 gross-income ledger binding."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal[BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION] = BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION

    modelo: Modelo = Modelo("210")
    target_casilla_id: CasillaId
    fact: Literal["gross_income_sum"] = "gross_income_sum"
    source_jurisdictions: tuple[CountryCodeAlpha2, ...] = Field(min_length=1)
    """Source jurisdictions whose income the binding admits; any other source is out of scope."""

    @field_validator("modelo")
    @classmethod
    @pydantic_validation_boundary
    def _require_modelo_210(cls, value: Modelo) -> Modelo:
        if value != Modelo("210"):
            raise ValueError("ledger_irnr_income_aggregation modelo must be '210'")
        return value

    @field_validator("source_jurisdictions")
    @classmethod
    @pydantic_validation_boundary
    def _require_distinct_uppercase_jurisdictions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not code.isalpha() or code != code.upper() for code in value):
            raise ValueError("ledger_irnr_income_aggregation source_jurisdictions must be uppercase alpha-2 codes")
        if len(set(value)) != len(value):
            raise ValueError("ledger_irnr_income_aggregation source_jurisdictions must not repeat a code")
        return value


def ledger_irnr_income_source_jurisdictions(
    revision: ModeloRevision,
    *,
    target_casilla_id: CasillaId,
) -> frozenset[str] | None:
    """Return the source-jurisdiction scope the revision declares for ``target_casilla_id``.

    ``None`` means the revision declares no single scope for the target, which
    callers must treat as an unavailable declaration rather than an open scope.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    scopes = {
        frozenset(selector.source_jurisdictions)
        for binding in revision.bindings
        if binding.source == BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION
        and (selector := _irnr_ledger_income_selector(binding)).target_casilla_id == target_casilla_id
    }
    if len(scopes) != 1:
        return None
    return scopes.pop()


_IRNR_GROSS_INCOME_CASILLAS: frozenset[CasillaId] = frozenset(
    (validated_casilla_id("rendimientos_integros", surface="_IRNR_GROSS_INCOME_CASILLAS"),),
)


def _irnr_ledger_income_selector(binding: BindingDefinition) -> LedgerIrnrIncomeProvider:
    try:
        return provider_member(binding, LedgerIrnrIncomeProvider)
    except (ValueError, TypeError) as exc:
        raise RegistryValidationError(
            f"binding {binding.id!r} has malformed ledger_irnr_income_aggregation selector: {exc}",
        ) from exc


def validate_ledger_irnr_income_aggregation_binding_definition(binding: BindingDefinition) -> None:
    """Validate a ``ledger_irnr_income_aggregation`` binding definition."""
    if binding.source != BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION:
        raise RegistryValidationError(f"binding {binding.id!r} is not a ledger_irnr_income_aggregation source")
    selector = _irnr_ledger_income_selector(binding)
    if selector.target_casilla_id not in _IRNR_GROSS_INCOME_CASILLAS:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {selector.target_casilla_id!r} "
            f"is outside the supported Modelo 210 gross-income casillas {sorted(_IRNR_GROSS_INCOME_CASILLAS)!r}",
        )
    if binding_aggregation_op(binding) is not BindingAggregationOp.SUM:
        raise RegistryValidationError(
            f"binding {binding.id!r} ledger_irnr_income_aggregation supports only aggregation op 'sum'",
        )


def validate_ledger_irnr_income_aggregation_binding(binding: BindingDefinition) -> list[str]:
    """Validate a ``ledger_irnr_income_aggregation`` binding at registry-build time."""
    failures = selector_against_model(binding, LedgerIrnrIncomeProvider)
    if failures:
        return failures
    return invariant_diagnostics(
        binding,
        "ledger_irnr_income_aggregation",
        validate_ledger_irnr_income_aggregation_binding_definition,
    )


class IrnrIncomeObservationProtocol(Protocol):
    """Structural protocol for one selected M210 gross-income observation."""

    @property
    def target_casilla_id(self) -> CasillaId:
        """Return the casilla this observation's gross income is routed to."""
        ...

    @property
    def gross_income_amount(self) -> Decimal:
        """Return the observed gross income amount."""
        ...


def _irnr_income_build_matcher(
    selector: LedgerIrnrIncomeProvider,
) -> Callable[[IrnrIncomeObservationProtocol], bool]:
    target_casilla_id = selector.target_casilla_id

    def matcher(observation: IrnrIncomeObservationProtocol) -> bool:
        return observation.target_casilla_id == target_casilla_id

    return matcher


def _irnr_income_aggregate(
    matched: Sequence[IrnrIncomeObservationProtocol],
    selector: LedgerIrnrIncomeProvider,
) -> Decimal:
    del selector  # single declared fact (gross_income_sum); nothing to dispatch on
    return sum((observation.gross_income_amount for observation in matched), Decimal("0"))


def resolve_ledger_irnr_income_aggregation_binding_values(
    revision: ModeloRevision,
    observations: Iterable[IrnrIncomeObservationProtocol],
) -> dict[BindingId, Decimal]:
    """Resolve Modelo 210 gross-income bindings from selected M210 observations.

    Delegates the filter/aggregate skeleton to
    :func:`resolve_ledger_family_binding_values`, shared by every ledger
    family resolver.

    Args:
        revision: The :class:`ModeloRevision` that declares the bindings to resolve.
        observations: Selected M210 gross-income observations.

    Returns:
        Binding ids mapped to their selected gross-income totals.

    Raises:
        RegistryValidationError: If a declared binding has a malformed selector.
    """
    return resolve_ledger_family_binding_values(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
        parse_selector=_irnr_ledger_income_selector,
        build_matcher=_irnr_income_build_matcher,
        aggregate=_irnr_income_aggregate,
    )


def unsupported_ledger_irnr_income_observations(
    revision: ModeloRevision,
    observations: Iterable[IrnrIncomeObservationProtocol],
) -> tuple[IrnrIncomeObservationProtocol, ...]:
    """Return non-zero M210 observations no declared source binding consumes.

    Delegates the screen to :func:`unsupported_ledger_family_observations` —
    see that function for the shared fail-closed contract (why an unmatched
    observation is a modelling gap, not a legitimate zero). This family's
    own contribution is narrow: the ``target_casilla_id`` match predicate
    (reused from the resolver's ``_irnr_income_build_matcher``) and a
    zero-``gross_income_amount`` false-fire guard. No ``extra_exclusion``.

    Args:
        revision: The :class:`ModeloRevision` whose bindings determine support.
        observations: Selected M210 gross-income observations to inspect.

    Returns:
        Non-zero observations that no declared binding consumes.

    Raises:
        RegistryValidationError: If a declared binding has a malformed selector.
    """
    return unsupported_ledger_family_observations(
        revision,
        observations,
        source_kind=BindingSourceKind.LEDGER_IRNR_INCOME_AGGREGATION,
        parse_selector=_irnr_ledger_income_selector,
        build_matcher=_irnr_income_build_matcher,
        is_declarable=lambda observation: observation.gross_income_amount != Decimal("0"),
    )
