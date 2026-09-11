"""Modelo 100 regularization semantic-role registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_registry_support import _modelo_100_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGULARIZATION_ART_97_REF = "ley-35-2006:art-97"
_RECTIFICATION_IBAN_ROLE = "irpf_rectificacion_iban"
_RECTIFICATION_SEPA_IBAN_ROLE = "irpf_regularizacion_sepa_cuenta_iban"
_RECTIFICATION_SEPA_SWIFT_ROLE = "irpf_rectsepa_swift_bic"
_LEGACY_RECTIFICATION_SEPA_IBAN_ROLE = "irpf_rectsepa_cuenta_iban"


def test_modelo_100_2020_rectification_iban_uses_root_regularization_account() -> None:
    revision = _modelo_100_snapshot(2020).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0687")

    assert casilla.label == "IBAN rectificación"
    assert tuple(casilla.section) == ("resultados", "regularizacion_res")
    assert casilla.data_type == "iban"
    assert casilla.semantic_role == _RECTIFICATION_IBAN_ROLE
    assert _REGULARIZATION_ART_97_REF in casilla.legal_refs


@pytest.mark.parametrize("filing_year", [2021, 2022, 2023])
def test_modelo_100_rectification_sepa_account_is_iban_typed_and_role_specific(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"1780", "1781", "1782"}}
    stale_roles = [
        casilla.id for casilla in revision.casillas if casilla.semantic_role == _LEGACY_RECTIFICATION_SEPA_IBAN_ROLE
    ]

    assert not stale_roles
    assert set(casillas_by_id) == {"1780", "1781", "1782"}

    root_iban = casillas_by_id["1780"]
    assert root_iban.label == "IBAN rectificación"
    assert tuple(root_iban.section) == ("resultados", "regularizacion_res")
    assert root_iban.data_type == "iban"
    assert root_iban.semantic_role == _RECTIFICATION_IBAN_ROLE
    assert _REGULARIZATION_ART_97_REF in root_iban.legal_refs

    sepa_iban = casillas_by_id["1781"]
    assert sepa_iban.label == "SEPA rectificación"
    assert tuple(sepa_iban.section) == ("resultados", "regularizacion_res", "rectsepa")
    assert sepa_iban.data_type == "iban"
    assert sepa_iban.semantic_role == _RECTIFICATION_SEPA_IBAN_ROLE
    assert _REGULARIZATION_ART_97_REF in sepa_iban.legal_refs

    sepa_swift = casillas_by_id["1782"]
    assert sepa_swift.label == "SWIFT rectificación"
    assert tuple(sepa_swift.section) == ("resultados", "regularizacion_res", "rectsepa")
    assert sepa_swift.data_type == "text"
    assert sepa_swift.semantic_role == _RECTIFICATION_SEPA_SWIFT_ROLE
    assert _REGULARIZATION_ART_97_REF in sepa_swift.legal_refs
