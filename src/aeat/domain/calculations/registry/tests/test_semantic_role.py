"""Roundtrip and validator tests for semantic_role + aliases.

`CasillaDefinition` gained an optional `semantic_role: str | None`
slot and an `aliases: tuple[CasillaAlias, ...]` slot. The
snapshot-build validator now enforces that every casilla sharing a
`semantic_role` declares the same `data_type` and structurally
compatible `constraints`. Single-occurrence role values emit a
typo-twin diagnostic warning and fail registry-scope validation.

These tests exercise the field shape, the consistency validator,
the typo-twin warning surface, and the alias-preservation
round-trip.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .. import CasillaId, load_modelo_path, validated_casilla_id
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
    _emit_semantic_role_typo_twin_warnings,
    _validate_semantic_role_cardinality,
    _validate_semantic_role_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TEST_CASILLA_ID: CasillaId = validated_casilla_id("test_casilla", surface="_TEST_CASILLA_ID")


def _casilla(
    *,
    cid: CasillaId = _TEST_CASILLA_ID,
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
            "label": "Test casilla",
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
            "title": f"Modelo {modelo_id}",
            "official_name": f"Modelo {modelo_id}",
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


class TestSemanticRoleFieldShape:
    def test_default_role_is_none(self) -> None:
        c = _casilla()
        assert c.semantic_role is None
        assert c.aliases == ()

    def test_role_round_trips(self) -> None:
        c = _casilla(semantic_role="taxpayer_nif", data_type="nif")
        rebuilt = CasillaDefinition.model_validate(c.model_dump())
        assert rebuilt.semantic_role == "taxpayer_nif"
        assert rebuilt == c

    def test_empty_role_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _casilla(semantic_role="")

    def test_intentional_singleton_role_requires_semantic_role(self) -> None:
        with pytest.raises(ValidationError):
            _casilla(
                semantic_role_cardinality="intentional_singleton",
                semantic_role_cardinality_reason="2025-only legal slot",
            )

    def test_intentional_singleton_role_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            _casilla(
                semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
                semantic_role_cardinality="intentional_singleton",
            )

    def test_singleton_reason_requires_intentional_singleton_cardinality(self) -> None:
        with pytest.raises(ValidationError):
            _casilla(
                semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
                semantic_role_cardinality_reason="2025-only legal slot",
            )

    def test_intentional_singleton_cardinality_round_trips(self) -> None:
        c = _casilla(
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        rebuilt = CasillaDefinition.model_validate(c.model_dump())
        assert rebuilt.semantic_role_cardinality == "intentional_singleton"
        assert rebuilt.semantic_role_cardinality_reason == "2025-only legal slot"

    def test_aliases_round_trip(self) -> None:
        alias = CasillaAlias(
            label="NIF declarante",
            legal_refs=("ley-58-2003:art-29",),
            source_refs=("aeat-manual",),
        )
        c = _casilla(semantic_role="taxpayer_nif", data_type="nif", aliases=[alias])
        rebuilt = CasillaDefinition.model_validate(c.model_dump())
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

    def test_intentional_singleton_role_repeated_elsewhere_fails(self) -> None:
        a = _casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = _casilla(cid="b", semantic_role="is_pf_mod_40_3_b2_base_tipo_3")
        m1 = _registry_modelo("202", "2025-y-siguientes", [a])
        m2 = _registry_modelo("202", "2026-y-siguientes", [b])
        failures = _validate_semantic_role_cardinality([m1, m2])
        assert failures == (
            "semantic_role 'is_pf_mod_40_3_b2_base_tipo_3': casilla "
            "202.2025-y-siguientes.a declares semantic_role_cardinality "
            "'intentional_singleton' but role appears 2 times",
        )


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
            ("184", "2015-y-siguientes", "tipo2.clave", "tipo_renta_atribuida_clave"),
            ("184", "2015-y-siguientes", "tipo2.subclave", "tipo_renta_atribuida_subclave"),
            ("190", "2024-y-siguientes", "decl.total-percepciones", "total_percepciones_count"),
            ("190", "2024-y-siguientes", "decl.percepciones-total", "total_percepciones_amount"),
            ("202", "2025-y-siguientes", "61", "is_pf_mod_40_3_b2_base_tipo_3"),
            ("202", "2025-y-siguientes", "62", "is_pf_mod_40_3_b2_porcentaje_3"),
            ("202", "2025-y-siguientes", "64", "is_pf_mod_40_3_b2_base_tipo_4"),
            ("202", "2025-y-siguientes", "65", "is_pf_mod_40_3_b2_porcentaje_4"),
            ("202", "2025-y-siguientes", "67", "is_pf_mod_40_3_correcciones_impuesto_complementario"),
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
            ("100", "2025", "2234", "irpf_perdida_fondos_coti_importe_computable"),
            ("100", "2025", "0360", "irpf_ganancia_premios_juegos_valoracion_b"),
            ("100", "2025", "0361", "irpf_ganancia_premios_juegos_pub_valoracion_b"),
            # M303 compensacion-pendiente roles appear in both 2009-y-siguientes and
            # 2023-y-siguientes revisions; the validator requires unique occurrence for
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

    def test_reviewed_singleton_markers_do_not_warn(self) -> None:
        reviewed_modelos = (
            _bundled_modelo("100"),
            _bundled_modelo("184"),
            _bundled_modelo("190"),
            _bundled_modelo("202"),
            _bundled_modelo("303"),
            _bundled_modelo("369"),
        )
        reviewed_roles = {
            "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_precio",
            "irpf_deduccion_madrid_vivienda_nacimiento_adopcion_anio",
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
            "irpf_perdida_fondos_coti_importe_computable",
            "irpf_ganancia_premios_juegos_valoracion_b",
            "irpf_ganancia_premios_juegos_pub_valoracion_b",
            "iva_oss_union_servicios_destino_de_cuota",
            "iva_oss_union_servicios_destino_fr_cuota",
        }

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings(reviewed_modelos)

        messages = [str(item.message) for item in captured]
        for role in reviewed_roles:
            assert not any(role in message for message in messages)

    def test_single_occurrence_role_emits_warning(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer-nif", data_type="nif")  # note hyphen typo
        m = _registry_modelo("180", "2023", [a])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("taxpayer-nif" in str(w.message) for w in captured)

    def test_single_occurrence_near_duplicate_role_emits_warning(self) -> None:
        typo = _casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = _casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        m = _registry_modelo("180", "2023", [typo, canonical_a, canonical_b])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("taxpayer_niff" in str(w.message) for w in captured)

    def test_typo_twin_blocks_registry_scope(self) -> None:
        typo = _casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = _casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        modelo = _registry_modelo("180", "2025", [typo, canonical_a, canonical_b])

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            failures = validate_registry_scope([modelo])

        assert captured == []
        assert failures == (
            "semantic_role 'taxpayer_niff' appears on exactly one casilla "
            "(180.2025.a); likely typo or missing role declarations on sibling casillas",
        )

    def test_intentional_singleton_role_does_not_emit_warning(self) -> None:
        a = _casilla(
            cid="a",
            semantic_role="taxpayer-nif",
            data_type="nif",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="legacy source spelling is legally unique",
        )
        m = _registry_modelo("180", "2023", [a])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_repeated_role_does_not_warn(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _registry_modelo("180", "2023", [a])
        m2 = _registry_modelo("184", "2023", [b])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m1, m2])
        role_warnings = [w for w in captured if "taxpayer_nif" in str(w.message)]
        assert role_warnings == []

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
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

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
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("permanent_aumento" in str(w.message) for w in captured)

    def test_token_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        anteriores = _casilla(
            cid="a",
            semantic_role="iva_compensacion_pendiente_anteriores",
        )
        posteriores = _casilla(
            cid="b",
            semantic_role="iva_compensacion_pendiente_posteriores",
        )
        m = _registry_modelo("303", "2009-y-siguientes", [anteriores, posteriores])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_optional_negation_sibling_roles_do_not_warn_as_typos(self) -> None:
        con_mantenimiento = _casilla(
            cid="a",
            semantic_role="is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
        )
        sin_mantenimiento = _casilla(
            cid="b",
            semantic_role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
        )
        m = _registry_modelo("200", "2024-y-siguientes", [con_mantenimiento, sin_mantenimiento])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_legal_reference_axis_roles_do_not_warn_as_typos(self) -> None:
        article = _casilla(
            cid="a",
            semantic_role="is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
        )
        transitional = _casilla(
            cid="b",
            semantic_role="is_correccion_operaciones_a_plazos_dt1_permanente_aumento",
        )
        m = _registry_modelo("200", "2024-y-siguientes", [article, transitional])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_optional_legal_regime_roles_do_not_warn_as_typos(self) -> None:
        rdleg = _casilla(
            cid="a",
            semantic_role="is_deduccion_di_internacional_rdleg_pendiente",
        )
        current = _casilla(
            cid="b",
            semantic_role="is_deduccion_di_internacional_pendiente",
        )
        m = _registry_modelo("200", "2024-y-siguientes", [rdleg, current])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_scope_token_sibling_roles_do_not_warn_as_typos(self) -> None:
        detalle = _casilla(
            cid="a",
            semantic_role="is_correccion_detalle_correcciones_resultado_permanente_disminucion",
        )
        otras = _casilla(
            cid="b",
            semantic_role="is_correccion_otras_correcciones_resultado_permanente_disminucion",
        )
        m = _registry_modelo("200", "2024-y-siguientes", [detalle, otras])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_numeric_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        first_window = _casilla(cid="a", semantic_role="irpf_red_prevision_social_exceso_2015_2019")
        second_window = _casilla(cid="b", semantic_role="irpf_red_prevision_social_exceso_2016_2020")
        m = _registry_modelo("100", "2021", [first_window, second_window])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_relationship_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        descendant = _casilla(cid="a", semantic_role="irpf_descendiente_fecha_nacimiento")
        ascendant = _casilla(cid="b", semantic_role="irpf_ascendiente_fecha_nacimiento")
        m = _registry_modelo("100", "2025", [descendant, ascendant])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_optional_scope_axis_roles_do_not_warn_as_typos(self) -> None:
        listed = _casilla(cid="a", semantic_role="irpf_anexo_b_aav_importe_satisfecho")
        general = _casilla(cid="b", semantic_role="irpf_anexo_b_importe_satisfecho")
        m = _registry_modelo("100", "2025", [listed, general])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_coti_scope_marker_is_not_optional_axis_token(self) -> None:
        coti = _casilla(cid="a", semantic_role="irpf_ganancia_fondos_coti_ganancia")
        general_a = _casilla(cid="b", semantic_role="irpf_ganancia_fondos_ganancia")
        general_b = _casilla(cid="c", semantic_role="irpf_ganancia_fondos_ganancia")
        m = _registry_modelo("100", "2025", [coti, general_a, general_b])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("irpf_ganancia_fondos_coti_ganancia" in str(item.message) for item in captured)

    def test_public_source_marker_is_not_optional_axis_token(self) -> None:
        assert (
            semantic_roles_are_axis_siblings(
                "irpf_ganancia_premios_juegos_pub_valoracion",
                "irpf_ganancia_premios_juegos_valoracion",
            )
            is False
        )

    def test_optional_numeric_axis_roles_do_not_warn_as_typos(self) -> None:
        annual_line = _casilla(cid="a", semantic_role="irpf_deduccion_cantabria_obras_mejora_pendiente_1")
        general_line = _casilla(cid="b", semantic_role="irpf_deduccion_cantabria_obras_mejora_pendiente_2")
        m = _registry_modelo("100", "2025", [annual_line, general_line])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_ccaa_axis_roles_do_not_warn_as_typos(self) -> None:
        murcia = _casilla(cid="a", semantic_role="irpf_deduccion_murcia_vehiculo_importe")
        asturias = _casilla(cid="b", semantic_role="irpf_deduccion_asturias_vehiculo_importe")
        m = _registry_modelo("100", "2025", [murcia, asturias])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_optional_field_scope_axis_roles_do_not_warn_as_typos(self) -> None:
        parent = _casilla(cid="a", semantic_role="irpf_deduccion_madrid_vivienda_municipio_riesgo")
        year = _casilla(cid="b", semantic_role="irpf_deduccion_madrid_vivienda_municipio_riesgo_anio")
        price = _casilla(cid="c", semantic_role="irpf_deduccion_madrid_vivienda_municipio_riesgo_precio")
        m = _registry_modelo("100", "2025", [parent, year, price])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []


class TestSemanticRoleTypoTwinHelpers:
    """Direct coverage of the extracted near-match scan helpers.

    The end-to-end warning surface above exercises these through
    ``_emit_semantic_role_typo_twin_warnings``; these tests pin the filter-chain
    contract at the helper boundary so the cheap-to-expensive ordering and the
    sibling exemptions cannot silently regress.
    """

    @staticmethod
    def _index(*known_roles: str) -> _SemanticRoleTypoIndex:
        return _build_semantic_role_typo_index(known_roles)

    def test_identity_candidate_is_not_a_typo_twin(self) -> None:
        role = "taxpayer_nif"
        index = self._index(role)
        assert _candidate_is_typo_twin(role, set(role), len(role), role, len(role), 1, index) is False

    def test_single_char_substitution_is_a_typo_twin(self) -> None:
        # taxpayer_niff vs taxpayer_nif: a near-duplicate that is not a sibling.
        role = "taxpayer_niff"
        known = "taxpayer_nif"
        index = self._index(known)
        max_diff = int(0.08 * (len(role) + len(known)))
        assert _candidate_is_typo_twin(role, set(role), len(role), known, len(known), max_diff, index) is True

    def test_axis_sibling_candidate_is_exempt(self) -> None:
        # ascendiente vs descendiente share a relationship axis -> not a typo twin.
        role = "irpf_ascendiente_fecha_nacimiento"
        known = "irpf_descendiente_fecha_nacimiento"
        index = self._index(known)
        max_diff = int(0.08 * (len(role) + len(known)))
        # The two differ by more than the fast-check budget, so they never reach
        # the sibling exemption: the fast prefix/suffix filter rejects first.
        assert _candidate_is_typo_twin(role, set(role), len(role), known, len(known), max_diff, index) is False

    def test_scan_finds_near_duplicate_across_length_buckets(self) -> None:
        index = self._index("taxpayer_nif", "unrelated_role_value")
        assert _scan_length_buckets_for_typo_twin("taxpayer_niff", index) is True

    def test_scan_returns_false_when_no_near_duplicate(self) -> None:
        index = self._index("taxpayer_nif", "counterparty_amount")
        assert _scan_length_buckets_for_typo_twin("completely_distinct_role", index) is False


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
