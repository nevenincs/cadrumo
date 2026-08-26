"""The guarded application-owned edit executor for the Modelo Edit Contract V1.

Behind :mod:`cadrumo.application.modelo`. Only the enrolled operation executor
may invoke this boundary (D6). Immediately before effect it revision-loads the
work and calculation catalogues and rechecks every baseline coordinate through
:func:`~._edit_services.reconfirm_modelo_edit_baseline`; any disagreement
refuses with ``stale_edit_baseline``, writes nothing, and settles the domain
effect as ``NONE``. It never silently rebases, merges, or promotes a green
preflight into authority.

V1 scope: the ``CALCULATE`` mutation family with ``SET_TYPED_VALUE`` and
``CLEAR_DECLARED_VALUE`` scalar intents, because those are the only intents
the shared calculation boundary
(:func:`~._calculation_actions.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`)
has an input shape for today -- a set value and an explicit clear, the latter
via its own ``cleared_casilla_ids`` identity axis so a cleared casilla stays
provably distinguishable from one never declared. Every other syntactically
admitted intent -- including every binding-override intent, which the
calculate boundary has no ``binding_overrides``-clearing input shape for yet
-- refuses with a typed, enumerated
:class:`~._edit_models.ModeloEditUnsupportedIntentReason` naming the specific
intent kind, not a generic bucket -- extending the shared calculation
boundary's own input surface further, or materialising repeatable rows inside
this executor, are out of this Step's scope (they would either widen the live
calculate path's blast radius or re-implement the write path it already
owns).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...adapters.persistence.profile.modelos_edit_receipts import ModeloEditReceiptRepository
from ...core import CasillaId
from ...core.hashing import content_hash_hex
from ...domain.buckets import BucketEventHistoryRepositoryProtocol
from ...domain.modelos import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from ._edit_models import (
    ModeloEditApplyRequestV1,
    ModeloEditBindingIntentKind,
    ModeloEditExecutionNoEffectV1,
    ModeloEditExecutionResultV1,
    ModeloEditExecutionUpdatedV1,
    ModeloEditMutationFamily,
    ModeloEditMutationResultReceiptV1,
    ModeloEditRowIntentKind,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloEditUnsupportedIntentReason,
    ModeloEditUnsupportedIntentRefusalV1,
)
from ._edit_services import _validate_scalar_intent, _writable_scalar_entry, reconfirm_modelo_edit_baseline

if TYPE_CHECKING:
    from ...adapters.persistence.storage import SecureObjectWrite

_RESPONSIBLE_OWNER = "modelo.edit"
_UNSUPPORTED_RECONSIDERATION = "resubmit without this intent once its follow-on Step lands, or split the submission"

_ROW_UNSUPPORTED_REASON: dict[ModeloEditRowIntentKind, ModeloEditUnsupportedIntentReason] = {
    ModeloEditRowIntentKind.ADD_ROW: ModeloEditUnsupportedIntentReason.ADD_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.UPDATE_ROW: ModeloEditUnsupportedIntentReason.UPDATE_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.DELETE_ROW: ModeloEditUnsupportedIntentReason.DELETE_ROW_NOT_YET_WIRED,
    ModeloEditRowIntentKind.MOVE_ROW: ModeloEditUnsupportedIntentReason.MOVE_ROW_NOT_YET_WIRED,
}

_BINDING_UNSUPPORTED_REASON: dict[ModeloEditBindingIntentKind, ModeloEditUnsupportedIntentReason] = {
    ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE: ModeloEditUnsupportedIntentReason.SET_OVERRIDE_VALUE_NOT_YET_WIRED,
    ModeloEditBindingIntentKind.REMOVE_OVERRIDE: ModeloEditUnsupportedIntentReason.REMOVE_OVERRIDE_NOT_YET_WIRED,
}

_NUMERIC_DATA_TYPES = frozenset({"decimal", "money", "integer", "ratio", "year"})


def _unsupported_intent_refusal(
    reason: ModeloEditUnsupportedIntentReason, *, address: object = None
) -> ModeloEditExecutionNoEffectV1:
    return ModeloEditExecutionNoEffectV1(
        refusal=ModeloEditUnsupportedIntentRefusalV1(
            address=address,
            reason=reason,
            responsible_owner=_RESPONSIBLE_OWNER,
            reconsideration_condition=_UNSUPPORTED_RECONSIDERATION,
        ),
    )


def _reachable_scalar_inputs(
    submission: ModeloEditSubmissionV1,
) -> tuple[dict[str, Decimal], dict[str, str], tuple[CasillaId, ...]] | ModeloEditExecutionNoEffectV1:
    """Translate SET_TYPED_VALUE and CLEAR_DECLARED_VALUE scalar intents into the calculate boundary's own input shape.

    A ``CLEAR_DECLARED_VALUE`` intent contributes no entry to either casilla
    input dict; it contributes its address to the returned cleared-casilla
    tuple instead, which the caller threads into the calculate boundary's own
    ``cleared_casilla_ids`` identity axis so the clear is provably
    distinguishable from a casilla simply never supplied.

    Every other intent kind this V1 executor cannot yet reach refuses here,
    before any catalogue read, naming the exact unreachable intent kind
    (never a single generic "unsupported" bucket).
    """
    if submission.row_intents:
        first_row = submission.row_intents[0]
        return _unsupported_intent_refusal(_ROW_UNSUPPORTED_REASON[first_row.kind], address=first_row.address)
    if submission.binding_intents:
        first_binding = submission.binding_intents[0]
        return _unsupported_intent_refusal(
            _BINDING_UNSUPPORTED_REASON[first_binding.kind], address=first_binding.address
        )

    baseline = submission.baseline
    casilla_inputs: dict[str, Decimal] = {}
    text_casilla_inputs: dict[str, str] = {}
    cleared_casilla_ids: list[CasillaId] = []
    for intent in submission.scalar_intents:
        if intent.kind is ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE:
            cleared_casilla_ids.append(intent.address.casilla_id)
            continue
        entry = _writable_scalar_entry(baseline, intent.address.casilla_id)
        data_type = entry.data_type if entry is not None else "text"
        if data_type in _NUMERIC_DATA_TYPES:
            casilla_inputs[intent.address.casilla_id] = Decimal(str(intent.value))
        else:
            text_casilla_inputs[intent.address.casilla_id] = str(intent.value)
    return casilla_inputs, text_casilla_inputs, tuple(cleared_casilla_ids)


def apply_modelo_edit(
    request: ModeloEditApplyRequestV1,
    *,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol,
    receipt_repository: ModeloEditReceiptRepository,
    now: datetime,
    result_destination: str,
) -> ModeloEditExecutionResultV1:
    """Recheck the baseline at the guarded commit point and execute a CALCULATE edit.

    Delegates the actual formula evaluation and persistence to the existing
    calculation boundary and single-writer primitive; this function adds only
    the commit-point recheck, the intent-reachability gate, and the
    atomically co-committed result receipt.
    """
    submission = request.submission
    baseline = submission.baseline

    if submission.mutation_family is not ModeloEditMutationFamily.CALCULATE:
        return _unsupported_intent_refusal(ModeloEditUnsupportedIntentReason.RECALCULATE_NOT_YET_WIRED)

    reachable = _reachable_scalar_inputs(submission)
    if isinstance(reachable, ModeloEditExecutionNoEffectV1):
        return reachable
    casilla_inputs, text_casilla_inputs, cleared_casilla_ids = reachable

    for intent in submission.scalar_intents:
        refusal = _validate_scalar_intent(baseline, intent.address, intent.kind)
        if refusal is not None:
            return ModeloEditExecutionNoEffectV1(refusal=refusal)

    # Immediately before effect: revision-load the catalogues and recheck
    # every baseline coordinate. No re-read happens between this check and
    # the guarded commit below other than the calculation boundary's own
    # internal, independently CAS-guarded reads.
    work_catalogue = work_unit_repository.load()
    calculation_catalogue = calculation_repository.load()
    stale = reconfirm_modelo_edit_baseline(
        baseline, work_catalogue=work_catalogue, calculation_catalogue=calculation_catalogue
    )
    if stale is not None:
        return ModeloEditExecutionNoEffectV1(refusal=stale)

    captured_receipt: list[ModeloEditMutationResultReceiptV1] = []

    def _co_commit_receipt(
        calculation_revision_id: str, bucket_event_id: str | None
    ) -> tuple[SecureObjectWrite, ...]:
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

    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        baseline.work_unit_id,
        actor=_RESPONSIBLE_OWNER,
        casilla_inputs=casilla_inputs or None,
        text_casilla_inputs=text_casilla_inputs or None,
        cleared_casilla_ids=cleared_casilla_ids,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        clock=now,
        additional_secure_object_writes_for_revision=_co_commit_receipt,
    )
    assert captured_receipt, "the calculation boundary must resolve exactly one revision id per call"
    return ModeloEditExecutionUpdatedV1(receipt=captured_receipt[0])


__all__ = ["apply_modelo_edit"]
