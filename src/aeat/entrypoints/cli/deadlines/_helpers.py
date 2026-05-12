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
    """Load and validate the active :class:`AutonomoProfile`.

    Reads the workflow's active profile values and projects them onto
    the legacy ``AutonomoProfile`` record via the wizard descriptor's
    typed projection. The on-disk JSON envelope is no longer used.

    Args:
        path: Ignored. Retained for source-compatibility.

    Returns:
        The validated profile.

    Raises:
        ProfileError: When no profile is active or required fields
            (``tax.id``) are missing.
    """
    del path
    from ....application.wizard._status import load_active_autonomo_profile
    from ....application.workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    try:
        return load_active_autonomo_profile(state)
    except ValueError as exc:
        raise ProfileError(str(exc)) from exc
    except (OSError, AeatError) as exc:  # pragma: no cover - defensive
        _logger.error("load_profile: failed to project active profile", exc_info=True)
        raise ProfileError(str(exc)) from exc


def build_engine() -> DeadlineEngine:
    """Construct a :class:`DeadlineEngine` configured from Settings."""
    settings = load_settings()
    return DeadlineEngine(due_soon_days=settings.aeat_deadline_due_soon_days)
