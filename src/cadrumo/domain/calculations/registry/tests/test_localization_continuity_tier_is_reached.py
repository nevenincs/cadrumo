"""The casilla localization chain: tiers, the Spanish barrier, and the backstop.

A casilla's text resolves through an ordered chain of keys, most specific
first: the revision occurrence, the stating edition's occurrence for an
inherited row, then the lineage-wide ``continuidad_id`` key. Catalogues store a
value at the least specific key that yields the same text, so every tier must
really be consulted, and a requested locale must not read a translation that
lives below the tier where Spanish resolves.

The proofs run against fixture catalogues through
:func:`~cadrumo.core.i18n.render.override_locales_root`. A proof drawn from the
shipped catalogue would depend on it still carrying the defects the catalogue
purity work removes (valueless keys, untranslated rows), so it would retire
itself exactly when the catalogue becomes clean. The chains themselves are
taken from a real bundled casilla, so the accessors are exercised on the key
shapes production derives.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from .....core.i18n.render import override_locales_root
from ..modelo_localization import resolve_modelo_localization
from .registry_tree import bundled_registry_tree

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LOCALES = ("es", "en", "ca", "hu")


def _chained_casilla() -> CasillaDefinition:
    """A bundled casilla whose label chain has an occurrence and a continuity key."""
    return next(
        casilla
        for modelo in bundled_registry_tree()[0]
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if len(casilla.localization_keys) >= 2
    )


def _nested(entries: Mapping[str, str | None]) -> dict[str, object]:
    tree: dict[str, object] = {}
    for dotted, value in entries.items():
        node = tree
        *parents, leaf = dotted.split(".")
        for part in parents:
            child = node.setdefault(part, {})
            assert isinstance(child, dict)
            node = child
        node[leaf] = value
    return tree


@pytest.fixture
def catalogues(tmp_path: Path) -> Iterator[dict[str, dict[str, str | None]]]:
    """Per-locale fixture entries, written to disk on demand by :func:`_install`."""
    entries: dict[str, dict[str, str | None]] = {locale: {} for locale in _LOCALES}
    with override_locales_root(tmp_path):
        yield entries


def _install(root: Path, entries: Mapping[str, Mapping[str, str | None]]) -> None:
    for locale, values in entries.items():
        (root / f"{locale}.yml").write_text(
            yaml.safe_dump(_nested(values), allow_unicode=True),
            encoding="utf-8",
        )


def test_each_tier_is_reached_when_more_specific_keys_carry_nothing(
    tmp_path: Path,
    catalogues: dict[str, dict[str, str | None]],
) -> None:
    """A present-but-valueless key and an absent key both advance the chain."""
    casilla = _chained_casilla()
    occurrence, continuity = casilla.localization_keys[0], casilla.localization_keys[-1]
    catalogues["es"][occurrence] = None
    catalogues["es"][continuity] = "Base imponible"
    catalogues["en"][continuity] = "Tax base"
    _install(tmp_path, catalogues)

    assert casilla.get_label("es") == "Base imponible"
    assert casilla.get_label("en") == "Tax base"


def test_the_occurrence_value_wins_over_the_lineage_value(
    tmp_path: Path,
    catalogues: dict[str, dict[str, str | None]],
) -> None:
    """A revision that states its own wording keeps it, in every locale."""
    casilla = _chained_casilla()
    occurrence, continuity = casilla.localization_keys[0], casilla.localization_keys[-1]
    catalogues["es"].update({occurrence: "Base imponible del ejercicio", continuity: "Base imponible"})
    catalogues["en"].update({occurrence: "Base for the year", continuity: "Tax base"})
    _install(tmp_path, catalogues)

    assert casilla.get_label("es") == "Base imponible del ejercicio"
    assert casilla.get_label("en") == "Base for the year"


def test_a_translation_below_the_spanish_tier_is_not_served(
    tmp_path: Path,
    catalogues: dict[str, dict[str, str | None]],
) -> None:
    """The barrier: a lineage translation must not stand in for edition-specific Spanish.

    Spanish resolves on the occurrence key, so its text differs from the
    lineage text; the English lineage value translates that other text.
    """
    casilla = _chained_casilla()
    occurrence, continuity = casilla.localization_keys[0], casilla.localization_keys[-1]
    catalogues["es"].update({occurrence: "Base imponible del ejercicio", continuity: "Base imponible"})
    catalogues["en"][continuity] = "Tax base"
    _install(tmp_path, catalogues)

    assert casilla.get_label("en") == "Base imponible del ejercicio"
    assert resolve_modelo_localization(casilla.localization_keys, locale="en") == "Base imponible del ejercicio"


def test_the_spanish_backstop_serves_an_untranslated_locale(
    tmp_path: Path,
    catalogues: dict[str, dict[str, str | None]],
) -> None:
    """A locale with no value at or above the Spanish tier renders the Spanish text."""
    casilla = _chained_casilla()
    catalogues["es"][casilla.localization_keys[-1]] = "Base imponible"
    _install(tmp_path, catalogues)

    assert casilla.get_label("hu") == "Base imponible"


def test_help_follows_the_label_chain(
    tmp_path: Path,
    catalogues: dict[str, dict[str, str | None]],
) -> None:
    """Help derives its chain from the label chain, so it inherits the same tiers."""
    casilla = _chained_casilla()
    continuity_help = f"{casilla.localization_keys[-1].removesuffix('.label')}.help"
    catalogues["es"][continuity_help] = "Importe sobre el que se aplica el tipo."
    _install(tmp_path, catalogues)

    assert casilla.get_help("ca") == "Importe sobre el que se aplica el tipo."
    assert casilla.get_help("es") == "Importe sobre el que se aplica el tipo."


def test_an_unresolvable_chain_returns_nothing(
    tmp_path: Path,
    catalogues: dict[str, dict[str, str | None]],
) -> None:
    """No tier and no Spanish text: the optional resolver reports absence."""
    _install(tmp_path, catalogues)

    assert resolve_modelo_localization(_chained_casilla().localization_keys, locale="en") is None
