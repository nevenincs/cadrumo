"""Locale catalogue coverage for every closed workflow summary identity."""

from __future__ import annotations

import string

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, lookup_translation_entry
from ..run_models import WORKFLOW_SUMMARY_LOCALE_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _placeholder_names(value: str) -> frozenset[str]:
    return frozenset(field_name for _, field_name, _, _ in string.Formatter().parse(value) if field_name is not None)


def test_every_workflow_summary_key_is_real_and_placeholder_aligned_in_every_locale() -> None:
    for key in WORKFLOW_SUMMARY_LOCALE_KEYS:
        values: dict[str, str] = {}
        placeholder_sets: set[frozenset[str]] = set()
        for locale in SUPPORTED_OUTPUT_LANGUAGES:
            present, value = lookup_translation_entry(key, locale=locale)
            assert present, f"{locale}:{key} is absent"
            assert isinstance(value, str) and value.strip(), f"{locale}:{key} is blank"
            assert value != key, f"{locale}:{key} is a key echo"
            values[locale] = value
            placeholder_sets.add(_placeholder_names(value))

        assert len(placeholder_sets) == 1, f"placeholder drift for {key}: {placeholder_sets}"
        assert len(set(values.values())) == len(SUPPORTED_OUTPUT_LANGUAGES), (
            f"workflow summary is not independently localized: {key} -> {values}"
        )
