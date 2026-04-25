"""Shared helpers for the ``aeat deadlines`` CLI sub-app.

Pure CLI glue: profile loading, schedule materialisation. Every domain
decision is delegated to :mod:`aeat.deadlines`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...config import load_settings
from ...deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    ProfileError,
)


def resolve_profile_path(explicit: Path | None) -> Path:
    """Return the path to the profile JSON to load.

    Args:
        explicit: ``--profile`` value from the CLI, if any.

    Returns:
        The resolved path.

    Raises:
        typer.BadParameter: If neither ``--profile`` nor
            ``AEAT_DEFAULT_PROFILE_PATH`` is set.
    """
    if explicit is not None:
        return explicit
    settings = load_settings()
    if settings.aeat_default_profile_path is None:
        raise typer.BadParameter(
            "no profile path supplied; pass --profile PATH or set AEAT_DEFAULT_PROFILE_PATH in env/.env"
        )
    return settings.aeat_default_profile_path


def load_profile(path: Path) -> AutonomoProfile:
    """Load and validate an :class:`AutonomoProfile` from JSON on disk.

    Args:
        path: Path to a JSON file matching the
            :class:`AutonomoProfile` schema.

    Returns:
        The validated profile.

    Raises:
        ProfileError: If the file does not exist or its contents are
            not a valid profile.
    """
    if not path.exists():
        raise ProfileError(f"profile file not found: {path}")
    try:
        return AutonomoProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive: covered by tests
        raise ProfileError(f"invalid profile JSON at {path}: {exc}") from exc


def build_engine() -> DeadlineEngine:
    """Construct a :class:`DeadlineEngine` configured from Settings."""
    settings = load_settings()
    return DeadlineEngine(due_soon_days=settings.aeat_deadline_due_soon_days)
