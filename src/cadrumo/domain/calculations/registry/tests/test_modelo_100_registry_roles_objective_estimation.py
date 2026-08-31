"""Modelo 100 objective-estimation semantic-role registry tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import validated_casilla_id
from ._modelo_100_registry_support import _loaded_registry

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_eo_module_units_are_decimal() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_legal_refs = {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        for casilla_id in ("1445", "1448", "1451", "1454", "1457", "1460", "1463"):
            casilla = next(
                casilla
                for casilla in revision.casillas
                if casilla.id == validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
            )

            assert casilla.label == "Nº de unidades"
            assert tuple(casilla.section) == (
                "toma_datos_ampliada",
                "reg_estima_obj",
                "actividad_est_obj",
            )
            assert casilla.data_type == "decimal"
            assert casilla.semantic_role == "irpf_eo_modulo_num_unidades"
            assert expected_legal_refs.issubset(casilla.legal_refs)
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_eo_correction_indices_are_decimal() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_legal_refs = {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }
    expected_roles = {
        "1469": "irpf_eo_indice_corrector_especial",
        "1470": "irpf_eo_indice_corrector_pequena_dimension",
        "1471": "irpf_eo_indice_corrector_temporada",
        "1472": "irpf_eo_indice_corrector_exceso",
        "1473": "irpf_eo_indice_corrector_inicio",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casillas_by_id = {
            casilla.id: casilla
            for casilla in revision.casillas
            if casilla.id
            in {
                validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
                for casilla_id in expected_roles
            }
        }

        assert set(casillas_by_id) == {
            validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
            for casilla_id in expected_roles
        }
        for casilla_id, expected_role in expected_roles.items():
            casilla = casillas_by_id[validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")]

            assert "Índice corrector" in casilla.label
            assert tuple(casilla.section) == (
                "toma_datos_ampliada",
                "reg_estima_obj",
                "actividad_est_obj",
            )
            assert casilla.data_type == "decimal"
            assert casilla.semantic_role == expected_role
            assert expected_legal_refs.issubset(casilla.legal_refs)
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_eo_agricultural_activity_key_is_integer() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_legal_refs = {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.id == validated_casilla_id("1486", surface="test_modelo_100_registry.casilla")
        )

        assert casilla.label == "Actividad realizada. Clave"
        assert tuple(casilla.section) == (
            "toma_datos_ampliada",
            "reg_estima_obj_agricola",
            "actividad_agr",
        )
        assert casilla.data_type == "integer"
        assert casilla.semantic_role == "irpf_eo_agr_clave_actividad"
        assert expected_legal_refs.issubset(casilla.legal_refs)
        assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
            casilla.source_refs,
        )


def test_modelo_100_eo_agricultural_product_indices_are_decimal() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_legal_refs = {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }
    expected_ids = {
        validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
        for casilla_id in (
            "1489",
            "1492",
            "1495",
            "1498",
            "1501",
            "1504",
            "1507",
            "1510",
            "1513",
            "1516",
            "1519",
            "1522",
            "1525",
            "1528",
            "1531",
            "1534",
        )
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        ids_for_year = set(expected_ids)
        if filing_year == 2025:
            ids_for_year.add(validated_casilla_id("0158", surface="test_modelo_100_registry.casilla"))
        casillas_by_id = {
            casilla.id: casilla for casilla in revision.casillas if casilla.semantic_role == "irpf_eo_agr_indice"
        }

        assert set(casillas_by_id) == ids_for_year
        for casilla in casillas_by_id.values():
            assert casilla.label == "Índice"
            assert tuple(casilla.section) == (
                "toma_datos_ampliada",
                "reg_estima_obj_agricola",
                "actividad_agr",
            )
            assert casilla.data_type == "decimal"
            assert expected_legal_refs.issubset(casilla.legal_refs)
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )


def test_modelo_100_eo_agricultural_indices_are_decimal() -> None:
    modelos_by_id, _ = _loaded_registry()
    modelo = modelos_by_id["100"]
    expected_legal_refs = {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-31",
        "ley-35-2006:art-32",
    }
    expected_roles = {
        "1540": "irpf_eo_agr_indice_medios_ajenos",
        "1541": "irpf_eo_agr_indice_personal_asalariado",
        "1542": "irpf_eo_agr_indice_tierras_arrendadas",
        "1544": "irpf_eo_agr_indice_ecologica",
        "1545": "irpf_eo_agr_indice_regadio_electrico",
        "1546": "irpf_eo_agr_indice_pequena_empresa",
        "1547": "irpf_eo_agr_indice_forestal",
    }

    for filing_year in range(2020, 2026):
        revision = modelo.revisions[str(filing_year)]
        roles_for_year = dict(expected_roles)
        if filing_year == 2025:
            roles_for_year["0160"] = "irpf_eo_agr_indice_corrector_mejillon_batea"

        casillas_by_id = {
            casilla.id: casilla
            for casilla in revision.casillas
            if casilla.id
            in {
                validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
                for casilla_id in roles_for_year
            }
        }

        assert set(casillas_by_id) == {
            validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")
            for casilla_id in roles_for_year
        }
        for casilla_id, expected_role in roles_for_year.items():
            casilla = casillas_by_id[validated_casilla_id(casilla_id, surface="test_modelo_100_registry.casilla")]

            assert tuple(casilla.section) == (
                "toma_datos_ampliada",
                "reg_estima_obj_agricola",
                "actividad_agr",
            )
            assert casilla.data_type == "decimal"
            assert casilla.semantic_role == expected_role
            assert expected_legal_refs.issubset(casilla.legal_refs)
            assert {f"aeat-dr-100-{filing_year}-dictionary", f"aeat-dr-100-{filing_year}-xsd"}.issubset(
                casilla.source_refs,
            )
