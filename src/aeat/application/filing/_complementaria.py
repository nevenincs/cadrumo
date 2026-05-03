"""Filing-amendment boundaries for :mod:`aeat.application.filing`.

The persisted amendment records live in :mod:`aeat.domain.filing`. This
application module keeps the load/list surfaces available, but amendment
construction is fail-closed until registry-backed amendment definitions
provide amendment kind, legal period rules, liability anchors, and delta
semantics.
"""

from __future__ import annotations

from pathlib import Path

from ...core.config import load_settings
from ...core.logging import get_logger
from ...core.paths import resolve_record_json_path
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


def build_complementaria(
    original: object,
    updated_inputs: CasillaInputs,
    *,
    schema_provider: CasillaSchemaProvider,
) -> FilingAmendment:
    """Refuse amendment construction until registry-backed rules exist."""

    del original, updated_inputs, schema_provider
    raise FilingBuilderError(
        "complementaria construction requires validated registry snapshots; "
        "legacy Python amendment anchors are disabled"
    )


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
