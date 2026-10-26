"""Modelo 222 modalidad 40.2 rate as one open row across its editions.

Every instructions era the Modelo 222 editions cite prints the same "porcentaje
del 18%" for the modalidad 40.2 instalment, so the rate is one open row that the
later editions inherit rather than a row each edition restates from its own
first day. Each edition still cites the instructions in force for its years.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_base import DateAxis

from ..conformance.registry_schema_support import committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "222"
_PARAMETER = "is.modalidad_cuota.percentage"
_RATE_TEXT = "porcentaje del 18%"
_RATE = Decimal("18")


@cache
def _modelo() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return committed_modelo(_MODELO)


def _editions() -> list[ModeloRevision]:
    modelo, _catalogues = _modelo()
    return sorted(modelo.revisions.values(), key=lambda revision: revision.valid_from)


def _rate_row_problems(editions: list[ModeloRevision]) -> list[str]:
    """Name every edition whose rate is not the single open row the first edition starts."""
    problems: list[str] = []
    starts = set()
    for revision in editions:
        (parameter,) = (item for item in revision.parameters if item.id == _PARAMETER)
        rows = [row for row in parameter.values if row.date_axis is DateAxis.FILING_PERIOD]
        if len(rows) != 1 or rows[0].valid_to is not None or rows[0].value != _RATE:
            problems.append(f"{revision.id}: expected one open 18 row, found {rows!r}")
            continue
        starts.add(rows[0].valid_from)
    if len(starts) > 1:
        problems.append(f"editions restate the unchanged rate from {sorted(starts)}")
    return problems


def test_every_edition_inherits_one_open_rate_row() -> None:
    assert _rate_row_problems(_editions()) == []


@pytest.mark.parametrize("revision_id", [str(revision.id) for revision in _editions()])
def test_each_edition_cites_rate_instructions_in_force_for_its_years(revision_id: str) -> None:
    modelo, catalogues = _modelo()
    revision = modelo.revisions[revision_id]
    (parameter,) = (item for item in revision.parameters if item.id == _PARAMETER)
    cited = [citation for citation in parameter.source_citations if _RATE_TEXT in citation.required_text]

    assert cited, f"{revision_id} cites no instructions text for the 18% rate"
    for citation in cited:
        source = catalogues.sources[citation.source_ref]
        assert source.applies_from is None or source.applies_from <= revision.valid_from
        last_day = revision.valid_to or date(revision.valid_from.year, 12, 31)
        assert source.applies_to is None or source.applies_to >= last_day


def test_rate_row_check_detects_an_edition_restating_the_rate_from_its_own_start() -> None:
    """A later edition closing nothing and restating the same rate from its first day is reported."""
    editions = _editions()
    latest = editions[-1]
    (parameter,) = (item for item in latest.parameters if item.id == _PARAMETER)
    restated_rows = tuple(row.model_copy(update={"valid_from": latest.valid_from}) for row in parameter.values)
    restated = latest.model_copy(
        update={
            "parameters": tuple(
                item.model_copy(update={"values": restated_rows}) if item.id == _PARAMETER else item
                for item in latest.parameters
            )
        }
    )

    problems = _rate_row_problems([*editions[:-1], restated])

    assert any("restate the unchanged rate" in problem for problem in problems)
