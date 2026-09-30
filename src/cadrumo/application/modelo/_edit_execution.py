"""The guarded application-owned edit executor for the Modelo Edit Contract V1.

Only the enrolled operation executor may invoke this boundary. Immediately
before effect it revision-loads the work and calculation catalogues and
rechecks every baseline coordinate through
:func:`~.edit_services.reconfirm_modelo_edit_baseline`; any disagreement
refuses with ``stale_edit_baseline``, writes nothing, and settles the domain
effect as ``NONE``. It never silently rebases, merges, or promotes a green
preflight into authority.

An edit is applied to the operator's own work, not to a blank slate. The
executor starts from the caller context of the current calculation head
(:mod:`.caller_context`) -- its operator layer, explicit clears, detail rows,
Modelo 303 filing-instance evidence, Modelo 210 selections and borrador
snapshot -- and applies the submitted intents to it:

* ``SET_TYPED_VALUE`` / ``SET_OVERRIDE_VALUE`` replace the operator's value and
  withdraw an earlier clear;
* ``CLEAR_DECLARED_VALUE`` removes the operator's value and records an explicit
  clear, refused when a source feeds the casilla (a restore is the answer
  there);
* ``RESTORE_SOURCE_VALUE`` / ``REMOVE_OVERRIDE`` remove the operator's value so
  the source tiers win again;
* an address the submission does not name keeps its operator value.

The resulting calculation records the new operator layer, so the next edit or
recalculation starts from it. Every value, channel and precondition failure
returns a typed no-effect refusal; none escapes as a raw exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.error_codes import get_registered_error_code
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import content_hash_hex
from ...core.secure_object_write import SecureObjectWrite
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.runtime_graph import enum_consumed_binding_ids, revision_date_binding_ids
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.filing.schema import ModeloScalar
from ...domain.identifiers import canonical_decimal_string
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.row_models import ModeloDetailRow
from .action_errors import ModeloClearedCasillaSourceFedError
from .calculation_action_ports import CalculationActionPorts
from .calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .caller_context import CalculationCallerContext, caller_context_calculation_inputs, caller_context_of
from .edit_contract import ModeloEditMutationFamily, ModeloEditMutationResultReceiptV1
from .edit_models import (
    ModeloBindingEditIntentV1,
    ModeloDetailRowEditIntentV1,
    ModeloEditAddressV1,
    ModeloEditApplyRequestV1,
    ModeloEditBindingIntentKind,
    ModeloEditDetailRowIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionResultV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditRefusalCode,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditUnsupportedIntentReason,
    ModeloEditUnsupportedIntentRefusalV1,
    ModeloScalarEditIntentV1,
)
from .edit_receipt_ports import ModeloEditReceiptRepositoryPort
from .edit_services import RESPONSIBLE_OWNER as _RESPONSIBLE_OWNER
from .edit_services import (
    detail_row_natural_key,
    reconfirm_modelo_edit_baseline,
    validate_binding_intent,
    validate_scalar_intent,
    writable_scalar_entry,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_UNSUPPORTED_RECONSIDERATION = "resubmit without this intent once its capability lands, or split the submission"

_ROW_UNSUPPORTED_REASON: dict[ModeloEditRowIntentKind, ModeloEditUnsupportedIntentReason] = {
    ModeloEditRowIntentKind.ADD_ROW: ModeloEditUnsupportedIntentReason.ADD_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.UPDATE_ROW: ModeloEditUnsupportedIntentReason.UPDATE_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.DELETE_ROW: ModeloEditUnsupportedIntentReason.DELETE_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.MOVE_ROW: ModeloEditUnsupportedIntentReason.MOVE_ROW_NOT_YET_WIRED,
}

#: Casilla data types the engine reads on its decimal channel. A boolean casilla
#: answers on the same channel encoded 0 / 1; date and year have no engine
#: channel at all yet, so an edit of one is refused rather than guessed.
_DECIMAL_CHANNEL_DATA_TYPES = frozenset({"decimal", "money", "integer", "ratio"})
_BOOLEAN_DATA_TYPE = "boolean"
_CHANNEL_UNAVAILABLE_DATA_TYPES = frozenset({"date", "year"})
_BOOLEAN_TOKENS: dict[str, str] = {"0": "0", "1": "1"}

#: A typed application refusal raised before the calculation boundary built its
#: commit is a precondition the submission cannot satisfy: nothing was written,
#: so it settles as a no-effect refusal naming its registered error code, never
#: as a raw failure. One raised once the commit is being written stays raised,
#: because its effect is no longer known.
_PRE_EFFECT_REFUSALS: tuple[type[BaseException], ...] = (CadrumoError,)


def _unsupported_intent_refusal(
    reason: ModeloEditUnsupportedIntentReason, *, address: ModeloEditAddressV1 | None = None
) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(
        refusal=ModeloEditUnsupportedIntentRefusalV1(
            address=address,
            reason=reason,
            responsible_owner=_RESPONSIBLE_OWNER,
            reconsideration_condition=_UNSUPPORTED_RECONSIDERATION,
        ),
    )


def _domain_refusal(
    code: ModeloEditRefusalCode,
    *,
    condition: str,
    address: ModeloEditAddressV1 | None = None,
    facts: tuple[str, ...] = (),
) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(
        refusal=ModeloEditDomainRefusalV1(
            code=code,
            address=address,
            facts=facts,
            responsible_owner=_RESPONSIBLE_OWNER,
            reconsideration_condition=condition,
        )
    )


def _value_refusal(address: ModeloEditAddressV1, fact: str) -> ModeloEditExecutionNoEffectV1:
    return _domain_refusal(
        ModeloEditRefusalCode.VALIDATION_FAILED,
        address=address,
        facts=(fact,),
        condition="submit a value the address's declared type and channel accept",
    )


@dataclass(slots=True)
class _OperatorState:
    """The mutable working copy of one caller context's operator values and clears."""

    decimal_casilla_inputs: dict[CasillaId, str]
    text_casilla_inputs: dict[CasillaId, str]
    binding_overrides: dict[BindingId, str]
    cleared_casilla_ids: set[CasillaId] = field(default_factory=set)

    @classmethod
    def from_context(cls, context: CalculationCallerContext) -> _OperatorState:
        layer = context.known_operator_layer
        return cls(
            decimal_casilla_inputs=dict(layer.decimal_casilla_inputs),
            text_casilla_inputs=dict(layer.text_casilla_inputs),
            binding_overrides=dict(layer.binding_overrides),
            cleared_casilla_ids=set(context.cleared_casilla_ids),
        )

    def operator_sets(self, casilla_id: CasillaId) -> bool:
        return casilla_id in self.decimal_casilla_inputs or casilla_id in self.text_casilla_inputs

    def withdraw(self, casilla_id: CasillaId) -> None:
        self.decimal_casilla_inputs.pop(casilla_id, None)
        self.text_casilla_inputs.pop(casilla_id, None)

    def layer(self) -> CalculationOperatorLayer:
        return CalculationOperatorLayer(
            decimal_casilla_inputs=dict(sorted(self.decimal_casilla_inputs.items())),
            text_casilla_inputs=dict(sorted(self.text_casilla_inputs.items())),
            binding_overrides=dict(sorted(self.binding_overrides.items())),
        )


def _canonical_decimal_value(value: ModeloScalar) -> Decimal | None:
    """Read a typed or wire-carried amount through the canonical decimal grammar, never coercing."""
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return try_parse_canonical_decimal(value)
    return None


def _boolean_token(value: ModeloScalar) -> str | None:
    """Encode a boolean answer on the engine's 0 / 1 decimal channel."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal | int):
        return _BOOLEAN_TOKENS.get(canonical_decimal_string(Decimal(value)))
    if isinstance(value, str):
        return _BOOLEAN_TOKENS.get(value.strip())
    return None


def _apply_set_scalar(
    state: _OperatorState,
    intent: ModeloScalarEditIntentV1,
    *,
    data_type: str,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Route one SET value onto the channel its casilla's declared type reaches."""
    casilla_id = intent.address.casilla_id
    value = intent.value
    if data_type in _CHANNEL_UNAVAILABLE_DATA_TYPES:
        return _value_refusal(intent.address, "value_channel_unavailable")
    if data_type == _BOOLEAN_DATA_TYPE:
        token = _boolean_token(value)
        if token is None:
            return _value_refusal(intent.address, "not_a_boolean")
        state.withdraw(casilla_id)
        state.decimal_casilla_inputs[casilla_id] = token
    elif data_type in _DECIMAL_CHANNEL_DATA_TYPES:
        amount = _canonical_decimal_value(value)
        if amount is None:
            return _value_refusal(intent.address, "not_a_number")
        state.withdraw(casilla_id)
        state.decimal_casilla_inputs[casilla_id] = canonical_decimal_string(amount)
    else:
        if not isinstance(value, str):
            return _value_refusal(intent.address, "not_text")
        state.withdraw(casilla_id)
        state.text_casilla_inputs[casilla_id] = value.strip()
    state.cleared_casilla_ids.discard(casilla_id)
    return None


def _source_fed_clear_refusal(address: ModeloEditScalarAddressV1) -> ModeloEditExecutionNoEffectV1:
    return _domain_refusal(
        ModeloEditRefusalCode.DISALLOWED_INTENT,
        address=address,
        facts=("source_fed_casilla",),
        condition="restore the source value instead of clearing a casilla a source feeds",
    )


def _apply_scalar_intents(
    state: _OperatorState,
    submission: ModeloEditSubmissionV1,
    *,
    head: CalculationRevision | None,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Apply every scalar intent to the operator state, refusing the first invalid one."""
    for intent in submission.scalar_intents:
        casilla_id = intent.address.casilla_id
        if intent.kind is ModeloEditScalarIntentKind.SET_TYPED_VALUE:
            entry = writable_scalar_entry(submission.baseline, casilla_id)
            if entry is None:
                return _value_refusal(intent.address, "address_not_writable")
            refusal = _apply_set_scalar(state, intent, data_type=str(entry.data_type))
            if refusal is not None:
                return refusal
        elif intent.kind is ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE:
            # A value in the head's merged inputs that the operator did not
            # author came from a source; clearing it would contradict it.
            if (
                not state.operator_sets(casilla_id)
                and head is not None
                and casilla_id in head.input_values_by_casilla_id
            ):
                return _source_fed_clear_refusal(intent.address)
            state.withdraw(casilla_id)
            state.cleared_casilla_ids.add(casilla_id)
        else:
            state.withdraw(casilla_id)
            state.cleared_casilla_ids.discard(casilla_id)
    return None


def _operator_binding_value(
    intent: ModeloBindingEditIntentV1,
    *,
    revision: ModeloRevision,
) -> str | ModeloEditExecutionNoEffectV1:
    """Canonicalise one SET override for the channel its binding declares."""
    binding_id = intent.address.binding_id
    value = intent.value
    if binding_id in revision_date_binding_ids(revision):
        return _value_refusal(intent.address, "value_channel_unavailable")
    if binding_id in enum_consumed_binding_ids(revision):
        if not isinstance(value, str) or not value.strip():
            return _value_refusal(intent.address, "not_a_choice")
        return value.strip()
    token = _boolean_token(value) if isinstance(value, bool) else None
    if token is not None:
        return token
    amount = _canonical_decimal_value(value)
    if amount is None:
        return _value_refusal(intent.address, "not_a_number")
    return canonical_decimal_string(amount)


def _apply_binding_intents(
    state: _OperatorState,
    submission: ModeloEditSubmissionV1,
    *,
    revision: ModeloRevision,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Apply every binding intent to the operator state, refusing the first invalid one."""
    for intent in submission.binding_intents:
        binding_id = intent.address.binding_id
        if intent.kind is ModeloEditBindingIntentKind.REMOVE_OVERRIDE:
            state.binding_overrides.pop(binding_id, None)
            continue
        value = _operator_binding_value(intent, revision=revision)
        if isinstance(value, ModeloEditExecutionNoEffectV1):
            return value
        state.binding_overrides[binding_id] = value
    return None


def _refuse_unaddressable_intents(submission: ModeloEditSubmissionV1) -> ModeloEditExecutionNoEffectV1 | None:
    """Refuse, before any catalogue read, every intent the surface or executor cannot reach."""
    if submission.mutation_family is not ModeloEditMutationFamily.CALCULATE:
        return _unsupported_intent_refusal(ModeloEditUnsupportedIntentReason.RECALCULATE_NOT_YET_WIRED)
    if submission.row_intents:
        first_row = submission.row_intents[0]
        return _unsupported_intent_refusal(_ROW_UNSUPPORTED_REASON[first_row.kind], address=first_row.address)
    baseline = submission.baseline
    for intent in submission.scalar_intents:
        refusal = validate_scalar_intent(baseline, intent.address, intent.kind)
        if refusal is not None:
            return ModeloEditExecutionNoEffectV1(refusal=refusal)
    for binding_intent in submission.binding_intents:
        refusal = validate_binding_intent(baseline, binding_intent.address, binding_intent.kind)
        if refusal is not None:
            return ModeloEditExecutionNoEffectV1(refusal=refusal)
    return None


def _detail_row_natural_key_refusal(address: ModeloEditAddressV1) -> ModeloEditExecutionNoEffectV1:
    return _domain_refusal(
        ModeloEditRefusalCode.DISALLOWED_INTENT,
        address=address,
        condition="address only a detail row currently declared under this natural key",
    )


def _detail_rows_by_kind(
    current_detail_rows: tuple[ModeloDetailRow, ...],
) -> dict[str, list[ModeloDetailRow]]:
    """Group the current rows without changing their within-kind order."""
    by_kind: dict[str, list[ModeloDetailRow]] = {}
    for row in current_detail_rows:
        by_kind.setdefault(row.row_type, []).append(row)
    return by_kind


def _apply_detail_row_intent(
    by_kind: dict[str, list[ModeloDetailRow]],
    intent: ModeloDetailRowEditIntentV1,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Apply one natural-key row intent, returning its typed refusal if invalid."""
    kind = intent.address.detail_row_kind
    rows = by_kind.setdefault(kind, [])
    keys = [detail_row_natural_key(row) for row in rows]
    if intent.kind is ModeloEditDetailRowIntentKind.ADD_ROW:
        if intent.row is None:
            return _detail_row_natural_key_refusal(intent.address)
        rows.append(intent.row)
    elif intent.kind is ModeloEditDetailRowIntentKind.UPDATE_ROW:
        if intent.row is None:
            return _detail_row_natural_key_refusal(intent.address)
        if intent.address.natural_key not in keys:
            return _detail_row_natural_key_refusal(intent.address)
        rows[keys.index(intent.address.natural_key)] = intent.row
    else:
        if intent.address.natural_key not in keys:
            return _detail_row_natural_key_refusal(intent.address)
        rows.pop(keys.index(intent.address.natural_key))
    return None


def _reconstruct_detail_rows(
    *,
    current_detail_rows: tuple[ModeloDetailRow, ...],
    detail_row_intents: tuple[ModeloDetailRowEditIntentV1, ...],
) -> tuple[ModeloDetailRow, ...] | ModeloEditExecutionNoEffectV1:
    """Rebuild the complete ``detail_rows`` tuple from the head's rows and the row intents.

    Rows are grouped by ``row_type`` and addressed by their own natural key,
    never position or a minted identity. A row absent from the result is simply
    not declared. No intent reorders a row: the revision's content address is
    order-blind, so a pure reorder would be absorbed as the same revision.
    """
    by_kind = _detail_rows_by_kind(current_detail_rows)
    for intent in detail_row_intents:
        refusal = _apply_detail_row_intent(by_kind, intent)
        if refusal is not None:
            return refusal
    result: list[ModeloDetailRow] = []
    for kind in sorted(by_kind):
        result.extend(by_kind[kind])
    return tuple(result)


def _capture_edit_receipt(
    calculation_revision_id: str,
    bucket_event_id: str | None,
    *,
    request: ModeloEditApplyRequestV1,
    submission: ModeloEditSubmissionV1,
    receipt_repository: ModeloEditReceiptRepositoryPort,
    now: datetime,
    result_destination: str,
    captured_receipt: list[ModeloEditMutationResultReceiptV1],
) -> tuple[SecureObjectWrite, ...]:
    """Build and capture the safe receipt co-committed with the calculation."""
    baseline = submission.baseline
    receipt_id = content_hash_hex(
        {
            "operation_id": request.operation_id,
            "baseline_id": baseline.baseline_id,
            "calculation_revision_id": calculation_revision_id,
            "bucket_event_id": bucket_event_id or "",
        },
    )
    receipt = ModeloEditMutationResultReceiptV1(
        receipt_id=receipt_id,
        operation_id=request.operation_id,
        mutation_family=submission.mutation_family,
        baseline_id=baseline.baseline_id,
        work_unit_id=baseline.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_event_id=bucket_event_id,
        committed_at=now,
        result_destination=result_destination,
    )
    captured_receipt.append(receipt)
    return (receipt_repository.to_secure_object_write(receipt),)


def _pre_effect_refusal(error: BaseException) -> ModeloEditExecutionNoEffectV1:
    """Translate a precondition the calculation refused before persisting into a typed refusal."""
    code = get_registered_error_code(error).code
    if isinstance(error, ModeloClearedCasillaSourceFedError):
        return _domain_refusal(
            ModeloEditRefusalCode.DISALLOWED_INTENT,
            facts=("source_fed_casilla", code),
            condition="restore the source value instead of clearing a casilla a source feeds",
        )
    return _domain_refusal(
        ModeloEditRefusalCode.VALIDATION_FAILED,
        facts=(code,),
        condition="resolve the calculation precondition the edit could not satisfy, then resubmit",
    )


@dataclass(frozen=True, slots=True)
class _PreparedEdit:
    """Everything the calculation needs, assembled before the effect."""

    context: CalculationCallerContext
    layer: CalculationOperatorLayer
    cleared_casilla_ids: tuple[CasillaId, ...]
    detail_rows: tuple[ModeloDetailRow, ...]
    revision: ModeloRevision


def _execute_modelo_edit(
    *,
    request: ModeloEditApplyRequestV1,
    prepared: _PreparedEdit,
    ports: CalculationActionPorts,
    receipt_repository: ModeloEditReceiptRepositoryPort,
    now: datetime,
    result_destination: str,
) -> ModeloEditExecutionResultV1:
    """Run the canonical calculation writer on the edited caller context and retain its receipt."""
    submission = request.submission
    captured_receipt: list[ModeloEditMutationResultReceiptV1] = []

    def _co_commit_receipt(calculation_revision_id: str, bucket_event_id: str | None) -> tuple[SecureObjectWrite, ...]:
        return _capture_edit_receipt(
            calculation_revision_id,
            bucket_event_id,
            request=request,
            submission=submission,
            receipt_repository=receipt_repository,
            now=now,
            result_destination=result_destination,
            captured_receipt=captured_receipt,
        )

    try:
        replay = caller_context_calculation_inputs(
            CalculationCallerContext(
                operator_layer=prepared.layer,
                cleared_casilla_ids=prepared.cleared_casilla_ids,
                detail_rows=prepared.detail_rows,
                filing_instance_evidence=prepared.context.filing_instance_evidence,
                m210_official_tipo_renta_code=prepared.context.m210_official_tipo_renta_code,
                m210_gross_income_source_mode=prepared.context.m210_gross_income_source_mode,
                borrador_snapshot_id=prepared.context.borrador_snapshot_id,
            ),
            revision=prepared.revision,
        )
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            submission.baseline.work_unit_id,
            actor=_RESPONSIBLE_OWNER,
            casilla_inputs=replay.casilla_inputs,
            text_casilla_inputs=replay.text_casilla_inputs,
            cleared_casilla_ids=replay.cleared_casilla_ids,
            record_operator_layer=True,
            binding_values=replay.binding_values,
            enum_binding_values=replay.enum_binding_values,
            detail_rows=replay.detail_rows,
            filing_instance_evidence=replay.filing_instance_evidence,
            m210_official_tipo_renta_code=replay.m210_official_tipo_renta_code,
            m210_gross_income_source_mode=replay.m210_gross_income_source_mode,
            borrador_snapshot_id=replay.borrador_snapshot_id,
            ports=ports,
            clock=now,
            additional_secure_object_writes_for_revision=_co_commit_receipt,
        )
    except _PRE_EFFECT_REFUSALS as refused:
        if captured_receipt:
            raise
        return _pre_effect_refusal(refused)
    if not captured_receipt:
        raise ModeloError("the calculation boundary resolved no revision id for the applied edit")
    return ModeloEditExecutionUpdatedV1(receipt=captured_receipt[0])


def _prepare_edit(
    submission: ModeloEditSubmissionV1,
    *,
    head: CalculationRevision | None,
    operation: PinnedAuthorityOperation,
) -> _PreparedEdit | ModeloEditExecutionNoEffectV1:
    """Apply the intents to the head's caller context under the baseline's authority revision."""
    baseline = submission.baseline
    try:
        if head is not None:
            require_calculation_revision_coordinates_current(head, operation=operation)
        snapshot = operation.snapshot(
            str(baseline.modelo),
            filing_year=baseline.filing_year,
            period=baseline.period.registry_token,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
    except _PRE_EFFECT_REFUSALS as refused:
        return _pre_effect_refusal(refused)
    if snapshot.revision.id != baseline.law_selected_revision_id:
        return _domain_refusal(
            ModeloEditRefusalCode.REGISTRY_SCHEMA_CONFLICT,
            facts=("law_selected_revision_id",),
            condition="refresh the edit baseline against its current authority revision",
        )
    context = caller_context_of(head)
    state = _OperatorState.from_context(context)
    refusal = _apply_scalar_intents(state, submission, head=head) or _apply_binding_intents(
        state, submission, revision=snapshot.revision
    )
    if refusal is not None:
        return refusal
    detail_rows = _reconstruct_detail_rows(
        current_detail_rows=context.detail_rows,
        detail_row_intents=submission.detail_row_intents,
    )
    if isinstance(detail_rows, ModeloEditExecutionNoEffectV1):
        return detail_rows
    return _PreparedEdit(
        context=context,
        layer=state.layer(),
        cleared_casilla_ids=tuple(sorted(state.cleared_casilla_ids)),
        detail_rows=detail_rows,
        revision=snapshot.revision,
    )


def apply_modelo_edit(
    request: ModeloEditApplyRequestV1,
    *,
    ports: CalculationActionPorts,
    receipt_repository: ModeloEditReceiptRepositoryPort,
    now: datetime,
    result_destination: str,
) -> ModeloEditExecutionResultV1:
    """Recheck the baseline at the guarded commit point and execute a CALCULATE edit.

    Synchronous and blocking: the enrolled operation executor runs it off the
    event loop. Delegates formula evaluation and persistence to the canonical
    calculation boundary and single-writer primitive; this function adds the
    commit-point recheck, the caller-context replay, the intent application
    and the atomically co-committed result receipt.
    """
    submission = request.submission
    refusal = _refuse_unaddressable_intents(submission)
    if refusal is not None:
        return refusal
    baseline = submission.baseline
    # Immediately before effect: revision-load the catalogues and recheck
    # every baseline coordinate. No re-read happens between this check and
    # the guarded commit below other than the calculation boundary's own
    # internal, independently CAS-guarded reads.
    work_catalogue = ports.work_unit_repository.load()
    calculation_catalogue = ports.calculation_repository.load()
    stale = reconfirm_modelo_edit_baseline(
        baseline, work_catalogue=work_catalogue, calculation_catalogue=calculation_catalogue
    )
    if stale is not None:
        return ModeloEditExecutionNoEffectV1(refusal=stale)
    head = (
        calculation_catalogue.get(baseline.current_calculation_revision_id)
        if baseline.current_calculation_revision_id is not None
        else None
    )
    prepared = _prepare_edit(submission, head=head, operation=ports.operation)
    if isinstance(prepared, ModeloEditExecutionNoEffectV1):
        return prepared
    return _execute_modelo_edit(
        request=request,
        prepared=prepared,
        ports=ports,
        receipt_repository=receipt_repository,
        now=now,
        result_destination=result_destination,
    )


__all__ = ["apply_modelo_edit"]
