"""Modelo 100 capital-gains semantic-role registry tests."""

from __future__ import annotations

from functools import lru_cache

import pytest

from cadrumo.application.modelo.semantic_role_resolution import casilla_id_for_unique_revision_semantic_role

from .authored_edition_support import authored_revisions
from .modelo_100_registry_support import modelo_100_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CRYPTO_SECTION = ("toma_datos_ampliada", "gp_otros_criptomonedas", "elemento_criptomoneda")
_INMUEBLE_SECTION = ("toma_datos_ampliada", "gp_otros_inmuebles", "elemento_inmueble")
_OTHER_ELEMENTS_SECTION = ("toma_datos_ampliada", "gp_otros_elementos", "elemento_patrimonial")
_CRYPTO_COLLECTION_YEARS_ROLE = "irpf_ganancia_cripto_anios_cobro_total"
_INMUEBLE_COLLECTION_YEARS_ROLE = "irpf_ganancia_inmueble_anios_cobro_pendiente"
_OTHER_COLLECTION_YEARS_ROLE = "irpf_ganancia_otros_anios_cobro_pendiente"
_STALE_CRYPTO_PENDING_YEARS_ROLE = "irpf_ganancia_cripto_anios_cobro_pendiente"
_CAPITAL_GAIN_REFS = {"ley-35-2006:art-33", "ley-35-2006:art-34"}
# Every authored Modelo 100 edition, oldest first. The special-asset casillas (crypto, immovables) exist from the
# third edition on, and the instalment label names the pending balance from the fifth.
_LIVE_M100_YEARS = tuple(revision.valid_from.year for revision in authored_revisions("100"))
_SPECIAL_ASSET_YEARS = _LIVE_M100_YEARS[2:]
_PENDING_LABEL_FROM = _LIVE_M100_YEARS[4]
_COLLECTION_YEAR_COUNT_CASES = tuple(
    (year, casilla_id, role, section, year >= _PENDING_LABEL_FROM)
    for casilla_id, role, section, years in (
        ("0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, _LIVE_M100_YEARS),
        ("1859", _CRYPTO_COLLECTION_YEARS_ROLE, _CRYPTO_SECTION, _SPECIAL_ASSET_YEARS),
        ("1881", _INMUEBLE_COLLECTION_YEARS_ROLE, _INMUEBLE_SECTION, _SPECIAL_ASSET_YEARS),
    )
    for year in years
)
_OTHER_ELEMENT_IMPUTATION_ROLES = {
    "0363": "irpf_ganancia_otros_anio_imputacion_1",
    "0367": "irpf_ganancia_otros_anio_imputacion_2",
    "0371": "irpf_ganancia_otros_anio_imputacion_3",
    "0375": "irpf_ganancia_otros_anio_imputacion_4",
}
_SPECIAL_ASSET_IMPUTATION_CASES = (
    (
        _CRYPTO_SECTION,
        {
            "1861": "irpf_ganancia_cripto_anio_imputacion_1",
            "1865": "irpf_ganancia_cripto_anio_imputacion_2",
            "1869": "irpf_ganancia_cripto_anio_imputacion_3",
            "1873": "irpf_ganancia_cripto_anio_imputacion_4",
        },
    ),
    (
        _INMUEBLE_SECTION,
        {
            "1886": "irpf_ganancia_inmueble_anio_imputacion_1",
            "1890": "irpf_ganancia_inmueble_anio_imputacion_2",
            "1894": "irpf_ganancia_inmueble_anio_imputacion_3",
            "1898": "irpf_ganancia_inmueble_anio_imputacion_4",
        },
    ),
)


@lru_cache
def _revision_for(filing_year: int):
    return modelo_100_revision(filing_year)


def test_modelo_100_instalment_collection_year_counts_are_integer() -> None:
    for filing_year, casilla_id, expected_role, expected_section, expected_pending_word in _COLLECTION_YEAR_COUNT_CASES:
        revision = _revision_for(filing_year)
        casilla = next(casilla for casilla in revision.casillas if casilla.id == casilla_id)

        assert "cobro" in casilla.label, (filing_year, casilla_id)
        assert ("pendiente" in casilla.label) is expected_pending_word, (filing_year, casilla_id)
        assert tuple(casilla.section) == expected_section, (filing_year, casilla_id)
        assert casilla.data_type == "integer", (filing_year, casilla_id)
        assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
        assert set(casilla.legal_refs) >= _CAPITAL_GAIN_REFS, (filing_year, casilla_id)
        assert casilla_id_for_unique_revision_semantic_role(revision, expected_role) == casilla_id


def test_modelo_100_other_element_imputation_years_are_positional_years() -> None:
    for filing_year in _LIVE_M100_YEARS:
        revision = _revision_for(filing_year)
        casillas_by_id = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in _OTHER_ELEMENT_IMPUTATION_ROLES
        }

        assert set(casillas_by_id) == set(_OTHER_ELEMENT_IMPUTATION_ROLES)
        for casilla_id, expected_role in _OTHER_ELEMENT_IMPUTATION_ROLES.items():
            casilla = casillas_by_id[casilla_id]

            assert casilla.label == "Año de imputación"
            assert tuple(casilla.section) == _OTHER_ELEMENTS_SECTION
            assert casilla.data_type == "year"
            assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
            assert set(casilla.legal_refs) >= _CAPITAL_GAIN_REFS
            assert {
                f"aeat-dr-100-{filing_year}-dictionary",
                f"aeat-dr-100-{filing_year}-xsd",
            }.issubset(casilla.source_refs)
            assert casilla_id_for_unique_revision_semantic_role(revision, expected_role) == casilla_id


def test_modelo_100_special_asset_imputation_years_are_years() -> None:
    for filing_year in _SPECIAL_ASSET_YEARS:
        revision = _revision_for(filing_year)
        for expected_section, expected_roles in _SPECIAL_ASSET_IMPUTATION_CASES:
            casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in expected_roles}

            assert set(casillas_by_id) == set(expected_roles)
            for casilla_id, expected_role in expected_roles.items():
                casilla = casillas_by_id[casilla_id]

                assert casilla.label == "Año de imputación"
                assert tuple(casilla.section) == expected_section
                assert casilla.data_type == "year"
                assert casilla.semantic_role == expected_role, (filing_year, casilla_id)
                assert set(casilla.legal_refs) >= _CAPITAL_GAIN_REFS
                assert {
                    f"aeat-dr-100-{filing_year}-dictionary",
                    f"aeat-dr-100-{filing_year}-xsd",
                }.issubset(casilla.source_refs)
                assert casilla_id_for_unique_revision_semantic_role(revision, expected_role) == casilla_id


def test_modelo_100_crypto_instalment_collection_years_role_uses_total_not_pending_name() -> None:
    for filing_year in _SPECIAL_ASSET_YEARS:
        revision = _revision_for(filing_year)

        assert casilla_id_for_unique_revision_semantic_role(revision, _STALE_CRYPTO_PENDING_YEARS_ROLE) is None
