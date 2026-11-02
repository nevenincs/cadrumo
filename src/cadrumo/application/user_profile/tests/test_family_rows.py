"""The leaves served for a descendant row cover every fact the row can store."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.descendant_relacion_catalogue import descendant_relacion_adoption_token
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.family_types import GuarderiaMonthSpend
from ..family_rows import ProfileViewFamilyGroupItem, ProfileViewFamilyRowItem, family_row_items

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
