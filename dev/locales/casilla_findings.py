"""Ordered casilla key, text, resolution, and lineage audit projections."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modelo_casilla_catalogue import ModeloCasillaCatalogue
from collections.abc import Mapping

from .casilla_catalogue_models import (
    CatalogueFindings,
    CollapseResult,
)
from .casilla_resolution import _served_locale
from .casilla_text_comparison import (
    _is_derived_help,
)
from .casilla_text_policy import (
    _EDITION_TEXT_PLACEHOLDER,
    _FIELDS,
    _GLOSSARY_ARTIFACT,
    _IRREGULAR_WHITESPACE,
    _PLACEHOLDER,
    _TRUNCATED,
    SOURCE_LOCALE,
    SOURCE_TRUNCATED_SPANISH,
)


def _record_casilla_key_findings(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, leaves: Mapping[str, str | None]
) -> None:
    """Record casilla key findings."""
    found.orphan_keys[locale] = tuple(
        sorted(key for key in leaves if key not in self.dependents and not self._undeclared_revision(key))
    )
    found.undeclared_revision_keys[locale] = tuple(sorted(key for key in leaves if self._undeclared_revision(key)))
    found.null_leaves[locale] = tuple(
        sorted(key for key, value in leaves.items() if value is None and key in self.dependents)
    )


def _record_derived_casilla_help(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, leaves: Mapping[str, str | None]
) -> None:
    """Record derived casilla help."""
    found.derived_help[locale] = tuple(
        sorted(key for key, value in leaves.items() if value is not None and _is_derived_help(key, value))
    )


def _record_casilla_placeholders(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, leaves: Mapping[str, str | None]
) -> None:
    """Record casilla placeholders."""
    found.placeholders[locale] = tuple(
        sorted(
            key
            for key, value in leaves.items()
            if value is not None
            and (
                (key.endswith(".label") and _PLACEHOLDER.search(value))
                or (key.endswith(".title") and _EDITION_TEXT_PLACEHOLDER.search(value))
            )
        )
    )


def _record_casilla_glossary_artifacts(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, leaves: Mapping[str, str | None]
) -> None:
    """Record casilla glossary artifacts."""
    artifact = _GLOSSARY_ARTIFACT.get(locale)
    found.glossary_artifacts[locale] = (
        ()
        if artifact is None
        else tuple(sorted(key for key, value in leaves.items() if value and artifact.search(value)))
    )


def _record_casilla_truncation(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, leaves: Mapping[str, str | None]
) -> None:
    """Record casilla truncation."""
    sources = self.served_sources(locale) if locale != SOURCE_LOCALE else {}
    found.truncated_text[locale] = tuple(
        sorted(
            key
            for key, value in leaves.items()
            if value
            and _TRUNCATED.search(value)
            and value not in SOURCE_TRUNCATED_SPANISH
            and not (sources.get(key, frozenset()) & SOURCE_TRUNCATED_SPANISH)
        )
    )


def _record_casilla_whitespace(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, leaves: Mapping[str, str | None]
) -> None:
    """Record casilla whitespace."""
    found.irregular_whitespace[locale] = tuple(
        sorted(key for key, value in leaves.items() if value and _IRREGULAR_WHITESPACE.search(value))
    )


def _record_casilla_plan_findings(
    self: ModeloCasillaCatalogue, locale: str, found: CatalogueFindings, plan: CollapseResult
) -> None:
    """Record casilla plan findings."""
    found.redundant_values[locale] = tuple(
        sorted(key for key, reason in plan.plan.removals.get(locale, {}).items() if reason == "redundant")
    )
    found.lineage_lifts[locale] = tuple(sorted(plan.plan.settings.get(locale, {})))


def _record_casilla_unresolved_spanish(self: ModeloCasillaCatalogue, found: CatalogueFindings) -> None:
    """Record casilla unresolved spanish."""
    found.unresolved_spanish = tuple(
        sorted(
            f"{occurrence.modelo}/{occurrence.revision}/{occurrence.casilla}"
            for index, occurrence in enumerate(self.occurrences)
            if self.resolve(index, "label", SOURCE_LOCALE) is None
        )
    )


def _record_casilla_fallback_translations(self: ModeloCasillaCatalogue, found: CatalogueFindings) -> None:
    """Record casilla fallback translations."""
    found.untranslated = {
        locale: sum(
            1
            for index in range(len(self.occurrences))
            for field_name in _FIELDS
            if self.resolve(index, field_name, locale) is not None
            and _served_locale(self, index, field_name, locale) != locale
        )
        for locale in self.locales
        if locale != SOURCE_LOCALE
    }


def _record_casilla_content_and_segment_drift(self: ModeloCasillaCatalogue, found: CatalogueFindings) -> None:
    """Record casilla content and segment drift."""
    found.dropped_source_content = {
        locale: tuple(sorted(self.dropped_source_content(locale))) for locale in self.locales if locale != SOURCE_LOCALE
    }
    found.shared_translations = {
        locale: tuple(sorted(self.shared_translations(locale))) for locale in self.locales if locale != SOURCE_LOCALE
    }
    found.segment_drift = {
        locale: tuple(sorted(self.segment_drift(locale))) for locale in self.locales if locale != SOURCE_LOCALE
    }
    found.shared_segments = {
        locale: tuple(sorted(self.shared_segments(locale))) for locale in self.locales if locale != SOURCE_LOCALE
    }


def _record_casilla_lineage_translation_drift(self: ModeloCasillaCatalogue, found: CatalogueFindings) -> None:
    """Record casilla lineage translation drift."""
    found.translation_drift = self.translation_drift()
    found.stale_translations = {
        locale: self.stale_translations(locale) for locale in self.locales if locale != SOURCE_LOCALE
    }
    found.stranded_translations = {
        locale: self.stranded_translations(locale) for locale in self.locales if locale != SOURCE_LOCALE
    }
