"""Justificante and CSV enrollment checks for external Modelo filing imports."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.action_errors import ExternalModeloImportError
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind
from cadrumo.entrypoints.tests.profile_persistence.import_flow_support import (
    T1,
    TAX_ID,
    Repos,
    import_external_filing,
    persist_matching_justificante,
    repos,
    seed_work_unit,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_import_refuses_justificante_evidence_without_persisted_artifact(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUST-MISSING",
            expected_tax_id=TAX_ID,
            clock=T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_missing"


def test_import_refuses_justificante_evidence_without_expected_tax_id(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)
    persist_matching_justificante(
        "JUSTNOTAXID1",
        work_unit,
        captured_at=T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUSTNOTAXID1",
            clock=T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_tax_id_missing"


def test_import_refuses_justificante_evidence_for_different_period(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)
    persist_matching_justificante(
        "JUSTMISMATCH",
        work_unit,
        period="2T",
        captured_at=T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUSTMISMATCH",
            expected_tax_id=TAX_ID,
            clock=T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_refuses_justificante_evidence_for_different_taxpayer(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)
    persist_matching_justificante(
        "JUSTWRONGTAXPAYER",
        work_unit,
        captured_at=T1,
    )

    with pytest.raises(ExternalModeloImportError) as raised:
        import_external_filing(
            repos,
            work_unit,
            evidence_reference_id="JUSTWRONGTAXPAYER",
            expected_tax_id="B00015016",
            clock=T1,
        )

    assert raised.value.translated_message == "application.modelo.errors.external_import_justificante_mismatch"


def test_import_justificante_taxpayer_match_is_case_insensitive(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)
    persist_matching_justificante(
        "JUSTCASETAXPAYER",
        work_unit,
        captured_at=T1,
        tax_id="X0001500M",
    )

    filing = import_external_filing(
        repos,
        work_unit,
        evidence_reference_id="JUSTCASETAXPAYER",
        expected_tax_id="x0001500m",
        clock=T1,
    )

    assert filing.aeat_accepted is True
    assert filing.external_evidence is not None
    assert filing.external_evidence.reference_id == "JUSTCASETAXPAYER"


def test_import_justificante_pdf_refuses_without_enrolled_justificante(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _, _, _, bucket_event_repository = repos
    work_unit = seed_work_unit(wu_repo, bucket_event_repository, operation=operation)

    with pytest.raises(ExternalModeloImportError) as exc_info:
        import_external_filing(
            repos,
            work_unit,
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id="PDF-MISSING-JUSTIFICANTE",
            expected_tax_id=TAX_ID,
            clock=T1,
        )
    assert exc_info.value.translated_message == "application.modelo.errors.external_import_justificante_missing"
