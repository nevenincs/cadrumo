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

A withdrawal that leaves a calculation-refusing carry unstated does not
recalculate: :mod:`.edit_carry_withdrawal` returns the work unit to no current
calculation, or refuses when that would discard other values or touch a
declaration recorded as filed.

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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Final

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
from ...domain.modelos.calculation_revision_operator_layer import (
    ATTESTED_ZERO,
    AttestedSource,
    CalculationOperatorLayer,
    ValueAttestation,
)
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue
from ..calculations.cross_period_clean_state import attestable_carry_sources
from ..calculations.cross_period_models import CrossPeriodDependencyRequirement
from ..operator_actions.models import ActionReference
from .action_errors import ModeloClearedCasillaSourceFedError
from .calculation_action_ports import CalculationActionPorts
from .calculation_bucket_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from .calculation_revision_gate import require_calculation_revision_coordinates_current
from .caller_context import CalculationCallerContext, caller_context_calculation_inputs, caller_context_of
from .edit_carry_withdrawal import (
    calculation_refusing_carry_bindings,
    carry_withdrawal_block,
    is_carry_withdrawal,
    withdraw_current_calculation,
)
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
from .edit_services import (
    RESPONSIBLE_OWNER,
    detail_row_natural_key,
    reconfirm_modelo_edit_baseline,
    validate_binding_intent,
    validate_scalar_intent,
)
from .edit_value_grammar import ModeloEditValueChannel, ModeloEditValueGrammarV1
from .refusal_door_verdicts import caller_defect_verdict
from .work_missing_input import ModeloPriorCarryAbsenceUnstatedError, ModeloPriorPeriodUnfiledError

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

#: The door an edit refused for an unstated earlier-ejercicio carry offers: state the carries.
PRIOR_CARRIES_ACTION: Final[ActionReference] = ActionReference(action_id="operator.modelo.work.attest_prior_carries")


def _unsupported_intent_refusal(
    reason: ModeloEditUnsupportedIntentReason, *, address: ModeloEditAddressV1 | None = None
) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(
        refusal=ModeloEditUnsupportedIntentRefusalV1(
            address=address,
            reason=reason,
            responsible_owner=RESPONSIBLE_OWNER,
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
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition=condition,
        )
    )


def _parse_refusal(outcome: ModeloEditParseRefusalV1) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(refusal=outcome)


def channel_value(
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
    attested_binding_ids: set[BindingId] = field(default_factory=set)
    value_attestations: dict[BindingId, ValueAttestation] = field(default_factory=dict)

    @classmethod
    def from_context(cls, context: CalculationCallerContext) -> _OperatorState:
        layer = context.known_operator_layer
        return cls(
            decimal_casilla_inputs=dict(layer.decimal_casilla_inputs),
            text_casilla_inputs=dict(layer.text_casilla_inputs),
            binding_overrides=dict(layer.binding_overrides),
            cleared_casilla_ids=set(context.cleared_casilla_ids),
            attested_binding_ids=set(layer.attested_binding_ids),
            value_attestations=dict(layer.value_attestations),
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
            attested_binding_ids=tuple(sorted(self.attested_binding_ids)),
            value_attestations=dict(sorted(self.value_attestations.items())),
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
    value = channel_value(intent.value, address=intent.address, grammar=grammar, tax_id_format=tax_id_format)
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


def _attest_prior_value(
    state: _OperatorState,
    intent: ModeloBindingEditIntentV1,
    *,
    sources: tuple[CrossPeriodDependencyRequirement, ...] | None,
    grammar: ModeloEditValueGrammarV1 | None,
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditExecutionNoEffectV1 | None:
    """Record the operator's stated figure for a scalar carry whose earlier filings the application does not hold.

    The value takes the same path as an override; the operator layer also names
    every earlier filing it stands in for. A binding with a held source, or a
    row-set binding, is not attestable, however the baseline came to offer it.
    """
    binding_id = intent.address.binding_id
    if sources is None or len(sources) == 0 or grammar is None or grammar.channel is not ModeloEditValueChannel.DECIMAL:
        return _domain_refusal(
            ModeloEditRefusalCode.DISALLOWED_INTENT,
            address=intent.address,
            facts=("upstream_source_held",),
            condition="state a figure only for a carry the application holds no earlier source for",
        )
    value = channel_value(intent.value, address=intent.address, grammar=grammar, tax_id_format=tax_id_format)
    if isinstance(value, ModeloEditParseRefusalV1):
        return _parse_refusal(value)
    state.binding_overrides[binding_id] = value
    first, *rest = sources
    state.value_attestations[binding_id] = ValueAttestation(
        source_modelo=first.source_modelo,
        source_filing_year=first.filing_year,
        source_period=first.period.registry_token,
        further_sources=tuple(
            AttestedSource(
                source_modelo=item.source_modelo,
                source_filing_year=item.filing_year,
                source_period=item.period.registry_token,
            )
            for item in rest
        ),
    )
    return None


def _apply_binding_intents(
    state: _OperatorState,
    submission: ModeloEditSubmissionV1,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
    attestable_sources: Mapping[BindingId, tuple[CrossPeriodDependencyRequirement, ...]],
) -> ModeloEditExecutionNoEffectV1 | None:
    """Apply every binding intent to the operator state, refusing the first invalid one."""
    for intent in submission.binding_intents:
        binding_id = intent.address.binding_id
        # Whatever the intent, an earlier statement on the binding gives way to it.
        state.attested_binding_ids.discard(binding_id)
        state.value_attestations.pop(binding_id, None)
        if intent.kind is ModeloEditBindingIntentKind.REMOVE_OVERRIDE:
            state.binding_overrides.pop(binding_id, None)
            continue
        if intent.kind is ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT:
            state.binding_overrides[binding_id] = ATTESTED_ZERO
            state.attested_binding_ids.add(binding_id)
            continue
        grammar = modelo_edit_address_grammar(submission.baseline, intent.address)
        if intent.kind is ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE:
            refusal = _attest_prior_value(
                state,
                intent,
                sources=attestable_sources.get(binding_id),
                grammar=grammar,
                tax_id_format=tax_id_format,
            )
            if refusal is not None:
                return refusal
            continue
        if grammar is None:
            return _parse_refusal(
                ModeloEditParseRefusalV1(address=intent.address, reason=ModeloEditParseReason.ADDRESS_NOT_WRITABLE)
            )
        value = channel_value(intent.value, address=intent.address, grammar=grammar, tax_id_format=tax_id_format)
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


def reconstruct_detail_rows(
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
    calculation_revision_id: str | None,
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


def _unresolved_binding_edit_refusal(
    context: Mapping[str, object], revision: ModeloRevision, code: str
) -> ModeloEditExecutionNoEffectV1 | None:
    """Validate the closed missing-binding producer's context against the actual revision."""
    # Only this closed producer identifies an unresolved bound source.
    # Its context is validated against the actual revision, never parsed
    # from the exception's sentence or rendered directly to the filer.
    casilla = next((item for item in revision.casillas if item.id == context.get("casilla_id")), None)
    raw = context.get("binding_id")
    binding_ids = tuple(raw.split(",")) if isinstance(raw, str) else ()
    declared = {binding.id for binding in revision.bindings}
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
    return None


def _first_box_fed_by(raw: object, revision: ModeloRevision) -> Mapping[str, object] | None:
    """Name the first box, in the revision's order, that the refused carries feed, with the carries it reads.

    An earlier return that does not show the boxes a carry reads refuses every
    such carry at once, naming them by binding; the filer answers them in the
    boxes they feed, so the refusal is addressed to the first of those.
    """
    if not isinstance(raw, str):
        return None
    refused = set(raw.split(","))
    for casilla in revision.casillas:
        fed = tuple(binding_id for binding_id in bound_casilla_binding_ids(casilla) if binding_id in refused)
        if fed:
            return {"casilla_id": casilla.id, "binding_id": ",".join(fed)}
    return None


def _unresolved_source_context(error: BaseException, revision: ModeloRevision) -> Mapping[str, object] | None:
    """The box and bindings of a calculation refused for a source it could not resolve, if it was.

    An unstated carry from an earlier ejercicio is addressed to the first box
    its still open carries feed, as an earlier return that cannot show them is,
    so the refused Apply names a carry the filer has not answered yet; a carry
    waiting on an unfiled earlier period is addressed to the box it feeds.
    """
    if isinstance(error, ModeloPriorCarryAbsenceUnstatedError):
        return _first_box_fed_by(",".join(error.open_carry_ids), revision)
    if isinstance(error, ModeloPriorPeriodUnfiledError):
        return _first_box_fed_by(error.binding_id, revision)
    if not isinstance(error, RegistryValidationError) or error.context is None:
        return None
    if error.translated_message == "errors.calc.bound_casilla_binding_value_missing":
        return error.context
    if error.translated_message == "errors.calc.previous_filing_casillas_unobserved":
        return _first_box_fed_by(error.context.get("binding_ids"), revision)
    return None


def _with_prior_carry_door(
    outcome: ModeloEditExecutionNoEffectV1, error: BaseException
) -> ModeloEditExecutionNoEffectV1:
    """Name the family and the statement door on an edit refused for an unstated carry; others pass unchanged."""
    refusal = outcome.refusal
    if not isinstance(error, ModeloPriorCarryAbsenceUnstatedError) or not isinstance(
        refusal, ModeloEditDomainRefusalV1
    ):
        return outcome
    return ModeloEditExecutionNoEffectV1(
        refusal=refusal.model_copy(
            update={"facts": (*refusal.facts, error.family.value), "recovery_action": PRIOR_CARRIES_ACTION}
        )
    )


def pre_effect_refusal(
    error: BaseException, *, revision: ModeloRevision | None = None
) -> ModeloEditExecutionNoEffectV1:
    """Translate a precondition the calculation refused before persisting into a typed refusal.

    ``revision`` is a :class:`ModeloRevision`.
    """
    code = get_registered_error_code(error).code
    if revision is not None:
        context = _unresolved_source_context(error, revision)
        refusal = None if context is None else _unresolved_binding_edit_refusal(context, revision, code)
        if refusal is not None:
            return _with_prior_carry_door(refusal, error)
    if isinstance(error, ModeloPriorCarryAbsenceUnstatedError):
        return _with_prior_carry_door(
            _domain_refusal(
                ModeloEditRefusalCode.VALIDATION_FAILED,
                facts=(code,),
                condition="state the carries from earlier ejercicios before the declaration is calculated",
            ),
            error,
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
    head: CalculationRevision | None
    work_unit: WorkUnit | None


def _withdraw_carry_statement(
    submission: ModeloEditSubmissionV1,
    *,
    prepared: _PreparedEdit,
    ports: CalculationActionPorts,
    now: datetime,
    co_commit: Callable[[], tuple[SecureObjectWrite, ...]],
) -> ModeloEditExecutionNoEffectV1 | None:
    """Settle a withdrawal that left a calculation-refusing carry unstated, returning its refusal if refused.

    ``None`` when the work unit returned to no current calculation, which
    ``co_commit`` recorded, or when the edit is no such withdrawal.

    It is one when the submission only withdraws statements, withdraws one of
    such a carry, and the head holds such a statement. The work unit then
    returns to no current calculation, or the withdrawal is refused when the
    declaration is recorded as filed or the head holds other values of the
    filer's.
    """
    head, work_unit = prepared.head, prepared.work_unit
    carry_bindings = calculation_refusing_carry_bindings(prepared.revision)
    if (
        head is None
        or work_unit is None
        or not is_carry_withdrawal(submission, carry_bindings)
        or head.operator_layer is None
        or not set(head.operator_layer.attested_binding_ids) & carry_bindings
    ):
        return None
    block = carry_withdrawal_block(head, work_unit, carry_bindings)
    if block is not None:
        return _domain_refusal(
            ModeloEditRefusalCode.DISALLOWED_INTENT,
            facts=(block.value,),
            condition="replace the statement with the carried figures, or amend a declaration recorded as filed",
        )
    stale = withdraw_current_calculation(
        submission.baseline,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
        operation=ports.operation,
        now=now,
        co_commit=co_commit,
    )
    if stale is not None:
        return ModeloEditExecutionNoEffectV1(refusal=stale)
    return None


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

    def _co_commit_receipt(
        calculation_revision_id: str | None, bucket_event_id: str | None
    ) -> tuple[SecureObjectWrite, ...]:
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
            actor=RESPONSIBLE_OWNER,
            casilla_inputs=replay.casilla_inputs,
            text_casilla_inputs=replay.text_casilla_inputs,
            cleared_casilla_ids=replay.cleared_casilla_ids,
            record_operator_layer=True,
            attested_binding_ids=replay.attested_binding_ids,
            value_attestations=replay.value_attestations,
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
        if isinstance(refused, ModeloPriorCarryAbsenceUnstatedError):
            withdrawn = _withdraw_carry_statement(
                submission,
                prepared=prepared,
                ports=ports,
                now=now,
                co_commit=lambda: _co_commit_receipt(None, None),
            )
            if withdrawn is not None:
                return withdrawn
            if captured_receipt:
                return ModeloEditExecutionUpdatedV1(receipt=captured_receipt[0])
        return pre_effect_refusal(refused, revision=prepared.revision)
    if not captured_receipt:
        raise ModeloError(
            "the calculation boundary resolved no revision id for the applied edit",
            translated_message="application.modelo.errors.edit_revision_id_unresolved",
            precondition_verdict=caller_defect_verdict("edit_calculation_revision_id"),
        )
    return ModeloEditExecutionUpdatedV1(receipt=captured_receipt[0])


def _prepare_edit(
    submission: ModeloEditSubmissionV1,
    *,
    head: CalculationRevision | None,
    operation: PinnedAuthorityOperation,
    ports: CalculationActionPorts,
    work_catalogue: WorkUnitCatalogue,
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
        return pre_effect_refusal(refused)
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
    ) or _apply_binding_intents(
        state,
        submission,
        tax_id_format=tax_id_format,
        attestable_sources=attestable_carry_sources(
            snapshot,
            operation=operation,
            observation_repository=ports.observation_repository,
            filing_catalogue=ports.filing_repository.load(),
            work_catalogue=work_catalogue,
        ),
    )
    if refusal is not None:
        return refusal
    detail_rows = reconstruct_detail_rows(
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
        head=head,
        work_unit=work_catalogue.get(baseline.work_unit_id),
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
    calculation_catalogue = ports.calculation_repository.load(operation=ports.operation)
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
    prepared = _prepare_edit(
        submission, head=head, operation=ports.operation, ports=ports, work_catalogue=work_catalogue
    )
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
