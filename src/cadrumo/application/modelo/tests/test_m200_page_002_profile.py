"""Modelo 200 page 002 rows come from the taxpayer profile, or the export refuses with a door."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.form_codes import form_for_role
from ....domain.calculations.registry.m200_page_002_rules import resolve_m200_page_002_rules
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ....domain.calculations.registry.tests.authored_editions import open_ended_revision, revision_first_exercise
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileFactValue,
    UserProfileRecord,
    create_user_profile_record,
)
from ...filing.m200_projection import (
    m200_projection_families,
    m200_projection_field_widths,
    m200_projection_slot_limits,
)
from ...operations.next_step import OperationOpenProfileFieldStepV1
from ..action_errors import ModeloProfileReadinessError
from ..m200_page_002_profile import (
    M200Page002FamilyState,
    M200Page002Refusal,
    m200_page_002_family_answers,
    modelo_200_profile_facts,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5d0c7e1b-3a64-4f8e-b2a9-6c1d9e4f7a30"
_AT = datetime.fromtimestamp(0, tz=UTC)
_ADMINISTRADOR_NIF = "Y0000000Z"
_SOCIO_NIF = "Y0000001S"
_ANSWERED_NONE = (
    "has_secretario_consejo",
    "has_participacion_directa",
    "has_establecimiento_permanente",
    "has_socio_sicav_disolucion",
)


def _work_unit() -> tuple[WorkUnit, ExportLayoutDefinition]:
    modelo = form_for_role("sociedades.annual")
    exercise = revision_first_exercise(modelo, str(open_ended_revision(modelo).id))
    period = Period.from_year_and_code(exercise, "0A")
    snapshot = published_snapshot(modelo, filing_year=exercise, period="0A", grade=RegistryAuthorityGrade.CALCULATION)
    revision_id = str(snapshot.revision.id)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=exercise,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=exercise,
        period=period,
        revision_id=revision_id,
        name="Annual return",
        created_at=_AT,
        updated_at=_AT,
        state=WorkUnitState.BORRADOR,
    )
    return work_unit, snapshot.revision.export_layouts[0]


def _record(operation: PinnedAuthorityOperation, facts: dict[str, UserProfileFactValue]) -> UserProfileRecord:
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=tuple(UserProfileFact(path=path, value=value) for path, value in facts.items()),
        context=operation.profile_create_context(),
    )


def _sociedad_limitada(**overrides: UserProfileFactValue | None) -> dict[str, UserProfileFactValue]:
    facts: dict[str, UserProfileFactValue | None] = {
        "taxpayer_type.entity_type": "legal_entity",
        "taxpayer_type.legal_entity_form": "sl",
        "taxpayer_type.fiscal_residency": "resident_irpf",
        "m200_administrador.0.nif": _ADMINISTRADOR_NIF,
        "m200_administrador.0.apellidos_nombre_razon_social": "ADMINISTRADORA PRUEBA",
        "m200_administrador.0.forma_juridica": "F",
        "m200_participacion_socio.0.nif": _SOCIO_NIF,
        "m200_participacion_socio.0.representante": False,
        "m200_participacion_socio.0.forma_juridica": "F",
        "m200_participacion_socio.0.apellidos_nombre_razon_social": "SOCIA PRUEBA",
        "m200_participacion_socio.0.codigo_provincia_pais": "28",
        "m200_participacion_socio.0.nominal": Decimal("3000.00"),
        "m200_participacion_socio.0.porcentaje_participacion": Decimal("100"),
        "m200_relaciones.has_participacion_socio": True,
        "m200_representante_legal.0.apellidos_y_nombre": "ADMINISTRADORA PRUEBA",
        "m200_representante_legal.0.nif": _ADMINISTRADOR_NIF,
        "m200_representante_legal.0.fecha_poder": _AT.date(),
        "m200_representante_legal.0.notaria_otros": "MADRID",
        "m200_relaciones.has_representante_legal": True,
        **{f"m200_relaciones.{field}": False for field in _ANSWERED_NONE},
    }
    facts.update(overrides)
    return {path: value for path, value in facts.items() if value is not None}


def _refusal(
    operation: PinnedAuthorityOperation, facts: dict[str, UserProfileFactValue]
) -> ModeloProfileReadinessError:
    work_unit, layout = _work_unit()
    with pytest.raises(ModeloProfileReadinessError) as raised:
        modelo_200_profile_facts(
            work_unit=work_unit,
            operation=operation,
            export_layout=layout,
            profile_record=_record(operation, facts),
        )
    return raised.value


def test_a_sociedad_limitada_profile_fills_the_administrador_and_socio_rows(
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit, layout = _work_unit()
    families = m200_projection_families(work_unit.period.end_date, authority=operation)

    facts = modelo_200_profile_facts(
        work_unit=work_unit,
        operation=operation,
        export_layout=layout,
        profile_record=_record(operation, _sociedad_limitada()),
    )

    rows = facts.projection_rows
    (administrador,) = getattr(rows, families["m200_administrador"])
    assert administrador.model_dump() == {
        "nif": _ADMINISTRADOR_NIF,
        "apellidos_nombre_razon_social": "ADMINISTRADORA PRUEBA",
        "forma_juridica": "F",
        "representante": None,
        "domicilio_fiscal": None,
        "codigo_provincia": None,
    }
    (socio,) = getattr(rows, families["m200_participacion_socio"])
    assert socio.model_dump() == {
        "nif": _SOCIO_NIF,
        "representante": "0",
        "forma_juridica": "F",
        "apellidos_nombre_razon_social": "SOCIA PRUEBA",
        "codigo_provincia_pais": "28",
        "nominal": "3000.00",
        "porcentaje_participacion": "100",
    }
    (representante,) = getattr(rows, families["m200_representante_legal"])
    assert (representante.nif, representante.apellidos_y_nombre, representante.notaria_otros) == (
        _ADMINISTRADOR_NIF,
        "ADMINISTRADORA PRUEBA",
        "MADRID",
    )
    filled = {
        families["m200_administrador"],
        families["m200_participacion_socio"],
        families["m200_representante_legal"],
    }
    assert all(getattr(rows, name) == () for name in type(rows).model_fields if name not in filled)


def test_a_resident_declarant_leaves_the_administrador_irnr_fields_blank(
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit, layout = _work_unit()
    families = m200_projection_families(work_unit.period.end_date, authority=operation)

    facts = modelo_200_profile_facts(
        work_unit=work_unit,
        operation=operation,
        export_layout=layout,
        profile_record=_record(
            operation,
            _sociedad_limitada(**{"m200_administrador.0.domicilio_fiscal": "CALLE PRUEBA 1"}),
        ),
    )

    (administrador,) = getattr(facts.projection_rows, families["m200_administrador"])
    assert administrador.model_dump()["domicilio_fiscal"] is None


def test_a_profile_without_an_administrador_refuses_with_a_door_to_its_nif(
    operation: PinnedAuthorityOperation,
) -> None:
    refusal = _refusal(
        operation,
        _sociedad_limitada(
            **{
                "m200_administrador.0.nif": None,
                "m200_administrador.0.apellidos_nombre_razon_social": None,
                "m200_administrador.0.forma_juridica": None,
            }
        ),
    )

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.ROWS_REQUIRED.value
    assert refusal.context["profile_path"] == "m200_administrador.nif"
    step = refusal.operation_next_step(OutputLanguage.ES)
    assert isinstance(step, OperationOpenProfileFieldStepV1)
    assert step.path == "m200_administrador.nif"


def test_a_sociedad_limitada_cannot_state_it_has_no_socios(operation: PinnedAuthorityOperation) -> None:
    socio_paths = {path: None for path in _sociedad_limitada() if path.startswith("m200_participacion_socio.")}
    refusal = _refusal(
        operation,
        _sociedad_limitada(**socio_paths, **{"m200_relaciones.has_participacion_socio": False}),
    )

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.NONE_REFUSED_FOR_FORM.value
    assert refusal.context["entity_form"] == "sl"


def test_a_declarant_cannot_state_it_has_no_representante_legal(operation: PinnedAuthorityOperation) -> None:
    representante_paths = {path: None for path in _sociedad_limitada() if path.startswith("m200_representante_legal.")}
    refusal = _refusal(
        operation,
        _sociedad_limitada(**representante_paths, **{"m200_relaciones.has_representante_legal": False}),
    )

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.NONE_REFUSED_FOR_FORM.value
    assert refusal.context["profile_section"] == "m200_representante_legal"


def test_socio_percentages_short_of_one_hundred_refuse(operation: PinnedAuthorityOperation) -> None:
    refusal = _refusal(
        operation,
        _sociedad_limitada(**{"m200_participacion_socio.0.porcentaje_participacion": Decimal("99.99")}),
    )

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.PERCENTAGE_TOTAL.value
    assert refusal.context["percentage_sum"] == "99.99"
    assert refusal.context["profile_path"] == "m200_participacion_socio.porcentaje_participacion"


def test_an_unanswered_family_refuses_with_a_door_to_its_answer(operation: PinnedAuthorityOperation) -> None:
    refusal = _refusal(operation, _sociedad_limitada(**{"m200_relaciones.has_secretario_consejo": None}))

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.FAMILY_UNANSWERED.value
    assert refusal.context["profile_path"] == "m200_relaciones.has_secretario_consejo"


def test_a_stated_none_contradicted_by_rows_refuses(operation: PinnedAuthorityOperation) -> None:
    refusal = _refusal(operation, _sociedad_limitada(**{"m200_relaciones.has_participacion_socio": False}))

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.ROWS_CONTRADICT_ANSWER.value


def test_an_incomplete_row_names_its_missing_field(operation: PinnedAuthorityOperation) -> None:
    refusal = _refusal(operation, _sociedad_limitada(**{"m200_participacion_socio.0.nominal": None}))

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.ROW_INCOMPLETE.value
    assert refusal.context["profile_path"] == "m200_participacion_socio.nominal"


def test_the_entidades_menores_family_is_served_as_not_applicable_to_a_sociedad_limitada(
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit, _ = _work_unit()
    as_of = work_unit.period.end_date
    rules = resolve_m200_page_002_rules(operation, effective_date=as_of)

    answers = {
        answer.section: answer
        for answer in m200_page_002_family_answers(_record(operation, _sociedad_limitada()), rules=rules, as_of=as_of)
    }

    entidad_menor = answers["m200_entidad_menor_dependiente"]
    assert entidad_menor.state is M200Page002FamilyState.NOT_APPLICABLE
    assert entidad_menor.deciding_fact == "taxpayer_type.legal_entity_form"
    assert entidad_menor.deciding_value == "sl"
    assert answers["m200_administrador"].state is M200Page002FamilyState.ROWS
    assert answers["m200_secretario_consejo"].state is M200Page002FamilyState.STATED_NONE


def test_rows_beyond_the_design_places_refuse(operation: PinnedAuthorityOperation) -> None:
    work_unit, layout = _work_unit()
    places = m200_projection_slot_limits(layout)["m200_administrador"]
    extra: dict[str, UserProfileFactValue | None] = {}
    for index in range(1, places + 1):
        extra[f"m200_administrador.{index}.nif"] = _ADMINISTRADOR_NIF
        extra[f"m200_administrador.{index}.apellidos_nombre_razon_social"] = "ADMINISTRADORA PRUEBA"
        extra[f"m200_administrador.{index}.forma_juridica"] = "F"

    refusal = _refusal(operation, _sociedad_limitada(**extra))

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.ROWS_EXCEED_DESIGN.value
    assert refusal.context["slots"] == places
    assert refusal.context["modelo"] == str(work_unit.modelo)


def test_a_name_wider_than_its_design_place_refuses_naming_the_field_and_limit(
    operation: PinnedAuthorityOperation,
) -> None:
    _, layout = _work_unit()
    limit = m200_projection_field_widths(layout)[("m200_administrador", "apellidos_nombre_razon_social")]
    name = "FERREIRA COSTA ANA".ljust(limit + 1, "A")

    refusal = _refusal(operation, _sociedad_limitada(**{"m200_administrador.0.apellidos_nombre_razon_social": name}))

    assert refusal.context is not None
    assert refusal.context["reason"] == M200Page002Refusal.VALUE_EXCEEDS_DESIGN.value
    assert refusal.context["field"] == "apellidos_nombre_razon_social"
    assert refusal.context["limit"] == limit
    assert refusal.context["length"] == limit + 1
    assert refusal.context["profile_path"] == "m200_administrador.apellidos_nombre_razon_social"
    assert name not in str(refusal.context.values())


def test_a_name_exactly_as_wide_as_its_design_place_is_carried(operation: PinnedAuthorityOperation) -> None:
    work_unit, layout = _work_unit()
    families = m200_projection_families(work_unit.period.end_date, authority=operation)
    limit = m200_projection_field_widths(layout)[("m200_administrador", "apellidos_nombre_razon_social")]
    name = "FERREIRA COSTA ANA".ljust(limit, "A")

    facts = modelo_200_profile_facts(
        work_unit=work_unit,
        operation=operation,
        export_layout=layout,
        profile_record=_record(
            operation, _sociedad_limitada(**{"m200_administrador.0.apellidos_nombre_razon_social": name})
        ),
    )

    (administrador,) = getattr(facts.projection_rows, families["m200_administrador"])
    assert administrador.apellidos_nombre_razon_social == name
