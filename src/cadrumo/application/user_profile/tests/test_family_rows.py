"""The leaves served for a descendant row cover every fact the row can store."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.descendant_relacion_catalogue import descendant_relacion_adoption_token
from ....domain.calculations.registry.tests.modelo_100_profile_binding_tables import FAMILY_ROW_BINDINGS
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.family_types import GuarderiaMonthSpend
from ....domain.user_profile.schema import ProfileFieldType
from ..family_rows import (
    ProfileFamilyGroupState,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_row_items,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Stored by the descendant record but asked by no wizard page, so no wording exists for it.
_STORED_WITHOUT_WORDING = frozenset({"segundo_ciclo_infantil_inicio_mes"})


def test_every_stored_descendant_leaf_but_one_has_served_wording() -> None:
    with bundled_indexed_authority().operation() as authority:
        full = DescendantInfo(
            birth_date=date(2021, 5, 17),
            relacion=descendant_relacion_adoption_token(authority=authority),
            inscripcion_registro_civil_date=date(2021, 9, 1),
            death_date=date(2025, 2, 3),
            discapacidad_grado=65,
            convive_con_contribuyente=False,
            dependencia_economica=True,
            custodia_compartida=True,
            rentas_anuales_euros=Decimal("10.25"),
            presenta_declaracion_propia=True,
            prorrata_minimo=False,
            meses_madre_trabajo=(3, 4),
            alta_posterior_nacimiento_mes=3,
            segundo_ciclo_infantil_inicio_mes=9,
            gastos_guarderia_mensuales=(GuarderiaMonthSpend(month=1, amount_euros=50),),
            nif="12345678Z",
        )
        stored = {
            path.removeprefix("renta_family.descendiente.0."): value
            for path, value in descendant_facts_from_list((full,), authority=authority)
            if path.startswith("renta_family.descendiente.0.")
        }
        values = {f"renta_family.descendiente.0.{leaf}": value for leaf, value in stored.items()}
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    group, row = items[0], items[1]
    assert isinstance(group, ProfileViewFamilyGroupItem) and isinstance(row, ProfileViewFamilyRowItem)
    served = {leaf.leaf for leaf in group.leaves}
    assert set(stored) - served == _STORED_WITHOUT_WORDING
    assert {fact.leaf for fact in row.facts} == set(stored) - _STORED_WITHOUT_WORDING


_ASCENDANT_OBJECT = "renta_family.ascendiente"
_ASCENDANT_COUNT = "renta_family.ascendientes_count"
# The Modelo 100 bindings read these two leaves from the object, but nothing can store them yet.
_BOUND_WITHOUT_STORED_LEAF = frozenset({"apellidos_nombre", "discapacidad_clave"})


def _ascendant_group(
    values: dict[str, str],
) -> tuple[ProfileViewFamilyGroupItem, tuple[ProfileViewFamilyRowItem, ...]]:
    with bundled_indexed_authority().operation() as authority:
        items = family_row_items(values, schema=authority.profile_schema(), operation=authority)
    group = next(
        item for item in items if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == _ASCENDANT_OBJECT
    )
    rows = tuple(
        item for item in items if isinstance(item, ProfileViewFamilyRowItem) and item.group_key == _ASCENDANT_OBJECT
    )
    return group, rows


def test_ascendant_leaves_are_those_the_form_reads_from_the_object_that_a_row_can_store() -> None:
    group, _ = _ascendant_group({})
    bound = {leaf for obj, leaf, _count in FAMILY_ROW_BINDINGS.values() if obj == _ASCENDANT_OBJECT}
    counts = {count for obj, _leaf, count in FAMILY_ROW_BINDINGS.values() if obj == _ASCENDANT_OBJECT}
    served = {leaf.leaf for leaf in group.leaves}
    assert bound - served == _BOUND_WITHOUT_STORED_LEAF
    assert served <= bound
    assert counts == {_ASCENDANT_COUNT}
    by_leaf = {leaf.leaf: leaf for leaf in group.leaves}
    assert by_leaf["birth_date"].field_type is ProfileFieldType.DATE and by_leaf["birth_date"].required
    assert by_leaf["fallecimiento"].field_type is ProfileFieldType.DATE and not by_leaf["fallecimiento"].required
    assert by_leaf["convivientes"].field_type is ProfileFieldType.INTEGER
    assert by_leaf["nif"].field_type is ProfileFieldType.STRING
    assert all(leaf.label and not leaf.choices for leaf in group.leaves)


def test_an_unstated_ascendant_household_is_unknown_and_a_stated_zero_is_declared_none() -> None:
    unknown, no_rows = _ascendant_group({})
    assert unknown.state is ProfileFamilyGroupState.UNKNOWN
    assert unknown.stated_count is None and unknown.row_count == 0 and not no_rows
    # A descendant count says nothing about ascendants.
    other, _ = _ascendant_group({"renta_family.descendientes_count": "0"})
    assert other.state is ProfileFamilyGroupState.UNKNOWN
    none_declared, rows = _ascendant_group({_ASCENDANT_COUNT: "0"})
    assert none_declared.state is ProfileFamilyGroupState.NONE_DECLARED
    assert none_declared.stated_count == "0" and not rows


def test_stored_ascendants_are_rows_holding_only_the_leaves_they_state() -> None:
    group, rows = _ascendant_group(
        {
            _ASCENDANT_COUNT: "2",
            f"{_ASCENDANT_OBJECT}.0.nif": "12345678Z",
            f"{_ASCENDANT_OBJECT}.0.birth_date": "1950-02-03",
            f"{_ASCENDANT_OBJECT}.0.convivientes": "2",
            f"{_ASCENDANT_OBJECT}.1.birth_date": "1948-07-09",
            f"{_ASCENDANT_OBJECT}.1.fallecimiento": "  ",
            # A leaf nothing stores, and a descendant row, are not ascendant facts.
            f"{_ASCENDANT_OBJECT}.1.apellidos_nombre": "Someone",
            "renta_family.descendiente.0.birth_date": "2020-01-01",
        }
    )
    assert group.state is ProfileFamilyGroupState.ROWS
    assert group.row_count == 2 and group.stated_count == "2"
    first, second = rows
    assert (first.row_index, second.row_index) == ("0", "1")
    assert [(fact.leaf, fact.value) for fact in first.facts] == [
        ("nif", "12345678Z"),
        ("birth_date", "1950-02-03"),
        ("convivientes", "2"),
    ]
    assert all(fact.path == f"{_ASCENDANT_OBJECT}.0.{fact.leaf}" and not fact.masked for fact in first.facts)
    assert [(fact.leaf, fact.value) for fact in second.facts] == [("birth_date", "1948-07-09")]


def test_stored_ascendants_beat_a_stated_zero_count() -> None:
    group, rows = _ascendant_group({_ASCENDANT_COUNT: "0", f"{_ASCENDANT_OBJECT}.0.birth_date": "1950-02-03"})
    assert group.state is ProfileFamilyGroupState.ROWS and len(rows) == 1
