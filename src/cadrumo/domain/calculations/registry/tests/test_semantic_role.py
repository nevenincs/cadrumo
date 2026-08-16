"""Roundtrip and validator tests for semantic_role + aliases.

`CasillaDefinition` gained an optional `semantic_role: str | None`
slot and an `aliases: tuple[CasillaAlias, ...]` slot. The
snapshot-build validator now enforces that every casilla sharing a
`semantic_role` declares the same `data_type` and structurally
compatible `constraints`. Single-occurrence role values are reported
as typo-twin diagnostic findings and fail registry-scope validation.

These tests exercise the field shape, the consistency validator,
the typo-twin diagnostic surface, and the alias-preservation
round-trip.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from datetime import date
from typing import Any, Literal, TypedDict

import pytest
from pydantic import ValidationError

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .. import load_modelo_path
from .._schema import (
    CasillaAlias,
    CasillaConstraints,
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevision,
    PeriodSelector,
)
from .._validate_registry_scope import validate_registry_scope
from .._validate_semantic_role_axes import semantic_roles_are_axis_siblings
from .._validate_semantic_role_typos import (
    _build_semantic_role_typo_index,
    _candidate_is_typo_twin,
    _scan_length_buckets_for_typo_twin,
    _SemanticRoleTypoIndex,
)
from .._validate_semantic_roles import (
    _validate_semantic_role_cardinality,
    _validate_semantic_role_consistency,
    _validate_semantic_role_typo_twins,
)
from ._synthetic_locale_fixtures import _synthetic_locale_scope, _write_test_label

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TEST_CASILLA_ID: CasillaId = validated_casilla_id("test_casilla", surface="_TEST_CASILLA_ID")

__all__ = ["_synthetic_locale_scope"]


def _casilla(
    *,
    cid: CasillaId = _TEST_CASILLA_ID,
    label: str = "Test casilla",
    data_type: str = "money",
    semantic_role: str | None = None,
    semantic_role_cardinality: str = "shared",
    semantic_role_cardinality_reason: str | None = None,
    aliases: Iterable[CasillaAlias] = (),
    constraints: CasillaConstraints | None = None,
) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": cid,
            "number": "01",
            "localization_keys": (_write_test_label(label),),
            "section": ("test",),
            "data_type": data_type,
            "semantic_role": semantic_role,
            "semantic_role_cardinality": semantic_role_cardinality,
            "semantic_role_cardinality_reason": semantic_role_cardinality_reason,
            "aliases": tuple(aliases),
            "constraints": constraints,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
        },
    )


def _registry_modelo(modelo_id: str, revision_id: str, casillas: Iterable[CasillaDefinition]) -> ModeloDefinition:
    revision = ModeloRevision.model_validate(
        {
            "id": revision_id,
            "localization_key": f"test.schema.revision.{revision_id}.label",
            "valid_from": date(2025, 1, 1),
            "period_selector": PeriodSelector(years=(2025,), periods=("0A",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": tuple(casillas),
        },
    )
    return ModeloDefinition.model_validate(
        {
            "id": modelo_id,
            "title_localization_key": f"test.schema.modelo.{modelo_id}.title",
            "official_name_localization_key": f"test.schema.modelo.{modelo_id}.official_name",
            "tax_domain": "iva",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": {revision_id: revision},
        },
    )


def _bundled_modelo(modelo_id: str) -> Any:
    path = bundled_path("registry", "aeat", "modelos", modelo_id)
    if path.exists():
        return load_modelo_path(path)
    return load_modelo_path(path.with_suffix(".toml"))


class _PartialCasillaUpdate(TypedDict, total=False):
    """Partial kwargs update for _casilla fixture in parametrize tests."""

    semantic_role: str
    semantic_role_cardinality: str
    semantic_role_cardinality_reason: str


class TestSemanticRoleFieldShape:
    def test_default_role_is_none(self) -> None:
        c = _casilla()
        assert c.semantic_role is None
        assert c.aliases == ()

    def test_role_round_trips(self) -> None:
        c = _casilla(semantic_role="taxpayer_nif", data_type="nif")
        rebuilt = CasillaDefinition.model_validate(
            {**c.model_dump(), "localization_keys": c.localization_keys},
        )
        assert rebuilt.semantic_role == "taxpayer_nif"
        assert rebuilt == c

    def test_invalid_semantic_role_shape_rejected(self) -> None:
        cases: tuple[
            tuple[
                str,
                dict[
                    Literal[
                        "semantic_role",
                        "semantic_role_cardinality",
                        "semantic_role_cardinality_reason",
                    ],
                    str,
                ],
            ],
            ...,
        ] = (
            ("empty-role", {"semantic_role": ""}),
            (
                "singleton-without-role",
                {
                    "semantic_role_cardinality": "intentional_singleton",
                    "semantic_role_cardinality_reason": "2025-only legal slot",
                },
            ),
            (
                "singleton-without-reason",
                {
                    "semantic_role": "is_pf_mod_40_3_b2_base_tipo_3",
                    "semantic_role_cardinality": "intentional_singleton",
                },
            ),
            (
                "reason-without-singleton",
                {
                    "semantic_role": "is_pf_mod_40_3_b2_base_tipo_3",
                    "semantic_role_cardinality_reason": "2025-only legal slot",
                },
            ),
        )

        for case_id, updates in cases:
            try:
                _casilla(**updates)
            except ValidationError:
                continue
            raise AssertionError(f"{case_id} accepted an invalid semantic-role shape")

    def test_empty_localization_keys_rejected(self) -> None:
        casilla = _casilla()
        with pytest.raises(ValidationError, match="localization_keys"):
            CasillaDefinition.model_validate({**casilla.model_dump(), "localization_keys": ()})

    def test_empty_alias_localization_key_rejected(self) -> None:
        with pytest.raises(ValidationError, match="localization_key"):
            CasillaAlias(
                localization_key="",
                legal_refs=("ley-58-2003:art-29",),
                source_refs=("aeat-manual",),
            )

    def test_intentional_singleton_cardinality_round_trips(self) -> None:
        c = _casilla(
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        rebuilt = CasillaDefinition.model_validate(
            {**c.model_dump(), "localization_keys": c.localization_keys},
        )
        assert rebuilt.semantic_role_cardinality == "intentional_singleton"
        assert rebuilt.semantic_role_cardinality_reason == "2025-only legal slot"

    def test_aliases_round_trip(self) -> None:
        alias = CasillaAlias(
            localization_key=_write_test_label("NIF declarante"),
            legal_refs=("ley-58-2003:art-29",),
            source_refs=("aeat-manual",),
        )
        c = _casilla(semantic_role="taxpayer_nif", data_type="nif", aliases=[alias])
        rebuilt = CasillaDefinition.model_validate(
            {
                **c.model_dump(),
                "localization_keys": c.localization_keys,
                "aliases": ({**alias.model_dump(), "localization_key": alias.localization_key},),
            },
        )
        assert len(rebuilt.aliases) == 1
        assert rebuilt.aliases[0].label == "NIF declarante"
        assert rebuilt.aliases[0].legal_refs == ("ley-58-2003:art-29",)


class TestValidateSemanticRoleConsistency:
    def test_no_role_declarations_passes(self) -> None:
        m = _registry_modelo("180", "2023", [_casilla()])
        assert _validate_semantic_role_consistency([m]) == ()

    def test_matching_role_declarations_pass(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _registry_modelo("180", "2023", [a])
        m2 = _registry_modelo("184", "2023", [b])
        assert _validate_semantic_role_consistency([m1, m2]) == ()

    def test_diverging_data_type_rejected(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="text")
        m1 = _registry_modelo("180", "2023", [a])
        m2 = _registry_modelo("184", "2023", [b])
        failures = _validate_semantic_role_consistency([m1, m2])
        assert any("data_type" in f for f in failures)
        assert any("taxpayer_nif" in f for f in failures)

    def test_diverging_constraints_rejected(self) -> None:
        common_legal = ("ley-58-2003:art-29",)
        common_source = ("aeat-manual",)
        constrained = CasillaConstraints(sign="non_negative", legal_refs=common_legal, source_refs=common_source)
        unconstrained = CasillaConstraints(sign="any", legal_refs=common_legal, source_refs=common_source)
        a = _casilla(cid="a", semantic_role="retenciones", data_type="money", constraints=constrained)
        b = _casilla(cid="b", semantic_role="retenciones", data_type="money", constraints=unconstrained)
        m1 = _registry_modelo("180", "2023", [a])
        m2 = _registry_modelo("184", "2023", [b])
        failures = _validate_semantic_role_consistency([m1, m2])
        assert any("constraints" in f for f in failures)


class TestValidateSemanticRoleCardinality:
    def test_intentional_singleton_role_with_single_occurrence_passes(self) -> None:
        c = _casilla(
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        m = _registry_modelo("202", "2025-y-siguientes", [c])
        assert _validate_semantic_role_cardinality([m]) == ()

    def test_intentional_singleton_role_repeated_within_one_revision_fails(self) -> None:
        """POSITIVE CONTROL: the gate must still bite on a real duplicate.

        Two bearers inside ONE revision co-apply in a single filing, which is
        exactly the defect ``intentional_singleton`` exists to catch. If this
        ever passes, the cardinality axis has been removed rather than
        rescoped, which is worse than the artefact the rescoping fixed.
        """
        a = _casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = _casilla(cid="b", semantic_role="is_pf_mod_40_3_b2_base_tipo_3")
        m = _registry_modelo("202", "2025-y-siguientes", [a, b])
        failures = _validate_semantic_role_cardinality([m])
        assert failures == (
            "semantic_role 'is_pf_mod_40_3_b2_base_tipo_3': casilla "
            "202.2025-y-siguientes.a declares semantic_role_cardinality "
            "'intentional_singleton' but role is shared by co-applying casillas "
            "(2 in one revision, 1 modelo(s))",
        )

    def test_intentional_singleton_role_in_a_second_modelo_fails(self) -> None:
        """POSITIVE CONTROL, second axis: two modelos genuinely co-exist.

        Modelo 303 and Modelo 390 are both filed, so a role borne by each is
        shared in the sense the marker denies. Only sibling revisions of ONE
        modelo are mutually exclusive.
        """
        a = _casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = _casilla(cid="b", semantic_role="is_pf_mod_40_3_b2_base_tipo_3")
        m1 = _registry_modelo("202", "2025-y-siguientes", [a])
        m2 = _registry_modelo("303", "2025-y-siguientes", [b])
        failures = _validate_semantic_role_cardinality([m1, m2])
        assert failures == (
            "semantic_role 'is_pf_mod_40_3_b2_base_tipo_3': casilla "
            "202.2025-y-siguientes.a declares semantic_role_cardinality "
            "'intentional_singleton' but role is shared by co-applying casillas "
            "(1 in one revision, 2 modelo(s))",
        )

    def test_intentional_singleton_role_across_sibling_revisions_passes(self) -> None:
        """NEGATIVE CONTROL: a revision split must not staleness-fail the marker.

        AEAT binds every ``(modelo, filing_year, period)`` to exactly one
        revision, so these two can never co-apply and the role has not gained a
        sibling -- the revision was cloned. Splitting a revision at a design
        re-layout clones every casilla, so counting raw observations would turn
        correct authoring into a validation failure that gets worse with each
        further split.
        """
        a = _casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = _casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        m1 = _registry_modelo("202", "2025-y-siguientes", [a])
        m2 = _registry_modelo("202", "2026-y-siguientes", [b])
        assert _validate_semantic_role_cardinality([m1, m2]) == ()


class TestTypoTwinWarning:
    def test_reviewed_singleton_roles_are_marked_in_committed_registry(self) -> None:
        reviewed_singletons = (
            (
                "100",
                "2024",
                "2028",
                "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_precio",
            ),
            (
                "100",
                "2024",
                "2029",
                "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_anio",
            ),
            (
                "100",
                "2020",
                "0463",
                "irpf_red_prevision_social_exceso_2015_2019",
            ),
            (
                "100",
                "2021",
                "0437",
                "irpf_red_prevision_social_exceso_2016_2020",
            ),
            (
                "100",
                "2021",
                "1757",
                "irpf_anexo_c_exceso_sps_rg_aportaciones_periodo",
            ),
            (
                "100",
                "2021",
                "1758",
                "irpf_anexo_c_exceso_sps_rg_aportaciones_aplicado",
            ),
            (
                "200",
                "2024-y-siguientes",
                "00827",
                "is_deduccion_di_internacional_rdleg_pendiente",
            ),
            (
                "200",
                "2024-y-siguientes",
                "00848",
                "is_deduccion_di_interna_rdleg_pendiente",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02511",
                "is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02512",
                "is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02513",
                "is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02516",
                "is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02517",
                "is_correccion_operaciones_a_plazos_art11_4_temporaria_ejercicio_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02518",
                "is_correccion_operaciones_a_plazos_art11_4_temporaria_anteriores_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03321",
                "is_correccion_operaciones_a_plazos_dt1_permanente_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03322",
                "is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03323",
                "is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03326",
                "is_correccion_operaciones_a_plazos_dt1_permanente_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03327",
                "is_correccion_operaciones_a_plazos_dt1_temporaria_ejercicio_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03328",
                "is_correccion_operaciones_a_plazos_dt1_temporaria_anteriores_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03396",
                "is_correccion_otras_correcciones_resultado_permanente_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "03397",
                "is_correccion_otras_correcciones_resultado_temporaria_ejercicio_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "00501",
                "is_liquidacion_i_importe",
            ),
            (
                "100",
                "2020",
                "1171",
                "irpf_deduccion_c_valenciana_ayudas_publicas_generalitat_2020",
            ),
            ("100", "2022", "1911", "irpf_num_hijos_maternidad_2020"),
            ("100", "2022", "1912", "irpf_incremento_maternidad_no_aplicado_2020"),
            ("100", "2022", "1914", "irpf_num_hijos_maternidad_2021"),
            ("100", "2022", "1915", "irpf_incremento_maternidad_no_aplicado_2021"),
            (
                "100",
                "2025",
                "2027",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo",
            ),
            (
                "100",
                "2025",
                "2028",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo_precio",
            ),
            (
                "100",
                "2025",
                "2029",
                "irpf_deduccion_madrid_vivienda_municipio_riesgo_anio",
            ),
            (
                "100",
                "2025",
                "1958",
                "irpf_deduccion_c_valenciana_autoconsumo_generado_pendiente_2",
            ),
            (
                "100",
                "2025",
                "2013",
                "irpf_deduccion_c_valenciana_autoconsumo_pendiente_2",
            ),
            (
                "100",
                "2025",
                "2022",
                "irpf_deduccion_madrid_nuevos_contribuyentes_pendiente_1",
            ),
            (
                "100",
                "2025",
                "2163",
                "irpf_deduccion_murcia_recursos_energeticos_renovables_pendiente_1",
            ),
            ("190", "2024-y-siguientes", "decl.total-percepciones", "total_percepciones_count"),
            ("190", "2024-y-siguientes", "decl.percepciones-total", "total_percepciones_amount"),
            ("202", "2025-y-siguientes", "61", "is_pf_mod_40_3_b2_base_tipo_3"),
            ("202", "2025-y-siguientes", "62", "is_pf_mod_40_3_b2_porcentaje_3"),
            ("202", "2025-y-siguientes", "64", "is_pf_mod_40_3_b2_base_tipo_4"),
            ("202", "2025-y-siguientes", "65", "is_pf_mod_40_3_b2_porcentaje_4"),
            ("202", "2025-y-siguientes", "67", "is_pf_mod_40_3_correcciones_impuesto_complementario"),
            (
                "200",
                "2024-y-siguientes",
                "02631",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02632",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02633",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02636",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02637",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_ejercicio_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02638",
                "is_correccion_libertad_amortizacion_mantenimiento_empleo_temporaria_anteriores_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02641",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02642",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02643",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_aumento",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02646",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02647",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_ejercicio_disminucion",
            ),
            (
                "200",
                "2024-y-siguientes",
                "02648",
                "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_temporaria_anteriores_disminucion",
            ),
            ("100", "2025", "0773", "irpf_deduccion_cantabria_desplazamiento_nuevos_residentes"),
            ("100", "2025", "0776", "irpf_deduccion_cantabria_desplazamiento_nuevos_residentes_generado"),
            ("100", "2025", "1715", "irpf_deduccion_cantabria_desplazamiento_nuevos_residentes_pendiente"),
            ("100", "2025", "1708", "irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero"),
            ("100", "2025", "1714", "irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero_generado"),
            ("100", "2025", "1717", "irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero_pendiente"),
            (
                "100",
                "2022",
                "0808",
                "irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio_anterior",
            ),
            (
                "100",
                "2022",
                "1117",
                "irpf_deduccion_c_valenciana_acciones_participaciones_aplicado_ejercicio",
            ),
            (
                "100",
                "2025",
                "1185",
                "irpf_deduccion_c_valenciana_danos_vivienda_dana_generado_pendiente_1",
            ),
            (
                "100",
                "2025",
                "2012",
                "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado_pendiente_1",
            ),
            ("100", "2025", "2014", "irpf_deduccion_c_valenciana_danos_vivienda_dana_pendiente_1"),
            (
                "100",
                "2025",
                "2015",
                "irpf_deduccion_c_valenciana_aportaciones_fondos_propios_pendiente_1",
            ),
            ("100", "2025", "2227", "irpf_ganancia_fondos_coti_valor_transmision_global"),
            ("100", "2025", "2228", "irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia"),
            ("100", "2025", "2229", "irpf_ganancia_fondos_coti_valor_adquisicion_global"),
            ("100", "2025", "2230", "irpf_ganancia_fondos_coti_ganancia"),
            ("100", "2025", "2231", "irpf_ganancia_fondos_coti_exenta_renta_vitalicia"),
            ("100", "2025", "2233", "irpf_perdida_fondos_coti_importe"),
            ("100", "2025", "2234", "irpf_perdida_fondos_coti_importe_computable"),
            ("100", "2025", "0360", "irpf_ganancia_premios_juegos_valoracion_b"),
            ("100", "2025", "0361", "irpf_ganancia_premios_juegos_pub_valoracion_b"),
            ("100", "2025", "0413", "irpf_ganancia_inmueble_referencia_catastral_4"),
            ("100", "2025", "0238", "irpf_eo_reintegro_subvenciones"),
            ("100", "2025", "0239", "irpf_eo_agr_reintegro_subvenciones"),
            ("100", "2025", "2202", "irpf_anexo_b_aav_importe_satisfecho"),
            ("100", "2025", "2243", "irpf_ganancia_inmueble_anexo_c1_referencia_catastral_4"),
            ("100", "2025", "2154", "irpf_deduccion_murcia_vehiculo_matricula"),
            ("100", "2025", "2155", "irpf_deduccion_murcia_vehiculo_importe"),
            ("100", "2025", "2246", "irpf_deduccion_canarias_acciones_participaciones"),
            # M303 compensacion-pendiente roles appear in both 2009-y-siguientes and
            # post-2022 Modelo 303 revisions; the validator requires unique occurrence for
            # intentional_singleton, so they carry semantic_role_cardinality="shared".
            ("369", "esquema-union", "iva.union.de.services-cuota", "iva_oss_union_servicios_destino_de_cuota"),
            ("369", "esquema-union", "iva.union.fr.services-cuota", "iva_oss_union_servicios_destino_fr_cuota"),
        )
        modelos = tuple(_bundled_modelo(modelo_id) for modelo_id in sorted({item[0] for item in reviewed_singletons}))
        casillas = {
            (modelo.id, revision.id, casilla.id): casilla
            for modelo in modelos
            for revision in modelo.revisions.values()
            for casilla in revision.casillas
        }

        for modelo_id, revision_id, casilla_id, role in reviewed_singletons:
            casilla = casillas[(modelo_id, revision_id, casilla_id)]
            assert casilla.semantic_role == role
            assert casilla.semantic_role_cardinality == "intentional_singleton"
            assert casilla.semantic_role_cardinality_reason is not None

    def test_m100_2024_2025_family_profile_roles_are_shared(self) -> None:
        modelo = _bundled_modelo("100")
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

        for casilla_id, role in shared_roles:
            casilla_2024 = casillas[("2024", casilla_id)]
            casilla_2025 = casillas[("2025", casilla_id)]
            assert casilla_2024.semantic_role == role
            assert casilla_2025.semantic_role == role
            assert casilla_2024.semantic_role_cardinality == "shared"
            assert casilla_2025.semantic_role_cardinality == "shared"

    def test_reviewed_singleton_markers_do_not_warn(self) -> None:
        reviewed_modelos = (
            _bundled_modelo("100"),
            _bundled_modelo("184"),
            _bundled_modelo("190"),
            _bundled_modelo("200"),
            _bundled_modelo("202"),
            _bundled_modelo("303"),
            _bundled_modelo("369"),
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

        failures = _validate_semantic_role_typo_twins(reviewed_modelos)

        for role in reviewed_roles:
            assert not any(role in failure for failure in failures)

    def test_single_occurrence_role_emits_warning(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer-nif", data_type="nif")  # note hyphen typo
        m = _registry_modelo("180", "2023", [a])
        failures = _validate_semantic_role_typo_twins([m])
        assert any("taxpayer-nif" in failure for failure in failures)

    def test_single_occurrence_near_duplicate_role_emits_warning(self) -> None:
        typo = _casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = _casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        m = _registry_modelo("180", "2023", [typo, canonical_a, canonical_b])
        failures = _validate_semantic_role_typo_twins([m])
        assert any("taxpayer_niff" in failure for failure in failures)

    def test_typo_twin_blocks_registry_scope(self) -> None:
        """A typo twin refuses through the scope validator, on a tree that can answer.

        The tree carries TWO modelos deliberately.
        :func:`_tree_can_answer_role_singleton_questions` abstains on a
        one-modelo/one-revision tree, where every role is a singleton by
        construction, so asserting a singleton refusal there would be asserting
        the pruning rather than the data.
        """
        typo = _casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = _casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        modelo = _registry_modelo("180", "2025", [typo, canonical_a, canonical_b])
        sibling = _registry_modelo("184", "2025", [_casilla(cid="d", semantic_role="taxpayer_nif", data_type="nif")])

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            failures = validate_registry_scope([modelo, sibling])

        assert captured == []
        assert failures == (
            "semantic_role 'taxpayer_niff' appears on exactly one casilla "
            "(180.2025.a); likely typo or missing role declarations on sibling casillas",
        )

    def test_a_one_modelo_one_revision_tree_abstains_from_the_singleton_question(self) -> None:
        """The control: the same typo goes unreported where the siblings were pruned.

        Without this, the test above could be passing because the check never
        abstains, and the abstention is what keeps generated-export-tree
        validation -- which mandates exactly one modelo and one revision -- from
        refusing every role in its candidate registry.
        """
        typo = _casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        modelo = _registry_modelo("180", "2025", [typo, canonical])

        assert validate_registry_scope([modelo]) == ()

    def test_intentional_singleton_role_does_not_emit_warning(self) -> None:
        a = _casilla(
            cid="a",
            semantic_role="taxpayer-nif",
            data_type="nif",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="legacy source spelling is legally unique",
        )
        m = _registry_modelo("180", "2023", [a])
        assert _validate_semantic_role_typo_twins([m]) == ()

    def test_repeated_role_does_not_warn(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _registry_modelo("180", "2023", [a])
        m2 = _registry_modelo("184", "2023", [b])
        failures = _validate_semantic_role_typo_twins([m1, m2])
        role_failures = [f for f in failures if "taxpayer_nif" in f]
        assert role_failures == []

    def test_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        aumento = _casilla(
            cid="a",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
        )
        disminucion = _casilla(
            cid="b",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_disminucion",
        )
        m = _registry_modelo("200", "2024-y-siguientes", [aumento, disminucion])
        assert _validate_semantic_role_typo_twins([m]) == ()

    def test_quarter_axis_siblings_do_not_warn_as_typos(self) -> None:
        """Modelo 347's four quarterly columns are an axis, not four spellings.

        Its Tipo 2 record declares "IMPORTE PERCIBIDO POR TRANSMISIONES DE
        INMUEBLES SUJETAS A IVA {PRIMER,SEGUNDO,TERCER,CUARTO} TRIMESTRE" as
        four separate sixteen-byte columns, so each role legitimately owns one
        casilla. They differ by a single digit, which is what drew the detector.
        """
        quarters = [
            _casilla(cid=f"q{index}", semantic_role=f"importe_transmisiones_q{index}", data_type="money")
            for index in (1, 2, 3, 4)
        ]
        m = _registry_modelo("347", "2008-y-siguientes", quarters)

        assert _validate_semantic_role_typo_twins([m]) == ()

    def test_a_misspelt_stem_under_the_same_quarter_token_still_warns(self) -> None:
        """The control: the exemption is scoped to the token, never the stem.

        Both roles end in ``q1``, so the quarter axis cannot exempt them -- it
        requires two DISTINCT tokens -- and the transposed stem is caught
        exactly as it was before the axis existed.
        """
        typo = _casilla(cid="a", semantic_role="importe_transmisionse_q1", data_type="money")
        canonical_a = _casilla(cid="b", semantic_role="importe_transmisiones_q1", data_type="money")
        canonical_b = _casilla(cid="c", semantic_role="importe_transmisiones_q1", data_type="money")
        m = _registry_modelo("347", "2008-y-siguientes", [typo, canonical_a, canonical_b])

        failures = _validate_semantic_role_typo_twins([m])

        assert any("transmisionse_q1" in failure for failure in failures)

    def test_near_duplicate_with_same_axis_still_warns(self) -> None:
        typo = _casilla(
            cid="a",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanent_aumento",
        )
        canonical = _casilla(
            cid="b",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
        )
        m = _registry_modelo("200", "2024-y-siguientes", [typo, canonical])
        failures = _validate_semantic_role_typo_twins([m])
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
        first_slot = _casilla(cid="a", semantic_role="related_party_nif_1", data_type="nif")
        second_slot = _casilla(cid="b", semantic_role="related_party_nif_2", data_type="nif")
        m = _registry_modelo("232", "2018-y-siguientes", [first_slot, second_slot])
        assert _validate_semantic_role_typo_twins([m]) == ()

    def test_coti_scope_marker_is_not_optional_axis_token(self) -> None:
        coti = _casilla(cid="a", semantic_role="irpf_ganancia_fondos_coti_ganancia")
        general_a = _casilla(cid="b", semantic_role="irpf_ganancia_fondos_ganancia")
        general_b = _casilla(cid="c", semantic_role="irpf_ganancia_fondos_ganancia")
        m = _registry_modelo("100", "2025", [coti, general_a, general_b])
        failures = _validate_semantic_role_typo_twins([m])
        assert any("irpf_ganancia_fondos_coti_ganancia" in failure for failure in failures)


class TestSemanticRoleTypoTwinHelpers:
    """Direct coverage of the extracted near-match scan helpers.

    The end-to-end surface above exercises these through
    ``_validate_semantic_role_typo_twins``; these tests pin the filter-chain
    contract at the helper boundary so the cheap-to-expensive ordering and the
    sibling exemptions cannot silently regress.
    """

    @staticmethod
    def _index(*known_roles: str) -> _SemanticRoleTypoIndex:
        return _build_semantic_role_typo_index(known_roles)

    def test_candidate_typo_twin_cases(self) -> None:
        cases = (
            ("identity", "taxpayer_nif", "taxpayer_nif", False),
            ("single-char-substitution", "taxpayer_niff", "taxpayer_nif", True),
            (
                "relationship-not-axis-exempt",
                "irpf_ascendiente_fecha_nacimiento",
                "irpf_descendiente_fecha_nacimiento",
                True,
            ),
        )

        for case_id, role, known, expected in cases:
            index = self._index(known)
            max_diff = max(1, int(0.08 * (len(role) + len(known))))
            assert (
                _candidate_is_typo_twin(role, set(role), len(role), known, len(known), max_diff, index) is expected
            ), case_id

    def test_scan_length_buckets_for_typo_twin_cases(self) -> None:
        cases = (
            ("near-duplicate", "taxpayer_niff", ("taxpayer_nif", "unrelated_role_value"), True),
            ("distinct", "completely_distinct_role", ("taxpayer_nif", "counterparty_amount"), False),
        )

        for case_id, candidate, known_roles, expected in cases:
            index = self._index(*known_roles)
            assert _scan_length_buckets_for_typo_twin(candidate, index) is expected, case_id


class TestSignedCuotaResultadoRoles:
    def test_irpf_and_is_signed_result_roles_are_bound_to_committed_casillas(self) -> None:
        modelos = {
            modelo.id: modelo
            for modelo in (
                _bundled_modelo("100"),
                _bundled_modelo("200"),
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

        assert signed_roles == {
            ("100", "2024", "0700", "resultado_ingresar_o_devolver_irpf", "decimal"),
            ("100", "2025", "0700", "resultado_ingresar_o_devolver_irpf", "decimal"),
            ("200", "2024-y-siguientes", "DP200014B:00599", "is_resultado_ingresar_o_devolver", "money"),
        }

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
        modelo = _bundled_modelo("347")
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
