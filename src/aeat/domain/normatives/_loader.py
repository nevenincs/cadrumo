"""File-backed loader for the ``aeat.domain.normatives`` corpus.

The loader walks ``AEAT_NORMATIVES_ROOT`` and produces a strictly-
validated :class:`NormativeCatalogue`. One JSON file per normative,
sorted alphabetically by filename for deterministic loading order.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...core.paths import file_stat_fingerprint
from ._errors import NormativeNotFoundError, NormativeParseError
from ._schema import NormativeCatalogue, NormativeReference

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
    resolved = root.resolve()
    paths = tuple(sorted(resolved.glob("*.json")))
    try:
        fingerprint = tuple(file_stat_fingerprint(path) for path in paths)
    except OSError as exc:
        raise NormativeParseError(f"unable to stat normative file ({exc})") from exc
    return _load_catalogue_cached(str(resolved), fingerprint)


@lru_cache(maxsize=16)
def _load_catalogue_cached(
    root: str,
    fingerprint: tuple[tuple[str, int, int], ...],
) -> NormativeCatalogue:
    root_path = Path(root)
    references: dict[str, NormativeReference] = {}
    for filename, _byte_count, _modified_ns in fingerprint:
        path = root_path / filename
        _logger.debug("loading normative %s", path)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            _logger.warning("normative file unreadable: %s", path, exc_info=True)
            raise NormativeParseError(f"{path}: unable to read file ({exc})") from exc
        try:
            reference = NormativeReference.model_validate_json(raw)
        except (ValueError, ValidationError) as exc:
            _logger.warning("normative validation failed: %s", path, exc_info=True)
            raise NormativeParseError(f"{path}: validation failed: {exc}") from exc
        if reference.id in references:
            _logger.warning(
                "normative duplicate id %r in %s; previously loaded id wins",
                reference.id,
                path,
            )
            raise NormativeParseError(
                f"{path}: duplicate normative id {reference.id!r} (already loaded from a previous file)",
            )
        references[reference.id] = reference

    _logger.debug("loaded %d normative(s) from %s", len(references), root_path)
    return NormativeCatalogue(references=references)
