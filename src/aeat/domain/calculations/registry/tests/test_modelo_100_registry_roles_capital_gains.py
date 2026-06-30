"""Modelo 100 capital-gains semantic-role registry tests."""

from __future__ import annotations

import pytest

from .....application.modelo._semantic_role_resolution import casilla_id_for_unique_revision_semantic_role
from ._modelo_100_registry_support import _modelo_100_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CRYPTO_SECTION = ("toma_datos_ampliada", "gp_otros_criptomonedas", "elemento_criptomoneda")
_CRYPTO_COLLECTION_YEARS_ROLE = "irpf_ganancia_cripto_anios_cobro_total"
_STALE_CRYPTO_PENDING_YEARS_ROLE = "irpf_ganancia_cripto_anios_cobro_pendiente"
_CAPITAL_GAIN_REFS = {"ley-35-2006:art-33", "ley-35-2006:art-34"}


@pytest.mark.parametrize(
    ("filing_year", "expected_pending_word"),
    [
        (2022, False),
        (2023, False),
        (2024, True),
        (2025, True),
    ],
)
def test_modelo_100_crypto_instalment_collection_years_role_covers_label_variants(
    filing_year: int,
    expected_pending_word: bool,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "1859")

    assert "cobro" in casilla.label
    assert ("pendiente" in casilla.label) is expected_pending_word
    assert tuple(casilla.section) == _CRYPTO_SECTION
    assert casilla.semantic_role == _CRYPTO_COLLECTION_YEARS_ROLE
    assert set(casilla.legal_refs) >= _CAPITAL_GAIN_REFS
    assert casilla_id_for_unique_revision_semantic_role(revision, _CRYPTO_COLLECTION_YEARS_ROLE) == "1859"
    assert casilla_id_for_unique_revision_semantic_role(revision, _STALE_CRYPTO_PENDING_YEARS_ROLE) is None
