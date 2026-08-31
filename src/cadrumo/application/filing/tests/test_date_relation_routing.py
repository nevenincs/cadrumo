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

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.runtime_graph import enum_consumed_binding_ids
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.submission.models import ModeloDraftStatus
from .._draft_construction import (
    _bound_casilla_binding_ids,
    _date_binding_ids,
    _date_inputs_for_ids,
    _formula_binding_ids,
    _relation_ids,
    _string_inputs_for_ids,
    build_draft,
)
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_M100_BIRTH_DATE_BINDING = "renta-2024-profile-taxpayer-birth-date"
_M100_TAX_RESIDENCE_CCAA_BINDING = "renta-2024-profile-tax-residence-ccaa"
_M100_ESTIMACION_DIRECTA_NORMAL_BINDING = "renta-2024-modelo-100-estimacion-directa-es-normal"
_M100_RELATIONS = (
    "renta-2024-rel-130-pagos-fraccionados",
    "renta-2024-rel-131-pagos-fraccionados",
)


def _m100_snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=2024, period="0A", on=None)


def _profile() -> ModeloOperatorProfile:
    return ModeloOperatorProfile(tax_id="12345678Z", display_name="M100 enum replay")


def test_date_binding_ids_identifies_m100_birth_date() -> None:
    """The taxpayer birth-date date-binding must be discovered from the formulas.

    ``age_at_year_end`` (mínimo del contribuyente) consumes it on the
    ``date_binding`` channel; a regression that stops discovering it sends the
    ISO date through the Decimal channel and reds every M100 verify.
    """
    snap = _m100_snapshot()
    assert _M100_BIRTH_DATE_BINDING in _date_binding_ids(snap)


def test_formula_binding_ids_traverses_nested_committed_m100_expression() -> None:
    """The filing replay path must retain the nested direct-estimation binding leaf."""
    snap = _m100_snapshot()

    assert _M100_ESTIMACION_DIRECTA_NORMAL_BINDING in _formula_binding_ids(snap)


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
    from ....domain.filing.errors import ModeloBuilderError

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


def test_tax_residence_ccaa_excluded_from_decimal_channel() -> None:
    """The M100 tax-residence CCAA enum must never reach Decimal extraction.

    ``work verify`` replay passes persisted profile bindings back through
    ``build_draft`` as a flat input map.  The CCAA selector is a string enum
    value, so ``build_draft`` must route it through ``enum_binding_values`` and
    exclude it from the Decimal id-set before calling ``_decimal_inputs_for_ids``.
    """
    snap = _m100_snapshot()
    calculation_binding_ids = _formula_binding_ids(snap) | _bound_casilla_binding_ids(snap)
    enum_binding_ids = enum_consumed_binding_ids(snap.revision)
    date_binding_ids = _date_binding_ids(snap)
    relation_ids = _relation_ids(snap)
    decimal_binding_ids = calculation_binding_ids - enum_binding_ids - date_binding_ids - relation_ids

    assert _M100_TAX_RESIDENCE_CCAA_BINDING in enum_binding_ids
    assert _M100_TAX_RESIDENCE_CCAA_BINDING not in decimal_binding_ids
    assert _string_inputs_for_ids(
        {_M100_TAX_RESIDENCE_CCAA_BINDING: "madrid"},
        enum_binding_ids,
    ) == {_M100_TAX_RESIDENCE_CCAA_BINDING: "madrid"}


def test_build_draft_replay_routes_m100_tax_residence_ccaa_string_enum() -> None:
    """Replay-style build_draft inputs route the CCAA string through enum values."""
    period = Period.from_year_and_code(2024, "0A")
    draft = build_draft(
        modelo="100",
        period=period,
        profile=_profile(),
        inputs={
            "0003": Decimal("10000"),
            _M100_TAX_RESIDENCE_CCAA_BINDING: "madrid",
            _M100_BIRTH_DATE_BINDING: "1975-06-15",
            _M100_ESTIMACION_DIRECTA_NORMAL_BINDING: "1",
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
            "renta-2024-profile-declaration-type": Decimal("1"),
            "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
            "renta-2024-profile-incremento-guarderia": Decimal("0"),
            "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
            "renta-2024-profile-descendientes-guarderia": Decimal("0"),
            "renta-2024-profile-marriage-full-year": Decimal("0"),
            "renta-2024-profile-marriage-month-start": Decimal("0"),
            "renta-2024-profile-marriage-month-end": Decimal("0"),
            "renta-2024-profile-anualidades-sin-minimo-descendientes": Decimal("0"),
            # Childless profile: Art. 58/61 LIRPF mínimo por descendientes aggregate
            # is zero.
            "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
            # Parte autonómica: non-Madrid profile mirrors the estatal zero.
            "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
            "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
            "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
            "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
            "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
            "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
            "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
            "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
        },
        schema_provider=build_runtime_schema_provider(modelos=("100",), filing_year=2024, period=period),
    )

    assert draft.modelo == "100"
    assert draft.status is ModeloDraftStatus.LISTO_PARA_PRESENTAR
    assert next(value.value for value in draft.values if value.casilla_id == "0003") == Decimal("10000")
