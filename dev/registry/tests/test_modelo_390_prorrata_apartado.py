"""Modelo 390 apartado 12 boxes 114 to 118 are register-bound casillas exported on page 7 every supported year.

The record design prints, for each of five activity rows, the CNAE code [114],
the volume of operations [115], the volume with the right to deduct [116], the
kind of prorrata [117] ("G", "E" or blank) and the definitive percentage [118].
Every one of those twenty-five slots is a casilla bound to its row of the
profile's prorrata register; none is an operator input, and each has exactly
one position in the page 7 record, so a value rendered there reads back the
same.

External authority: the record design of each bundled edition (page 7,
apartado 12), and the AEAT Modelo 303 instructions for the same per-activity
prorrata rows ("se consignara el codigo correspondiente a la Clasificacion
Nacional de Actividades Economicas ...").

Non-tautology: the read-back goes through the real fixed-width renderer and
parser; a CNAE code that lost its leading zero, an amount at the wrong scale
or a box at another box's position fails. The row geometry is checked against
the design's own layout rule, five adjacent boxes per row at one stride.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.fixed_width_parser import parse_fixed_width_export_field
from cadrumo.domain.calculations.registry.prorrata_register_activity_bindings import (
    ProrrataRegisterActivityProvider,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_FACTS = ("codigo-cnae", "importe-operaciones", "importe-con-derecho", "tipo", "porcentaje")
_BOXES = dict(zip(_FACTS, ("114", "115", "116", "117", "118"), strict=True))
_SLOTS = range(1, 6)


def _revision(year: int) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.snapshot(
            "390", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
        ).revision


def _casilla_id(slot: int, fact: str) -> str:
    return f"iva.anual.prorrata.actividad-{slot}.{fact}"


def _value(fact: str, field: ExportFieldDefinition) -> str | Decimal:
    """A row of a dental practice's register, sized to the slot the design prints."""
    match fact:
        case "codigo-cnae":
            # CNAE 0113 keeps its leading zero at either printed width.
            assert field.length is not None
            return "0113"[: field.length]
        case "importe-operaciones":
            return Decimal("72650.00")
        case "importe-con-derecho":
            return Decimal("58120.00")
        case "tipo":
            return "G"
        case _:
            return Decimal("80.00")


def _fields(revision: ModeloRevision) -> dict[str, list[ExportFieldDefinition]]:
    found: dict[str, list[ExportFieldDefinition]] = {}
    for layout in derive_export_layouts_from_bindings(revision):
        for record in layout.records:
            for field in record.fields:
                if field.casilla_id is not None:
                    found.setdefault(str(field.casilla_id), []).append(field)
    return found


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_every_apartado_box_is_bound_to_its_register_row(year: int) -> None:
    revision = _revision(year)
    casillas = {str(casilla.id): casilla for casilla in revision.casillas}
    bindings = {str(binding.id): binding for binding in revision.bindings}
    for slot in _SLOTS:
        for fact in _FACTS:
            casilla = casillas[_casilla_id(slot, fact)]
            assert casilla.form_number == _BOXES[fact]
            assert casilla.binding is not None
            provider = bindings[str(casilla.binding)].provider
            assert isinstance(provider, ProrrataRegisterActivityProvider)
            assert provider.slot == slot
    operator_inputs = [
        str(binding.id)
        for binding in revision.bindings
        if str(binding.id).startswith("modelo-390.page_7.prorratas-")
        and not str(binding.id).endswith("-actividad-desarrollada")
    ]
    assert operator_inputs == [], f"{year}: an apartado 12 box is still offered as an operator input"


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_every_apartado_box_round_trips_through_its_one_page_7_slot(year: int) -> None:
    fields = _fields(_revision(year))
    offsets: dict[int, list[int]] = {}
    for slot in _SLOTS:
        for fact in _FACTS:
            slots = fields.get(_casilla_id(slot, fact), [])
            assert len(slots) == 1, f"{year}: box [{_BOXES[fact]}] row {slot} must have exactly one export slot"
            (field,) = slots
            value = _value(fact, field)
            wire = render_fixed_width_export_field(field, value)
            assert len(wire) == field.length
            assert parse_fixed_width_export_field(field, wire) == value
            assert field.offset is not None
            offsets.setdefault(slot, []).append(field.offset)
    row_width = {slot: sum(fields[_casilla_id(slot, fact)][0].length or 0 for fact in _FACTS) for slot in _SLOTS}
    for slot in _SLOTS:
        row = [fields[_casilla_id(slot, fact)][0] for fact in _FACTS]
        for left, right in pairwise(row):
            assert left.offset is not None
            assert left.length is not None
            assert right.offset == left.offset + left.length, f"{year}: row {slot} boxes are not adjacent"
        assert row_width[slot] == row_width[1]
    strides = {offsets[slot + 1][0] - offsets[slot][0] for slot in range(1, 5)}
    assert len(strides) == 1, f"{year}: activity rows do not repeat at one stride"
