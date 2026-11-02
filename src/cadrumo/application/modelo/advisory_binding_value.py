"""Report every value a grade-capped binding produced, for all resolvers together.

A binding's grade cap is a registry declaration, so no resolver states it: each
resolver produces values and, where it can, says what those values rest on.
After the source mesh is merged this step reads the pinned revision's capped
bindings, finds each one that produced a value in any channel, and emits one
``advisory_binding_value`` diagnostic per box the value reaches. The diagnostic
carries the binding, the box, the cap's reason and provisions, the amount and
the resolver's stated outcome. A proven zero withholds nothing; every other
value, including one whose resolver stated no outcome, withholds verify, export
and local filing through the calculation-note gate.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.aggregation import BindingValueOutcome
from ...domain.calculations.registry.binding_grade_cap_reach import CappedBindingReach, capped_binding_reach
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...domain.modelos.calculation_revision_sources import GRADE_CAP_NOTE_SENTENCES, CalculationNoteFact
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .printed_boxes import snapshot_printed_boxes

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
    from ..aggregation.source_mesh import CalculationSourceResolution


_NOTHING_PRODUCED: Final = object()


def _produced_values(resolution: CalculationSourceResolution, binding_id: BindingId) -> Iterator[object]:
    """Yield every value ``binding_id`` produced, scalar channels first and then its rows."""
    for channel in (
        resolution.binding_values,
        resolution.enum_binding_values,
        resolution.date_binding_values,
        resolution.boolean_binding_values,
    ):
        if binding_id in channel:
            yield channel[binding_id]
    for (row_binding_id, _row_index), value in resolution.row_binding_values.items():
        if row_binding_id == binding_id:
            yield value


def _diagnostic(
    binding: BindingDefinition,
    reach: CappedBindingReach,
    *,
    casilla_id: str,
    box: str,
    value: object,
    outcome: BindingValueOutcome | None,
) -> CalculationSourceDiagnostic:
    cap = reach.cap
    proven_zero = outcome is BindingValueOutcome.PROVEN_ZERO
    message = (
        f"binding {binding.id!r} reaches box {box} with a proven zero: its rows carry nothing the "
        f"{cap.reason.value} cap concerns"
        if proven_zero
        else f"binding {binding.id!r} gives box {box} the value {value}, whose reach is capped at "
        f"{cap.grade.value} ({cap.reason.value}); checking, exporting and recording wait until the cap is removed"
    )
    return CalculationSourceDiagnostic(
        reason="advisory_binding_value",
        source_kind=binding.source.value,
        binding_source=binding.source,
        binding_id=binding.id,
        casilla_id=casilla_id,
        source_ref=str(binding.id),
        message=message,
        asserted_legal_refs=cap.legal_refs,
        fact=(
            CalculationNoteFact.of(GRADE_CAP_NOTE_SENTENCES[cap.reason], box=box, amount=value, binding=binding.id)
            if isinstance(value, Decimal)
            else None
        ),
        value_outcome=outcome if isinstance(value, Decimal) else None,
    )


def collect_advisory_binding_value_diagnostics(
    snapshot: RegistrySnapshot,
    resolution: CalculationSourceResolution,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one diagnostic per capped binding value and box it reaches, in declaration order.

    A stated outcome is carried only beside a decimal value, the one channel a
    resolver states it for; any other channel's capped value withholds.
    """
    reach_map = capped_binding_reach(snapshot.revision, authority=operation)
    if not reach_map:
        return ()
    bindings = revision_bindings_by_id(snapshot.revision)
    boxes = snapshot_printed_boxes(operation, snapshot)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding_id, reach in reach_map.items():
        # One report per box: a row binding's many rows are one capped value there.
        value = next(_produced_values(resolution, binding_id), _NOTHING_PRODUCED)
        if value is _NOTHING_PRODUCED:
            continue
        diagnostics.extend(
            _diagnostic(
                bindings[binding_id],
                reach,
                casilla_id=casilla_id,
                box=boxes.number(casilla_id) or casilla_id,
                value=value,
                outcome=resolution.value_outcomes.get(binding_id),
            )
            for casilla_id in reach.casilla_ids
        )
    return tuple(diagnostics)


def add_advisory_binding_value_diagnostics(
    snapshot: RegistrySnapshot,
    resolution: CalculationSourceResolution,
    *,
    operation: PinnedAuthorityOperation,
) -> CalculationSourceResolution:
    """Return ``resolution`` with every capped binding value reported; unchanged when there is none."""
    diagnostics = collect_advisory_binding_value_diagnostics(snapshot, resolution, operation=operation)
    if not diagnostics:
        return resolution
    return resolution.model_copy(update={"diagnostics": resolution.diagnostics + diagnostics})


__all__ = ["add_advisory_binding_value_diagnostics", "collect_advisory_binding_value_diagnostics"]
