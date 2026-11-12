"""The withdrawal of a carry statement that returns a work unit to no current calculation.

Some carries from earlier ejercicios refuse the calculation while nobody has
stated them: before the filer's statement the work unit had no calculation at
all. Withdrawing that statement therefore cannot recalculate. Instead, when the
withdrawal leaves the carry unstated and the head holds nothing of the filer's
but statements of such carries, the work unit returns to the state it had
before the statement: no current calculation. The family is all or nothing, so
withdrawing one member withdraws them all. Every revision stays stored.

A head holding any other value of the filer's is not withdrawn, because the
values would be lost with it; the filer replaces the statement with the figure
instead. A declaration recorded as filed is corrected by amendment only.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ...core.secure_object_write import SecureObjectWrite
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import FILED_REVISION_STATES, CalculationRevision
from ...domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.repository import upsert_work_unit
from ...domain.modelos.work_unit import WorkUnit
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .caller_context import CalculationCallerContext, caller_context_of
from .edit_models import (
    ModeloEditBaselineV1,
    ModeloEditBindingIntentKind,
    ModeloEditCarryWithdrawalBlock,
    ModeloEditRefusalV1,
    ModeloEditSubmissionV1,
)
from .edit_services import reconfirm_modelo_edit_baseline
from .work_missing_input import CALCULATION_REFUSING_ABSENCE_FAMILIES


def calculation_refusing_carry_bindings(revision: ModeloRevision) -> frozenset[BindingId]:
    """The bindings of ``revision`` whose carry, while unstated, refuses the calculation."""
    return frozenset(
        binding.id
        for binding in revision.bindings
        if binding.absence_attestation is not None
        and binding.absence_attestation in CALCULATION_REFUSING_ABSENCE_FAMILIES
    )


def is_carry_withdrawal(submission: ModeloEditSubmissionV1, carry_bindings: frozenset[BindingId]) -> bool:
    """Whether ``submission`` only withdraws statements and withdraws one of a calculation-refusing carry."""
    if submission.scalar_intents or submission.row_intents or submission.detail_row_intents:
        return False
    intents = submission.binding_intents
    return (
        bool(intents)
        and all(intent.kind is ModeloEditBindingIntentKind.REMOVE_OVERRIDE for intent in intents)
        and any(intent.address.binding_id in carry_bindings for intent in intents)
    )


def holds_only_carry_statements(head: CalculationRevision, carry_bindings: frozenset[BindingId]) -> bool:
    """Whether everything of the filer's on ``head`` is a statement that a calculation-refusing carry holds nothing.

    An unknown operator layer, a typed or stated figure, a clear, a detail row
    or any other caller input is something the filer would lose.
    """
    context = caller_context_of(head)
    layer = context.operator_layer
    if layer is None or _holds_other_caller_input(context):
        return False
    stated = set(layer.attested_binding_ids)
    return (
        bool(stated)
        and stated <= carry_bindings
        and set(layer.binding_overrides) == stated
        and all(value == ATTESTED_ZERO for value in layer.binding_overrides.values())
    )


def _holds_other_caller_input(context: CalculationCallerContext) -> bool:
    """Whether ``context`` carries any caller input besides carry-binding statements."""
    layer = context.operator_layer
    layer_inputs = (
        () if layer is None else (layer.decimal_casilla_inputs, layer.text_casilla_inputs, layer.value_attestations)
    )
    context_inputs = (
        context.filing_instance_evidence,
        context.m210_official_tipo_renta_code,
        context.m210_gross_income_source_mode,
        context.borrador_snapshot_id,
    )
    return (
        any(layer_inputs)
        or bool(context.cleared_casilla_ids)
        or bool(context.detail_rows)
        or any(value is not None for value in context_inputs)
    )


def recorded_as_filed(head: CalculationRevision, work_unit: WorkUnit) -> bool:
    """Whether the declaration, or the head the edit starts from, is recorded as filed."""
    return (
        head.state in FILED_REVISION_STATES
        or work_unit.filed_calculation_revision_id is not None
        or work_unit.current_filing_record_id is not None
    )


def carry_withdrawal_block(
    head: CalculationRevision, work_unit: WorkUnit, carry_bindings: frozenset[BindingId]
) -> ModeloEditCarryWithdrawalBlock | None:
    """Why the withdrawal cannot return the work unit to no calculation, or ``None`` when it can."""
    if recorded_as_filed(head, work_unit):
        return ModeloEditCarryWithdrawalBlock.FILED
    if not holds_only_carry_statements(head, carry_bindings):
        return ModeloEditCarryWithdrawalBlock.KEEPS_ENTRIES
    return None


def withdraw_current_calculation(
    baseline: ModeloEditBaselineV1,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    operation: PinnedAuthorityOperation,
    now: datetime,
    co_commit: Callable[[], tuple[SecureObjectWrite, ...]],
) -> ModeloEditRefusalV1 | None:
    """Return the work unit to no current calculation, co-committing ``co_commit``'s writes.

    The baseline is checked again against freshly read catalogues and the
    write is guarded by the catalogue revision it was derived from, so a
    concurrent change refuses rather than being overwritten. No revision is
    removed. ``None`` once the pointer moved.
    """
    work_units, work_units_revision_id = work_unit_repository.load_revisioned()
    stale = reconfirm_modelo_edit_baseline(
        baseline,
        work_catalogue=work_units,
        calculation_catalogue=calculation_repository.load(operation=operation),
    )
    if stale is not None:
        return stale
    unit = work_units.work_units[baseline.work_unit_id]
    withdrawn = upsert_work_unit(
        work_units, unit.model_copy(update={"current_calculation_revision_id": None, "updated_at": now})
    )
    work_unit_repository.save_with_secure_object_writes(
        withdrawn, co_commit(), expected_revision_id=work_units_revision_id
    )
    return None


__all__ = [
    "calculation_refusing_carry_bindings",
    "carry_withdrawal_block",
    "holds_only_carry_statements",
    "is_carry_withdrawal",
    "recorded_as_filed",
    "withdraw_current_calculation",
]
