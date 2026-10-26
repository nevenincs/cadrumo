"""Modelos 222 and 296 store their payload at the support floor and key later editions against it.

The support declaration keys the registry from its floor, so the edition that
answers the floor year states its own payload and every later edition names an
earlier edition as its storage baseline. A year stored as the difference from a
year that follows it inverts that direction.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection
from cadrumo.domain.calculations.registry.temporal import revision_temporal_resolution, select_revision

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS = ("222", "296")
_BASELINES = ("casilla_storage_baseline", "family_storage_baseline")


def _floor(catalogues: RegistryCatalogues) -> int:
    support = catalogues.supported_filing_years
    assert support is not None
    return support.floor


def _selected(modelo: ModeloDefinition, catalogues: RegistryCatalogues, year: int) -> ModeloRevision:
    period = ordered_revisions(modelo)[0].period_selector.periods[0]
    return select_revision(modelo, filing_year=year, period=period, support=catalogues.supported_filing_years)


def _backward_baselines(modelo: ModeloDefinition) -> list[tuple[str, str, str]]:
    """Every storage baseline that names an edition starting no earlier than the edition naming it."""
    starts: dict[str, date] = {
        str(revision_id): revision.valid_from for revision_id, revision in modelo.revisions.items()
    }
    return [
        (str(revision_id), field, str(baseline))
        for revision_id, revision in modelo.revisions.items()
        for field in _BASELINES
        if (baseline := getattr(revision, field)) is not None and starts[str(baseline)] >= starts[str(revision_id)]
    ]


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_the_floor_edition_is_authored_and_states_its_own_payload(modelo_id: str) -> None:
    modelo, catalogues = committed_modelo(modelo_id)
    floor = _floor(catalogues)
    revision = _selected(modelo, catalogues, floor)
    resolution = revision_temporal_resolution(
        revision,
        filing_year=floor,
        period=revision.period_selector.periods[0],
        support=catalogues.supported_filing_years,
    )
    assert resolution.projection_direction is TemporalProjectionDirection.AUTHORED
    assert [getattr(revision, field) for field in _BASELINES] == [None, None]
    assert revision.casillas


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_the_next_year_is_stored_against_the_floor_edition(modelo_id: str) -> None:
    modelo, catalogues = committed_modelo(modelo_id)
    floor = _floor(catalogues)
    floor_revision = _selected(modelo, catalogues, floor)
    following = _selected(modelo, catalogues, floor + 1)
    assert following.id != floor_revision.id
    assert [str(getattr(following, field)) for field in _BASELINES] == [str(floor_revision.id)] * 2


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_every_storage_baseline_names_an_earlier_edition(modelo_id: str) -> None:
    modelo, _ = committed_modelo(modelo_id)
    assert _backward_baselines(modelo) == []


@pytest.mark.parametrize("modelo_id", _MODELOS)
def test_a_floor_edition_stored_against_a_later_one_is_detected(modelo_id: str) -> None:
    modelo, catalogues = committed_modelo(modelo_id)
    floor_revision = _selected(modelo, catalogues, _floor(catalogues))
    later = _selected(modelo, catalogues, _floor(catalogues) + 1)
    inverted = floor_revision.model_copy(update={"casilla_storage_baseline": later.id})
    defective = modelo.model_copy(update={"revisions": {**modelo.revisions, floor_revision.id: inverted}})
    assert _backward_baselines(defective) == [(str(floor_revision.id), "casilla_storage_baseline", str(later.id))]
