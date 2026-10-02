"""A parameter row the law leaves unchanged is stated once and stays open across editions.

A value the law leaves unchanged is one open row, inherited by later editions.
Three authoring shapes store that one fact again and hide the continuity a
reader and the projection rely on:

- closing the row at its edition's end and restating it from the next edition's
  first day;
- keeping the row open but letting a later edition state it again, either in its
  own parameter declarations or as a sequence addition of an override;
- letting a later edition remove the open row and add it back with only its
  window re-keyed.

A genuine change still adds a row with different content, so only a row whose
content matches one its predecessor already carries is a defect. Content is
compared by typed meaning: ``12450.00`` restates ``12450`` and ``0.20`` restates
``0.2``, so a new decimal representation does not make a restatement a change.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import cast

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

from ..compiler.loader import load_modelo_declarations, load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_Row = DatedValue | BracketEntry | KeyedBracketEntry
_ROW_SEQUENCES: Mapping[str, type[_Row]] = {
    "values": DatedValue,
    "brackets": BracketEntry,
    "keyed_brackets": KeyedBracketEntry,
}


def _modelo_directories() -> tuple[Path, ...]:
    root = bundled_path("registry", "aeat", "modelos")
    return tuple(path for path in sorted(root.iterdir()) if (path / "revisions").is_dir())


@cache
def _modelos() -> tuple[ModeloDefinition, ...]:
    return tuple(load_modelo_directory(path) for path in _modelo_directories())


@cache
def _authored_revisions() -> Mapping[str, Mapping[str, Mapping[str, object]]]:
    """Each modelo's revisions as authored on disk, before inheritance."""
    authored: dict[str, Mapping[str, Mapping[str, object]]] = {}
    for path in _modelo_directories():
        declarations = load_modelo_declarations(path)
        modelo = cast("Mapping[str, object]", declarations["modelo"])
        authored[str(modelo["id"])] = cast("Mapping[str, Mapping[str, object]]", declarations["revisions"])
    return authored


def _is_filing_row(row: _Row) -> bool:
    return not isinstance(row, DatedValue) or row.date_axis is DateAxis.FILING_PERIOD


def _filing_rows(parameter: ParameterDefinition) -> Iterable[_Row]:
    rows: Iterable[_Row] = (*parameter.values, *parameter.brackets, *parameter.keyed_brackets)
    yield from (row for row in rows if _is_filing_row(row))


_Content = tuple[tuple[str, object], ...]


def _content(row: _Row) -> _Content:
    """A row's typed content without its window, as one comparable key.

    Fields keep their typed values, so ``12450.00`` and ``12450`` are one amount:
    ``Decimal`` compares and hashes by numeric value, not by its representation.
    """
    window = ("valid_from", "valid_to")
    dumped = cast("Mapping[str, object]", row.model_dump())
    return tuple((key, dumped[key]) for key in sorted(dumped) if key not in window)


def _covers(row: _Row, day: date) -> bool:
    return row.valid_from <= day and (row.valid_to is None or row.valid_to >= day)


def _window(row: _Row) -> tuple[date, date | None]:
    return row.valid_from, row.valid_to


def _open_rows(parameter: ParameterDefinition, boundary: date) -> dict[_Content, set[tuple[date, date | None]]]:
    """The rows still in force on ``boundary``, by content, with their windows."""
    open_rows: dict[_Content, set[tuple[date, date | None]]] = {}
    for row in _filing_rows(parameter):
        if _covers(row, boundary):
            open_rows.setdefault(_content(row), set()).add(_window(row))
    return open_rows


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


def _rekeyed_across(earlier: ModeloRevision, later: ModeloRevision) -> tuple[str, ...]:
    """Parameters whose row, still open when ``later`` starts, comes back in ``later`` keyed from another day.

    The later edition removed the inherited row and added the same content, in
    force when it starts, keyed from a new first day; inheriting the open row
    states the same fact once. A row that keeps its first day and only gains or
    moves its last day is a real change to its window, and a value that recurs
    in an earlier, closed window is another row, so neither is a re-key.
    """
    following = {parameter.id: parameter for parameter in later.parameters}
    rekeyed: list[str] = []
    for parameter in earlier.parameters:
        successor = following.get(parameter.id)
        if successor is None:
            continue
        open_rows = _open_rows(parameter, later.valid_from)
        if any(
            row.valid_from not in {first for first, _ in open_rows[content]}
            for row in _filing_rows(successor)
            if _covers(row, later.valid_from) and (content := _content(row)) in open_rows
        ):
            rekeyed.append(parameter.id)
    return tuple(rekeyed)


def _stated_rows(later: ModeloRevision, authored: Mapping[str, object]) -> dict[str, tuple[_Row, ...]]:
    """The parameter rows ``later`` states itself rather than inherits.

    A parameter declared in the edition's own fragments states every row it
    carries; an override states the rows its sequence additions add.
    """
    hydrated = {parameter.id: parameter for parameter in later.parameters}
    stated: dict[str, tuple[_Row, ...]] = {}
    for declaration in cast("Iterable[Mapping[str, object]]", authored.get("parameters", ())):
        parameter_id = str(declaration["id"])
        if parameter_id in hydrated:
            stated[parameter_id] = (*stated.get(parameter_id, ()), *_filing_rows(hydrated[parameter_id]))
    for override in cast("Iterable[Mapping[str, object]]", authored.get("family_overrides", ())):
        if override.get("family") != "parameters":
            continue
        parameter_id = str(cast("Mapping[str, object]", override["selector"])["id"])
        additions = cast("Mapping[str, Iterable[object]]", override.get("sequence_additions", {}))
        added = tuple(
            row
            for sequence, model in _ROW_SEQUENCES.items()
            for raw in additions.get(sequence, ())
            if _is_filing_row(row := model.model_validate(raw))
        )
        stated[parameter_id] = (*stated.get(parameter_id, ()), *added)
    return stated


def _restates_open_row(
    earlier: ModeloRevision,
    later: ModeloRevision,
    authored_later: Mapping[str, object],
) -> tuple[str, ...]:
    """Parameters whose row, still open when ``later`` starts, ``later`` states again with its window unchanged."""
    stated = _stated_rows(later, authored_later)
    restated: list[str] = []
    for parameter in earlier.parameters:
        open_rows = _open_rows(parameter, later.valid_from)
        if any(_window(row) in open_rows.get(_content(row), ()) for row in stated.get(parameter.id, ())):
            restated.append(parameter.id)
    return tuple(restated)


def _editions(modelo: ModeloDefinition) -> list[ModeloRevision]:
    return sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, str(revision.id)))


def _edition_pairs() -> Iterable[tuple[str, ModeloRevision, ModeloRevision]]:
    for modelo in _modelos():
        for earlier, later in pairwise(_editions(modelo)):
            yield str(modelo.id), earlier, later


def test_no_edition_restates_an_unchanged_row_its_predecessor_closed() -> None:
    restated = {
        (modelo_id, str(earlier.id), str(later.id)): ids
        for modelo_id, earlier, later in _edition_pairs()
        if (ids := _restated_across(earlier, later))
    }
    assert restated == {}, restated


def test_no_edition_states_again_a_row_its_predecessor_leaves_open() -> None:
    authored = _authored_revisions()
    restated = {
        (modelo_id, str(earlier.id), str(later.id)): ids
        for modelo_id, earlier, later in _edition_pairs()
        if (ids := _restates_open_row(earlier, later, authored[modelo_id][str(later.id)]))
    }
    assert restated == {}, restated


def test_no_edition_rekeys_the_window_of_a_row_its_predecessor_leaves_open() -> None:
    rekeyed = {
        (modelo_id, str(earlier.id), str(later.id)): ids
        for modelo_id, earlier, later in _edition_pairs()
        if (ids := _rekeyed_across(earlier, later))
    }
    assert rekeyed == {}, rekeyed


_DETECTOR_PARAMETER = {
    "id": "detector-parameter",
    "data_type": "decimal",
    "unit": "percent",
    "legal_refs": ("ley-35-2006:art-81",),
    "source_refs": ("aeat-detector-source",),
}


def _detector_parameter(*rows: Mapping[str, object]) -> ParameterDefinition:
    return ParameterDefinition.model_validate({**_DETECTOR_PARAMETER, "values": rows})


def _detector_row(value: str, valid_from: date, valid_to: date | None = None) -> dict[str, object]:
    return {"value": value, "date_axis": "filing_period", "valid_from": valid_from, "valid_to": valid_to}


def _live_pair(*, closed: bool) -> tuple[ModeloRevision, ModeloRevision]:
    """Two consecutive live editions starting on different days, the earlier one closed when ``closed`` is set."""
    return next(
        (a, b) for _, a, b in _edition_pairs() if a.valid_from < b.valid_from and (not closed or a.valid_to is not None)
    )


def test_a_closed_and_restated_row_is_detected() -> None:
    """The gate reports an unchanged row closed at one edition's end and restated by the next."""
    earlier, later = _live_pair(closed=True)
    closed = _detector_parameter(_detector_row("1", earlier.valid_from, earlier.valid_to))
    restated = _detector_parameter(_detector_row("1", later.valid_from))
    changed = _detector_parameter(_detector_row("2", later.valid_from))

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


def test_an_open_row_stated_again_by_a_later_edition_is_detected() -> None:
    """Inheriting an open row passes; the same row stated again by the later edition is reported."""
    earlier, later = _live_pair(closed=False)
    open_row = _detector_row("1", earlier.valid_from)
    predecessor = earlier.model_copy(update={"parameters": (_detector_parameter(open_row),)})
    successor = later.model_copy(update={"parameters": (_detector_parameter(open_row),)})
    selector = {"revision": str(earlier.id), "id": "detector-parameter"}

    assert _restates_open_row(predecessor, successor, {}) == ()
    assert _restates_open_row(predecessor, successor, {"parameters": [{"id": "detector-parameter"}]}) == (
        "detector-parameter",
    )
    readded = {"family": "parameters", "selector": selector, "sequence_additions": {"values": [open_row]}}
    assert _restates_open_row(predecessor, successor, {"family_overrides": [readded]}) == ("detector-parameter",)


def test_an_open_row_removed_and_readded_only_to_rekey_its_window_is_detected() -> None:
    """Inheriting an open row passes; the same content keyed from the later edition's start is reported."""
    earlier, later = _live_pair(closed=False)
    open_row = _detector_row("1", earlier.valid_from)
    predecessor = earlier.model_copy(update={"parameters": (_detector_parameter(open_row),)})
    inherited = later.model_copy(update={"parameters": (_detector_parameter(open_row),)})
    rekeyed = later.model_copy(update={"parameters": (_detector_parameter(_detector_row("1", later.valid_from)),)})

    assert _rekeyed_across(predecessor, inherited) == ()
    assert _rekeyed_across(predecessor, rekeyed) == ("detector-parameter",)


def test_a_genuine_change_to_an_open_row_is_not_reported() -> None:
    """Closing the open row and adding a different value is a real change, even when the close re-adds the row."""
    earlier, later = _live_pair(closed=False)
    predecessor = earlier.model_copy(
        update={"parameters": (_detector_parameter(_detector_row("1", earlier.valid_from)),)}
    )
    closed_row = _detector_row("1", earlier.valid_from, later.valid_from - timedelta(days=1))
    new_row = _detector_row("2", later.valid_from)
    successor = later.model_copy(update={"parameters": (_detector_parameter(closed_row, new_row),)})
    override = {
        "family": "parameters",
        "selector": {"revision": str(earlier.id), "id": "detector-parameter"},
        "sequence_additions": {"values": [closed_row, new_row]},
        "sequence_removals": {"values": [0]},
    }

    assert _restated_across(predecessor, successor) == ()
    assert _rekeyed_across(predecessor, successor) == ()
    assert _restates_open_row(predecessor, successor, {"family_overrides": [override]}) == ()


def _bracket_parameter(*rows: Mapping[str, object]) -> ParameterDefinition:
    return ParameterDefinition.model_validate(
        {**_DETECTOR_PARAMETER, "data_type": "bracket_table", "bracket_axis": "filing_period", "brackets": rows}
    )


def _bracket_row(lower: str, fixed: str, rate: str, valid_from: date) -> dict[str, object]:
    return {
        "lower_bound": lower,
        "upper_bound": None,
        "fixed_addition": fixed,
        "marginal_rate": rate,
        "valid_from": valid_from,
    }


def test_a_restatement_in_another_decimal_representation_is_detected() -> None:
    """``12450.00`` for ``12450`` and ``0.20`` for ``0.2`` restate the row; ``0.21`` changes it."""
    closing_earlier, closing_later = _live_pair(closed=True)
    closed = _detector_parameter(_detector_row("12450", closing_earlier.valid_from, closing_earlier.valid_to))
    assert _restated_across(
        closing_earlier.model_copy(update={"parameters": (closed,)}),
        closing_later.model_copy(
            update={"parameters": (_detector_parameter(_detector_row("12450.00", closing_later.valid_from)),)}
        ),
    ) == ("detector-parameter",)

    earlier, later = _live_pair(closed=False)
    predecessor = earlier.model_copy(
        update={"parameters": (_detector_parameter(_detector_row("0.2", earlier.valid_from)),)}
    )
    selector = {"revision": str(earlier.id), "id": "detector-parameter"}
    for value, reported in (("0.20", ("detector-parameter",)), ("0.21", ())):
        restated_row = _detector_row(value, earlier.valid_from)
        successor = later.model_copy(update={"parameters": (_detector_parameter(restated_row),)})
        readded = {"family": "parameters", "selector": selector, "sequence_additions": {"values": [restated_row]}}
        assert _restates_open_row(predecessor, successor, {"family_overrides": [readded]}) == reported, value


def test_a_rekey_in_another_decimal_representation_is_detected() -> None:
    """A value or a bracket rung re-keyed from the later edition's start in a new representation is reported."""
    earlier, later = _live_pair(closed=False)
    value_predecessor = earlier.model_copy(
        update={"parameters": (_detector_parameter(_detector_row("0.2", earlier.valid_from)),)}
    )
    bracket_predecessor = earlier.model_copy(
        update={"parameters": (_bracket_parameter(_bracket_row("12450", "1182.75", "0.12", earlier.valid_from)),)}
    )

    for value, reported in (("0.20", ("detector-parameter",)), ("0.21", ())):
        successor = later.model_copy(
            update={"parameters": (_detector_parameter(_detector_row(value, later.valid_from)),)}
        )
        assert _rekeyed_across(value_predecessor, successor) == reported, value
    for fixed, reported in (("1182.750", ("detector-parameter",)), ("1182.76", ())):
        successor = later.model_copy(
            update={"parameters": (_bracket_parameter(_bracket_row("12450.00", fixed, "0.120", later.valid_from)),)}
        )
        assert _rekeyed_across(bracket_predecessor, successor) == reported, fixed
