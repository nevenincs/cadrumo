"""No parameter row is closed at its edition's end only to be restated unchanged by the next edition.

A value the law leaves unchanged is one open row, inherited by later editions;
closing it at every edition boundary and restating it from the next edition's
first day stores the same fact once per edition and hides the continuity a
reader and the projection rely on. A genuine change still closes the row and
adds the new value, so only an unchanged restatement across the boundary is a
defect.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from itertools import pairwise

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_base import DateAxis
from cadrumo.domain.calculations.registry.schema_formula import (
    BracketEntry,
    DatedValue,
    KeyedBracketEntry,
    ParameterDefinition,
)

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Row = DatedValue | BracketEntry | KeyedBracketEntry


@cache
def _modelos() -> tuple[ModeloDefinition, ...]:
    root = bundled_path("registry", "aeat", "modelos")
    return tuple(load_modelo_directory(path) for path in sorted(root.iterdir()) if (path / "revisions").is_dir())


def _filing_rows(parameter: ParameterDefinition) -> Iterable[_Row]:
    yield from (row for row in parameter.values if row.date_axis is DateAxis.FILING_PERIOD)
    yield from parameter.brackets
    yield from parameter.keyed_brackets


def _content(row: _Row) -> str:
    """A row's content without its window, as one comparable key."""
    window = ("valid_from", "valid_to")
    return repr(sorted((key, repr(value)) for key, value in row.model_dump().items() if key not in window))


def _restated_across(earlier: ModeloRevision, later: ModeloRevision) -> tuple[str, ...]:
    """Parameters whose row closes at ``earlier``'s end and reappears unchanged from ``later``'s start."""
    if earlier.valid_to is None:
        return ()
    following = {parameter.id: parameter for parameter in later.parameters}
    restated: list[str] = []
    for parameter in earlier.parameters:
        successor = following.get(parameter.id)
        if successor is None:
            continue
        ending = {_content(row) for row in _filing_rows(parameter) if row.valid_to == earlier.valid_to}
        starting = {_content(row) for row in _filing_rows(successor) if row.valid_from == later.valid_from}
        if ending & starting:
            restated.append(parameter.id)
    return tuple(restated)


def _editions(modelo: ModeloDefinition) -> list[ModeloRevision]:
    return sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))


def test_no_edition_restates_an_unchanged_row_its_predecessor_closed() -> None:
    restated = {
        (str(modelo.id), str(earlier.id), str(later.id)): ids
        for modelo in _modelos()
        for earlier, later in pairwise(_editions(modelo))
        if (ids := _restated_across(earlier, later))
    }
    assert restated == {}, restated


def test_a_closed_and_restated_row_is_detected() -> None:
    """The gate reports an unchanged row closed at one edition's end and restated by the next."""
    modelo = next(m for m in _modelos() if any(r.valid_to is not None for r in m.revisions.values()))
    editions = _editions(modelo)
    earlier, later = next((a, b) for a, b in pairwise(editions) if a.valid_to is not None)
    row = {"value": "1", "date_axis": "filing_period", "valid_from": earlier.valid_from}
    parameter = {
        "id": "detector-parameter",
        "data_type": "decimal",
        "unit": "percent",
        "legal_refs": ("ley-35-2006:art-81",),
    }
    parameter["source_refs"] = ("aeat-detector-source",)
    closed = ParameterDefinition.model_validate({**parameter, "values": ({**row, "valid_to": earlier.valid_to},)})
    restated = ParameterDefinition.model_validate({**parameter, "values": ({**row, "valid_from": later.valid_from},)})
    changed = ParameterDefinition.model_validate(
        {**parameter, "values": ({**row, "value": "2", "valid_from": later.valid_from},)}
    )

    assert _restated_across(
        earlier.model_copy(update={"parameters": (closed,)}),
        later.model_copy(update={"parameters": (restated,)}),
    ) == ("detector-parameter",)
    assert (
        _restated_across(
            earlier.model_copy(update={"parameters": (closed,)}),
            later.model_copy(update={"parameters": (changed,)}),
        )
        == ()
    )
