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
from .binding_targets import bound_casilla_binding_ids
from .errors import RegistryValidationError
from .schema_input_kind import InputKind

if TYPE_CHECKING:
    from .ids import BindingId
    from .schema import BindingDefinition, ModeloRevision

__all__ = [
    "LEDGER_AGGREGATION_OPS",
    "ledger_binding_build_diagnostics",
    "ledger_binding_selector",
    "ledger_target_casilla_failures",
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


def ledger_target_casilla_failures(
    revision: ModeloRevision,
    *,
    source_kind: BindingSourceKind,
    target_casilla_id: Callable[[BindingDefinition], CasillaId],
    reciprocal: bool,
) -> list[str]:
    """Return the failures for family bindings aimed at a box the edition gives another owner.

    A ledger total may only land on a bound casilla that the same family feeds. A
    manual or computed box, or a box another family binds, is refused from the
    edition's own declarations, so no box list is restated here. ``reciprocal``
    further requires the target to name this exact binding; a family whose second
    quantity shares its observation key with the first leaves it unset.

    Args:
        revision: :class:`ModeloRevision` owning the bindings and target casillas.
        source_kind: Ledger aggregation family whose binding targets are checked.
        target_casilla_id: Read the target casilla from one family binding.
        reciprocal: Require the target casilla to name the same binding explicitly.
    """
    family = frozenset(binding.id for binding in revision.bindings if binding.source == source_kind)
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    failures: list[str] = []
    for binding in revision.bindings:
        if binding.source != source_kind:
            continue
        target = target_casilla_id(binding)
        casilla = casillas.get(target)
        if casilla is None:
            failures.append(f"binding {binding.id!r} targets casilla {target!r}, which the edition does not declare")
            continue
        owners = bound_casilla_binding_ids(casilla)
        if not _ledger_family_owns_casilla(casilla.input_kind, owners, family):
            failures.append(
                f"binding {binding.id!r} targets casilla {target!r}, which is {casilla.input_kind.value} "
                f"and bound by {sorted(owners)!r} rather than by the {source_kind.value} family",
            )
        elif reciprocal and binding.id not in owners:
            failures.append(
                f"binding {binding.id!r} targets casilla {target!r}, which is bound by {sorted(owners)!r}",
            )
    return failures


def _ledger_family_owns_casilla(
    input_kind: InputKind, owners: tuple[BindingId, ...], family: frozenset[BindingId]
) -> bool:
    return input_kind is InputKind.BOUND and bool(owners) and family.issuperset(owners)


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
