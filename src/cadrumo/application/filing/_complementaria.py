"""Filing-amendment boundaries for :mod:`application.filing`.

This module builds local complementaria records from a submitted-filing
shape such as :class:`domain.submission.ModeloPresentado`. It loads
the original :class:`domain.filing.ModeloDraft` through the governed
draft repository, verifies that the draft still matches the active registry
snapshot, rebuilds an amended draft with
:func:`application.filing.build_draft`, computes the
:class:`domain.filing.CasillaChange` delta, and persists the resulting
:class:`domain.filing.ModeloComplementaria`.

The read helpers expose the same governed amendment repository and may
return either :class:`domain.filing.ModeloComplementaria` or
:class:`domain.filing.ModeloSustitutiva` because the encrypted
repository stores both amendment variants.

See Also:
    :mod:`domain.filing`
        Canonical amendment records, draft records, and governed
        repository ports used by this application boundary.
    :class:`adapters.persistence.profile.filing_amendments.ModeloAmendmentRepository`
        AUDIT-classified encrypted persistence for complementaria and
        sustitutiva records.
    :mod:`application.modelo._amendment_actions`
        Separate work-unit amendment flow for externally evidenced modelo
        filing records.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from ...adapters.persistence.profile.filing_amendments import ModeloAmendmentRepository
from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ...core import Period
from ...core.logging import get_logger
from ...domain.filing import (
    AmendmentKind,
    CasillaChange,
    CasillaDelta,
    CasillaInputs,
    CasillaSchemaProvider,
    ModeloAmendmentError,
    ModeloBuilderError,
    ModeloCode,
    ModeloComplementaria,
    ModeloDraft,
    ModeloInputs,
    ModeloInputValue,
    ModeloSustitutiva,
    ModeloValueKind,
    make_amendment_id,
)

_logger = get_logger(__name__)


@runtime_checkable
class _SubmittedOriginal(Protocol):
    submission_id: str
    draft_id: str
    modelo: str
    period: Period
    profile_tax_id: str
    justificante_csv: str | None


def build_complementaria(
    original: object,
    updated_inputs: CasillaInputs,
    *,
    schema_provider: CasillaSchemaProvider,
) -> ModeloComplementaria:
    """Build, persist, and return the :class:`ModeloComplementaria` for a submitted filing."""
    original_submission = _submitted_original(original)
    original_draft = _load_original_draft(original_submission.draft_id)
    if original_draft.modelo != original_submission.modelo or original_draft.period != original_submission.period:
        raise ModeloBuilderError("original submission and persisted draft disagree on modelo or period")
    _require_original_registry_snapshot(original_draft, schema_provider=schema_provider)
    merged_inputs = _merge_inputs(original_draft, updated_inputs)
    from . import build_draft

    amended_draft = build_draft(
        modelo=original_submission.modelo,
        period=original_draft.period,
        profile=_DraftProfile(
            tax_id=original_submission.profile_tax_id,
            display_name=f"Complementaria {original_submission.submission_id}",
        ),
        inputs=merged_inputs,
        schema_provider=schema_provider,
    )
    delta = _delta(original_draft, amended_draft)
    if not delta:
        raise ModeloBuilderError("complementaria requires at least one changed casilla")
    amendment = ModeloComplementaria(
        amendment_id=make_amendment_id(
            submission_id=original_submission.submission_id,
            amendment_kind=AmendmentKind.COMPLEMENTARIA,
            delta=delta,
        ),
        submission_id=original_submission.submission_id,
        original_csv=original_submission.justificante_csv,
        original_model=original_submission.modelo,
        original_period=original_draft.period,
        delta=delta,
        amended_draft=amended_draft,
        created_at=amended_draft.created_at,
    )
    ModeloAmendmentRepository().save(amendment)
    _logger.info(
        "built complementaria amendment_id=%s submission_id=%s",
        amendment.amendment_id,
        amendment.submission_id,
    )
    return amendment


class _DraftProfile:
    def __init__(self, *, tax_id: str, display_name: str) -> None:
        self.tax_id = tax_id
        self.display_name = display_name


def _submitted_original(original: object) -> _SubmittedOriginal:
    required = ("submission_id", "draft_id", "modelo", "period", "profile_tax_id", "justificante_csv")
    missing = [name for name in required if not hasattr(original, name)]
    if missing:
        raise ModeloBuilderError(f"original submission is missing required fields: {missing!r}")
    if not isinstance(original, _SubmittedOriginal):
        raise ModeloBuilderError("original submission does not conform to the expected protocol shape")
    submitted: _SubmittedOriginal = original
    csv = submitted.justificante_csv
    if csv is None or not csv.strip():
        raise ModeloBuilderError("original submission must include an official justificante CSV")
    return submitted


def _load_original_draft(draft_id: str) -> ModeloDraft:
    repository = ModeloDraftRepository()
    draft = repository.load(draft_id)
    if draft is None:
        raise ModeloBuilderError(
            translated_message="application.filing.errors.original_draft_not_persisted",
            context={"draft_id": repr(draft_id)},
        )
    return draft


def _require_original_registry_snapshot(
    original_draft: ModeloDraft,
    *,
    schema_provider: CasillaSchemaProvider,
) -> None:
    collection = schema_provider.get_collection(original_draft.modelo)
    if original_draft.schema_version != collection.schema_version:
        raise ModeloBuilderError("original draft was not built from the active registry snapshot")


def _merge_inputs(original_draft: ModeloDraft, updated_inputs: CasillaInputs) -> ModeloInputs:
    # Only LITERAL casilla values are operator inputs. COMPUTED and
    # INHERITED entries are engine-derived (formula output and bound
    # binding projection respectively) and must not be re-supplied as
    # casilla inputs on rebuild — the registry calculation re-derives
    # them, and the runtime rejects bound casillas supplied via inputs
    # without their matching binding_values entry.
    merged: dict[str, ModeloInputValue] = {
        value.casilla_id: value.value
        for value in original_draft.values
        if value.value is not None and value.kind is ModeloValueKind.LITERAL
    }
    # Re-project the original draft's binding values into the inputs
    # dict keyed by binding_id. build_draft routes binding_id-keyed
    # entries through filing_binding_values into the engine's
    # binding_values parameter; without this step, the rebuild would
    # lose every previously-supplied binding (e.g. the M130 carry-
    # forward binding modelo-130-resultados-negativos-anteriores or
    # construct bindings like irpf.previous_year_economic_activity_net_income).
    for binding_value in original_draft.binding_values:
        if binding_value.value is None:
            continue
        merged.setdefault(binding_value.binding_id, binding_value.value)
    merged.update(updated_inputs)
    return merged


def _delta(original_draft: ModeloDraft, amended_draft: ModeloDraft) -> CasillaDelta:
    original_values = {
        value.casilla_id: value.value for value in original_draft.values if isinstance(value.value, Decimal)
    }
    changes: list[CasillaChange] = []
    for amended in amended_draft.values:
        if not isinstance(amended.value, Decimal):
            continue
        old = original_values.get(amended.casilla_id)
        if old == amended.value:
            continue
        changes.append(
            CasillaChange(
                casilla_id=amended.casilla_id,
                old_value=old,
                new_value=amended.value,
                reason="registry recalculation changed casilla value",
            ),
        )
    return tuple(changes)


def load_amendment(amendment_id: str) -> ModeloComplementaria | ModeloSustitutiva:
    """Load a previously persisted amendment by id.

    Returns a :class:`ModeloComplementaria` or :class:`ModeloSustitutiva`
    depending on the amendment kind.
    """
    repository = ModeloAmendmentRepository()
    try:
        repository.envelope_path_for(amendment_id)
    except ValueError as exc:
        raise ModeloAmendmentError(str(exc)) from exc
    loaded = repository.load(amendment_id)
    if loaded is None:
        raise ModeloAmendmentError(
            translated_message="application.filing.errors.amendment_not_persisted",
            context={"amendment_id": repr(amendment_id)},
        )
    _logger.debug("loaded amendment amendment_id=%s", amendment_id)
    return loaded


def list_amendments(*, modelo: str | None = None) -> tuple[ModeloComplementaria | ModeloSustitutiva, ...]:
    """Return every persisted amendment, optionally filtered by modelo.

    Each element is a :class:`ModeloSustitutiva` or
    :class:`ModeloComplementaria` depending on its amendment kind.
    """
    repository = ModeloAmendmentRepository()
    results = tuple(
        amendment for amendment in repository.iter_amendments() if modelo is None or amendment.original_model == modelo
    )
    _logger.debug("listed %d amendments modelo_filter=%s", len(results), modelo)
    return results


__all__ = [
    "AmendmentKind",
    "CasillaChange",
    "CasillaDelta",
    "CasillaInputs",
    "ModeloCode",
    "ModeloComplementaria",
    "ModeloSustitutiva",
    "build_complementaria",
    "list_amendments",
    "load_amendment",
    "make_amendment_id",
]
