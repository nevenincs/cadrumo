"""Semantic role typo-twin warnings and the signed result and quarterly counterpart role declarations."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import pytest

from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.registry_scope import validate_registry_scope
from ..compiler.validate_semantic_role_axes import semantic_roles_are_axis_siblings
from ..compiler.validate_semantic_roles import (
    semantic_role_typo_twin_failures,
)
from .semantic_role_support import (
    FAMILY_FIELD_FIRST_EDITION,
    SUPPORT,
    bundled_modelo,
    registry_modelo,
    semantic_role_casilla,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The edition id of the one-revision trees below; the support envelope's horizon stands in for any authored edition.
_EDITION = str(filing_year_envelope().horizon)
# A closed multi-year edition id, spanning the support envelope.
_SPAN_EDITION = f"{filing_year_envelope().floor}-{filing_year_envelope().horizon}"
# An open-ended edition id.
_OPEN_EDITION = f"{filing_year_envelope().floor}-y-siguientes"


@dataclass(frozen=True, slots=True)
class _Singleton:
    """One casilla whose role is reviewed as an intentional singleton, named by modelo, casilla and role."""

    modelo_id: str
    casilla_id: str
    role: str


class TestTypoTwinWarning:
    def test_reviewed_singleton_roles_are_marked_in_committed_registry(self) -> None:
        reviewed_singletons = (
            _Singleton("100", casilla_id="2028", role="irpf_deduccion_madrid_vivienda_nacimiento_adopcion_precio"),
            _Singleton("100", casilla_id="2029", role="irpf_deduccion_madrid_vivienda_nacimiento_adopcion_anio"),
            _Singleton("100", casilla_id="0463", role="irpf_red_prevision_social_exceso_2015_2019"),
            _Singleton("100", casilla_id="0437", role="irpf_red_prevision_social_exceso_2016_2020"),
            _Singleton("100", casilla_id="1757", role="irpf_anexo_c_exceso_sps_rg_aportaciones_periodo"),
            _Singleton("100", casilla_id="1758", role="irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado"),
            _Singleton("200", casilla_id="00827", role="is_deduccion_di_internacional_rdleg_pendiente"),
            _Singleton("200", casilla_id="00848", role="is_deduccion_di_interna_rdleg_pendiente"),
            _Singleton("200", casilla_id="02511", role="is_correccion_operaciones_a_plazos_art11_4_permanente_aumento"),
            _Singleton(
                "200",
                casilla_id="02512",
                role="is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02513",
                role="is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_aumento",
            ),
            _Singleton(
                "200", casilla_id="02516", role="is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion"
            ),
            _Singleton(
                "200",
                casilla_id="02517",
                role="is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="02518",
                role="is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_disminucion",
            ),
            _Singleton("200", casilla_id="03321", role="is_correccion_operaciones_a_plazos_dt1_permanente_aumento"),
            _Singleton(
                "200", casilla_id="03322", role="is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_aumento"
            ),
            _Singleton(
                "200", casilla_id="03323", role="is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_aumento"
            ),
            _Singleton("200", casilla_id="03326", role="is_correccion_operaciones_a_plazos_dt1_permanente_disminucion"),
            _Singleton(
                "200",
                casilla_id="03327",
                role="is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="03328",
                role="is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_disminucion",
            ),
            _Singleton(
                "200", casilla_id="03396", role="is_correccion_otras_correcciones_resultado_permanente_disminucion"
            ),
            _Singleton(
                "200",
                casilla_id="03397",
                role="is_correccion_otras_correcciones_resultado_temporaria_ejercicio_disminucion",
            ),
            _Singleton("200", casilla_id="DP200012:00501", role="is_liquidacion_i_importe"),
            _Singleton("100", casilla_id="1171", role="irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020"),
            _Singleton("100", casilla_id="1911", role="irpf_num_hijos_maternidad_2020"),
            _Singleton("100", casilla_id="1912", role="irpf_incremento_maternidad_no_aplicado_2020"),
            _Singleton("100", casilla_id="1914", role="irpf_num_hijos_maternidad_2021"),
            _Singleton("100", casilla_id="1915", role="irpf_incremento_maternidad_no_aplicado_2021"),
            _Singleton("100", casilla_id="2027", role="irpf_deduccion_madrid_vivienda_municipio_riesgo"),
            _Singleton("100", casilla_id="2028", role="irpf_deduccion_madrid_vivienda_municipio_riesgo_precio"),
            _Singleton("100", casilla_id="2029", role="irpf_deduccion_madrid_vivienda_municipio_riesgo_anio"),
            _Singleton("100", casilla_id="1958", role="irpf_deduccion_c_valenciana_autoconsumo_generado_pendiente_2"),
            _Singleton("100", casilla_id="2013", role="irpf_deduccion_c_valenciana_autoconsumo_pendiente_2"),
            _Singleton("100", casilla_id="2022", role="irpf_deduccion_madrid_nuevos_contribuyentes_pendiente_1"),
            _Singleton(
                "100", casilla_id="2163", role="irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente_1"
            ),
            _Singleton("190", casilla_id="decl.total-percepciones", role="total_percepciones_count"),
            _Singleton("190", casilla_id="decl.percepciones-total", role="total_percepciones_amount"),
            _Singleton("202", casilla_id="61", role="is_pf_mod_40_3_b2_base_tipo_3"),
            _Singleton("202", casilla_id="62", role="is_pf_mod_40_3_b2_porcentaje_3"),
            _Singleton("202", casilla_id="64", role="is_pf_mod_40_3_b2_base_tipo_4"),
            _Singleton("202", casilla_id="65", role="is_pf_mod_40_3_b2_porcentaje_4"),
            _Singleton("202", casilla_id="67", role="is_pf_mod_40_3_correcciones_impuesto_complementario"),
            _Singleton(
                "200",
                casilla_id="02631",
                role="is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02632",
                role="is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02633",
                role="is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02636",
                role="is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="02637",
                role="is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="02638",
                role="is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="02641",
                role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02642",
                role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02643",
                role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento",
            ),
            _Singleton(
                "200",
                casilla_id="02646",
                role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="02647",
                role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion",
            ),
            _Singleton(
                "200",
                casilla_id="02648",
                role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion",
            ),
            _Singleton("100", casilla_id="0773", role="irpf_deduccion_cantabria_desplazamiento_nuevos_residentes"),
            _Singleton(
                "100", casilla_id="0776", role="irpf_deduccion_cantabria_desplazamiento_nuevos_residentes_generado"
            ),
            _Singleton(
                "100", casilla_id="1715", role="irpf_deduccion_cantabria_desplazamiento_nuevos_residentes_pendiente"
            ),
            _Singleton("100", casilla_id="1708", role="irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero"),
            _Singleton(
                "100", casilla_id="1714", role="irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero_generado"
            ),
            _Singleton(
                "100", casilla_id="1717", role="irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero_pendiente"
            ),
            _Singleton(
                "100",
                casilla_id="0808",
                role="irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio_anterior",
            ),
            _Singleton(
                "100", casilla_id="1117", role="irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio"
            ),
            _Singleton(
                "100", casilla_id="1185", role="irpf_deduccion_c_valenciana_danos_vivienda_dana_generado_pendiente_1"
            ),
            _Singleton(
                "100",
                casilla_id="2012",
                role="irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado_pendiente_1",
            ),
            _Singleton("100", casilla_id="2014", role="irpf_deduccion_c_valenciana_danos_vivienda_dana_pendiente_1"),
            _Singleton(
                "100", casilla_id="2015", role="irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_1"
            ),
            _Singleton("100", casilla_id="2227", role="irpf_ganancia_fondos_coti_valor_transmision_global"),
            _Singleton("100", casilla_id="2228", role="irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia"),
            _Singleton("100", casilla_id="2229", role="irpf_ganancia_fondos_coti_valor_adquisicion_global"),
            _Singleton("100", casilla_id="2230", role="irpf_ganancia_fondos_coti_ganancia"),
            _Singleton("100", casilla_id="2231", role="irpf_ganancia_fondos_coti_exenta_renta_vitalicia"),
            _Singleton("100", casilla_id="2233", role="irpf_perdida_fondos_coti_importe"),
            _Singleton("100", casilla_id="2234", role="irpf_perdida_fondos_coti_importe_computable"),
            _Singleton("100", casilla_id="0360", role="irpf_ganancia_premios_juegos_valoracion_b"),
            _Singleton("100", casilla_id="0361", role="irpf_ganancia_premios_juegos_pub_valoracion_b"),
            _Singleton("100", casilla_id="0413", role="irpf_ganancia_inmueble_referencia_catastral_4"),
            _Singleton("100", casilla_id="0238", role="irpf_eo_reintegro_subvenciones"),
            _Singleton("100", casilla_id="0239", role="irpf_eo_agr_reintegro_subvenciones"),
            _Singleton("100", casilla_id="2202", role="irpf_anexo_b_aav_importe_satisfecho"),
            _Singleton("100", casilla_id="2243", role="irpf_ganancia_inmueble_anexo_c1_referencia_catastral_4"),
            _Singleton("100", casilla_id="2154", role="irpf_deduccion_murcia_vehiculo_matricula"),
            _Singleton("100", casilla_id="2155", role="irpf_deduccion_murcia_vehiculo_importe"),
            _Singleton("100", casilla_id="2246", role="irpf_deduccion_canarias_acciones_participaciones"),
            _Singleton(
                "369", casilla_id="iva.union.de.services-cuota", role="iva_oss_union_servicios_destino_de_cuota"
            ),
            _Singleton(
                "369", casilla_id="iva.union.fr.services-cuota", role="iva_oss_union_servicios_destino_fr_cuota"
            ),
        )
        modelos = tuple(
            bundled_modelo(modelo_id) for modelo_id in sorted({item.modelo_id for item in reviewed_singletons})
        )
        # Which editions declare each casilla with its role is read from the registry, so a
        # reviewed singleton is checked in every edition that carries it.
        carriers: dict[tuple[str, str, str], list[tuple[str, CasillaDefinition]]] = {}
        for modelo in modelos:
            for revision in modelo.revisions.values():
                for casilla in revision.casillas:
                    carriers.setdefault((modelo.id, casilla.id, casilla.semantic_role or ""), []).append(
                        (str(revision.id), casilla)
                    )

        for item in reviewed_singletons:
            found = carriers.get((item.modelo_id, item.casilla_id, item.role), [])
            assert found, f"no edition of modelo {item.modelo_id} declares casilla {item.casilla_id} as {item.role}"
            for revision_id, casilla in found:
                assert casilla.semantic_role == item.role, (item, revision_id)
                assert casilla.semantic_role_cardinality == "intentional_singleton", (item, revision_id)
                assert casilla.semantic_role_cardinality_reason is not None, (item, revision_id)

    def test_m100_family_profile_roles_are_shared_across_editions(self) -> None:
        modelo = bundled_modelo("100")
        casillas = {
            (revision.id, casilla.id): casilla
            for revision in modelo.revisions.values()
            for casilla in revision.casillas
        }
        shared_roles = (
            ("DECFAL", "irpf_declarante_fecha_fallecimiento"),
            ("APENOMDLG", "irpf_descendiente_apellidos_nombre"),
            ("FNACDLG", "irpf_descendiente_fecha_nacimiento"),
            ("MINUSDLG", "irpf_descendiente_clave_discapacidad"),
            ("FALLDLG", "irpf_descendiente_fecha_fallecimiento"),
            ("APENOMDLG_ASC", "irpf_ascendiente_apellidos_nombre"),
            ("ANOASDLG", "irpf_ascendiente_fecha_nacimiento"),
            ("PCTMINASDLG", "irpf_ascendiente_clave_discapacidad"),
            ("FALLASDLG", "irpf_ascendiente_fecha_fallecimiento"),
        )

        editions = tuple(
            str(year) for year in SUPPORT.years if year >= FAMILY_FIELD_FIRST_EDITION and str(year) in modelo.revisions
        )
        assert len(editions) >= 2, editions

        for casilla_id, role in shared_roles:
            for edition in editions:
                casilla = casillas[(edition, casilla_id)]
                assert casilla.semantic_role == role, (edition, casilla_id)
                assert casilla.semantic_role_cardinality == "shared", (edition, casilla_id)

    def test_reviewed_singleton_markers_do_not_warn(self) -> None:
        reviewed_modelos = (
            bundled_modelo("100"),
            bundled_modelo("184"),
            bundled_modelo("190"),
            bundled_modelo("200"),
            bundled_modelo("202"),
            bundled_modelo("303"),
            bundled_modelo("369"),
        )
        reviewed_roles = {
            "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_precio",
            "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_anio",
            "irpf_red_prevision_social_exceso_2015_2019",
            "irpf_red_prevision_social_exceso_2016_2020",
            "irpf_anexo_c_exceso_sps_rg_aportaciones_periodo",
            "irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado",
            "is_deduccion_di_internacional_rdleg_pendiente",
            "is_deduccion_di_interna_rdleg_pendiente",
            "is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
            "is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_aumento",
            "is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_aumento",
            "is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion",
            "is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_disminucion",
            "is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_disminucion",
            "is_correccion_operaciones_a_plazos_dt1_permanente_aumento",
            "is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_aumento",
            "is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_aumento",
            "is_correccion_operaciones_a_plazos_dt1_permanente_disminucion",
            "is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_disminucion",
            "is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_disminucion",
            "is_correccion_otras_correcciones_resultado_permanente_disminucion",
            "is_correccion_otras_correcciones_resultado_temporaria_ejercicio_disminucion",
            "is_liquidacion_i_importe",
            "irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020",
            "irpf_num_hijos_maternidad_2020",
            "irpf_incremento_maternidad_no_aplicado_2020",
            "irpf_num_hijos_maternidad_2021",
            "irpf_incremento_maternidad_no_aplicado_2021",
            "irpf_deduccion_madrid_vivienda_municipio_riesgo",
            "irpf_deduccion_madrid_vivienda_municipio_riesgo_precio",
            "irpf_deduccion_madrid_vivienda_municipio_riesgo_anio",
            "irpf_deduccion_c_valenciana_autoconsumo_generado_pendiente_2",
            "irpf_deduccion_c_valenciana_autoconsumo_pendiente_2",
            "irpf_deduccion_madrid_nuevos_contribuyentes_pendiente_1",
            "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente_1",
            "tipo_renta_atribuida_clave",
            "tipo_renta_atribuida_subclave",
            "total_percepciones_count",
            "total_percepciones_amount",
            "iva_compensacion_pendiente_anteriores",
            "iva_compensacion_pendiente_posteriores",
            "is_pf_mod_40_3_b2_base_tipo_3",
            "is_pf_mod_40_3_b2_porcentaje_3",
            "is_pf_mod_40_3_b2_base_tipo_4",
            "is_pf_mod_40_3_b2_porcentaje_4",
            "is_pf_mod_40_3_correcciones_impuesto_complementario",
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento",
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento",
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion",
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion",
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion",
            "irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio_anterior",
            "irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio",
            "irpf_deduccion_c_valenciana_danos_vivienda_dana_generado_pendiente_1",
            "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado_pendiente_1",
            "irpf_deduccion_c_valenciana_danos_vivienda_dana_pendiente_1",
            "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_1",
            "irpf_ganancia_fondos_coti_valor_transmision_global",
            "irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia",
            "irpf_ganancia_fondos_coti_valor_adquisicion_global",
            "irpf_ganancia_fondos_coti_ganancia",
            "irpf_ganancia_fondos_coti_exenta_renta_vitalicia",
            "irpf_perdida_fondos_coti_importe",
            "irpf_perdida_fondos_coti_importe_computable",
            "irpf_ganancia_premios_juegos_valoracion_b",
            "irpf_ganancia_premios_juegos_pub_valoracion_b",
            "irpf_ganancia_inmueble_referencia_catastral_4",
            "irpf_eo_reintegro_subvenciones",
            "irpf_eo_agr_reintegro_subvenciones",
            "irpf_anexo_b_aav_importe_satisfecho",
            "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_4",
            "irpf_deduccion_murcia_vehiculo_matricula",
            "irpf_deduccion_murcia_vehiculo_importe",
            "irpf_deduccion_canarias_acciones_participaciones",
            "iva_oss_union_servicios_destino_de_cuota",
            "iva_oss_union_servicios_destino_fr_cuota",
        }

        failures = semantic_role_typo_twin_failures(reviewed_modelos)

        for role in reviewed_roles:
            assert not any(role in failure for failure in failures)

    def test_single_occurrence_role_emits_warning(self) -> None:
        a = semantic_role_casilla(cid="a", semantic_role="taxpayer-nif", data_type="nif")  # note hyphen typo
        m = registry_modelo("180", _EDITION, [a])
        failures = semantic_role_typo_twin_failures([m])
        assert any("taxpayer-nif" in failure for failure in failures)

    def test_single_occurrence_near_duplicate_role_emits_warning(self) -> None:
        typo = semantic_role_casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = semantic_role_casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = semantic_role_casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        m = registry_modelo("180", _EDITION, [typo, canonical_a, canonical_b])
        failures = semantic_role_typo_twin_failures([m])
        assert any("taxpayer_niff" in failure for failure in failures)

    def test_typo_twin_blocks_registry_scope(self) -> None:
        """A typo twin refuses through the scope validator, on a tree that can answer.

        The tree carries TWO modelos deliberately.
        :func:`_tree_can_answer_role_singleton_questions` abstains on a
        one-modelo/one-revision tree, where every role is a singleton by
        construction, so asserting a singleton refusal there would be asserting
        the pruning rather than the data.
        """
        typo = semantic_role_casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = semantic_role_casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = semantic_role_casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        modelo = registry_modelo("180", _EDITION, [typo, canonical_a, canonical_b])
        sibling = registry_modelo(
            "184", _EDITION, [semantic_role_casilla(cid="d", semantic_role="taxpayer_nif", data_type="nif")]
        )

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            failures = validate_registry_scope([modelo, sibling])

        assert captured == []
        assert failures == (
            "semantic_role 'taxpayer_niff' appears on exactly one casilla "
            f"(180.{_EDITION}.a); likely typo or missing role declarations on sibling casillas",
        )

    def test_a_one_modelo_one_revision_tree_abstains_from_the_singleton_question(self) -> None:
        """The control: the same typo goes unreported where the siblings were pruned.

        Without this, the test above could be passing because the check never
        abstains, and the abstention is what keeps generated-export-tree
        validation -- which mandates exactly one modelo and one revision -- from
        refusing every role in its candidate registry.
        """
        typo = semantic_role_casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical = semantic_role_casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        modelo = registry_modelo("180", _EDITION, [typo, canonical])

        assert validate_registry_scope([modelo]) == ()

    def test_intentional_singleton_role_does_not_emit_warning(self) -> None:
        a = semantic_role_casilla(
            cid="a",
            semantic_role="taxpayer-nif",
            data_type="nif",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="legacy source spelling is legally unique",
        )
        m = registry_modelo("180", _EDITION, [a])
        assert semantic_role_typo_twin_failures([m]) == ()

    def test_repeated_role_does_not_warn(self) -> None:
        a = semantic_role_casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = semantic_role_casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = registry_modelo("180", _EDITION, [a])
        m2 = registry_modelo("184", _EDITION, [b])
        failures = semantic_role_typo_twin_failures([m1, m2])
        role_failures = [f for f in failures if "taxpayer_nif" in f]
        assert role_failures == []

    def test_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        aumento = semantic_role_casilla(
            cid="a",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
        )
        disminucion = semantic_role_casilla(
            cid="b",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion",
        )
        m = registry_modelo("200", _EDITION, [aumento, disminucion])
        assert semantic_role_typo_twin_failures([m]) == ()

    def test_quarter_axis_siblings_do_not_warn_as_typos(self) -> None:
        """Modelo 347's four quarterly columns are an axis, not four spellings.

        Its Tipo 2 record declares "IMPORTE PERCIBIDO POR TRANSMISIONES DE
        INMUEBLES SUJETAS A IVA {PRIMER,SEGUNDO,TERCER,CUARTO} TRIMESTRE" as
        four separate sixteen-byte columns, so each role legitimately owns one
        casilla. They differ by a single digit, which is what drew the detector.
        """
        quarters = [
            semantic_role_casilla(cid=f"q{index}", semantic_role=f"importe_transmisiones_q{index}", data_type="money")
            for index in (1, 2, 3, 4)
        ]
        m = registry_modelo("347", _SPAN_EDITION, quarters)

        assert semantic_role_typo_twin_failures([m]) == ()

    def test_a_misspelt_stem_under_the_same_quarter_token_still_warns(self) -> None:
        """The control: the exemption is scoped to the token, never the stem.

        Both roles end in ``q1``, so the quarter axis cannot exempt them -- it
        requires two DISTINCT tokens -- and the transposed stem is caught
        exactly as it was before the axis existed.
        """
        typo = semantic_role_casilla(cid="a", semantic_role="importe_transmisionse_q1", data_type="money")
        canonical_a = semantic_role_casilla(cid="b", semantic_role="importe_transmisiones_q1", data_type="money")
        canonical_b = semantic_role_casilla(cid="c", semantic_role="importe_transmisiones_q1", data_type="money")
        m = registry_modelo("347", _SPAN_EDITION, [typo, canonical_a, canonical_b])

        failures = semantic_role_typo_twin_failures([m])

        assert any("transmisionse_q1" in failure for failure in failures)

    def test_near_duplicate_with_same_axis_still_warns(self) -> None:
        typo = semantic_role_casilla(
            cid="a",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanent_aumento",
        )
        canonical = semantic_role_casilla(
            cid="b",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
        )
        m = registry_modelo("200", _EDITION, [typo, canonical])
        failures = semantic_role_typo_twin_failures([m])
        assert any("permanent_aumento" in failure for failure in failures)

    def test_non_axis_token_pairs_are_not_axis_siblings(self) -> None:
        cases = (
            ("renta-attribuida", "tipo_renta_atribuida_clave", "tipo_renta_atribuida_subclave"),
            ("percepciones-total", "total_percepciones_count", "total_percepciones_amount"),
            (
                "iva-compensacion-temporal",
                "iva_compensacion_pendiente_anteriores",
                "iva_compensacion_pendiente_posteriores",
            ),
            (
                "ganancia-valor-kind",
                "irpf_ganancia_valor_transmision",
                "irpf_ganancia_valor_adquisicion",
            ),
            ("anexo-b-letter", "irpf_anexo_b_ab_importe", "irpf_anexo_b_c_importe"),
            (
                "sin-maintenance",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
            ),
            (
                "legal-reference",
                "is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
                "is_correccion_operaciones_a_plazos_dt1_permanente_aumento",
            ),
            (
                "legal-regime",
                "is_deduccion_di_internacional_rdleg_pendiente",
                "is_deduccion_di_internacional_pendiente",
            ),
            (
                "numeric-window",
                "irpf_red_prevision_social_exceso_2015_2019",
                "irpf_red_prevision_social_exceso_2016_2020",
            ),
            (
                "period-applied",
                "irpf_anexo_c_exceso_sps_rg_aportaciones_periodo",
                "irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado",
            ),
            (
                "internal-international",
                "is_deduccion_di_interna_rdleg_pendiente",
                "is_deduccion_di_internacional_rdleg_pendiente",
            ),
            (
                "detail-other",
                "is_correccion_detalle_correcciones_resultado_permanente_disminucion",
                "is_correccion_otras_correcciones_resultado_permanente_disminucion",
            ),
            ("roman-liquidation", "is_liquidacion_i_importe", "is_liquidacion_ii_importe"),
            (
                "birth-death",
                "irpf_descendiente_fecha_nacimiento",
                "irpf_descendiente_fecha_fallecimiento",
            ),
            (
                "relationship",
                "irpf_descendiente_apellidos_nombre",
                "irpf_ascendiente_apellidos_nombre",
            ),
            (
                "anexo-b-aav-marker",
                "irpf_anexo_b_aav_importe_satisfecho",
                "irpf_anexo_b_importe_satisfecho",
            ),
            (
                "public-source",
                "irpf_ganancia_premios_juegos_pub_valoracion",
                "irpf_ganancia_premios_juegos_valoracion",
            ),
            (
                "agricultural-objective-estimation",
                "irpf_eo_agr_reintegro_subvenciones",
                "irpf_eo_reintegro_subvenciones",
            ),
            (
                "numeric-line",
                "irpf_deduccion_cantabria_obras_mejora_pendiente_1",
                "irpf_deduccion_cantabria_obras_mejora_pendiente_2",
            ),
            (
                "ccaa",
                "irpf_deduccion_murcia_vehiculo_importe",
                "irpf_deduccion_asturias_vehiculo_importe",
            ),
            (
                "field-detail-year",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo_anio",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo",
            ),
            (
                "field-detail-price",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo_precio",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo",
            ),
            (
                "cadastral-anexo-c1",
                "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_4",
                "irpf_ganancia_inmueble_referencia_catastral_4",
            ),
        )

        for case_id, left, right in cases:
            assert semantic_roles_are_axis_siblings(left, right) is False, case_id

    def test_related_party_row_slot_roles_do_not_warn_as_typos(self) -> None:
        first_slot = semantic_role_casilla(cid="a", semantic_role="related_party_nif_1", data_type="nif")
        second_slot = semantic_role_casilla(cid="b", semantic_role="related_party_nif_2", data_type="nif")
        m = registry_modelo("232", _OPEN_EDITION, [first_slot, second_slot])
        assert semantic_role_typo_twin_failures([m]) == ()

    def test_coti_scope_marker_is_not_optional_axis_token(self) -> None:
        coti = semantic_role_casilla(cid="a", semantic_role="irpf_ganancia_fondos_coti_ganancia")
        general_a = semantic_role_casilla(cid="b", semantic_role="irpf_ganancia_fondos_ganancia")
        general_b = semantic_role_casilla(cid="c", semantic_role="irpf_ganancia_fondos_ganancia")
        m = registry_modelo("100", _EDITION, [coti, general_a, general_b])
        failures = semantic_role_typo_twin_failures([m])
        assert any("irpf_ganancia_fondos_coti_ganancia" in failure for failure in failures)


class TestSignedCuotaResultadoRoles:
    def test_irpf_and_is_signed_result_roles_are_bound_to_committed_casillas(self) -> None:
        modelos = {
            modelo.id: modelo
            for modelo in (
                bundled_modelo("100"),
                bundled_modelo("200"),
            )
        }

        signed_roles = {
            (
                modelo.id,
                revision.id,
                casilla.id,
                casilla.semantic_role,
                casilla.data_type,
            )
            for modelo in modelos.values()
            for revision in modelo.revisions.values()
            for casilla in revision.casillas
            if casilla.semantic_role
            in {
                "resultado_ingresar_o_devolver_irpf",
                "is_resultado_ingresar_o_devolver",
                "resultado_ingresar_o_devolver_is",
            }
        }

        # Each modelo binds its signed result to one committed casilla and data type in
        # every edition that carries the role; which editions carry it is read from the
        # registry rather than listed here.
        assert {
            (modelo_id, casilla_id, role, data_type) for modelo_id, _rev, casilla_id, role, data_type in signed_roles
        } == {
            ("100", "RESINGDEV", "resultado_ingresar_o_devolver_irpf", "decimal"),
            ("200", "DP200014B:00599", "is_resultado_ingresar_o_devolver", "money"),
        }
        for modelo in modelos.values():
            newest = max(modelo.revisions.values(), key=lambda revision: revision.valid_from)
            assert (modelo.id, newest.id) in {
                (modelo_id, revision_id) for modelo_id, revision_id, *_ in signed_roles
            }, f"modelo {modelo.id}'s newest edition {newest.id} binds no signed result role"

        stale_is_role_members = [item for item in signed_roles if item[3] == "resultado_ingresar_o_devolver_is"]
        assert stale_is_role_members == []


class TestModelo347QuarterlyContraparteRolesAreIntentionalSingletons:
    """M347 per-quarter contraparte importe roles must not trip the typo-twin warning.

    Modelo 347 desglosa el importe de operaciones con la contraparte por
    trimestre (Q1-Q4) into four distinct casillas (RD 1065/2007 art. 31). Each
    ``contraparte_importe_qN`` role therefore appears on exactly one casilla and
    looks like a typo of its siblings, so without an ``intentional_singleton``
    cardinality marker the typo-twin validator emits a ``UserWarning`` on every
    registry load and pollutes the operator's stderr (round-29/30 finding).
    """

    def test_quarterly_contraparte_importe_roles_marked_intentional_singleton(self) -> None:
        modelo = bundled_modelo("347")
        quarterly_ids = {
            "contraparte.importe-Q1",
            "contraparte.importe-Q2",
            "contraparte.importe-Q3",
            "contraparte.importe-Q4",
        }
        found = {
            casilla.id: casilla
            for revision in modelo.revisions.values()
            for casilla in revision.casillas
            if casilla.id in quarterly_ids
        }
        assert quarterly_ids <= set(found), f"missing quarterly casillas: {sorted(quarterly_ids - set(found))}"
        for casilla_id, casilla in found.items():
            assert casilla.semantic_role_cardinality == "intentional_singleton", (
                f"{casilla_id} is not marked intentional_singleton; the typo-twin validator will warn on it"
            )
            assert casilla.semantic_role_cardinality_reason, f"{casilla_id} lacks the required cardinality reason"
