"""Modelo 840 reads the stored facts of the one activity it declares.

A local afecto indirectamente belongs to Apartado V, not to the Anexo "Relación de
locales"; one Modelo 840 declares one activity, so facts naming two activities are
refused rather than mixed onto one declaration. Apartado V and Apartado VI C each
describe one local, and an unstated figure stays absent rather than reading zero.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.contribuyente.iae_local_facts import (
    IAE_ELEMENTO_TRIBUTARIO_SECTION,
    IAE_LOCAL_SECTION,
    IAE_LOCAL_SUPERFICIE_SECTION,
)
from ....domain.contribuyente.iae_local_record import SuperficieRegla14Clase
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...filing.producer_snapshot_m840 import Modelo840ElementoLinea, Modelo840LocalRow, Modelo840SuperficieClase
from ..action_errors import ModeloProfileReadinessError
from ..m840_anexo_profile import modelo_840_profile_facts

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "840"
_PERIOD = "0A"
_BUCKET_ID = "m840-anexo-profile"


def _work_unit() -> WorkUnit:
    snapshot = published_snapshot(_MODELO, filing_year=filing_year_envelope().horizon, period=_PERIOD)
    year = snapshot.snapshot_ref.modelo_year
    period = Period.from_year_and_code(year, _PERIOD)
    stamp = datetime(year, 1, 1, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo=_MODELO, filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET_ID,
        modelo=_MODELO,
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="m840-anexo",
        created_at=stamp,
        updated_at=stamp,
    )


def _local(row: int, **leaves: str) -> dict[str, object]:
    return {f"{IAE_LOCAL_SECTION}.{row}.{leaf}": value for leaf, value in leaves.items()}


def test_only_exercised_premises_fill_the_anexo_in_stored_order() -> None:
    path_values = (
        _local(4, actividad="0", afectacion="ejercicio", via_nombre="CALLE MAYOR", numero="7", superficie_total="120")
        | _local(1, actividad="0", afectacion="indirecta", via_nombre="ALMACEN NORTE")
        | _local(2, actividad="0", afectacion="ejercicio", postcode="50001", municipality_name="ZARAGOZA")
    )

    facts = modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert facts.local_rows == (
        Modelo840LocalRow(codigo_postal="50001", municipio_nombre="ZARAGOZA"),
        Modelo840LocalRow(nombre_via="CALLE MAYOR", numero=7, total=120),
    )


def test_a_profile_without_premises_lists_none() -> None:
    assert modelo_840_profile_facts(work_unit=_work_unit(), path_values={}).local_rows == ()


def test_exercised_premises_of_two_activities_are_refused() -> None:
    path_values = _local(1, actividad="0", afectacion="ejercicio") | _local(2, actividad="1", afectacion="ejercicio")

    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert refused.value.translated_message == "application.modelo.errors.m840_anexo_activities_ambiguous"
    assert (refused.value.context or {})["activities"] == "0, 1"


def _row(section: str, row: int, **leaves: str) -> dict[str, object]:
    return {f"{section}.{row}.{leaf}": value for leaf, value in leaves.items()}


def test_the_declaration_header_reads_the_stored_censo_and_fiscal_address() -> None:
    path_values: dict[str, object] = {
        "censo.aeat_delegacion_code": "28",
        "censo.aeat_administracion_code": "286",
        "censo.aeat_administracion_name": "MADRID CENTRO",
        "contact.fiscal_address_municipality_name": "ALCALA DE HENARES",
    }

    facts = modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert facts.delegacion_codigo == "28"
    assert facts.administracion_codigo == "286"
    assert facts.administracion_nombre == "MADRID CENTRO"
    assert facts.sujeto_pasivo_municipio == "ALCALA DE HENARES"


def test_the_activity_the_premises_name_supplies_its_facts_lines_and_apartado_v() -> None:
    path_values = (
        _row("activities", 0, description="COMERCIO", municipality_name="MADRID", maquinas_recreativas_tipo_a="9")
        | _row(
            "activities",
            1,
            description="TALLER",
            municipality_name="ZARAGOZA",
            cuota_provincial_province_code="50",
            maquinas_recreativas_tipo_b="2",
            expositores_autoventa="0",
        )
        | _local(3, actividad="1", afectacion="ejercicio")
        | _local(5, actividad="1", afectacion="indirecta", municipality_name="UTEBO")
        | _row(IAE_ELEMENTO_TRIBUTARIO_SECTION, 0, actividad="1", linea="2", code="OB", numero="3.50")
    )

    facts = modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert facts.actividad_municipio == "ZARAGOZA"
    assert facts.actividad_provincia_codigo == "50"
    assert facts.local_indirecto_municipio == "UTEBO"
    assert facts.elementos == (Modelo840ElementoLinea(linea=2, codigo="OB", numero=Decimal("3.50")),)
    assert (facts.maquinas_tipo_a, facts.maquinas_tipo_b, facts.expositores_autoventa) == (None, 2, 0)


def test_without_premises_the_one_activity_stating_modelo_840_facts_is_declared() -> None:
    path_values = _row("activities", 0, description="ASESORIA") | _row(
        "activities", 1, description="FERIA", municipality_name="HUESCA"
    )

    facts = modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert facts.actividad_municipio == "HUESCA"
    assert facts.local_rows == ()


def test_two_activities_stating_modelo_840_facts_without_premises_are_refused() -> None:
    path_values = _row("activities", 0, municipality_name="HUESCA") | _row("activities", 2, expositores_autoventa="1")

    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    context = refused.value.context or {}
    assert refused.value.translated_message == "application.modelo.errors.m840_anexo_activities_ambiguous"
    assert (context["activities"], context["profile_section"]) == ("0, 2", "activities")


def test_a_tax_element_line_of_another_activity_is_refused() -> None:
    path_values = _local(1, actividad="0", afectacion="ejercicio") | _row(
        IAE_ELEMENTO_TRIBUTARIO_SECTION, 0, actividad="1", linea="1", code="KW", numero="5"
    )

    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    context = refused.value.context or {}
    assert context["activities"] == "0, 1"
    assert context["profile_section"] == f"{IAE_LOCAL_SECTION}, {IAE_ELEMENTO_TRIBUTARIO_SECTION}"


def test_apartado_vi_c_states_the_classes_of_the_exercised_local_and_keeps_unstated_figures_absent() -> None:
    path_values = (
        _local(1, actividad="0", afectacion="ejercicio")
        | _local(2, actividad="0", afectacion="indirecta")
        | _row(IAE_LOCAL_SUPERFICIE_SECTION, 0, local="1", clase="5.0", total="40", computable="21")
        | _row(IAE_LOCAL_SUPERFICIE_SECTION, 1, local="1", clase="0.1", total="120")
        | _row(IAE_LOCAL_SUPERFICIE_SECTION, 2, local="2", clase="0.1", total="999")
    )

    facts = modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    assert facts.superficies == (
        Modelo840SuperficieClase(clase=SuperficieRegla14Clase.SIN_REDUCCION, total=120),
        Modelo840SuperficieClase(clase=SuperficieRegla14Clase.ALMACEN, total=40, computable=21),
    )


def test_surface_classes_of_two_exercised_locales_are_refused_rather_than_added() -> None:
    path_values = (
        _local(1, actividad="0", afectacion="ejercicio")
        | _local(4, actividad="0", afectacion="ejercicio")
        | _row(IAE_LOCAL_SUPERFICIE_SECTION, 0, local="1", clase="0.1", total="120")
        | _row(IAE_LOCAL_SUPERFICIE_SECTION, 1, local="4", clase="0.1", total="80")
    )

    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    context = refused.value.context or {}
    assert refused.value.translated_message == "application.modelo.errors.m840_apartado_locales_ambiguous"
    assert (context["apartado"], context["locales"]) == ("VI C", "1, 4")


def test_two_locales_afectos_indirectamente_are_refused_for_apartado_v() -> None:
    path_values = _local(1, actividad="0", afectacion="indirecta") | _local(2, actividad="0", afectacion="indirecta")

    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values=path_values)

    context = refused.value.context or {}
    assert (context["apartado"], context["locales"], context["activity"]) == ("V", "1, 2", "0")


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("censo.aeat_delegacion_code", "2"),
        ("censo.aeat_administracion_code", "28A"),
        ("censo.aeat_administracion_name", "A" * 21),
        ("contact.fiscal_address_municipality_name", "M" * 31),
        ("activities.0.maquinas_recreativas_tipo_a", "12345678"),
    ],
)
def test_a_fact_outside_its_design_shape_is_refused_naming_it_and_its_door(path: str, value: str) -> None:
    with pytest.raises(ModeloProfileReadinessError) as refused:
        modelo_840_profile_facts(work_unit=_work_unit(), path_values={path: value})

    field = path.replace(".0.", ".")
    context = refused.value.context or {}
    assert (context["key"], context["profile_path"]) == (field, field)
    assert (refused.value.translated_message or "").startswith("application.modelo.errors.m840_fact_")
    assert refused.value.operation_next_step(OutputLanguage.EN) is not None
    assert refused.value.terminal_precondition_verdict is not None


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
@pytest.mark.parametrize(
    "key",
    [
        "m840_anexo_activities_ambiguous",
        "m840_apartado_locales_ambiguous",
        "m840_fact_code_digits",
        "m840_fact_text_width",
        "m840_fact_units",
    ],
)
def test_each_refusal_reads_in_every_locale(locale: str, key: str) -> None:
    sentence = tr(
        f"application.modelo.errors.{key}",
        locale=locale,
        modelo="840",
        filing_year=filing_year_envelope().horizon,
        activities="0, 1",
        apartado="VI C",
        activity="0",
        locales="1, 4",
        profile_section=IAE_LOCAL_SECTION,
        profile_path=IAE_LOCAL_SECTION,
        digits="2",
        width="30",
    )

    assert "%{" not in sentence and "840" in sentence
