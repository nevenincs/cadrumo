"""Persistence helpers for extracted :class:`~aeat.domain.schema.Modelo` records.

Canonical layout: ``<cache_root>/modelo_<code.value>/<boe_ref>.json``.
Serialised with sorted keys and ``by_alias=True`` so ``RangeRule``
emits ``min`` / ``max`` (not ``min_`` / ``max_``) in the on-disk JSON.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from ...core.logging import get_logger
from ..modelos import ModeloCode
from ._errors import SchemaCacheError, SchemaValidationError
from ._models import Modelo

_logger = get_logger(__name__)

_BOE_REF_RE = re.compile(r"^(?=.*[A-Z0-9])[A-Z0-9-]+$")
"""Mirrors the inbound schema fetcher BOE reference rule — kept local to
avoid cross-module coupling; both patterns MUST agree."""


def resolve_schema_cache_file(
    code: ModeloCode,
    boe_ref: str,
    root: Path,
) -> Path:
    """Return the canonical JSON cache path for ``(code, boe_ref)``.

    Args:
        code: Target modelo identifier.
        boe_ref: BOE-A identifier (uppercase letters, digits, hyphens).
        root: Cache root directory (typically
            :attr:`Settings.aeat_schema_cache_dir`).

    Returns:
        ``root / modelo_<code.value> / <boe_ref>.json``.

    Raises:
        aeat.domain.schema.SchemaCacheError: If ``boe_ref`` contains
            unexpected characters.
    """
    if not _BOE_REF_RE.fullmatch(boe_ref):
        raise SchemaCacheError(
            f"invalid boe_ref {boe_ref!r}; expected [A-Z0-9-]+",
        )
    return root / f"modelo_{code.value}" / f"{boe_ref}.json"


def save_modelo_to_cache(modelo: Modelo, root: Path, boe_ref: str) -> Path:
    """Reject legacy schema-cache writes.

    Runtime modelo definitions now belong in the audited registry tree.
    This helper remains importable during migration so old readers can be
    identified, but it must never create filing-grade JSON artefacts.
    """

    del modelo, root, boe_ref
    raise SchemaCacheError("schema cache writes are disabled; migrate definitions through registry/aeat")


def load_modelo_from_cache(
    code: ModeloCode,
    boe_ref: str,
    root: Path,
) -> Modelo:
    """Load a :class:`Modelo` record from its canonical cache path.

    Args:
        code: Target modelo identifier.
        boe_ref: BOE-A identifier.
        root: Cache root directory.

    Returns:
        The validated :class:`Modelo`.

    Raises:
        aeat.domain.schema.SchemaCacheError: When the file is missing.
        aeat.domain.schema.SchemaValidationError: When the JSON fails model
            validation.
    """
    path = resolve_schema_cache_file(code, boe_ref, root)
    if not path.exists():
        _logger.debug("schema cache miss: modelo=%s boe_ref=%s path=%s", code.value, boe_ref, path)
        raise SchemaCacheError(f"schema cache file not found: {path}")
    try:
        return Modelo.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        _logger.warning(
            "schema cache validation failed: modelo=%s boe_ref=%s path=%s",
            code.value,
            boe_ref,
            path,
            exc_info=True,
        )
        raise SchemaValidationError(
            f"{path}: cached schema failed validation ({exc})",
        ) from exc
