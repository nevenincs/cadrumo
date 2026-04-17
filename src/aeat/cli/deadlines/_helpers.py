"""Shared helpers for the ``aeat deadlines`` CLI sub-app.

Pure CLI glue: profile loading, in-process catalogue stub, schedule
materialisation. Every domain decision is delegated to
:mod:`aeat.deadlines`.
"""

from __future__ import annotations

from pathlib import Path

import typer

from aeat.config import load_settings
from aeat.deadlines import (
    KNOWN_AUTONOMO_MODELOS,
    AutonomoProfile,
    DeadlineEngine,
    ModeloIdentifier,
)


class InProcessCatalogue:
    """Real Protocol implementation of :class:`ModeloCatalogueLoader`.

    Ships the closed v1 set of autónomo modelos so the CLI can run
    before #6 ``aeat.models`` lands on ``main``. The class is
    deliberately concrete (not a mock) and lives under the CLI module
    so it never leaks into the engine's public API.
    """

    def known_modelos(self) -> tuple[ModeloIdentifier, ...]:
        """Return the closed tuple of v1 autónomo modelos."""
        return tuple(ModeloIdentifier(m) for m in KNOWN_AUTONOMO_MODELOS)

    def is_known(self, modelo: ModeloIdentifier) -> bool:
        """Return ``True`` iff ``modelo`` is part of the v1 set."""
        return modelo in KNOWN_AUTONOMO_MODELOS


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
        typer.BadParameter: If ``path`` does not point to a readable
            JSON file matching the :class:`AutonomoProfile` schema.
    """
    if not path.exists():
        raise typer.BadParameter(f"profile file not found: {path}")
    if path.is_dir():
        raise typer.BadParameter(f"profile path must point to a JSON file, got directory: {path}")
    try:
        return AutonomoProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive: covered by tests
        raise typer.BadParameter(f"invalid profile JSON at {path}: {exc}") from exc


def build_engine() -> DeadlineEngine:
    """Construct a :class:`DeadlineEngine` configured from Settings."""
    settings = load_settings()
    return DeadlineEngine(
        InProcessCatalogue(),
        due_soon_days=settings.aeat_deadline_due_soon_days,
    )
