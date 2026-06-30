"""Modelo 100 capital-gains semantic-role registry tests."""

from __future__ import annotations

import pytest

from .....application.modelo._semantic_role_resolution import casilla_id_for_unique_revision_semantic_role
from ._modelo_100_registry_support import _modelo_100_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CRYPTO_SECTION = ("toma_datos_ampliada", "gp_otros_criptomonedas", "elemento_criptomoneda")
_INMUEBLE_SECTION = ("toma_datos_ampliada", "gp_otros_inmuebles", "elemento_inmueble")
_OTHER_ELEMENTS_SECTION = ("toma_datos_ampliada", "gp_otros_elementos", "elemento_patrimonial")
_CRYPTO_COLLECTION_YEARS_ROLE = "irpf_ganancia_cripto_anios_cobro_total"
_INMUEBLE_COLLECTION_YEARS_ROLE = "irpf_ganancia_inmueble_anios_cobro_pendiente"
_OTHER_COLLECTION_YEARS_ROLE = "irpf_ganancia_otros_anios_cobro_pendiente"
_STALE_CRYPTO_PENDING_YEARS_ROLE = "irpf_ganancia_cripto_anios_cobro_pendiente"
_CAPITAL_GAIN_REFS = {"ley-35-2006:art-33", "ley-35-2006:art-34"}


@pytest.mark.parametrize(
    ("filing_year", "casilla_id", "expected_role", "expected_section", "expected_pending_word"),
    [
        (2020, "0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, False),
        (2021, "0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, False),
        (2022, "0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, False),
        (2023, "0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, False),
        (2024, "0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, True),
        (2025, "0358", _OTHER_COLLECTION_YEARS_ROLE, _OTHER_ELEMENTS_SECTION, True),
        (2022, "1859", _CRYPTO_COLLECTION_YEARS_ROLE, _CRYPTO_SECTION, False),
        (2023, "1859", _CRYPTO_COLLECTION_YEARS_ROLE, _CRYPTO_SECTION, False),
        (2024, "1859", _CRYPTO_COLLECTION_YEARS_ROLE, _CRYPTO_SECTION, True),
        (2025, "1859", _CRYPTO_COLLECTION_YEARS_ROLE, _CRYPTO_SECTION, True),
        (2022, "1881", _INMUEBLE_COLLECTION_YEARS_ROLE, _INMUEBLE_SECTION, False),
        (2023, "1881", _INMUEBLE_COLLECTION_YEARS_ROLE, _INMUEBLE_SECTION, False),
        (2024, "1881", _INMUEBLE_COLLECTION_YEARS_ROLE, _INMUEBLE_SECTION, True),
        (2025, "1881", _INMUEBLE_COLLECTION_YEARS_ROLE, _INMUEBLE_SECTION, True),
    ],
)
def test_modelo_100_instalment_collection_year_counts_are_integer(
    filing_year: int,
    casilla_id: str,
    expected_role: str,
    expected_section: tuple[str, ...],
    expected_pending_word: bool,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == casilla_id)

    assert "cobro" in casilla.label
    assert ("pendiente" in casilla.label) is expected_pending_word
    assert tuple(casilla.section) == expected_section
    assert casilla.data_type == "integer"
    assert casilla.semantic_role == expected_role
    assert set(casilla.legal_refs) >= _CAPITAL_GAIN_REFS
    assert casilla_id_for_unique_revision_semantic_role(revision, expected_role) == casilla_id


@pytest.mark.parametrize("filing_year", [2022, 2023, 2024, 2025])
def test_modelo_100_crypto_instalment_collection_years_role_uses_total_not_pending_name(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision

    assert casilla_id_for_unique_revision_semantic_role(revision, _STALE_CRYPTO_PENDING_YEARS_ROLE) is None
