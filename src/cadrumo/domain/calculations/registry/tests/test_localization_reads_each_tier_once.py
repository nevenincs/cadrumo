"""Resolving a text reads the catalogue only as often as the selection needs.

Selecting which tier serves a chain means READING that tier. The renderer then
looked the very same coordinate up a second time to obtain what the selection
had already discarded, so every resolved text cost one wasted catalogue read --
and the registry resolves one per casilla per revision, 213k of them in a
single validation pass.

These gates hold the read count, not just the answer: a correct value obtained
through redundant reads is exactly the defect, and no assertion about the value
alone can see it.
"""

from __future__ import annotations

import pytest

from ..modelo_localization import (
    modelo_localization_source,
    resolve_modelo_localization,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SPECIFIC = "modelo.303.revision.2025.casilla.01.label"
_LINEAGE = "modelo.303.casilla.01.label"
_CHAIN = (_SPECIFIC, _LINEAGE)


class _CountingCatalogue:
    """A catalogue that records every coordinate it is asked for."""

    def __init__(self, entries: dict[tuple[str, str], str]) -> None:
        self.entries = entries
        self.reads: list[tuple[str, str]] = []

    def __call__(self, key: str, locale: str) -> str | None:
        self.reads.append((key, locale))
        return self.entries.get((key, locale))


def test_the_selection_stops_at_the_tier_that_serves() -> None:
    """A chain served by its first tier reads that tier and no other."""
    catalogue = _CountingCatalogue({(_SPECIFIC, "es"): "Base imponible"})

    assert modelo_localization_source(_CHAIN, locale="es", lookup=catalogue) == (_SPECIFIC, "es")
    assert catalogue.reads == [(_SPECIFIC, "es")]


def test_a_chain_served_by_its_lineage_tier_reads_each_tier_once() -> None:
    """The scan advances on an absent VALUE and stops; no tier is read twice."""
    catalogue = _CountingCatalogue({(_LINEAGE, "es"): "Base imponible"})

    assert modelo_localization_source(_CHAIN, locale="es", lookup=catalogue) == (_LINEAGE, "es")
    assert catalogue.reads == [(_SPECIFIC, "es"), (_LINEAGE, "es")]


def test_an_unserved_chain_reads_every_tier_and_resolves_to_nothing() -> None:
    catalogue = _CountingCatalogue({})

    assert modelo_localization_source(_CHAIN, locale="es", lookup=catalogue) is None
    assert catalogue.reads == [(_SPECIFIC, "es"), (_LINEAGE, "es")]


def test_a_translation_is_read_only_down_to_the_spanish_tier() -> None:
    """A non-Spanish locale reads Spanish to find the barrier, then the locale."""
    catalogue = _CountingCatalogue(
        {(_LINEAGE, "es"): "Base imponible", (_LINEAGE, "en"): "Taxable base"},
    )

    assert modelo_localization_source(_CHAIN, locale="en", lookup=catalogue) == (_LINEAGE, "en")
    assert catalogue.reads == [
        (_SPECIFIC, "es"),
        (_LINEAGE, "es"),
        (_SPECIFIC, "en"),
        (_LINEAGE, "en"),
    ]


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        pytest.param({(_SPECIFIC, "es"): "Primera"}, "Primera", id="specific-tier"),
        pytest.param({(_LINEAGE, "es"): "Lineage"}, "Lineage", id="lineage-tier"),
        pytest.param({}, None, id="unserved"),
    ],
)
def test_the_rendered_value_is_the_one_the_selection_read(
    entries: dict[tuple[str, str], str],
    expected: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Carrying the value forward must render exactly what a re-read would have.

    The counting catalogue is installed as the module's own reader, which is
    the only seam ``resolve_modelo_localization`` has, so the read count it
    records is the real one.
    """
    catalogue = _CountingCatalogue(entries)
    monkeypatch.setattr(
        "cadrumo.domain.calculations.registry.modelo_localization._catalogue_lookup",
        catalogue,
    )

    assert resolve_modelo_localization(_CHAIN, locale="es") == expected
    assert len(catalogue.reads) == len(set(catalogue.reads)), "no coordinate may be read twice"
