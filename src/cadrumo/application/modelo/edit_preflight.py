"""In-process preflight of a Modelo edit submission, naming the address of every finding.

A settled edit operation carries only its refusal family, so it cannot say
which casilla failed. Preflight runs before the operation, in the frontend's
own process, against the same baseline, typed validation and current head the
executor will use, and returns addressable findings:

* ``error`` findings are the ones the executor would refuse: a value its
  grammar refuses, an intent the surface does not admit, or a clear of a
  casilla a source feeds (restore it instead);
* ``warning`` findings are review material: an operator value that will
  displace a source value, a required casilla left empty, and a head whose
  operator layer is unknown because it was stored before layers existed;
* ``info`` findings note a restore with nothing to restore.

A stale baseline returns the typed compare-and-swap refusal instead of
findings; a baseline that merely expired should be renewed first. A green
preflight is review material, never authority: execution repeats every check.
Findings carry codes, addresses and bounds, never a value.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.casilla_id import CasillaId
from ...core.identity.documents import SpanishTaxIdFormat
from ...domain.calculations.registry.ids import BindingId
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue
from .caller_context import caller_context_of
from .edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditFindingSeverity,
    ModeloEditFindingV1,
    ModeloEditParseRefusalV1,
    ModeloEditPreflightEvaluatedV1,
    ModeloEditPreflightResultV1,
    ModeloEditRefusedV1,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditWritableScalarSurfaceEntryV1,
    ModeloScalarEditIntentV1,
)
from .edit_parsing import modelo_edit_address_grammar, validate_modelo_edit_value
from .edit_services import reconfirm_modelo_edit_baseline, validate_binding_intent, validate_scalar_intent

INTENT_NOT_ADMITTED = "intent_not_admitted"
CLEAR_OF_SOURCE_FED_CASILLA = "clear_of_source_fed_casilla"
OVERRIDES_SOURCE_VALUE = "overrides_source_value"
REQUIRED_EMPTY = "required_empty"
OPERATOR_LAYER_UNKNOWN = "operator_layer_unknown"
NOTHING_TO_RESTORE = "nothing_to_restore"
VALUE_REFUSED_PREFIX = "value."
"""A refused value's finding code is this prefix plus its :class:`~.edit_models.ModeloEditParseReason`."""


@dataclass(frozen=True, slots=True)
class _Head:
    """What the current head says about each address, with the operator's own values set apart."""

    revision: CalculationRevision | None
    operator_casillas: frozenset[CasillaId]
    operator_bindings: frozenset[BindingId]
    layer_known: bool

    def source_feeds_casilla(self, casilla_id: CasillaId) -> bool:
        return (
            self.revision is not None
            and casilla_id in self.revision.input_values_by_casilla_id
            and casilla_id not in self.operator_casillas
        )

    def source_feeds_binding(self, binding_id: BindingId) -> bool:
        return (
            self.revision is not None
            and binding_id in self.revision.binding_overrides
            and binding_id not in self.operator_bindings
        )


def _finding(
    code: str,
    severity: ModeloEditFindingSeverity,
    address: ModeloEditAddressV1 | None = None,
    arguments: tuple[str, ...] = (),
) -> ModeloEditFindingV1:
    return ModeloEditFindingV1(code=code, severity=severity, address=address, message_arguments=arguments)


def _value_findings(
    intent: ModeloScalarEditIntentV1 | ModeloBindingEditIntentV1,
    submission: ModeloEditSubmissionV1,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
) -> list[ModeloEditFindingV1]:
    grammar = modelo_edit_address_grammar(submission.baseline, intent.address)
    if grammar is None:
        return [_finding(INTENT_NOT_ADMITTED, ModeloEditFindingSeverity.ERROR, intent.address)]
    outcome = validate_modelo_edit_value(
        intent.value, address=intent.address, grammar=grammar, tax_id_format=tax_id_format
    )
    if isinstance(outcome, ModeloEditParseRefusalV1):
        return [
            _finding(
                f"{VALUE_REFUSED_PREFIX}{outcome.reason.value}",
                ModeloEditFindingSeverity.ERROR,
                intent.address,
                outcome.message_arguments,
            )
        ]
    return []


def _scalar_findings(
    intent: ModeloScalarEditIntentV1,
    submission: ModeloEditSubmissionV1,
    head: _Head,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
) -> list[ModeloEditFindingV1]:
    if validate_scalar_intent(submission.baseline, intent.address, intent.kind) is not None:
        return [_finding(INTENT_NOT_ADMITTED, ModeloEditFindingSeverity.ERROR, intent.address)]
    casilla_id = intent.address.casilla_id
    if intent.kind is ModeloEditScalarIntentKind.SET_TYPED_VALUE:
        findings = _value_findings(intent, submission, tax_id_format=tax_id_format)
        if not findings and head.source_feeds_casilla(casilla_id):
            findings.append(_finding(OVERRIDES_SOURCE_VALUE, ModeloEditFindingSeverity.WARNING, intent.address))
        return findings
    if intent.kind is ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE:
        if head.source_feeds_casilla(casilla_id):
            return [_finding(CLEAR_OF_SOURCE_FED_CASILLA, ModeloEditFindingSeverity.ERROR, intent.address)]
        return []
    if head.layer_known and casilla_id not in head.operator_casillas:
        return [_finding(NOTHING_TO_RESTORE, ModeloEditFindingSeverity.INFO, intent.address)]
    return []


def _binding_findings(
    intent: ModeloBindingEditIntentV1,
    submission: ModeloEditSubmissionV1,
    head: _Head,
    *,
    tax_id_format: SpanishTaxIdFormat | None,
) -> list[ModeloEditFindingV1]:
    if validate_binding_intent(submission.baseline, intent.address, intent.kind) is not None:
        return [_finding(INTENT_NOT_ADMITTED, ModeloEditFindingSeverity.ERROR, intent.address)]
    binding_id = intent.address.binding_id
    if intent.kind is ModeloEditBindingIntentKind.REMOVE_OVERRIDE:
        if head.layer_known and binding_id not in head.operator_bindings:
            return [_finding(NOTHING_TO_RESTORE, ModeloEditFindingSeverity.INFO, intent.address)]
        return []
    findings = _value_findings(intent, submission, tax_id_format=tax_id_format)
    if not findings and head.source_feeds_binding(binding_id):
        findings.append(_finding(OVERRIDES_SOURCE_VALUE, ModeloEditFindingSeverity.WARNING, intent.address))
    return findings


def _required_empty_findings(submission: ModeloEditSubmissionV1, head: _Head) -> list[ModeloEditFindingV1]:
    """Name every required writable casilla that will hold no value once the submission applies."""
    named = {intent.address.casilla_id: intent.kind for intent in submission.scalar_intents}
    findings: list[ModeloEditFindingV1] = []
    for entry in submission.baseline.permitted_surface:
        if not isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) or not entry.grammar.required:
            continue
        casilla_id = entry.casilla_id
        kind = named.get(casilla_id)
        if kind is ModeloEditScalarIntentKind.SET_TYPED_VALUE:
            continue
        if kind is ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE:
            filled = False
        elif kind is ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE:
            filled = head.source_feeds_casilla(casilla_id)
        else:
            filled = head.revision is not None and casilla_id in head.revision.input_values_by_casilla_id
        if not filled:
            findings.append(
                _finding(
                    REQUIRED_EMPTY,
                    ModeloEditFindingSeverity.WARNING,
                    ModeloEditScalarAddressV1(casilla_id=casilla_id),
                )
            )
    return findings


def preflight_modelo_edit(
    submission: ModeloEditSubmissionV1,
    *,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    tax_id_format: SpanishTaxIdFormat | None,
) -> ModeloEditPreflightResultV1:
    """Recheck the baseline, then evaluate every intent and the resulting required casillas.

    ``tax_id_format`` is the governed Spanish tax-identifier format NIF values
    are validated with; ``None`` reports NIF values as refused rather than
    validating them against nothing.
    """
    baseline = submission.baseline
    stale = reconfirm_modelo_edit_baseline(
        baseline, work_catalogue=work_catalogue, calculation_catalogue=calculation_catalogue
    )
    if stale is not None:
        return ModeloEditRefusedV1(refusal=stale)
    revision = (
        calculation_catalogue.get(baseline.current_calculation_revision_id)
        if baseline.current_calculation_revision_id is not None
        else None
    )
    context = caller_context_of(revision)
    layer = context.known_operator_layer
    head = _Head(
        revision=revision,
        operator_casillas=layer.casilla_ids(),
        operator_bindings=frozenset(layer.binding_overrides),
        layer_known=context.operator_layer_known,
    )
    findings: list[ModeloEditFindingV1] = []
    if not head.layer_known:
        findings.append(_finding(OPERATOR_LAYER_UNKNOWN, ModeloEditFindingSeverity.WARNING))
    for intent in submission.scalar_intents:
        findings.extend(_scalar_findings(intent, submission, head, tax_id_format=tax_id_format))
    for binding_intent in submission.binding_intents:
        findings.extend(_binding_findings(binding_intent, submission, head, tax_id_format=tax_id_format))
    findings.extend(_required_empty_findings(submission, head))
    return ModeloEditPreflightEvaluatedV1(baseline_id=baseline.baseline_id, findings=tuple(findings))


__all__ = [
    "CLEAR_OF_SOURCE_FED_CASILLA",
    "INTENT_NOT_ADMITTED",
    "NOTHING_TO_RESTORE",
    "OPERATOR_LAYER_UNKNOWN",
    "OVERRIDES_SOURCE_VALUE",
    "REQUIRED_EMPTY",
    "VALUE_REFUSED_PREFIX",
    "preflight_modelo_edit",
]
