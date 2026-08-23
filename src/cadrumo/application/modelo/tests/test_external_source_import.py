"""Source-only external filing baseline composition tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from ....domain.buckets import BucketEventType
from ....domain.modelos import CalculationRevisionAmendmentKind, ExternalEvidenceKind
from .. import (
    ExternalFilingBaselineSource,
    amend_modelo_revision,
    get_calculation_revision,
    import_external_filing_source,
)
from .._action_errors import ExternalModeloImportError
from .._external_import_actions import _validated_source_lexicals
from ._import_flow_support import (
    _IMPORT_EXPENSE_CASILLA,
    _IMPORT_INCOME_CASILLA,
    _PROFILE_ID,
    _T1,
    _T2,
    _TAX_ID,
    _Repos,
    repos,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_source_lexicals_refuse_dropped_casillas() -> None:
    with pytest.raises(ExternalModeloImportError):
        _validated_source_lexicals(
            canonical_values={
                _IMPORT_INCOME_CASILLA: Decimal("1500"),
                _IMPORT_EXPENSE_CASILLA: Decimal("300"),
            },
            source_lexicals={_IMPORT_INCOME_CASILLA: "1500"},
        )


def test_source_lexicals_refuse_value_shadowing() -> None:
    with pytest.raises(ExternalModeloImportError):
        _validated_source_lexicals(
            canonical_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
            source_lexicals={_IMPORT_INCOME_CASILLA: "1501"},
        )


def test_source_payload_import_creates_exact_amendable_baseline(
    repos: _Repos,
) -> None:
    """The CSV-register source's complete casilla map reaches one durable baseline."""
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    reference_id = "SOURCECSV0001"
    filing = import_external_filing_source(
        ExternalFilingBaselineSource(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id=reference_id,
            tax_id=_TAX_ID,
            casilla_lexicals={
                _IMPORT_INCOME_CASILLA: " 001500.00 ",
                _IMPORT_EXPENSE_CASILLA: "300,0",
            },
        ),
        bucket_id=_PROFILE_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    assert len(wu_repo.load()) == 1
    baseline = get_calculation_revision(
        filing.calculation_revision_id,
        calculation_repository=cr_repo,
    )
    assert baseline.input_values_by_casilla_id == {
        _IMPORT_INCOME_CASILLA: " 001500.00 ",
        _IMPORT_EXPENSE_CASILLA: "300,0",
    }
    assert baseline.casilla_values == {
        _IMPORT_INCOME_CASILLA: Decimal("1500.00"),
        _IMPORT_EXPENSE_CASILLA: Decimal("300.0"),
    }

    amended = amend_modelo_revision(
        from_filing_record_id=filing.filing_record_id,
        overrides={_IMPORT_INCOME_CASILLA: Decimal("1600")},
        amendment_kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        reason="source-only baseline is immediately amendable",
        actor="operator",
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )
    assert amended.amends_filing_record_id == filing.filing_record_id


def test_public_source_import_refuses_partial_required_manifest_without_writes(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(ExternalModeloImportError):
        import_external_filing_source(
            ExternalFilingBaselineSource(
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                evidence_reference_id="PARTIALCSV01",
                tax_id=_TAX_ID,
                casilla_lexicals={_IMPORT_INCOME_CASILLA: "1500"},
            ),
            bucket_id=_PROFILE_ID,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
    assert not wu_repo.load()
    assert not bv_repo.load().for_bucket(
        _PROFILE_ID,
        event_types=(BucketEventType.MODELO_WORK_UNIT_CREATED,),
    )


def test_failed_receipt_evidence_validation_leaves_no_work_unit_or_event(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    with pytest.raises(ExternalModeloImportError):
        import_external_filing_source(
            ExternalFilingBaselineSource(
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                evidence_reference_id="MISSINGPDF01",
                tax_id=_TAX_ID,
                casilla_lexicals={
                    _IMPORT_INCOME_CASILLA: "1500",
                    _IMPORT_EXPENSE_CASILLA: "300",
                },
            ),
            bucket_id=_PROFILE_ID,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )
    assert not wu_repo.load()
    assert not bv_repo.load().for_bucket(
        _PROFILE_ID,
        event_types=(BucketEventType.MODELO_WORK_UNIT_CREATED,),
    )
