"""Source-only external filing baseline composition tests."""

from __future__ import annotations

from decimal import Decimal
from typing import override

import pytest

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.storage import SecureObjectRevisionConflictError, SecureObjectWrite
from ....core import Period
from ....domain.buckets import BucketEventType
from ....domain.modelos import ExternalEvidenceKind
from ....domain.modelos.calculation_revision import CalculationRevisionAmendmentKind
from ...calculations import (
    CalculationObservationRepository,
    CrossPeriodCleanStateBlocker,
    ObservationEnvelopePayload,
    ObservationSourceKind,
)
from ...calculations import (
    filing_external_evidence_blockers as _filing_external_evidence_blockers,
)
from .._action_errors import ExternalModeloImportError
from .._amendment_actions import amend_modelo_revision
from .._calculation_actions import get_calculation_revision
from .._work_lifecycle import create_work_unit
from ..external_import_actions import (
    ExternalFilingBaselineSource,
    _validated_source_lexicals,
    import_external_filing_source,
)
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

_STALE_REVISION_ID = "0" * 64


class _ConflictingObservationRepository(CalculationObservationRepository):
    """Inject a real observation-row CAS conflict into the production batch."""

    @override
    def to_secure_object_write(
        self,
        payload: ObservationEnvelopePayload,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return super().to_secure_object_write(payload, expected_revision_id=_STALE_REVISION_ID)


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
    observed = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))
    assert observed is not None
    assert observed.source_kind is ObservationSourceKind.AEAT_CSV_REGISTER
    assert observed.source_metadata["external_evidence_reference_id"] == reference_id
    assert observed.source_metadata["filing_record_id"] == filing.filing_record_id
    assert not _filing_external_evidence_blockers(
        filing,
        observed.source_kind.value,
        justificante_repository=JustificanteRepository(),
        taxpayer_tax_id=_TAX_ID,
        observation_source_metadata=observed.source_metadata,
    )

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
    assert (
        CalculationObservationRepository().load_observation(
            "130",
            Period.from_year_and_code(2026, "1T"),
        )
        is None
    )


def test_csv_filing_refuses_tampered_observation_evidence_binding(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    filing = import_external_filing_source(
        ExternalFilingBaselineSource(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="TAMPERCSV001",
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
    blockers = _filing_external_evidence_blockers(
        filing,
        ObservationSourceKind.AEAT_CSV_REGISTER.value,
        justificante_repository=JustificanteRepository(),
        taxpayer_tax_id=_TAX_ID,
        observation_source_metadata={
            "external_evidence_reference_id": "OTHERCSV001",
            "filing_record_id": filing.filing_record_id,
        },
    )
    assert blockers == [CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD]


def test_observation_write_failure_rolls_back_entire_external_import_batch(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = create_work_unit(
        bucket_id=_PROFILE_ID,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    import_external_filing_source(
        ExternalFilingBaselineSource(
            modelo="130",
            filing_year=2026,
            period=work_unit.period,
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="ROLLBACKBASE01",
            tax_id=_TAX_ID,
            casilla_lexicals={
                _IMPORT_INCOME_CASILLA: "1400",
                _IMPORT_EXPENSE_CASILLA: "250",
            },
        ),
        bucket_id=_PROFILE_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=fr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    baseline_work_units = wu_repo.load()
    baseline_revisions = cr_repo.load()
    baseline_filings = fr_repo.load()
    baseline_events = bv_repo.load()
    observations = _ConflictingObservationRepository()
    baseline_observation = observations.load_observation("130", work_unit.period)
    assert baseline_observation is not None

    with pytest.raises(SecureObjectRevisionConflictError):
        import_external_filing_source(
            ExternalFilingBaselineSource(
                modelo="130",
                filing_year=2026,
                period=work_unit.period,
                evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                evidence_reference_id="ROLLBACKCSV01",
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
            observation_repository=observations,
            clock=_T2,
        )

    assert wu_repo.load() == baseline_work_units
    assert cr_repo.load() == baseline_revisions
    assert fr_repo.load() == baseline_filings
    assert bv_repo.load() == baseline_events
    assert observations.load_observation("130", work_unit.period) == baseline_observation


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
