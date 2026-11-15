"""The Modelo 200 work form names a rotating slot's year for the ejercicio being filed.

A rotating slot's caption names a year counted from the ejercicio (a deduction
generated five years earlier, the ejercicio's own negative base), so the form
for one ejercicio must name that year, not a relative token. Real behaviour
throughout: an isolated encrypted profile, the bundled authority and the
production form service, for every ejercicio Modelo 200 authors an edition for.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ....application.modelo.work_form_field_vocabulary import ModeloFormCasillaAddressV1
from ....application.modelo.work_form_models import ModeloWorkForm
from ....application.modelo.work_form_service import load_modelo_work_form
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import OutputLanguage
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import supported_authored_exercises
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "200"
_PERIOD = "0A"
_ENTITY = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="identity.legal_name", value="Test Company SL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
    UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
    UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
)


def _rotating_offsets(year: int) -> dict[str, int]:
    """The rotating-slot offset of every casilla the edition serving ``year`` declares one for."""
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot(
            _MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
        )
        return {
            str(casilla.id): casilla.rotating_year_offset
            for casilla in snapshot.revision.casillas
            if casilla.rotating_year_offset is not None
        }


def _form(work: SeededOperatorWork, language: OutputLanguage) -> ModeloWorkForm:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=work.admit(),
        language=language,
    ).form


@pytest.mark.parametrize("year", supported_authored_exercises(_MODELO))
@pytest.mark.parametrize("language", [OutputLanguage.ES, OutputLanguage.HU])
def test_every_rotating_slot_on_the_form_names_its_year(tmp_path: Path, year: int, language: OutputLanguage) -> None:
    offsets = _rotating_offsets(year)
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path,
            modelo=_MODELO,
            filing_year=year,
            period_code=_PERIOD,
            extra_facts=_ENTITY,
            estimation_regime=None,
        ) as work,
    ):
        form = _form(work, language)

    slots = [
        (field.address.casilla_id, field, offsets[field.address.casilla_id])
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1) and field.address.casilla_id in offsets
    ]
    assert slots, f"the {year} form shows no rotating slot, so this check proves nothing"
    wrong = [
        f"{casilla_id}: {field.label.text!r}"
        for casilla_id, field, offset in slots
        if str(year - offset) not in field.label.text or "{year}" in field.label.text
    ]
    assert wrong == []
