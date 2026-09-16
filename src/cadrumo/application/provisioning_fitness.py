"""Durable record of each local reader model's fitness for its role.

A fitness probe costs a model load plus a full answer budget, so a status
surface must not run one on every refresh. The verdict is recorded here by the
verify action and read back by status. It is keyed by endpoint, model and the
runtime's content digest: a verdict describes exact weights, so a pull that
replaces them or a removal drops the record rather than letting it describe
different bytes.

The record is operational state about a public model, never taxpayer data, and
lives in one fixed file under the storage root.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, Field, ValidationError

from ..core.atomic_write import atomic_write_text
from ..core.config import Settings, load_settings
from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.paths import effective_storage_root
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_location

__all__ = [
    "FITNESS_VERDICT_SCHEMA_VERSION",
    "RecordedFitnessVerdict",
    "RoleFitnessVerdict",
    "fitness_verdict_path",
    "invalidate_role_fitness",
    "read_fitness_verdict",
    "record_fitness_verdict",
]

FITNESS_VERDICT_SCHEMA_VERSION: Final[Literal[1]] = 1


class RoleFitnessVerdict(StrEnum):
    """What a completed fitness probe concluded about a model."""

    FIT = "fit"
    UNFIT = "unfit"
    TIMED_OUT = "timed_out"


class RecordedFitnessVerdict(BaseModel):
    """One settled probe verdict for exact weights served by one endpoint."""

    model_config = STRICT_FROZEN_CONFIG

    endpoint: str = Field(min_length=1)
    model: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    role: ModelRole
    verdict: RoleFitnessVerdict
    failed_condition_id: str | None = Field(default=None, min_length=1)
    elapsed_ms: int = Field(ge=0)
    recorded_at: datetime

    def matches(self, *, endpoint: str, model: str, digest: str, role: ModelRole) -> bool:
        """Return whether this record describes exactly the given key."""
        return (self.endpoint, self.model, self.digest, self.role) == (endpoint, model, digest, role)


class _FitnessVerdictDocument(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1]
    verdicts: tuple[RecordedFitnessVerdict, ...] = ()


def fitness_verdict_path(settings: Settings | None = None) -> Path:
    """Return the verdict record's path under the effective storage root."""
    root = effective_storage_root(settings=settings if settings is not None else load_settings())
    return root / storage_location(StorageCategory.LOCAL_READER_FITNESS_VERDICTS).relative_path()


def _read_document(path: Path) -> _FitnessVerdictDocument:
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return _FitnessVerdictDocument(schema_version=FITNESS_VERDICT_SCHEMA_VERSION)
    try:
        return _FitnessVerdictDocument.model_validate(json.loads(payload), strict=False)
    except (ValueError, ValidationError):
        # An unreadable record proves nothing about any model. It reads as "not
        # verified", which keeps readiness closed, and the next verify replaces it.
        return _FitnessVerdictDocument(schema_version=FITNESS_VERDICT_SCHEMA_VERSION)


def _write_document(path: Path, document: _FitnessVerdictDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(document.model_dump(mode="json"), sort_keys=True, indent=2) + "\n")


def read_fitness_verdict(
    *,
    endpoint: str,
    model: str,
    digest: str,
    role: ModelRole,
    settings: Settings | None = None,
) -> RecordedFitnessVerdict | None:
    """Return the recorded verdict for these exact weights, or ``None`` when none was recorded."""
    document = _read_document(fitness_verdict_path(settings))
    return next(
        (item for item in document.verdicts if item.matches(endpoint=endpoint, model=model, digest=digest, role=role)),
        None,
    )


def record_fitness_verdict(verdict: RecordedFitnessVerdict, settings: Settings | None = None) -> None:
    """Record ``verdict``, replacing any earlier verdict for the same endpoint, model and role."""
    path = fitness_verdict_path(settings)
    document = _read_document(path)
    kept = tuple(
        item
        for item in document.verdicts
        if (item.endpoint, item.model, item.role) != (verdict.endpoint, verdict.model, verdict.role)
    )
    _write_document(
        path,
        _FitnessVerdictDocument(schema_version=FITNESS_VERDICT_SCHEMA_VERSION, verdicts=(*kept, verdict)),
    )


def invalidate_role_fitness(settings: Settings | None = None) -> None:
    """Drop every recorded verdict for the configured endpoint, after its model store changed."""
    resolved = settings if settings is not None else load_settings()
    path = fitness_verdict_path(resolved)
    document = _read_document(path)
    endpoint = resolved.cadrumo_llm_ollama_chat_url
    kept = tuple(item for item in document.verdicts if item.endpoint != endpoint)
    if kept == document.verdicts:
        return
    _write_document(path, _FitnessVerdictDocument(schema_version=FITNESS_VERDICT_SCHEMA_VERSION, verdicts=kept))
