"""Finite locale families the activity-asset register serves by key."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fstring_registry import FStringKeyRegistration


def activity_asset_dynamic_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Register the timeline's fact words from the facts the record models carry."""
    from cadrumo.application.actividad_asset.activity_asset_read_models import (
        TIMELINE_FIELD_PATHS,
        timeline_field_word_key,
    )

    from .fstring_registry import FStringKeyRegistration

    return (
        FStringKeyRegistration(
            description="ledger.actividad_asset.field.* (facts of an asset record that the timeline words)",
            key_factory=lambda key: key,
            values=tuple(timeline_field_word_key(path) for path in TIMELINE_FIELD_PATHS),
        ),
    )
