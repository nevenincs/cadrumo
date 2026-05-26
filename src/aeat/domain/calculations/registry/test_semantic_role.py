"""Roundtrip and validator tests for Plan C semantic_role + aliases.

`CasillaDefinition` gained an optional `semantic_role: str | None`
slot and an `aliases: tuple[CasillaAlias, ...]` slot. The
snapshot-build validator now enforces that every casilla sharing a
`semantic_role` declares the same `data_type` and structurally
compatible `constraints`. Single-occurrence role values emit a
typo-twin warning via `warnings.warn`.

These tests exercise the field shape, the consistency validator,
the typo-twin warning surface, and the alias-preservation
round-trip.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from typing import Any

import pytest
from pydantic import ValidationError

from aeat.core.resources import bundled_path

from . import load_modelo_path
from ._schema import CasillaAlias, CasillaConstraints, CasillaDefinition
from ._validate_semantic_roles import (
    _emit_semantic_role_typo_twin_warnings,
    _semantic_roles_are_axis_siblings,
    _validate_semantic_role_cardinality,
    _validate_semantic_role_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _casilla(
    *,
    cid: str = "test_casilla",
    data_type: str = "money",
    semantic_role: str | None = None,
    semantic_role_cardinality: str = "shared",
    semantic_role_cardinality_reason: str | None = None,
    aliases: Iterable[CasillaAlias] = (),
    constraints: CasillaConstraints | None = None,
) -> CasillaDefinition:
    return CasillaDefinition.model_validate({
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
    })


def _modelo(modelo_id: str, revision_id: str, casillas: Iterable[CasillaDefinition]) -> Any:
    """Build the minimum object shape `_validate_semantic_role_consistency` expects.

    The validator only reads `.id` on the modelo, `.id` on each
    revision, and walks `.casillas`. Use a lightweight stand-in to
    avoid pulling the full ModeloDefinition / ModeloRevision schema
    (with its many required fields) for unit-test scope.
    """

    class _Rev:
        def __init__(self) -> None:
            self.id = revision_id
            self.casillas = tuple(casillas)

    class _Mod:
        def __init__(self) -> None:
            self.id = modelo_id
            self.revisions = {revision_id: _Rev()}

    return _Mod()


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
        m = _modelo("180", "2023", [_casilla()])
        assert _validate_semantic_role_consistency([m]) == ()

    def test_matching_role_declarations_pass(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        assert _validate_semantic_role_consistency([m1, m2]) == ()

    def test_diverging_data_type_rejected(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="text")
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        failures = _validate_semantic_role_consistency([m1, m2])
        assert any("data_type" in f for f in failures)
        assert any("taxpayer_nif" in f for f in failures)

    def test_diverging_constraints_rejected(self) -> None:
        common_legal = ("ley-58-2003:art-29",)
        common_source = ("aeat-manual",)
        constrained = CasillaConstraints(
            sign="non_negative", legal_refs=common_legal, source_refs=common_source
        )
        unconstrained = CasillaConstraints(
            sign="any", legal_refs=common_legal, source_refs=common_source
        )
        a = _casilla(cid="a", semantic_role="retenciones", data_type="money", constraints=constrained)
        b = _casilla(cid="b", semantic_role="retenciones", data_type="money", constraints=unconstrained)
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        failures = _validate_semantic_role_consistency([m1, m2])
        assert any("constraints" in f for f in failures)


class TestValidateSemanticRoleCardinality:
    def test_intentional_singleton_role_with_single_occurrence_passes(self) -> None:
        c = _casilla(
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        m = _modelo("202", "2025-y-siguientes", [c])
        assert _validate_semantic_role_cardinality([m]) == ()

    def test_intentional_singleton_role_repeated_elsewhere_fails(self) -> None:
        a = _casilla(
            cid="a",
            semantic_role="is_pf_mod_40_3_b2_base_tipo_3",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="2025-only legal slot",
        )
        b = _casilla(cid="b", semantic_role="is_pf_mod_40_3_b2_base_tipo_3")
        m1 = _modelo("202", "2025-y-siguientes", [a])
        m2 = _modelo("202", "2026-y-siguientes", [b])
        failures = _validate_semantic_role_cardinality([m1, m2])
        assert failures == (
            "semantic_role 'is_pf_mod_40_3_b2_base_tipo_3': casilla "
            "202.2025-y-siguientes.a declares semantic_role_cardinality "
            "'intentional_singleton' but role appears 2 times",
        )


class TestTypoTwinWarning:
    def test_reviewed_singleton_roles_are_marked_in_committed_registry(self) -> None:
        reviewed_singletons = (
            ("100", "2025", "2022", "irpf_deduccion_madrid_generado_pendiente_aplicacion"),
            ("100", "2025", "2154", "irpf_deduccion_murcia_vehiculo_matricula"),
            ("100", "2025", "2155", "irpf_deduccion_murcia_vehiculo_importe"),
            ("100", "2025", "2227", "irpf_ganancia_fondos_coti_valor_transmision_global"),
            (
                "100",
                "2025",
                "2228",
                "irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia",
            ),
            ("100", "2025", "2229", "irpf_ganancia_fondos_coti_valor_adquisicion_global"),
            ("100", "2025", "2230", "irpf_ganancia_fondos_coti_ganancia"),
            ("100", "2025", "2231", "irpf_ganancia_fondos_coti_exenta_renta_vitalicia"),
            ("100", "2025", "2234", "irpf_perdida_fondos_coti_importe_computable"),
            ("100", "2025", "2246", "irpf_deduccion_canarias_acciones_participaciones"),
            ("184", "2015-y-siguientes", "tipo2.clave", "tipo_renta_atribuida_clave"),
            ("184", "2015-y-siguientes", "tipo2.subclave", "tipo_renta_atribuida_subclave"),
            ("190", "2025-y-siguientes", "decl.total-percepciones", "total_percepciones_count"),
            ("190", "2025-y-siguientes", "decl.percepciones-total", "total_percepciones_amount"),
            (
                "200",
                "2024-y-siguientes",
                "00827",
                "is_deduccion_di_internacional_rdleg_pendiente",
            ),
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
            ("202", "2025-y-siguientes", "61", "is_pf_mod_40_3_b2_base_tipo_3"),
            ("202", "2025-y-siguientes", "62", "is_pf_mod_40_3_b2_porcentaje_3"),
            ("202", "2025-y-siguientes", "64", "is_pf_mod_40_3_b2_base_tipo_4"),
            ("202", "2025-y-siguientes", "65", "is_pf_mod_40_3_b2_porcentaje_4"),
            ("202", "2025-y-siguientes", "67", "is_pf_mod_40_3_correcciones_impuesto_complementario"),
            (
                "303",
                "2009-y-siguientes",
                "iva.compensacion-pendiente-periodos-anteriores",
                "iva_compensacion_pendiente_anteriores",
            ),
            (
                "303",
                "2009-y-siguientes",
                "iva.compensacion-pendiente-periodos-posteriores",
                "iva_compensacion_pendiente_posteriores",
            ),
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
            _bundled_modelo("200"),
            _bundled_modelo("202"),
            _bundled_modelo("303"),
            _bundled_modelo("369"),
        )
        reviewed_roles = {
            "irpf_deduccion_madrid_generado_pendiente_aplicacion",
            "irpf_deduccion_murcia_vehiculo_matricula",
            "irpf_deduccion_murcia_vehiculo_importe",
            "irpf_ganancia_fondos_coti_valor_transmision_global",
            "irpf_ganancia_fondos_coti_valor_transmision_renta_vitalicia",
            "irpf_ganancia_fondos_coti_valor_adquisicion_global",
            "irpf_ganancia_fondos_coti_ganancia",
            "irpf_ganancia_fondos_coti_exenta_renta_vitalicia",
            "irpf_perdida_fondos_coti_importe_computable",
            "irpf_deduccion_canarias_acciones_participaciones",
            "tipo_renta_atribuida_clave",
            "tipo_renta_atribuida_subclave",
            "total_percepciones_count",
            "total_percepciones_amount",
            "is_deduccion_di_internacional_rdleg_pendiente",
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
            "iva_compensacion_pendiente_anteriores",
            "iva_compensacion_pendiente_posteriores",
            "is_pf_mod_40_3_b2_base_tipo_3",
            "is_pf_mod_40_3_b2_porcentaje_3",
            "is_pf_mod_40_3_b2_base_tipo_4",
            "is_pf_mod_40_3_b2_porcentaje_4",
            "is_pf_mod_40_3_correcciones_impuesto_complementario",
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
        m = _modelo("180", "2023", [a])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("taxpayer-nif" in str(w.message) for w in captured)

    def test_single_occurrence_near_duplicate_role_emits_warning(self) -> None:
        typo = _casilla(cid="a", semantic_role="taxpayer_niff", data_type="nif")
        canonical_a = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        canonical_b = _casilla(cid="c", semantic_role="taxpayer_nif", data_type="nif")
        m = _modelo("180", "2023", [typo, canonical_a, canonical_b])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("taxpayer_niff" in str(w.message) for w in captured)

    def test_intentional_singleton_role_does_not_emit_warning(self) -> None:
        a = _casilla(
            cid="a",
            semantic_role="taxpayer-nif",
            data_type="nif",
            semantic_role_cardinality="intentional_singleton",
            semantic_role_cardinality_reason="legacy source spelling is legally unique",
        )
        m = _modelo("180", "2023", [a])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_repeated_role_does_not_warn(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
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
        m = _modelo("200", "2024-y-siguientes", [aumento, disminucion])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_correction_balance_axis_roles_do_not_warn_as_typos(self) -> None:
        opening_balance = _casilla(
            cid="a",
            semantic_role="is_correccion_operaciones_art19_otras_saldo_inicial",
        )
        closing_balance = _casilla(
            cid="b",
            semantic_role="is_correccion_operaciones_art19_otras_saldo_final",
        )
        m = _modelo("200", "2024-y-siguientes", [opening_balance, closing_balance])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_correction_mismatch_bucket_roles_remain_warning_only_axes(self) -> None:
        increase = _casilla(
            cid="a",
            semantic_role="is_correccion_libertad_amortizacion_vehiculos_permanente_aumento",
        )
        decrease = _casilla(
            cid="b",
            semantic_role="is_correccion_libertad_amortizacion_vehiculos_permanente_disminucion",
        )
        m = _modelo("200", "2024-y-siguientes", [increase, decrease])
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
        m = _modelo("200", "2024-y-siguientes", [typo, canonical])
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
        m = _modelo("303", "2009-y-siguientes", [anteriores, posteriores])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_optional_negation_roles_are_not_axis_siblings_without_source_policy(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
        )

    def test_optional_negation_near_roles_warn_without_singleton_policy(self) -> None:
        con_mantenimiento = _casilla(
            cid="a",
            semantic_role="is_correccion_libertad_amortizacion_mantenimiento_empleo_permanente_aumento",
        )
        sin_mantenimiento = _casilla(
            cid="b",
            semantic_role="is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento",
        )
        m = _modelo("200", "2024-y-siguientes", [con_mantenimiento, sin_mantenimiento])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any(
            "is_correccion_libertad_amortizacion_sin_mantenimiento_empleo_permanente_aumento"
            in str(warning.message)
            for warning in captured
        )

    def test_legal_reference_roles_are_not_axis_siblings_without_source_policy(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "is_correccion_operaciones_a_plazos_art11_4_permanente_aumento",
            "is_correccion_operaciones_a_plazos_dt1_permanente_aumento",
        )
        assert not _semantic_roles_are_axis_siblings(
            "is_deduccion_di_internacional_rdleg_pendiente",
            "is_deduccion_di_internacional_pendiente",
        )

    def test_scope_token_sibling_roles_do_not_warn_as_typos(self) -> None:
        detalle = _casilla(
            cid="a",
            semantic_role="is_correccion_detalle_correcciones_resultado_permanente_disminucion",
        )
        otras = _casilla(
            cid="b",
            semantic_role="is_correccion_otras_correcciones_resultado_permanente_disminucion",
        )
        m = _modelo("200", "2024-y-siguientes", [detalle, otras])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_numeric_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        first_window = _casilla(cid="a", semantic_role="irpf_red_prevision_social_exceso_2015_2019")
        second_window = _casilla(cid="b", semantic_role="irpf_red_prevision_social_exceso_2016_2020")
        m = _modelo("100", "2021", [first_window, second_window])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_relationship_axis_sibling_roles_do_not_warn_as_typos(self) -> None:
        descendant = _casilla(cid="a", semantic_role="irpf_descendiente_fecha_nacimiento")
        ascendant = _casilla(cid="b", semantic_role="irpf_ascendiente_fecha_nacimiento")
        m = _modelo("100", "2025", [descendant, ascendant])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_coti_roles_are_not_axis_siblings_without_source_policy(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "irpf_ganancia_fondos_coti_ganancia",
            "irpf_ganancia_fondos_ganancia",
        )

    def test_coti_near_roles_warn_without_singleton_policy(self) -> None:
        listed = _casilla(cid="a", semantic_role="irpf_ganancia_fondos_coti_ganancia")
        general = _casilla(cid="b", semantic_role="irpf_ganancia_fondos_ganancia")
        m = _modelo("100", "2025", [listed, general])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("irpf_ganancia_fondos_coti_ganancia" in str(warning.message) for warning in captured)

    def test_multiple_optional_scope_axis_roles_do_not_warn_as_typos(self) -> None:
        scoped = _casilla(cid="a", semantic_role="irpf_ganancia_premios_juegos_pub_valoracion_b")
        general = _casilla(cid="b", semantic_role="irpf_ganancia_premios_juegos_valoracion")
        m = _modelo("100", "2025", [scoped, general])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_optional_numeric_axis_roles_do_not_warn_as_typos(self) -> None:
        annual_line = _casilla(cid="a", semantic_role="irpf_deduccion_cantabria_generado_2025_pendiente_2")
        general_line = _casilla(cid="b", semantic_role="irpf_deduccion_cantabria_generado_pendiente")
        m = _modelo("100", "2025", [annual_line, general_line])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_cross_ccaa_roles_are_not_axis_siblings_without_source_policy(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_murcia_vehiculo_importe",
            "irpf_deduccion_asturias_vehiculo_importe",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_andalucia_nacimiento_adopcion",
            "irpf_deduccion_madrid_nacimiento_adopcion",
        )

    def test_optional_field_scope_axis_roles_do_not_warn_as_typos(self) -> None:
        parent = _casilla(cid="a", semantic_role="irpf_deduccion_madrid_vivienda_municipio_riesgo")
        year = _casilla(cid="b", semantic_role="irpf_deduccion_madrid_vivienda_municipio_riesgo_anio")
        price = _casilla(cid="c", semantic_role="irpf_deduccion_madrid_vivienda_municipio_riesgo_precio")
        m = _modelo("100", "2025", [parent, year, price])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_anexo_c_carryforward_state_roles_do_not_warn_as_typos(self) -> None:
        pending_start = _casilla(
            cid="a",
            semantic_role="irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio",
        )
        applied = _casilla(
            cid="b",
            semantic_role="irpf_anexo_c_saldo_neg_gyp_general_aplicado",
        )
        pending_future = _casilla(
            cid="c",
            semantic_role="irpf_anexo_c_saldo_neg_gyp_general_pendiente_fin",
        )
        m = _modelo("100", "2025", [pending_start, applied, pending_future])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_anexo_c_carryforward_baskets_are_not_axis_siblings(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "irpf_anexo_c_saldo_neg_gyp_general_pendiente_inicio",
            "irpf_anexo_c_saldo_neg_gyp_ahorro_pendiente_inicio",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_anexo_c_exceso_eeficiencia_pendiente_fin",
            "irpf_anexo_c_exceso_eficiencia_energetica_generado",
        )

    def test_deferred_imputation_slot_roles_do_not_warn_as_typos(self) -> None:
        first_slot = _casilla(
            cid="a",
            semantic_role="irpf_ganancia_cripto_importe_percibir_1",
        )
        second_slot = _casilla(
            cid="b",
            semantic_role="irpf_ganancia_cripto_importe_percibir_2",
        )
        rest_slot = _casilla(
            cid="c",
            semantic_role="irpf_ganancia_cripto_importe_percibir_resto",
        )
        m = _modelo("100", "2025", [first_slot, second_slot, rest_slot])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_deferred_imputation_branches_and_polarity_are_not_axis_siblings(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "irpf_ganancia_otros_importe_percibir_1",
            "irpf_ganancia_cripto_importe_percibir_1",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_ganancia_inmueble_ganancia_pendiente_imputacion",
            "irpf_perdida_inmueble_pendiente_imputacion",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_ganancia_otros_valor_transmision_1",
            "irpf_ganancia_otros_valor_transmision_resto",
        )

    def test_cadastral_reference_fields_and_flags_are_not_axis_siblings(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_canarias_referencia_catastral_1",
            "irpf_deduccion_canarias_referencia_catastral_1_flag",
        )

    def test_approved_family_local_generated_pending_roles_do_not_warn_as_typos(self) -> None:
        c_valenciana_generated = _casilla(
            cid="a",
            semantic_role="irpf_deduccion_c_valenciana_autoconsumo_2025_generado",
        )
        c_valenciana_pending = _casilla(
            cid="b",
            semantic_role="irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente",
        )
        murcia_generated = _casilla(
            cid="c",
            semantic_role="irpf_deduccion_murcia_infraestructuras_generado",
        )
        murcia_pending = _casilla(
            cid="d",
            semantic_role="irpf_deduccion_murcia_infraestructuras_2025_pendiente",
        )
        madrid_generated = _casilla(
            cid="e",
            semantic_role="irpf_deduccion_madrid_nuevos_contribuyentes_generado",
        )
        madrid_pending = _casilla(
            cid="f",
            semantic_role="irpf_deduccion_madrid_nuevos_contribuyentes_pendiente",
        )
        m = _modelo(
            "100",
            "2025",
            [
                c_valenciana_generated,
                c_valenciana_pending,
                murcia_generated,
                murcia_pending,
                madrid_generated,
                madrid_pending,
            ],
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert captured == []

    def test_family_local_generated_pending_guard_preserves_blocked_generic_bases(self) -> None:
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_la_rioja_generado_2025",
            "irpf_deduccion_la_rioja_generado_2025_pendiente",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_catalunya_generado_2025",
            "irpf_deduccion_catalunya_pendiente_ejercicio_anterior",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_murcia_infraestructuras_generado",
            "irpf_deduccion_murcia_vehiculo_generado",
        )
        assert not _semantic_roles_are_axis_siblings(
            "irpf_deduccion_c_valenciana_autoconsumo_hasta_2022",
            "irpf_deduccion_c_valenciana_autoconsumo_desde_2023",
        )
