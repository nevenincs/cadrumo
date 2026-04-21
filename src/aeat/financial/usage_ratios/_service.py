"""Atomic load/save helpers for :class:`UsageRatioProfile` (issue #259)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from ...logging import get_logger
from ._errors import UsageRatioPersistenceError
from ._model import UsageRatioProfile

__all__ = ["load_usage_ratios", "save_usage_ratios"]

_LOGGER = get_logger(__name__)


def load_usage_ratios(path: Path) -> UsageRatioProfile:
    """Load Kent's persisted usage-ratio profile, or return an empty one.

    A missing file is not an error — it is the virgin state — so this helper
    returns an empty :class:`UsageRatioProfile` in that case. Any other I/O
    failure or JSON validation error is surfaced as
    :class:`UsageRatioPersistenceError`.

    Args:
        path: JSON file containing a serialised :class:`UsageRatioProfile`.

    Returns:
        The validated profile, or an empty one when ``path`` does not exist.

    Raises:
        UsageRatioPersistenceError: If the file cannot be read (other than
            ``FileNotFoundError``) or its JSON payload is invalid.
    """
    target = path.resolve()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        _LOGGER.info("usage-ratios file not found at %s; returning empty profile", target)
        return UsageRatioProfile()
    except OSError as exc:
        raise UsageRatioPersistenceError(
            f"unable to read usage-ratio profile: {target}: {exc.__class__.__name__}: {exc}"
        ) from exc
    # Strip a leading UTF-8 BOM — Windows Notepad (pre-2019) and several
    # Excel/CSV tools default to UTF-8-with-BOM when saving JSON by hand.
    # Pydantic's Rust JSON parser rejects the BOM; Kent would otherwise
    # get an unhelpful "expected value at line 1 column 1" error.
    if raw.startswith("﻿"):
        raw = raw[1:]
    try:
        profile = UsageRatioProfile.model_validate_json(raw)
    except ValidationError as exc:
        raise UsageRatioPersistenceError(
            f"invalid usage-ratio profile JSON: {target}\n{_summarise_validation_errors(exc)}"
        ) from exc
    _LOGGER.info("loaded %s usage ratios from %s", len(profile.ratios), target)
    return profile


def _summarise_validation_errors(exc: ValidationError) -> str:
    """Render a short, Kent-legible summary of a pydantic validation failure.

    The default ``str(ValidationError)`` is verbose and includes pydantic doc URLs;
    this helper extracts one human-readable line per error with the offending
    path (e.g. ``ratios.suministros_home_office_luz``) and the message.
    """
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = error.get("msg", "validation error")
        lines.append(f"  - {location}: {message}" if location else f"  - {message}")
    return "\n".join(lines) if lines else "  - validation error"


def save_usage_ratios(profile: UsageRatioProfile, path: Path) -> None:
    """Persist Kent's usage-ratio profile atomically via ``os.replace``.

    The payload is first written to a sibling :func:`tempfile.NamedTemporaryFile`
    in the same directory and then atomically moved into place, matching the
    invoice catalogue persistence pattern.

    Args:
        profile: The profile to persist.
        path: Destination JSON file.

    Raises:
        UsageRatioPersistenceError: If the write cannot be completed.
    """
    target = path.resolve()
    payload = profile.model_dump_json(indent=2)
    tmp_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f"{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(payload)
        os.replace(tmp_path, target)
    except OSError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise UsageRatioPersistenceError(
            f"unable to write usage-ratio profile: {target}: {exc.__class__.__name__}: {exc}"
        ) from exc
    _LOGGER.info("saved %s usage ratios to %s", len(profile.ratios), target)
