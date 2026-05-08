"""Shared helpers for the ``aeat deadlines`` CLI sub-app.

Pure CLI glue: profile loading, schedule materialisation. Every domain
decision is delegated to :mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ....core.config import load_settings
from ....core.errors import AeatError
from ....core.logging import get_logger
from ....domain.deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    ProfileError,
)
from .._i18n import tr

_logger = get_logger(__name__)


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
        raise typer.BadParameter(tr("cli.financial.profile.labels.no_active"))
    return settings.aeat_default_profile_path


def load_profile(path: Path) -> AutonomoProfile:
    """Load and validate an :class:`AutonomoProfile` from disk.

    The setup wizard writes the profile as an encrypted envelope at
    IDENTITY class via :func:`aeat.application.setup.write_profile_file`; this
    helper round-trips through the matching loader so the on-disk
    record is always ciphertext.

    Args:
        path: Logical handle for the setup-profile entry. The path's
            resolved POSIX form is used as the SQL secure-object key;
            the on-disk file does not need to exist.

    Returns:
        The validated profile.

    Raises:
        ProfileError: If no profile envelope is registered under the
            logical handle, or its contents are not a valid profile.
    """
    from ....application.setup._env_writer import load_profile_envelope

    try:
        return load_profile_envelope(path)
    except FileNotFoundError as exc:
        raise ProfileError(f"profile file not found: {path}") from exc
    except (OSError, ValueError, AeatError) as exc:  # pragma: no cover - defensive: covered by tests
        _logger.error("load_profile: failed to load profile envelope at %s", path, exc_info=True)
        raise ProfileError(f"invalid profile envelope at {path}: {exc}") from exc


def build_engine() -> DeadlineEngine:
    """Construct a :class:`DeadlineEngine` configured from Settings."""
    settings = load_settings()
    return DeadlineEngine(due_soon_days=settings.aeat_deadline_due_soon_days)
