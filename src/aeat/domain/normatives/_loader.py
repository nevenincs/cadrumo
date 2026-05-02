"""File-backed loader for the ``aeat.domain.normatives`` corpus.

The loader walks ``AEAT_NORMATIVES_ROOT`` and produces a strictly-
validated :class:`NormativeCatalogue`. One JSON file per normative,
sorted alphabetically by filename for deterministic loading order.
"""

from __future__ import annotations

from pathlib import Path

from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ._schema import NormativeCatalogue, NormativeReference
from .errors import NormativeNotFoundError, NormativeParseError

_logger = get_logger(__name__)


def _root_from_settings(settings: Settings | None) -> Path:
    """Resolve the normatives corpus root directory.

    Uses ``settings`` when supplied, otherwise loads a fresh
    :class:`aeat.core.config.Settings` via
    :func:`aeat.core.config.load_settings`.
    """
    return (settings or load_settings()).aeat_normatives_root


def load_catalogue(*, settings: Settings | None = None) -> NormativeCatalogue:
    """Load every ``<id>.json`` under ``AEAT_NORMATIVES_ROOT``.

    Args:
        settings: Optional settings instance; loaded on demand otherwise.

    Returns:
        A fully-validated :class:`NormativeCatalogue`.

    Raises:
        NormativeNotFoundError: If the root directory does not exist.
        NormativeParseError: If any committed file fails schema
            validation or declares an id that collides with another
            file already loaded.
    """
    root = _root_from_settings(settings)
    if not root.exists():
        raise NormativeNotFoundError(f"normatives root does not exist: {root}")
    if not root.is_dir():
        raise NormativeParseError(f"normatives root is not a directory: {root}")

    references: dict[str, NormativeReference] = {}
    for path in sorted(root.glob("*.json")):
        _logger.debug("loading normative %s", path)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise NormativeParseError(f"{path}: unable to read file ({exc})") from exc
        try:
            reference = NormativeReference.model_validate_json(raw)
        except Exception as exc:  # pydantic ValidationError subclasses Exception
            raise NormativeParseError(f"{path}: validation failed: {exc}") from exc
        if reference.id in references:
            raise NormativeParseError(
                f"{path}: duplicate normative id {reference.id!r} (already loaded from a previous file)"
            )
        references[reference.id] = reference

    _logger.info("loaded %d normative(s) from %s", len(references), root)
    return NormativeCatalogue(references=references)
