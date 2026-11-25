"""Modelo 100 regularization semantic-role registry tests."""

from __future__ import annotations

import pytest

from .authored_edition_support import authored_revisions, oldest_authored_edition
from .modelo_100_registry_support import modelo_100_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The oldest authored Modelo 100 revision, a storage root below the support floor,
# whose rectification IBAN is still the root regularization account.
_ROOT_EDITION = oldest_authored_edition("100")
# The three editions after the root carry the SEPA rectification account triple.
_SEPA_ACCOUNT_EDITIONS = tuple(revision.valid_from.year for revision in authored_revisions("100"))[1:4]

_REGULARIZATION_ART_97_REF = "ley-35-2006:art-97"
_RECTIFICATION_IBAN_ROLE = "irpf_rectificacion_iban"
_RECTIFICATION_SEPA_IBAN_ROLE = "irpf_regularizacion_sepa_cuenta_iban"
_RECTIFICATION_SEPA_SWIFT_ROLE = "irpf_rectsepa_swift_bic"
_LEGACY_RECTIFICATION_SEPA_IBAN_ROLE = "irpf_rectsepa_cuenta_iban"


def test_modelo_100_root_revision_rectification_iban_uses_root_regularization_account() -> None:
    revision = modelo_100_revision(_ROOT_EDITION)
    casilla = next(casilla for casilla in revision.casillas if casilla.id == "0687")

    assert casilla.label == "IBAN rectificación"
    assert tuple(casilla.section) == ("resultados", "regularizacion_res")
    assert casilla.data_type == "iban"
    assert casilla.semantic_role == _RECTIFICATION_IBAN_ROLE
    assert _REGULARIZATION_ART_97_REF in casilla.legal_refs


@pytest.mark.parametrize("filing_year", _SEPA_ACCOUNT_EDITIONS)
def test_modelo_100_rectification_sepa_account_is_iban_typed_and_role_specific(
    filing_year: int,
) -> None:
    revision = modelo_100_revision(filing_year)
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
