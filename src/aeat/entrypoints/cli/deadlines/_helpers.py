"""Shared helpers for the ``aeat deadlines`` CLI sub-app.

Pure CLI glue: profile loading, schedule materialisation. Every domain
decision is delegated to :mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

from ....core.config import load_settings
from ....core.errors import AeatError
from ....core.logging import get_logger
from ....domain.deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    ProfileError,
)

_logger = get_logger(__name__)


def load_profile() -> AutonomoProfile:
    """Load and validate the active :class:`AutonomoProfile`.

    Reads the workflow's active profile values and projects them onto
    the ``AutonomoProfile`` record via the wizard descriptor's typed
    projection.

    Returns:
        The validated profile.

    Raises:
        ProfileError: When no profile is active or required fields
            (``tax.id``) are missing.
    """
    from ....application.wizard._status import WizardStatusError, load_active_autonomo_profile
    from ....application.workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    try:
        return load_active_autonomo_profile(state)
    except WizardStatusError as exc:
        raise ProfileError(str(exc)) from exc
    except (OSError, AeatError) as exc:  # pragma: no cover - defensive
        _logger.error("load_profile: failed to project active profile", exc_info=True)
        raise ProfileError(str(exc)) from exc


def build_engine() -> DeadlineEngine:
    """Construct a :class:`DeadlineEngine` configured from Settings."""
    settings = load_settings()
    return DeadlineEngine(due_soon_days=settings.aeat_deadline_due_soon_days)
