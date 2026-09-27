"""Modelo 100 pension-social semantic-role registry tests."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.semantic_role_resolution import casilla_id_for_unique_revision_semantic_role

from ._modelo_100_registry_support import _modelo_100_revision
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = committed_supported_filing_years()
# The authored-history edition, below the support floor, whose 0426 is the employer
# anexo C.3 slot; its dictionaries and XSD are the cited evidence.
_EMPLOYER_ANEXO_C3_EDITION = 2021
# From the floor every authored edition repurposes 0426 as the worker contribution
# slot; the horizon only projects the newest of them.
_WORKER_CONTRIBUTION_EDITIONS = tuple(year for year in _SUPPORT.years if year < _SUPPORT.horizon)

_PREVISION_SOCIAL_SECTION = ("toma_datos_ampliada", "red_base_imponible", "red_prevision_social")
_ART_51_REF = "ley-35-2006:art-51"
# The anexo C.3 revision's applicability window predates art. 52's current
# catalogue redaction (effective_from 2023-01-01, Ley 31/2022 art. 62.1); it
# cites the version-scoped 2021-only redaction (Ley 11/2020 art. 62.2) instead.
_ART_52_REF = "ley-35-2006:art-52-2021"
_AEAT_ANEXO_C3_DICTIONARY_REF = f"aeat-dr-100-{_EMPLOYER_ANEXO_C3_EDITION}-dictionary"
_AEAT_ANEXO_C3_INPUT_DICTIONARY_REF = f"aeat-dr-100-{_EMPLOYER_ANEXO_C3_EDITION}-input-dictionary"
_AEAT_ANEXO_C3_XSD_REF = f"aeat-dr-100-{_EMPLOYER_ANEXO_C3_EDITION}-xsd"
_EMPLOYER_ANEXO_C3_ROLE = "irpf_red_prevision_social_contribuciones_empresariales_anexo_c3"
_GENERAL_EMPLOYER_ROLE = "irpf_red_prevision_social_contribuciones_empresariales_excepto_scd"
_WORKER_WITH_EMPLOYER_CONTRIBUTION_ROLE = (
    "irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial"
)


def test_modelo_100_anexo_c3_edition_prevision_social_0426_is_distinct_employer_slot() -> None:
    revision = _modelo_100_revision(_EMPLOYER_ANEXO_C3_EDITION)
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"0426", "0427"}}

    assert set(casillas_by_id) == {"0426", "0427"}
    casilla_0426 = casillas_by_id["0426"]
    casilla_0427 = casillas_by_id["0427"]

    assert casilla_0426.label.startswith("Contribuciones empresariales")
    assert "Cumplimente el anexo C.3" in casilla_0426.label
    assert tuple(casilla_0426.section) == _PREVISION_SOCIAL_SECTION
    assert casilla_0426.semantic_role == _EMPLOYER_ANEXO_C3_ROLE
    assert casilla_0426.semantic_role_cardinality == "intentional_singleton"
    assert casilla_0426.semantic_role_cardinality_reason
    assert {_ART_51_REF, _ART_52_REF} <= set(casilla_0426.legal_refs)
    assert {
        _AEAT_ANEXO_C3_DICTIONARY_REF,
        _AEAT_ANEXO_C3_INPUT_DICTIONARY_REF,
        _AEAT_ANEXO_C3_XSD_REF,
    } <= set(casilla_0426.source_refs)

    assert casilla_0427.semantic_role == _GENERAL_EMPLOYER_ROLE
    assert casilla_0427.semantic_role != casilla_0426.semantic_role
    assert casilla_id_for_unique_revision_semantic_role(revision, _EMPLOYER_ANEXO_C3_ROLE) == "0426"
    assert casilla_id_for_unique_revision_semantic_role(revision, _GENERAL_EMPLOYER_ROLE) == "0427"
    assert casilla_id_for_unique_revision_semantic_role(revision, _WORKER_WITH_EMPLOYER_CONTRIBUTION_ROLE) is None


@pytest.mark.parametrize("filing_year", _WORKER_CONTRIBUTION_EDITIONS)
def test_modelo_100_supported_editions_prevision_social_0426_is_worker_contribution_slot(filing_year: int) -> None:
    revision = _modelo_100_revision(filing_year)
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in {"0426", "0427"}}

    assert set(casillas_by_id) == {"0426", "0427"}
    casilla_0426 = casillas_by_id["0426"]
    casilla_0427 = casillas_by_id["0427"]

    assert casilla_0426.label.startswith("Aportaciones del trabajador")
    assert "contribuciones empresariales" in casilla_0426.label
    assert tuple(casilla_0426.section) == _PREVISION_SOCIAL_SECTION
    assert casilla_0426.semantic_role == _WORKER_WITH_EMPLOYER_CONTRIBUTION_ROLE

    assert casilla_0427.semantic_role == _GENERAL_EMPLOYER_ROLE
    assert casilla_0427.semantic_role != casilla_0426.semantic_role
    assert (
        casilla_id_for_unique_revision_semantic_role(
            revision,
            _WORKER_WITH_EMPLOYER_CONTRIBUTION_ROLE,
        )
        == "0426"
    )
    assert casilla_id_for_unique_revision_semantic_role(revision, _GENERAL_EMPLOYER_ROLE) == "0427"
    assert casilla_id_for_unique_revision_semantic_role(revision, _EMPLOYER_ANEXO_C3_ROLE) is None
