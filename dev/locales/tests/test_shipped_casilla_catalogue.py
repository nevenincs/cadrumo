"""Gate: the shipped casilla catalogue is stored in its delta-keyed form.

Measured through the published authority's key chains and the runtime
resolution rule, so the verdict is about what operators are served.
"""

from __future__ import annotations

from functools import cache

import pytest

from .._paths import LOCALES_DIR
from ..modelo_casilla_catalogue import (
    REVIEWED_EQUIVALENT_SPANISH,
    SOURCE_TRUNCATED_SPANISH,
    CatalogueFindings,
    ModeloCasillaCatalogue,
    edition_text_gaps,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _findings() -> CatalogueFindings:
    return ModeloCasillaCatalogue.published(LOCALES_DIR).findings()


def test_the_shipped_casilla_catalogue_stores_each_text_once() -> None:
    """No orphan, null, redundant, liftable or derived leaf remains.

    Repair with ``python -m dev.locales casilla-collapse --apply``.
    """
    findings = _findings()
    assert findings.structurally_pure, findings.counts()


def test_every_casilla_label_resolves_in_spanish() -> None:
    assert _findings().unresolved_spanish == ()


def test_no_casilla_label_is_a_scaffold_placeholder() -> None:
    assert not any(_findings().placeholders.values()), _findings().placeholders


def test_no_casilla_text_is_cut_short_glossary_output_or_padded() -> None:
    """Stored text is complete, translated as prose, and free of copied whitespace.

    Complete cut text from the official record design, retranslate glossary
    output, and install both with ``python -m dev.locales casilla-author``.
    """
    findings = _findings()
    defects = {
        family: {locale: keys[:3] for locale, keys in getattr(findings, family).items() if keys}
        for family in ("truncated_text", "glossary_artifacts", "irregular_whitespace")
    }
    assert not any(defects.values()), defects


def test_every_source_truncation_is_still_stored() -> None:
    """An exemption for a cut official text must name Spanish the catalogue still stores."""
    stored = {text for text in ModeloCasillaCatalogue.published(LOCALES_DIR).values["es"].values() if text}
    assert stored >= SOURCE_TRUNCATED_SPANISH, sorted(SOURCE_TRUNCATED_SPANISH - stored)


def test_every_edition_text_is_authored_in_every_locale() -> None:
    """Revision labels and construct titles have no chain, so a null or placeholder renders nothing useful."""
    gaps = {locale: keys for locale, keys in edition_text_gaps(LOCALES_DIR).items() if keys}
    assert gaps == {}, {locale: (len(keys), keys[:5]) for locale, keys in gaps.items()}


def test_every_reviewed_equivalence_still_excuses_a_shared_translation() -> None:
    """Each entry must still match a lineage the screen would otherwise report, or it is stale."""
    catalogue = ModeloCasillaCatalogue.published(LOCALES_DIR)
    unexcused = {
        locale: set(catalogue.stale_translations(locale, excused={}))
        for locale in {locale for locale, _modelo, _lineage in REVIEWED_EQUIVALENT_SPANISH}
    }
    stale_entries = [
        (locale, modelo, lineage)
        for (locale, modelo, lineage), reason in REVIEWED_EQUIVALENT_SPANISH.items()
        if not reason.strip() or f"{modelo}/{lineage}" not in unexcused[locale]
    ]
    assert stale_entries == []


def test_no_lineage_keeps_a_translation_the_spanish_outgrew() -> None:
    findings = _findings()
    assert not any(findings.stale_translations.values()), findings.stale_translations
