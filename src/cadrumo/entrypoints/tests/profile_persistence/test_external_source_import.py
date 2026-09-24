"""Source-only external filing baseline composition tests."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, override

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.entrypoints.tests.profile_persistence.import_flow_support import (
    _IMPORT_EXPENSE_CASILLA,
    _IMPORT_INCOME_CASILLA,
    _PROFILE_ID,
    _T1,
    _T2,
    _TAX_ID,
    _Repos,
    repos,
)
from cadrumo.adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from cadrumo.application.calculations.cross_period_external_evidence import (
    filing_external_evidence_blockers as _filing_external_evidence_blockers,
)
from cadrumo.application.calculations.cross_period_models import CrossPeriodCleanStateBlocker
from cadrumo.application.calculations.observations_repository import ObservationEnvelopePayload, ObservationSourceKind
from cadrumo.application.modelo.action_errors import ExternalModeloImportError
from cadrumo.application.modelo.amendment_actions import amend_modelo_revision
from cadrumo.application.modelo.calculation_actions import get_calculation_revision
from cadrumo.application.modelo.external_import_actions import (
    ExternalFilingBaselineSource,
    import_external_filing_evidence,
    import_external_filing_source,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.modelos.calculation_revision_amendment import CalculationRevisionAmendmentKind
from cadrumo.domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from cadrumo.entrypoints.adapter_composition import (
    build_amendment_action_ports,
    build_calculation_action_ports,
    build_work_lifecycle_ports,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_STALE_REVISION_ID = "0" * 64


def _import_external_filing_source(source: Any, **kwargs: Any) -> Any:
    """Compose external-import lifecycle and observation capabilities canonically."""
    for key in ("work_unit_repository", "calculation_repository", "filing_repository", "bucket_event_repository"):
        kwargs.pop(key, None)
    kwargs.setdefault("work_lifecycle_ports", build_work_lifecycle_ports(bucket_id=_PROFILE_ID))
    kwargs.setdefault("observation_repository", CalculationObservationRepository())
    if "operation" in kwargs:
        return import_external_filing_source(source, **kwargs).filing_record
    with bundled_indexed_authority().operation() as operation:
        return import_external_filing_source(source, operation=operation, **kwargs).filing_record


def _import_external_filing_evidence(**kwargs: Any) -> Any:
    """Compose the observation capability required by evidence import."""
    kwargs.setdefault("observation_repository", CalculationObservationRepository())
    return import_external_filing_evidence(**kwargs).filing_record


def _get_calculation_revision(calculation_revision_id: str, **kwargs: Any) -> Any:
    """Read calculations through the current calculation capability contract."""
    kwargs.pop("calculation_repository", None)
    with bundled_indexed_authority().operation() as operation:
        return get_calculation_revision(
            calculation_revision_id,
            ports=build_calculation_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            **kwargs,
        )


def _amend_modelo_revision(**kwargs: Any) -> Any:
    """Compose amendment capabilities through the current application contract."""
    for key in ("work_unit_repository", "calculation_repository", "filing_repository", "bucket_event_repository"):
        kwargs.pop(key, None)
    with bundled_indexed_authority().operation() as operation:
        return amend_modelo_revision(
            ports=build_amendment_action_ports(bucket_id=_PROFILE_ID, operation=operation),
            operation=operation,
            **kwargs,
        )


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


def test_source_lexicals_refuse_dropped_casillas(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2019-y-siguientes",
            ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
            operation=operation,
            clock=_T1,
        )
    with pytest.raises(ExternalModeloImportError):
        _import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={
                _IMPORT_INCOME_CASILLA: Decimal("1500"),
                _IMPORT_EXPENSE_CASILLA: Decimal("300"),
            },
            source_lexical_values_by_casilla_id={_IMPORT_INCOME_CASILLA: "1500"},
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="DROPPEDCASILLA01",
            expected_tax_id=_TAX_ID,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_source_lexicals_refuse_value_shadowing(repos: _Repos) -> None:
    wu_repo, cr_repo, fr_repo, _vr_repo, bv_repo = repos
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2019-y-siguientes",
            ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
            operation=operation,
            clock=_T1,
        )
    with pytest.raises(ExternalModeloImportError):
        _import_external_filing_evidence(
            work_unit_id=work_unit.work_unit_id,
            casilla_values={_IMPORT_INCOME_CASILLA: Decimal("1500")},
            source_lexical_values_by_casilla_id={_IMPORT_INCOME_CASILLA: "1501"},
            evidence_kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            evidence_reference_id="SHADOWVALUE01",
            expected_tax_id=_TAX_ID,
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            filing_repository=fr_repo,
            bucket_event_repository=bv_repo,
            clock=_T1,
        )


def test_source_payload_import_creates_exact_amendable_baseline(
    repos: _Repos,
) -> None:
    """The CSV-register source's complete casilla map reaches one durable baseline."""
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    reference_id = "SOURCECSV0001"
    filing = _import_external_filing_source(
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
    baseline = _get_calculation_revision(
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

    amended = _amend_modelo_revision(
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
        _import_external_filing_source(
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
    filing = _import_external_filing_source(
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
    with bundled_indexed_authority().operation() as operation:
        work_unit = create_work_unit(
            bucket_id=_PROFILE_ID,
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            revision_id="2019-y-siguientes",
            ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bv_repo),
            operation=operation,
            clock=_T1,
        )
    _import_external_filing_source(
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
        _import_external_filing_source(
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
            declared_kind=FilingDeclarationKind.COMPLEMENTARIA,
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
        _import_external_filing_source(
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
