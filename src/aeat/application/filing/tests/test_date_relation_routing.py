"""Regression tests for date-binding and relation routing in build_draft.

Before the fix, ``build_draft`` extracted only casilla, decimal-binding, and
enum-binding inputs from the flat ``ModeloInputs`` map; it never extracted the
date-binding (e.g. ``renta-2024-profile-taxpayer-birth-date`` consumed by
``age_at_year_end``) or the period-relation (e.g.
``renta-2024-rel-130-pagos-fraccionados``) inputs, and never passed them to
``calculate_registry_snapshot``'s ``date_binding_values`` / ``relation_values``
channels.

This made every ``work verify`` / ``work file`` replay of a draft that needed
those inputs crash at ``BUILDING_DRAFT`` with either
``date_binding '...' has no supplied value`` (input absent) or
``input '...' must be a Decimal value`` (ISO date wrongly coerced through the
Decimal channel). ``calculate_modelo_revision`` now persists the resolved
date-bindings on the revision's ``binding_overrides`` snapshot and relations on
``relation_overrides``; replay merges both into the flat input map, and
``build_draft`` routes them back onto their dedicated channels by registry
id-set — so the profile-independent verify replay reconstructs the identical
draft.

These tests guard each piece of that routing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import enum_consumed_binding_ids
from .. import (
    _bound_casilla_binding_ids,
    _date_binding_ids,
    _date_inputs_for_ids,
    _formula_binding_ids,
    _relation_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M100_BIRTH_DATE_BINDING = "renta-2024-profile-taxpayer-birth-date"
_M100_RELATIONS = (
    "renta-2024-rel-130-pagos-fraccionados",
    "renta-2024-rel-131-pagos-fraccionados",
)


def _m100_snapshot():  # type: ignore[return]
    return resources().modelos.authority.snapshot("100", filing_year=2024, period="0A", on=None)


def test_date_binding_ids_identifies_m100_birth_date() -> None:
    """The taxpayer birth-date date-binding must be discovered from the formulas.

    ``age_at_year_end`` (mínimo del contribuyente) consumes it on the
    ``date_binding`` channel; a regression that stops discovering it sends the
    ISO date through the Decimal channel and reds every M100 verify.
    """
    snap = _m100_snapshot()
    assert _M100_BIRTH_DATE_BINDING in _date_binding_ids(snap)


def test_relation_ids_identifies_m100_pago_fraccionado_relations() -> None:
    """The M130/M131 instalment relations must be discoverable for replay."""
    snap = _m100_snapshot()
    relation_ids = _relation_ids(snap)
    for relation in _M100_RELATIONS:
        assert relation in relation_ids, relation


def test_date_inputs_for_ids_parses_iso_date_strings() -> None:
    """ISO date strings persisted on the revision snapshot parse back to ``date``."""
    inputs = {
        _M100_BIRTH_DATE_BINDING: "1985-05-15",
        "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
    }
    result = _date_inputs_for_ids(inputs, {_M100_BIRTH_DATE_BINDING})
    assert result == {_M100_BIRTH_DATE_BINDING: date(1985, 5, 15)}


def test_date_inputs_for_ids_rejects_non_iso_value() -> None:
    """A corrupt (non-ISO) date value is refused, not silently dropped."""
    from ....domain.filing._errors import ModeloBuilderError

    with pytest.raises(ModeloBuilderError):
        _date_inputs_for_ids({_M100_BIRTH_DATE_BINDING: "not-a-date"}, {_M100_BIRTH_DATE_BINDING})


def test_birth_date_excluded_from_decimal_channel() -> None:
    """The birth-date binding must never reach the Decimal extraction set.

    It is a BOUND-casilla binding (so it appears in ``calculation_binding_ids``)
    *and* a date-binding. ``build_draft`` removes the date-binding ids from the
    Decimal set; this asserts that subtraction so a ``Decimal("1985-05-15")``
    crash cannot reappear.
    """
    snap = _m100_snapshot()
    calculation_binding_ids = _formula_binding_ids(snap) | _bound_casilla_binding_ids(snap)
    enum_binding_ids = enum_consumed_binding_ids(snap.revision)
    date_binding_ids = _date_binding_ids(snap)
    relation_ids = _relation_ids(snap)
    decimal_binding_ids = calculation_binding_ids - enum_binding_ids - date_binding_ids - relation_ids

    assert _M100_BIRTH_DATE_BINDING in date_binding_ids
    assert _M100_BIRTH_DATE_BINDING not in decimal_binding_ids
