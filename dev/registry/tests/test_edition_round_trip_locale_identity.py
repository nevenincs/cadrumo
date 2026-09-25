"""Real-behaviour tests for the round-trip gate's locale-identity comparison.

The gate proves a delta-authored edition means what its full copy meant. Locale
identity is the part the typed dump omits, and the part a storage change may
legitimately touch: an inherited row's chain carries the occurrence key of the
edition that last states it, so compacting an intermediate edition into a
technical root moves that key back one edition. The chains here are the ones
the loader produces for real editions of real modelos, and each rule is shown
biting: the moved key is not a difference, and the keys that carry identity or
text still are.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ..compiler.loader import load_modelo_directory
from ..edition_round_trip import localization_differences

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A real modelo whose 2016-2018 edition hydrates its rows from 2009-2011-junio
#: through 2011-julio-2015, the edition compaction turned into a technical root.
#: Its live chains carry the origin key this move produced; the chains the same
#: edition carried before the move name 2011-julio-2015 in that one position.
_MODELO = "308"
_EDITION = "2016-2018"
_BEFORE_COMPACTION = "2011-julio-2015"
_ORIGIN = "2009-2011-junio"

#: A real row of a real modelo whose own and lineage keys carry no help while a
#: sibling edition's occurrence key does, with every label resolving the same.
_HELP_MODELO = "303"
_HELP_EDITION = "2022"
_HELP_SIBLING = "2026-y-siguientes"
_HELP_ROW = "23"


def _definition(modelo_id: str) -> ModeloDefinition:
    return load_modelo_directory(Path(bundled_path("registry", "aeat", "modelos", modelo_id)))


@pytest.fixture(scope="module")
def modelo() -> ModeloDefinition:
    return _definition(_MODELO)


@pytest.fixture(scope="module")
def help_modelo() -> ModeloDefinition:
    return _definition(_HELP_MODELO)


def _rekeyed(revision: ModeloRevision, chains: Mapping[str, tuple[str, ...]]) -> ModeloRevision:
    """Return the edition with the named rows' key chains replaced and nothing else touched."""
    return revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"localization_keys": chain})
                if (chain := chains.get(str(casilla.id))) is not None
                else casilla
                for casilla in revision.casillas
            )
        }
    )


def _differences(definition: ModeloDefinition, edition: str, reference: ModeloRevision, modelo_id: str) -> list[str]:
    """Judge the modelo's real edition against ``reference``, the edition it is claimed to still mean."""
    return localization_differences(
        modelo_id=modelo_id,
        sibling_revision_ids=frozenset(definition.revisions) - {edition},
        reference=reference,
        live=definition.revisions[edition],
    )


def _occurrence(modelo_id: str, revision_id: str, casilla_id: str) -> str:
    return casilla_occurrence_locale_key(modelo_id, revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL)


def _chains_before_compaction(definition: ModeloDefinition, edition: str, modelo_id: str) -> dict[str, tuple[str, ...]]:
    """Return, per hydrated row of ``edition``, the chain it carried before its origin edition was compacted.

    A row qualifies by its live chain naming :data:`_ORIGIN` directly after its
    own key, which is the origin tier the compaction moved. Its earlier chain
    named the edition that stated the row then, so only that one key differs.
    """
    chains: dict[str, tuple[str, ...]] = {}
    for casilla in definition.revisions[edition].casillas:
        keys = tuple(casilla.localization_keys)
        if len(keys) < 2 or keys[1] != _occurrence(modelo_id, _ORIGIN, str(casilla.id)):
            continue
        chains[str(casilla.id)] = (keys[0], _occurrence(modelo_id, _BEFORE_COMPACTION, str(casilla.id)), *keys[2:])
    return chains


def test_an_origin_key_moved_back_one_edition_is_not_a_difference(modelo: ModeloDefinition) -> None:
    """The shape compaction produces: the row is stated one edition earlier, so its text is keyed there.

    Read off the real chains, which must name the origin edition to begin with,
    so the proof cannot pass on an edition that hydrates nothing.
    """
    chains = _chains_before_compaction(modelo, _EDITION, _MODELO)
    assert chains, f"{_EDITION} carries no row keyed to {_ORIGIN}"
    reference = _rekeyed(modelo.revisions[_EDITION], chains)
    assert [tuple(item.localization_keys) for item in reference.casillas] != [
        tuple(item.localization_keys) for item in modelo.revisions[_EDITION].casillas
    ]
    assert _differences(modelo, _EDITION, reference, _MODELO) == []


def test_a_changed_lineage_key_is_still_a_difference(modelo: ModeloDefinition) -> None:
    """The tier below the origins carries identity, not storage, so it is compared exactly."""
    chains = _chains_before_compaction(modelo, _EDITION, _MODELO)
    row_id, chain = next(iter(sorted(chains.items())))
    relineaged: dict[str, tuple[str, ...]] = {row_id: (*chain[:-1], chain[-1].replace(".label", ".plantado.label"))}
    differences = _differences(modelo, _EDITION, _rekeyed(modelo.revisions[_EDITION], relineaged), _MODELO)
    assert [item for item in differences if "key chain" in item], differences


def test_an_occurrence_key_below_the_lineage_tier_is_still_compared(modelo: ModeloDefinition) -> None:
    """Only the run of origin keys directly after the row's own key is set aside."""
    chains = _chains_before_compaction(modelo, _EDITION, _MODELO)
    row_id, chain = next(iter(sorted(chains.items())))
    appended: dict[str, tuple[str, ...]] = {row_id: (*chain, _occurrence(_MODELO, _BEFORE_COMPACTION, row_id))}
    differences = _differences(modelo, _EDITION, _rekeyed(modelo.revisions[_EDITION], appended), _MODELO)
    assert [item for item in differences if "key chain" in item], differences


def test_help_resolving_differently_is_reported_even_where_every_label_agrees(
    help_modelo: ModeloDefinition,
) -> None:
    """An origin key set aside must still carry no text, and help is text.

    The planted key is a sibling edition's occurrence key for the same row, so
    the chain comparison accepts it. That row's help lives only under the
    sibling's key, so accepting the chain without reading the help would let a
    row gain help text the reference never resolved.
    """
    edition = help_modelo.revisions[_HELP_EDITION]
    row = next(item for item in edition.casillas if str(item.id) == _HELP_ROW)
    keys = tuple(row.localization_keys)
    planted = _occurrence(_HELP_MODELO, _HELP_SIBLING, _HELP_ROW)
    assert planted not in keys
    reference = _rekeyed(edition, {_HELP_ROW: (keys[0], planted, *keys[1:])})

    differences = _differences(help_modelo, _HELP_EDITION, reference, _HELP_MODELO)
    assert [item for item in differences if "key chain" in item] == []
    assert [item for item in differences if "label in" in item] == []
    assert [item for item in differences if f"casilla {_HELP_ROW!r} help in 'es'" in item], differences
