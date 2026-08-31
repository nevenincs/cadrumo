"""Bucket-local last-known output-language hint.

The encrypted user-profile record remains the authority for
``preferences.output_language``. This sidecar carries only the last
successfully persisted supported language code so critical storage
failures can render in the profile language when the bucket DEK cannot
be unwrapped.
"""

from __future__ import annotations

from pathlib import Path

from .....core.atomic_write import atomic_write_text
from .....core.config import coerce_output_language_setting
from .....core.external_constants import UTF_8_ENCODING
from .....core.fsync import fsync_parent_dir
from .....core.logging import get_logger
from .._storage_path_definitions import BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME
from ._layout import bucket_paths

_log = get_logger(__name__)


def normalize_output_language_hint(value: object) -> str | None:
    """Return ``value`` as a supported output-language code, or ``None``."""
    if isinstance(value, bool) or not isinstance(value, str):
        return None
    normalized = coerce_output_language_setting(value)
    return normalized.value if normalized is not None else None


def bucket_output_language_hint_path(*, storage_root: Path, bucket_id: str) -> Path:
    """Return the bucket-local output-language hint path."""
    return bucket_paths(storage_root, bucket_id).bucket_dir / BUCKET_OUTPUT_LANGUAGE_HINT_FILENAME


def read_bucket_output_language_hint(*, storage_root: Path, bucket_id: str) -> str | None:
    """Read a supported bucket output-language hint, failing soft on absence or drift."""
    try:
        text = bucket_output_language_hint_path(storage_root=storage_root, bucket_id=bucket_id).read_text(
            encoding=UTF_8_ENCODING,
        )
    except Exception as exc:
        _log.debug(
            "bucket output-language hint unavailable bucket_id=%s error_type=%s",
            bucket_id,
            type(exc).__name__,
            exc_info=True,
        )
        return None
    return normalize_output_language_hint(text)


def write_bucket_output_language_hint(*, storage_root: Path, bucket_id: str, language: object) -> bool:
    """Atomically persist a supported bucket output-language hint.

    Returns ``True`` when a hint was written and ``False`` when ``language``
    is unsupported. Unsupported values never reach disk.
    """
    normalized = normalize_output_language_hint(language)
    if normalized is None:
        return False
    target = bucket_output_language_hint_path(storage_root=storage_root, bucket_id=bucket_id)
    atomic_write_text(target, normalized + "\n", encoding=UTF_8_ENCODING)
    return True


def clear_bucket_output_language_hint(*, storage_root: Path, bucket_id: str) -> None:
    """Remove the bucket output-language hint if it exists."""
    target = bucket_output_language_hint_path(storage_root=storage_root, bucket_id=bucket_id)
    try:
        target.unlink()
        fsync_parent_dir(target)
    except FileNotFoundError:
        return


__all__ = [
    "bucket_output_language_hint_path",
    "clear_bucket_output_language_hint",
    "normalize_output_language_hint",
    "read_bucket_output_language_hint",
    "write_bucket_output_language_hint",
]
