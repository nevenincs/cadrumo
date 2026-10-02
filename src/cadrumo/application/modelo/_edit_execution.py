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

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.errors.error_codes import get_registered_error_code
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import content_hash_hex
from ...core.identity.documents import SpanishTaxIdFormat
from ...core.secure_object_write import SecureObjectWrite
from ...domain.calculations.registry.binding_targets import bound_casilla_binding_ids
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
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
    ModeloDetailRowEditIntentV1,
    ModeloEditAddressV1,
    ModeloEditApplyRequestV1,
    ModeloEditBindingIntentKind,
    ModeloEditDetailRowIntentKind,
    ModeloEditDomainRefusalV1,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionResultV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditParseReason,
    ModeloEditParseRefusalV1,
    ModeloEditRefusalCode,
    ModeloEditRowIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditUnsupportedIntentReason,
    ModeloEditUnsupportedIntentRefusalV1,
    ModeloEditValueAddressV1,
    ModeloScalarEditIntentV1,
)
from .edit_parsing import modelo_edit_address_grammar, validate_modelo_edit_value
from .edit_receipt_ports import ModeloEditReceiptRepositoryPort
from .edit_services import RESPONSIBLE_OWNER as _RESPONSIBLE_OWNER
from .edit_services import (
    detail_row_natural_key,
    reconfirm_modelo_edit_baseline,
    validate_binding_intent,
    validate_scalar_intent,
)
from .edit_value_grammar import ModeloEditValueChannel, ModeloEditValueGrammarV1

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_UNSUPPORTED_RECONSIDERATION = "resubmit without this intent once its capability lands, or split the submission"

_ROW_UNSUPPORTED_REASON: dict[ModeloEditRowIntentKind, ModeloEditUnsupportedIntentReason] = {
    ModeloEditRowIntentKind.ADD_ROW: ModeloEditUnsupportedIntentReason.ADD_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.UPDATE_ROW: ModeloEditUnsupportedIntentReason.UPDATE_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.DELETE_ROW: ModeloEditUnsupportedIntentReason.DELETE_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.MOVE_ROW: ModeloEditUnsupportedIntentReason.MOVE_ROW_NOT_YET_WIRED,
}

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
    evidence: tuple[str, ...] = (),
) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(
        refusal=ModeloEditDomainRefusalV1(
            code=code,
            address=address,
            facts=facts,
            evidence=evidence,
            responsible_owner=_RESPONSIBLE_OWNER,
            reconsideration_condition=condition,
        )
    )


def _parse_refusal(outcome: ModeloEditParseRefusalV1) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(refusal=outcome)


def _channel_value(
    value: ModeloScalar,
    *,
    address: ModeloEditValueAddressV1,
    grammar: ModeloEditValueGrammarV1,
    tax_id_format: SpanishTaxIdFormat | None,
) -> str | ModeloEditParseRefusalV1:
    """Re-apply the parser's typed validation and render the value for its engine channel.

    A boolean travels the decimal channel encoded 0 / 1; a decimal as its
    canonical string; text as the canonical text the registry validator
    returned. The executor never trusts that a frontend ran the parser.
    """
    outcome = validate_modelo_edit_value(value, address=address, grammar=grammar, tax_id_format=tax_id_format)
    if isinstance(outcome, ModeloEditParseRefusalV1):
        return outcome
    parsed = outcome.value
    if isinstance(parsed, bool):
        return "1" if parsed else "0"
    if isinstance(parsed, Decimal):
        return canonical_decimal_string(parsed)
    return str(parsed)


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


def _apply_set_scalar(
    state: _OperatorState,
    intent: ModeloScalarEditIntentV1,
    *,
    grammar: ModeloEditValueGrammarV1,
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Validate one SET value and place it on the channel its grammar reaches."""
    casilla_id = intent.address.casilla_id
    value = _channel_value(intent.value, address=intent.address, grammar=grammar, tax_id_format=tax_id_format)
    if isinstance(value, ModeloEditParseRefusalV1):
        return _parse_refusal(value)
    state.withdraw(casilla_id)
    if grammar.channel is ModeloEditValueChannel.DECIMAL:
        state.decimal_casilla_inputs[casilla_id] = value
    else:
        state.text_casilla_inputs[casilla_id] = value
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
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Apply every scalar intent to the operator state, refusing the first invalid one."""
    for intent in submission.scalar_intents:
        casilla_id = intent.address.casilla_id
        if intent.kind is ModeloEditScalarIntentKind.SET_TYPED_VALUE:
            grammar = modelo_edit_address_grammar(submission.baseline, intent.address)
            if grammar is None:
                return _parse_refusal(
                    ModeloEditParseRefusalV1(address=intent.address, reason=ModeloEditParseReason.ADDRESS_NOT_WRITABLE)
                )
            refusal = _apply_set_scalar(state, intent, grammar=grammar, tax_id_format=tax_id_format)
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


def _apply_binding_intents(
    state: _OperatorState,
    submission: ModeloEditSubmissionV1,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Apply every binding intent to the operator state, refusing the first invalid one."""
    for intent in submission.binding_intents:
        binding_id = intent.address.binding_id
        if intent.kind is ModeloEditBindingIntentKind.REMOVE_OVERRIDE:
            state.binding_overrides.pop(binding_id, None)
            continue
        grammar = modelo_edit_address_grammar(submission.baseline, intent.address)
        if grammar is None:
            return _parse_refusal(
                ModeloEditParseRefusalV1(address=intent.address, reason=ModeloEditParseReason.ADDRESS_NOT_WRITABLE)
            )
        value = _channel_value(intent.value, address=intent.address, grammar=grammar, tax_id_format=tax_id_format)
        if isinstance(value, ModeloEditParseRefusalV1):
            return _parse_refusal(value)
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


def _pre_effect_refusal(
    error: BaseException, *, revision: ModeloRevision | None = None
) -> ModeloEditExecutionNoEffectV1:
    """Translate a precondition the calculation refused before persisting into a typed refusal."""
    code = get_registered_error_code(error).code
    if (
        isinstance(error, RegistryValidationError)
        and error.translated_message == "errors.calc.bound_casilla_binding_value_missing"
        and revision is not None
        and error.context is not None
    ):
        # Only this closed producer identifies an unresolved bound source.
        # Its context is validated against the actual revision, never parsed
        # from the exception's sentence or rendered directly to the filer.
        casilla = next((item for item in revision.casillas if item.id == error.context.get("casilla_id")), None)
        raw = error.context.get("binding_id")
        binding_ids = tuple(raw.split(",")) if isinstance(raw, str) else ()
        declared = {str(binding.id) for binding in revision.bindings}
        if (
            casilla is not None
            and 0 < len(binding_ids) <= 16
            and len(set(binding_ids)) == len(binding_ids)
            and set(binding_ids) <= declared
            and set(binding_ids) <= set(bound_casilla_binding_ids(casilla))
        ):
            return _domain_refusal(
                ModeloEditRefusalCode.VALIDATION_FAILED,
                address=ModeloEditScalarAddressV1(casilla_id=casilla.id),
                facts=(code, "calculation_source_unresolved"),
                evidence=binding_ids,
                condition="inspect the source required by this failed recalculation before resubmitting",
            )
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
        return _pre_effect_refusal(refused, revision=prepared.revision)
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
    tax_id_format = runtime_tax_id_format(authority=operation)
    refusal = _apply_scalar_intents(
        state, submission, head=head, tax_id_format=tax_id_format
    ) or _apply_binding_intents(state, submission, tax_id_format=tax_id_format)
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
