"""Canonical wire checks for the shared censal fact payload."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....domain.censo.tests.test_certificado import _certificado
from .. import _censo_payloads
from .._censo_payloads import CensoFactPayload, CensoFileIngestResult, CensoPullResult
from .._censo_transport import _file_import_preview_lines

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def test_censo_fact_payload_round_trips_a_valid_row() -> None:
    row = CensoFactPayload(path="contact.postcode", value="28001", source="censo_artefact_g313")

    assert row.path == "contact.postcode"
    assert row.source == "censo_artefact_g313"


@pytest.mark.parametrize(
    "kwargs",
    (
        {"path": "bad", "value": "x", "source": "censo_artefact_g313"},
        {"path": "", "value": "x", "source": "censo_artefact_g313"},
        {"path": "contact.postcode", "value": "x", "source": ""},
        {"path": "contact.postcode", "value": "x", "source": "a" * 81},
    ),
)
def test_censo_fact_payload_refuses_malformed_row(kwargs: dict[str, str]) -> None:
    """A malformed path or a blank/oversized source is refused.

    Whether a source token is declared by the profile schema is checked when a
    whole record is validated against its pinned schema, not on this wire row.
    """
    with pytest.raises(ValidationError):
        CensoFactPayload(**kwargs)


def test_censo_transport_and_pull_share_one_canonical_fact_wire_projection() -> None:
    assert not hasattr(_censo_payloads, "CensoPullFactPayload")
    assert not hasattr(_censo_payloads, "CensoFileFactPayload")

    row = CensoFactPayload(path="contact.postcode", value="28001", source="censo_artefact_g313")
    file_result = CensoFileIngestResult(applied=False, certificate=_certificado(), facts=(row,))
    pull_result = CensoPullResult(
        applied=False,
        source_url="https://example.invalid/censal",
        adopted=(row,),
        unchanged=(row,),
    )

    assert type(file_result.facts[0]) is CensoFactPayload
    assert type(pull_result.adopted[0]) is CensoFactPayload
    assert type(pull_result.unchanged[0]) is CensoFactPayload
    assert file_result.model_dump(mode="json")["facts"] == [row.model_dump(mode="json")]
    assert pull_result.model_dump(mode="json")["adopted"] == [row.model_dump(mode="json")]


def test_import_preview_retains_all_certified_axes_without_adopting_display_evidence() -> None:
    import json

    from .....domain.censo.certificado import censo_facts_from_certificado

    certificate = _certificado()
    facts = censo_facts_from_certificado(certificate)
    result = CensoFileIngestResult(
        applied=False,
        certificate=certificate,
        facts=tuple(CensoFactPayload(path=fact.path, value=str(fact.value), source=fact.source) for fact in facts),
    )
    json_evidence = result.model_dump(mode="json")["certificate"]
    text_evidence = json.loads(_file_import_preview_lines(result)[1])
    assert (
        json_evidence
        == text_evidence
        == {
            "domicilio_fiscal": "Calle Mayor 1, 28001 Madrid",
            "condicion_residencia": "Residente",
            "representantes_nif": ["12345678Z"],
            "situacion_tributaria": ["Alta en el censo de empresarios"],
            "actividades": [
                {"descripcion": "Programación informática", "epigrafe_iae": "763", "local": "Calle Mayor 1"}
            ],
            "obligaciones_periodicas": ["303 trimestral", "130 trimestral"],
        }
    )
    assert {fact.path for fact in result.facts} == {
        "contact.fiscal_address",
        "activities.description",
        "activities.iae_epigraph",
    }
    assert not result.applied
