"""Justificante and CSV enrollment checks for external Modelo filing imports."""

from __future__ import annotations

import pytest

from ....domain.modelos.filing_record import ExternalEvidenceKind
from .._action_errors import ExternalModeloImportError
from ._import_flow_support import (
    _T1,
    _TAX_ID,
    _import_external_filing,
    _persist_matching_justificante,
    _Repos,
    _seed_work_unit,
    repos,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_import_refuses_justificante_evidence_without_persisted_artifact(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-MISSING",
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_missing"


def test_import_refuses_justificante_evidence_without_expected_tax_id(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUSTNOTAXID1",
        work_unit,
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUSTNOTAXID1",
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_tax_id_missing"


def test_import_refuses_justificante_evidence_for_different_period(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUSTMISMATCH",
        work_unit,
        period="2T",
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUSTMISMATCH",
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_refuses_justificante_evidence_for_different_taxpayer(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUSTWRONGTAXPAYER",
        work_unit,
        captured_at=_T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        _import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUSTWRONGTAXPAYER",
            expected_tax_id="B12345674",
            clock=_T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_justificante_taxpayer_match_is_case_insensitive(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)
    _persist_matching_justificante(
        "JUSTCASETAXPAYER",
        work_unit,
        captured_at=_T1,
        tax_id="X1234567L",
    )

    filing = _import_external_filing(
        repos,
        work_unit,
        evidence_reference_id="JUSTCASETAXPAYER",
        expected_tax_id="x1234567l",
        clock=_T1,
    )

    assert filing.aeat_accepted is True
    assert filing.external_evidence is not None
    assert filing.external_evidence.reference_id == "JUSTCASETAXPAYER"


def test_import_justificante_pdf_refuses_without_enrolled_justificante(repos: _Repos) -> None:
    wu_repo, _, _, _, _ = repos
    work_unit = _seed_work_unit(wu_repo)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        _import_external_filing(
            repos,
            work_unit,
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="PDF-MISSING-JUSTIFICANTE",
            expected_tax_id=_TAX_ID,
            clock=_T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_justificante_missing"
