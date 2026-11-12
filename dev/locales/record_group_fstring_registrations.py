"""Finite locale families the grouped record read says its rows and relations with."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fstring_registry import FStringKeyRegistration


def record_group_dynamic_registrations() -> tuple[FStringKeyRegistration, ...]:
    """Register the row summary sentences and the relation words, read from the schema's row references."""
    from cadrumo.application.user_profile.record_row_words import record_relation_words_key, record_summary_words_keys
    from cadrumo.core.resources.bundled_data import bundled_path

    from .fstring_registry import FStringKeyRegistration
    from .registry_scanner import capture_profile_schema

    _payload, schema = capture_profile_schema(
        bundled_path("registry", "cadrumo", "user_profile", "schema.toml").resolve(),
    )
    relation_keys = tuple(
        record_relation_words_key(section, field) for section, field, _target in schema.row_references()
    )
    return (
        FStringKeyRegistration(
            description="application.user_profile.record_groups.* (row summaries and the words of a row reference)",
            key_factory=lambda key: key,
            values=(*sorted(record_summary_words_keys()), *relation_keys),
        ),
    )
