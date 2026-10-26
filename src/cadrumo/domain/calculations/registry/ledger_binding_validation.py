"""Validation contract shared by every ledger aggregation binding family.

A ledger family resolver folds the rows its selector matches into one total and
reads no other aggregation operator, so ``sum`` is the only operation a ledger
binding can honestly declare. Admitting ``copy`` (or ``rows`` on a scalar
resolver) would validate a declaration the resolver silently computes as a sum.

Each family keeps its own selector model, casilla scope and fact vocabulary; this
module owns the checks whose shape is identical across them: the source-kind gate,
the typed selector narrowing, the aggregation-operator gate, the target-casilla
scope gate, the fact gate, and the accumulating build-time adapter.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.casilla_id import CasillaId
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import invariant_diagnostics, provider_member, selector_against_model
from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "LEDGER_AGGREGATION_OPS",
    "ledger_binding_build_diagnostics",
    "ledger_binding_selector",
    "require_ledger_aggregation_op",
    "require_ledger_fact",
    "require_ledger_target_casilla",
]

LEDGER_AGGREGATION_OPS: Final = frozenset({BindingAggregationOp.SUM})
"""The aggregation operators a ledger family resolver actually evaluates."""


def ledger_binding_selector[ProviderT: BaseModel](
    binding: BindingDefinition,
    source_kind: BindingSourceKind,
    provider_model: type[ProviderT],
) -> ProviderT:
    """Return the typed selector of a binding that must belong to ``source_kind``.

    Raises:
        RegistryValidationError: The binding declares another source kind, or its
            provider member is not an instance of ``provider_model``.
    """
    if binding.source != source_kind:
        raise RegistryValidationError(f"binding {binding.id!r} is not a {source_kind.value} source")
    return provider_member(binding, provider_model)


def require_ledger_aggregation_op(binding: BindingDefinition) -> None:
    """Refuse a ledger binding whose effective operator its resolver cannot evaluate."""
    op = binding_aggregation_op(binding)
    if op not in LEDGER_AGGREGATION_OPS:
        permitted = ", ".join(repr(member.value) for member in sorted(LEDGER_AGGREGATION_OPS))
        raise RegistryValidationError(
            f"binding {binding.id!r} {binding.source.value} supports only aggregation op {permitted}, got {op.value!r}",
        )


def require_ledger_target_casilla(
    binding: BindingDefinition,
    target_casilla_id: CasillaId,
    supported: Collection[CasillaId],
    *,
    scope: str,
) -> None:
    """Refuse a ledger binding whose target casilla lies outside its family's ``scope``."""
    if target_casilla_id not in supported:
        raise RegistryValidationError(
            f"binding {binding.id!r} target_casilla_id {target_casilla_id!r} "
            f"is outside the {scope} {sorted(supported)!r}",
        )


def require_ledger_fact(binding: BindingDefinition, fact: str, supported: Collection[str]) -> None:
    """Refuse a ledger binding whose fact lies outside its family's vocabulary."""
    if fact not in supported:
        raise RegistryValidationError(
            f"binding {binding.id!r} {binding.source.value} supports only facts {sorted(supported)!r}, got {fact!r}",
        )


def ledger_binding_build_diagnostics(
    binding: BindingDefinition,
    provider_model: type[BaseModel],
    check: Callable[[BindingDefinition], object],
) -> list[str]:
    """Accumulate a ledger binding's selector-shape and invariant diagnostics.

    The selector shape is reported first and alone, preserving the underlying
    field message; only a well-formed selector reaches the family's raise-style
    invariant ``check``.
    """
    failures = selector_against_model(binding, provider_model)
    if failures:
        return failures
    return invariant_diagnostics(binding, binding.source.value, check)
