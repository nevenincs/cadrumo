"""Strict amendment models and builder helpers for :mod:`aeat.filing`."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .._paths import resolve_record_json_path
from ..config import load_settings
from ..justificante import parse_justificante
from ._errors import FilingAmendmentError, FilingAmendmentValidationError
from ._schema import FilingDraft, FilingScalar, FilingValue
from .runtime import FilingOperatorProfile, build_runtime_schema_provider

type ModeloCode = str
type CasillaInputs = Mapping[str, object]

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_REASONS_INPUT_KEY = "_reasons"
_AMENDMENTS_DIRNAME = "amendments"


class AmendmentKind(StrEnum):
    """Legally distinct amendment kinds supported by the engine."""

    COMPLEMENTARIA = "complementaria"
    SUSTITUTIVA = "sustitutiva"


class CasillaChange(BaseModel):
    """One changed casilla in an amendment delta."""

    model_config = _STRICT_FROZEN

    casilla_code: str = Field(min_length=1)
    old_value: Decimal | None = None
    new_value: Decimal
    reason: str = Field(min_length=1)


type CasillaDelta = tuple[CasillaChange, ...]


class FilingAmendment(BaseModel):
    """Immutable amendment record derived from a previously submitted filing."""

    model_config = _STRICT_FROZEN

    amendment_id: str = Field(min_length=1)
    submission_id: str = Field(min_length=1)
    original_csv: str = Field(min_length=1)
    original_model: ModeloCode = Field(min_length=1)
    original_period: str = Field(min_length=1)
    amendment_kind: AmendmentKind
    delta: CasillaDelta = Field(min_length=1)
    amended_draft: FilingDraft
    created_at: datetime


def build_complementaria(original, updated_inputs: CasillaInputs) -> FilingAmendment:
    """Build and persist an immutable amendment from ``original``."""
    from . import QUARTERLY_303_INPUT_KEY, build_draft

    original_draft = _load_original_draft(original.draft_id)
    metadata = _resolve_original_metadata(original)
    amendment_kind = _resolve_amendment_kind(metadata["original_model"], metadata["original_period"])
    amended_draft = _build_updated_draft(
        build_draft=build_draft,
        quarterly_key=QUARTERLY_303_INPUT_KEY,
        modelo=metadata["original_model"],
        period=metadata["original_period"],
        profile_tax_id=original.profile_tax_id,
        updated_inputs=updated_inputs,
    )
    delta = _compute_delta(
        original_values=original_draft.values,
        amended_values=amended_draft.values,
        reasons=_extract_reasons(updated_inputs),
    )
    if amendment_kind is AmendmentKind.COMPLEMENTARIA:
        _validate_complementaria_liability(
            modelo=metadata["original_model"],
            period=metadata["original_period"],
            original_draft=original_draft,
            amended_draft=amended_draft,
        )
    amendment = FilingAmendment(
        amendment_id=make_amendment_id(
            submission_id=original.submission_id,
            amendment_kind=amendment_kind,
            delta=delta,
        ),
        submission_id=original.submission_id,
        original_csv=metadata["original_csv"],
        original_model=metadata["original_model"],
        original_period=metadata["original_period"],
        amendment_kind=amendment_kind,
        delta=delta,
        amended_draft=amended_draft,
        created_at=datetime.now(tz=UTC),
    )
    _persist_amendment(amendment)
    return amendment


def load_amendment(amendment_id: str) -> FilingAmendment:
    """Load a previously persisted amendment by id.

    Wave-7/8: tries the FilingAmendmentRepository (ciphertext) first;
    falls back to the legacy plaintext path for un-migrated operators.
    """
    from ._complementaria_repository import FilingAmendmentRepository

    try:
        # Validate the id shape (rejects path traversal).
        resolve_record_json_path(_amendments_dir(), amendment_id, context="amendment id")
    except ValueError as exc:
        raise FilingAmendmentError(str(exc)) from exc
    repository = FilingAmendmentRepository(store_dir=_amendments_dir())
    via_repo = repository.load(amendment_id)
    if via_repo is not None:
        return via_repo
    legacy_path = _amendments_dir() / f"{amendment_id}.json"
    if not legacy_path.exists():
        raise FilingAmendmentError(f"no persisted amendment with id {amendment_id!r}")
    return FilingAmendment.model_validate_json(legacy_path.read_text(encoding="utf-8"))


def list_amendments(*, modelo: str | None = None) -> tuple[FilingAmendment, ...]:
    """Return every persisted amendment, optionally filtered by modelo.

    Reads both the new ciphertext envelopes and any legacy plaintext
    files for un-migrated operators."""
    from ._complementaria_repository import FilingAmendmentRepository

    target_dir = _amendments_dir()
    if not target_dir.exists():
        return ()
    repository = FilingAmendmentRepository(store_dir=target_dir)
    results: list[FilingAmendment] = []
    seen_ids: set[str] = set()
    for amendment in repository.iter_amendments():
        seen_ids.add(amendment.amendment_id)
        if modelo is not None and amendment.original_model != modelo:
            continue
        results.append(amendment)
    for path in sorted(target_dir.glob("*.json")):
        if path.name.endswith(".envelope.json"):
            continue
        amendment = FilingAmendment.model_validate_json(path.read_text(encoding="utf-8"))
        if amendment.amendment_id in seen_ids:
            continue
        if modelo is not None and amendment.original_model != modelo:
            continue
        results.append(amendment)
    return tuple(results)


def make_amendment_id(
    *,
    submission_id: str,
    amendment_kind: AmendmentKind,
    delta: CasillaDelta,
) -> str:
    """Compute a stable amendment identifier."""
    payload = {
        "submission_id": submission_id,
        "amendment_kind": amendment_kind.value,
        "delta": [change.model_dump(mode="json") for change in delta],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _amendments_dir() -> Path:
    settings = load_settings()
    target = settings.aeat_submissions_dir / _AMENDMENTS_DIRNAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def _persist_amendment(amendment: FilingAmendment) -> Path:
    """Persist ``amendment`` through the governed FilingAmendmentRepository.

    Wave-8 silent-leaker close: this helper used to write plaintext
    ``<amendment_id>.json`` directly to disk. It now routes through
    the AUDIT-class ciphertext repository.
    """
    from ._complementaria_repository import FilingAmendmentRepository

    try:
        # Reject path-traversal-shaped ids early (mirrors the legacy
        # ``resolve_record_json_path`` validation contract).
        resolve_record_json_path(_amendments_dir(), amendment.amendment_id, context="amendment id")
    except ValueError as exc:
        raise FilingAmendmentError(str(exc)) from exc
    repository = FilingAmendmentRepository(store_dir=_amendments_dir())
    repository.save(amendment)
    return repository.envelope_path_for(amendment.amendment_id)


def _load_original_draft(draft_id: str) -> FilingDraft:
    """Locate the original draft by id, supporting both ciphertext and
    legacy plaintext on-disk shapes."""
    from ._repository import FilingDraftRepository

    drafts_dir = load_settings().aeat_drafts_dir
    if not drafts_dir.exists():
        raise FilingAmendmentValidationError(f"drafts directory not found: {drafts_dir}")
    repository = FilingDraftRepository(store_dir=drafts_dir)
    via_repo = repository.load(draft_id)
    if via_repo is not None:
        return via_repo
    # Legacy plaintext fallback for un-migrated operators.
    for path in sorted(drafts_dir.glob("*.json")):
        if path.name.endswith(".envelope.json"):
            continue
        draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
        if draft.draft_id == draft_id:
            return draft
    raise FilingAmendmentValidationError(f"could not locate original draft for draft_id={draft_id!r}")


def _resolve_original_metadata(original) -> dict[str, str]:
    if original.justificante_pdf_path is not None and original.justificante_pdf_path.exists():
        justificante = parse_justificante(original.justificante_pdf_path)
        return {
            "original_csv": justificante.csv,
            "original_model": justificante.modelo,
            "original_period": original.period,
        }
    if original.justificante_csv is None:
        raise FilingAmendmentValidationError("submitted filing must carry justificante_csv or justificante_pdf_path")
    return {
        "original_csv": original.justificante_csv,
        "original_model": original.modelo,
        "original_period": original.period,
    }


def _resolve_amendment_kind(modelo: str, period: str) -> AmendmentKind:
    if modelo == "390":
        return AmendmentKind.SUSTITUTIVA
    if modelo == "303" and _period_uses_rectificativa(period):
        raise FilingAmendmentValidationError(
            f"modelo 303 period {period!r} uses autoliquidacion rectificativa, not complementaria"
        )
    if modelo in {"130", "303"}:
        return AmendmentKind.COMPLEMENTARIA
    raise FilingAmendmentValidationError(f"unsupported amendment modelo {modelo!r}")


def _period_uses_rectificativa(period: str) -> bool:
    if len(period) == 7 and period[4] == "-":
        year = int(period[:4])
        month = int(period[5:7])
        return (year, month) >= (2024, 9)
    if len(period) == 6 and period[4].upper() == "Q":
        year = int(period[:4])
        quarter = int(period[5])
        return (year, quarter) >= (2024, 3)
    return False


def _build_updated_draft(
    *,
    build_draft,
    quarterly_key: str,
    modelo: str,
    period: str,
    profile_tax_id: str,
    updated_inputs: CasillaInputs,
) -> FilingDraft:
    profile = FilingOperatorProfile(
        tax_id=profile_tax_id,
        display_name=f"Amendment {profile_tax_id}",
        applicable_modelos=(modelo,),
    )
    draft_inputs = dict(updated_inputs)
    draft_inputs.pop(_REASONS_INPUT_KEY, None)
    if modelo == "390" and quarterly_key not in draft_inputs:
        raise FilingAmendmentValidationError(
            "modelo 390 amendments require _quarterly_303 with the four quarterly drafts"
        )
    return build_draft(
        modelo=modelo,
        period=period,
        profile=profile,
        inputs=draft_inputs,
        schema_provider=build_runtime_schema_provider(),
    )


def _extract_reasons(updated_inputs: CasillaInputs) -> Mapping[str, str]:
    raw = updated_inputs.get(_REASONS_INPUT_KEY)
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise FilingAmendmentValidationError(f"{_REASONS_INPUT_KEY!r} must be a mapping of casilla->reason")
    reasons: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            raise FilingAmendmentValidationError(f"{_REASONS_INPUT_KEY!r} must contain non-empty string pairs")
        reasons[key] = value.strip()
    return reasons


def _compute_delta(
    *,
    original_values: tuple[FilingValue, ...],
    amended_values: tuple[FilingValue, ...],
    reasons: Mapping[str, str],
) -> CasillaDelta:
    original_index = {value.casilla_id: value for value in original_values}
    amended_index = {value.casilla_id: value for value in amended_values}
    changes: list[CasillaChange] = []
    for casilla_id in sorted(set(original_index) | set(amended_index)):
        original_value = original_index.get(casilla_id)
        amended_value = amended_index.get(casilla_id)
        if original_value is None or amended_value is None:
            raise FilingAmendmentValidationError(f"casilla {casilla_id!r} missing from original or amended draft")
        if original_value.value == amended_value.value:
            continue
        changes.append(
            CasillaChange(
                casilla_code=casilla_id,
                old_value=_scalar_to_decimal(original_value.value, casilla_id),
                new_value=_required_decimal(amended_value.value, casilla_id),
                reason=reasons.get(casilla_id, f"Updated after recomputing revised casilla inputs for {casilla_id}"),
            )
        )
    if not changes:
        raise FilingAmendmentValidationError("updated inputs do not change any casilla values")
    return tuple(changes)


def _validate_complementaria_liability(
    *,
    modelo: str,
    period: str,
    original_draft: FilingDraft,
    amended_draft: FilingDraft,
) -> None:
    anchor = _liability_anchor(modelo, period)
    original_value = _anchor_value(original_draft, anchor)
    amended_value = _anchor_value(amended_draft, anchor)
    if amended_value < original_value:
        raise FilingAmendmentValidationError(
            f"complementaria cannot reduce liability for modelo {modelo} period {period}: "
            f"{amended_value} < {original_value}"
        )


def _liability_anchor(modelo: str, period: str) -> str:
    del period
    if modelo == "130":
        return "07"
    if modelo == "303":
        return "69"
    raise FilingAmendmentValidationError(f"no complementaria liability anchor configured for modelo {modelo!r}")


def _anchor_value(draft: FilingDraft, casilla_id: str) -> Decimal:
    for value in draft.values:
        if value.casilla_id == casilla_id:
            return _required_decimal(value.value, casilla_id)
    raise FilingAmendmentValidationError(f"draft {draft.draft_id} is missing liability casilla {casilla_id!r}")


def _scalar_to_decimal(value: FilingScalar, casilla_id: str) -> Decimal | None:
    if value is None:
        return None
    return _required_decimal(value, casilla_id)


def _required_decimal(value: FilingScalar, casilla_id: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise FilingAmendmentValidationError(f"casilla {casilla_id!r} has boolean value, expected numeric")
    if isinstance(value, int):
        return Decimal(value)
    raise FilingAmendmentValidationError(
        f"casilla {casilla_id!r} has non-numeric value type {type(value).__name__}; amendment delta is numeric only"
    )


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
