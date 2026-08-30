"""Contract tests for the G313 certificate record and its fact projection."""

from __future__ import annotations

from typing import TypedDict, Unpack

import pytest
from pydantic import ValidationError

from ....core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ..certificado import ActividadLocalCertificada, CertificadoSituacionCensal, censo_facts_from_certificado

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _CertificadoFields(TypedDict):
    domicilio_fiscal: str
    condicion_residencia: str
    representantes_nif: tuple[str, ...]
    situacion_tributaria: tuple[str, ...]
    actividades: tuple[ActividadLocalCertificada, ...]
    obligaciones_periodicas: tuple[str, ...]


class _CertificadoOverrides(TypedDict, total=False):
    domicilio_fiscal: str
    condicion_residencia: str
    representantes_nif: tuple[str, ...]
    situacion_tributaria: tuple[str, ...]
    actividades: tuple[ActividadLocalCertificada, ...]
    obligaciones_periodicas: tuple[str, ...]


def _certificado(**overrides: Unpack[_CertificadoOverrides]) -> CertificadoSituacionCensal:
    payload: _CertificadoFields = {
        "domicilio_fiscal": "Calle Mayor 1, 28001 Madrid",
        "condicion_residencia": "Residente",
        "representantes_nif": ("12345678Z",),
        "situacion_tributaria": ("Alta en el censo de empresarios",),
        "actividades": (
            ActividadLocalCertificada(
                descripcion="Programación informática",
                epigrafe_iae="763",
                local="Calle Mayor 1",
            ),
        ),
        "obligaciones_periodicas": ("303 trimestral", "130 trimestral"),
    }
    payload.update(overrides)
    return CertificadoSituacionCensal(**payload)


def test_representative_nif_validates_through_core_identity() -> None:
    with pytest.raises(ValidationError):
        _certificado(representantes_nif=("12345678A",))  # wrong control letter


def test_fact_projection_carries_artefact_provenance() -> None:
    facts = censo_facts_from_certificado(_certificado())
    by_path = {fact.path: fact for fact in facts}
    assert by_path["contact.fiscal_address"].value == "Calle Mayor 1, 28001 Madrid"
    assert by_path["activities.description"].value == "Programación informática"
    assert str(by_path["activities.iae_epigraph"].value) == "763"
    assert all(fact.source == PROVENANCE_SOURCE_CENSO_ARTEFACT for fact in facts)


def test_fact_projection_never_invents_display_only_axes() -> None:
    """Residencia, representantes, situación, and obligaciones stay display-only.

    Each has no unambiguous profile counterpart (enum vocabulary unpinned,
    axis mismatch, or derived-schedule input) — the projection must not
    smuggle them into profile facts.
    """
    facts = censo_facts_from_certificado(_certificado())
    paths = {fact.path for fact in facts}
    assert paths == {"contact.fiscal_address", "activities.description", "activities.iae_epigraph"}


def test_fact_projection_omits_absent_actividad() -> None:
    facts = censo_facts_from_certificado(_certificado(actividades=()))
    assert {fact.path for fact in facts} == {"contact.fiscal_address"}


def test_fact_projection_carries_every_actividad_not_only_the_first() -> None:
    """The reported defect: a second local or epígrafe used to vanish with no warning.

    ``actividades[0]`` with no loop dropped every activity past the first at
    projection time -- a successful-looking cotejo that silently lost
    authoritative tax data. The primary activity keeps the implicit
    (unindexed) address every other single-activity producer in this
    codebase writes; every activity after it lands at its own numeric index,
    the addressing scheme the manager and status surfaces already read
    repeatable rows through.
    """
    facts = censo_facts_from_certificado(
        _certificado(
            actividades=(
                ActividadLocalCertificada(descripcion="Programación informática", epigrafe_iae="763"),
                ActividadLocalCertificada(descripcion="Consultoría técnica", epigrafe_iae="774"),
                ActividadLocalCertificada(descripcion="Sin epígrafe declarado"),
            ),
        ),
    )
    by_path = {fact.path: fact for fact in facts}

    assert by_path["activities.description"].value == "Programación informática"
    assert str(by_path["activities.iae_epigraph"].value) == "763"
    assert by_path["activities.1.description"].value == "Consultoría técnica"
    assert str(by_path["activities.1.iae_epigraph"].value) == "774"
    assert by_path["activities.2.description"].value == "Sin epígrafe declarado"
    assert "activities.2.iae_epigraph" not in by_path, "an absent epígrafe must not manufacture an empty fact"
    assert all(fact.source == PROVENANCE_SOURCE_CENSO_ARTEFACT for fact in facts)
