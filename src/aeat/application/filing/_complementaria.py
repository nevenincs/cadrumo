"""Filing-amendment boundaries for :mod:`aeat.application.filing`.

The persisted amendment records live in :mod:`aeat.domain.filing`. This
application module builds complementaria records from registry-backed
draft construction and persists them through the governed amendment
repository.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Protocol, cast

from ...core.config import load_settings
from ...core.logging import get_logger
from ...core.paths import resolve_record_json_path
from ...domain.filing import FilingDraft, FilingDraftRepository, FilingValueKind
from ...domain.filing._amendment import (
    AmendmentKind,
    CasillaChange,
    CasillaDelta,
    CasillaInputs,
    FilingAmendment,
    ModeloCode,
    make_amendment_id,
)
from ...domain.filing._errors import FilingAmendmentError, FilingBuilderError
from ...domain.filing._protocols import CasillaSchemaProvider

_logger = get_logger(__name__)
_AMENDMENTS_DIRNAME = "amendments"


class _SubmittedOriginal(Protocol):
    submission_id: str
    draft_id: str
    modelo: str
    period: str
    profile_tax_id: str
    justificante_csv: str | None


def build_complementaria(
    original: object,
    updated_inputs: CasillaInputs,
    *,
    schema_provider: CasillaSchemaProvider,
) -> FilingAmendment:
    """Build and persist a complementaria from a submitted filing."""

    original_submission = _submitted_original(original)
    original_draft = _load_original_draft(original_submission.draft_id)
    if original_draft.modelo != original_submission.modelo or original_draft.period != original_submission.period:
        raise FilingBuilderError("original submission and persisted draft disagree on modelo or period")
    merged_inputs = _merge_inputs(original_draft, updated_inputs)
    from . import build_draft

    amended_draft = build_draft(
        modelo=original_submission.modelo,
        period=original_submission.period,
        profile=_DraftProfile(
            tax_id=original_submission.profile_tax_id,
            display_name=f"Complementaria {original_submission.submission_id}",
            applicable_modelos=(original_submission.modelo,),
        ),
        inputs=merged_inputs,
        schema_provider=schema_provider,
    )
    delta = _delta(original_draft, amended_draft)
    if not delta:
        raise FilingBuilderError("complementaria requires at least one changed casilla")
    amendment = FilingAmendment(
        amendment_id=make_amendment_id(
            submission_id=original_submission.submission_id,
            amendment_kind=AmendmentKind.COMPLEMENTARIA,
            delta=delta,
        ),
        submission_id=original_submission.submission_id,
        original_csv=original_submission.justificante_csv or original_submission.submission_id,
        original_model=original_submission.modelo,
        original_period=original_submission.period,
        amendment_kind=AmendmentKind.COMPLEMENTARIA,
        delta=delta,
        amended_draft=amended_draft,
        created_at=amended_draft.created_at,
    )
    from ...domain.filing._complementaria_repository import FilingAmendmentRepository

    FilingAmendmentRepository(store_dir=_amendments_dir()).save(amendment)
    _logger.info(
        "built complementaria amendment_id=%s submission_id=%s",
        amendment.amendment_id,
        amendment.submission_id,
    )
    return amendment


class _DraftProfile:
    def __init__(self, *, tax_id: str, display_name: str, applicable_modelos: tuple[str, ...]) -> None:
        self.tax_id = tax_id
        self.display_name = display_name
        self.applicable_modelos = applicable_modelos


def _submitted_original(original: object) -> _SubmittedOriginal:
    required = ("submission_id", "draft_id", "modelo", "period", "profile_tax_id", "justificante_csv")
    missing = [name for name in required if not hasattr(original, name)]
    if missing:
        raise FilingBuilderError(f"original submission is missing required fields: {missing!r}")
    return cast("_SubmittedOriginal", original)


def _load_original_draft(draft_id: str) -> FilingDraft:
    repository = FilingDraftRepository(store_dir=load_settings().aeat_drafts_dir)
    draft = repository.load(draft_id)
    if draft is None:
        raise FilingBuilderError(f"original draft {draft_id!r} is not persisted")
    return draft


def _merge_inputs(original_draft: FilingDraft, updated_inputs: CasillaInputs) -> dict[str, object]:
    merged: dict[str, object] = {
        value.casilla_id: value.value
        for value in original_draft.values
        if value.value is not None and value.kind is not FilingValueKind.COMPUTED
    }
    merged.update(updated_inputs)
    return merged


def _delta(original_draft: FilingDraft, amended_draft: FilingDraft) -> CasillaDelta:
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
                casilla_code=amended.casilla_id,
                old_value=old,
                new_value=amended.value,
                reason="registry recalculation changed casilla value",
            )
        )
    return tuple(changes)


def load_amendment(amendment_id: str) -> FilingAmendment:
    """Load a previously persisted amendment by id."""
    from ...domain.filing._complementaria_repository import FilingAmendmentRepository

    try:
        resolve_record_json_path(_amendments_dir(), amendment_id, context="amendment id")
    except ValueError as exc:
        raise FilingAmendmentError(str(exc)) from exc
    repository = FilingAmendmentRepository(store_dir=_amendments_dir())
    loaded = repository.load(amendment_id)
    if loaded is None:
        raise FilingAmendmentError(f"no persisted amendment with id {amendment_id!r}")
    _logger.debug("loaded amendment amendment_id=%s", amendment_id)
    return loaded


def list_amendments(*, modelo: str | None = None) -> tuple[FilingAmendment, ...]:
    """Return every persisted amendment, optionally filtered by modelo."""
    from ...domain.filing._complementaria_repository import FilingAmendmentRepository

    target_dir = _amendments_dir()
    if not target_dir.exists():
        _logger.debug("amendments directory absent; returning empty list")
        return ()
    repository = FilingAmendmentRepository(store_dir=target_dir)
    results = tuple(
        amendment for amendment in repository.iter_amendments() if modelo is None or amendment.original_model == modelo
    )
    _logger.debug("listed %d amendments modelo_filter=%s", len(results), modelo)
    return results


def _amendments_dir() -> Path:
    settings = load_settings()
    target = settings.aeat_submissions_dir / _AMENDMENTS_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    return target


__all__ = [
    "AmendmentKind",
    "CasillaChange",
    "CasillaDelta",
    "CasillaInputs",
    "FilingAmendment",
    "ModeloCode",
    "build_complementaria",
    "list_amendments",
    "load_amendment",
    "make_amendment_id",
]
