"""Persistence helpers for extracted :class:`~aeat.schema.Modelo` records.

Canonical layout: ``<cache_root>/modelo_<code.value>/<boe_ref>.json``.
Serialised with sorted keys and ``by_alias=True`` so ``RangeRule``
emits ``min`` / ``max`` (not ``min_`` / ``max_``) in the on-disk JSON.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from ..logging import get_logger
from ..models import ModeloCode
from ._errors import SchemaCacheError, SchemaValidationError
from ._models import Modelo

_logger = get_logger(__name__)

_BOE_REF_RE = re.compile(r"^[A-Z0-9-]+$")


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
        aeat.schema.SchemaCacheError: If ``boe_ref`` contains
            unexpected characters.
    """
    if not _BOE_REF_RE.fullmatch(boe_ref):
        raise SchemaCacheError(
            f"invalid boe_ref {boe_ref!r}; expected [A-Z0-9-]+",
        )
    return root / f"modelo_{code.value}" / f"{boe_ref}.json"


def save_modelo_to_cache(modelo: Modelo, root: Path, boe_ref: str) -> Path:
    """Persist ``modelo`` under ``root`` keyed by ``boe_ref``.

    Uses ``model_dump(mode="json", by_alias=True)`` and re-serialises
    through :func:`json.dumps` with ``sort_keys=True`` so the on-disk
    bytes diff cleanly across extraction runs.

    Args:
        modelo: Extracted :class:`Modelo` record.
        root: Cache root directory.
        boe_ref: BOE-A identifier used as the on-disk filename stem.

    Returns:
        Absolute path of the written JSON file.
    """
    destination = resolve_schema_cache_file(modelo.modelo_code, boe_ref, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = modelo.model_dump(mode="json", by_alias=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _logger.info(
        "wrote schema cache modelo=%s boe_ref=%s path=%s",
        modelo.modelo_code.value,
        boe_ref,
        destination,
    )
    return destination


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
        aeat.schema.SchemaCacheError: When the file is missing.
        aeat.schema.SchemaValidationError: When the JSON fails model
            validation.
    """
    path = resolve_schema_cache_file(code, boe_ref, root)
    if not path.exists():
        raise SchemaCacheError(f"schema cache file not found: {path}")
    try:
        return Modelo.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise SchemaValidationError(
            f"{path}: cached schema failed validation ({exc})",
        ) from exc
