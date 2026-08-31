"""Real-storage proof for Modelo 303 prior-domiciliation election authority."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....application.calculations import (
    M303_DECLARATION_TYPE_HEADER_KEY,
    CalculationObservationRepository,
    ObservationSourceKind,
    ResultDispositionProjection,
)
from ....core import ObservedHeaderFact
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.result_disposition import ResultDisposition
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind, ModeloRecord, ModeloRecordStatus, derive_filing_record_id
from ....domain.modelos.filing_repository import upsert_filing_record
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import ModeloPriorDomiciliationElectionRefusedError
from .._prior_domiciliation import resolve_prior_domiciliation_election

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "21000000-0000-4000-8000-000000000021"
_WHEN = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
_EVIDENCE_REFERENCE = "CSV-303-2025-1T-S21"
_DECLARATION_TYPE_LOCATOR = "modelo-303-page-01:declaration-type:13:1"


def _submitted_file_declaration_type(
    value: str,
    *,
    locator: str = _DECLARATION_TYPE_LOCATOR,
) -> ObservedHeaderFact:
    return ObservedHeaderFact(
        header_key=M303_DECLARATION_TYPE_HEADER_KEY,
        value=value,
        source_artefact_kind="submitted_file",
        source_locator=locator,
    )


def _source_header_disposition(
    disposition: ResultDisposition,
    *,
    locator: str = _DECLARATION_TYPE_LOCATOR,
) -> ResultDispositionProjection:
    return ResultDispositionProjection(
        disposition=disposition,
        provenance_kind="source_header",
        provenance_locator=locator,
    )


def _work_unit(*, modelo: str = "303") -> WorkUnit:
    period = Period.from_year_and_code(2025, "1T")
    revision_id = (
        bundled_authority()
        .snapshot(
            modelo,
            filing_year=period.filing_year,
            period=period.registry_token,
        )
        .revision.id
    )
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=2025,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2025,
        period=period,
        revision_id=revision_id,
        name=f"{modelo}-2025-1T prior-domiciliation proof",
        created_at=_WHEN,
        updated_at=_WHEN,
    )


def _revision(
    work_unit: WorkUnit,
    *,
    amendment_kind: CalculationRevisionAmendmentKind | None,
    baseline_filing_record_id: str | None = None,
) -> CalculationRevision:
    # Built once and fed to BOTH the deriver and the revision: the id is content
    # addressed over the amendment identity, so deriving without it produces an id
    # the revision then rejects as not matching its own content.
    amendment_identity: CalculationRevisionAmendmentIdentity | None
    if amendment_kind is None:
        amendment_identity = None
    else:
        assert baseline_filing_record_id is not None
        amendment_identity = CalculationRevisionAmendmentIdentity(
            kind=amendment_kind,
            amends_filing_record_id=baseline_filing_record_id,
            m303_rectificativa_motive=None,
        )
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
            amendment_identity=amendment_identity,
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        created_at=_WHEN,
        updated_at=_WHEN,
        amendment_identity=amendment_identity,
        amendment_reason="correct prior direct-debit election" if amendment_kind is not None else None,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _baseline_filing(work_unit: WorkUnit) -> ModeloRecord:
    calculation_revision_id = "a" * 64
    filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        filed_by="aeat-import",
    )
    return ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=calculation_revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=_WHEN,
        filed_by="aeat-import",
        aeat_accepted=True,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id=_EVIDENCE_REFERENCE,
            imported_at=_WHEN,
        ),
    )


def test_keep_is_neutral_and_needs_no_filing_evidence(tmp_path: Path) -> None:
    """The default is a safe no-op rather than an inferred change request."""
    work_unit = _work_unit()
    revision = _revision(work_unit, amendment_kind=None)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        projection = resolve_prior_domiciliation_election(
            election=PriorDomiciliationElection.KEEP,
            work_unit=work_unit,
            revision=revision,
            filing_repository=ModeloRecordCatalogueRepository(objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
        )

    assert projection.election is PriorDomiciliationElection.KEEP
    assert projection.baseline_filing_record_id is None
    assert projection.baseline_evidence_reference_id is None
    assert projection.baseline_source_header_locator is None


@pytest.mark.parametrize(
    ("election", "modelo", "amendment_kind"),
    [
        pytest.param("X", "303", CalculationRevisionAmendmentKind.RECTIFICATIVA, id="raw-marker"),
        pytest.param(
            PriorDomiciliationElection.CANCEL_OR_MODIFY,
            "130",
            CalculationRevisionAmendmentKind.RECTIFICATIVA,
            id="non-m303",
        ),
        pytest.param(PriorDomiciliationElection.CANCEL_OR_MODIFY, "303", None, id="non-rectificativa"),
    ],
)
def test_cancel_or_modify_refuses_raw_unsupported_and_non_rectificativa_requests(
    tmp_path: Path,
    election: object,
    modelo: str,
    amendment_kind: CalculationRevisionAmendmentKind | None,
) -> None:
    """No untyped marker or unsupported filing shape can reach evidence lookup."""
    work_unit = _work_unit(modelo=modelo)
    revision = _revision(
        work_unit,
        amendment_kind=amendment_kind,
        baseline_filing_record_id=(
            _baseline_filing(work_unit).filing_record_id if amendment_kind is not None else None
        ),
    )

    with (
        isolated_runtime_profile(tmp_path=tmp_path) as profile,
        pytest.raises(
            ModeloPriorDomiciliationElectionRefusedError,
        ),
    ):
        resolve_prior_domiciliation_election(
            election=election,
            work_unit=work_unit,
            revision=revision,
            filing_repository=ModeloRecordCatalogueRepository(objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
        )


@pytest.mark.parametrize(
    ("source_kind", "source_headers", "result_disposition", "metadata_csv"),
    [
        pytest.param(
            ObservationSourceKind.APP_FILING,
            (_submitted_file_declaration_type("U"),),
            _source_header_disposition(ResultDisposition.DOMICILIACION),
            _EVIDENCE_REFERENCE,
            id="local-observation",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (_submitted_file_declaration_type("U"),),
            ResultDispositionProjection(
                disposition=ResultDisposition.DOMICILIACION,
                provenance_kind="app_filing",
                provenance_locator=_DECLARATION_TYPE_LOCATOR,
            ),
            _EVIDENCE_REFERENCE,
            id="non-header-disposition",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (_submitted_file_declaration_type("I"),),
            _source_header_disposition(ResultDisposition.INGRESO),
            _EVIDENCE_REFERENCE,
            id="non-u-disposition",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (_submitted_file_declaration_type("U"),),
            _source_header_disposition(ResultDisposition.DOMICILIACION),
            "CSV-OTHER-303-2025-1T",
            id="mismatched-external-reference",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (),
            _source_header_disposition(ResultDisposition.DOMICILIACION),
            _EVIDENCE_REFERENCE,
            id="headerless-forged-projection",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (
                _submitted_file_declaration_type("U"),
                _submitted_file_declaration_type(
                    "U",
                    locator="modelo-303-page-01:declaration-type:13:1:duplicate",
                ),
            ),
            _source_header_disposition(ResultDisposition.DOMICILIACION),
            _EVIDENCE_REFERENCE,
            id="duplicate-declaration-type-headers",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (
                _submitted_file_declaration_type("U"),
                _submitted_file_declaration_type(
                    "I",
                    locator="modelo-303-page-01:declaration-type:13:1:conflict",
                ),
            ),
            _source_header_disposition(ResultDisposition.DOMICILIACION),
            _EVIDENCE_REFERENCE,
            id="conflicting-declaration-type-headers",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (_submitted_file_declaration_type("U"),),
            _source_header_disposition(ResultDisposition.INGRESO),
            _EVIDENCE_REFERENCE,
            id="projection-header-disposition-disagreement",
        ),
        pytest.param(
            ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
            (_submitted_file_declaration_type("U"),),
            _source_header_disposition(
                ResultDisposition.DOMICILIACION,
                locator="modelo-303-page-01:declaration-type:forged-locator",
            ),
            _EVIDENCE_REFERENCE,
            id="projection-header-locator-disagreement",
        ),
    ],
)
def test_cancel_or_modify_refuses_every_missing_baseline_u_link(
    tmp_path: Path,
    source_kind: ObservationSourceKind,
    source_headers: tuple[ObservedHeaderFact, ...],
    result_disposition: ResultDispositionProjection,
    metadata_csv: str,
) -> None:
    """A persisted observation is insufficient unless its whole official U chain joins."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit = _work_unit()
        baseline = _baseline_filing(work_unit)
        filing_repository = ModeloRecordCatalogueRepository(objects=profile.repository)
        filing_repository.save(upsert_filing_record(filing_repository.load(), baseline))
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="303",
                    filing_year=2025,
                    period="1T",
                ),
                source_kind=source_kind,
                captured_at=_WHEN,
                source_metadata={"aeat_justificante_csv": metadata_csv},
                source_headers=source_headers,
                result_disposition=result_disposition,
            )
        )
        revision = _revision(
            work_unit,
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            baseline_filing_record_id=baseline.filing_record_id,
        )

        with pytest.raises(ModeloPriorDomiciliationElectionRefusedError):
            resolve_prior_domiciliation_election(
                election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
                work_unit=work_unit,
                revision=revision,
                filing_repository=filing_repository,
                observation_repository=observation_repository,
            )


def test_cancel_or_modify_persists_only_join_safe_baseline_u_provenance(tmp_path: Path) -> None:
    """The accepted route uses real encrypted storage and exposes no account material."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit = _work_unit()
        baseline = _baseline_filing(work_unit)
        filing_repository = ModeloRecordCatalogueRepository(objects=profile.repository)
        filing_repository.save(upsert_filing_record(filing_repository.load(), baseline))
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="303",
                    filing_year=2025,
                    period="1T",
                ),
                source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
                captured_at=_WHEN,
                source_metadata={"aeat_justificante_csv": _EVIDENCE_REFERENCE},
                source_headers=(_submitted_file_declaration_type("U"),),
                result_disposition=_source_header_disposition(ResultDisposition.DOMICILIACION),
            )
        )
        revision = _revision(
            work_unit,
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            baseline_filing_record_id=baseline.filing_record_id,
        )

        projection = resolve_prior_domiciliation_election(
            election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
            work_unit=work_unit,
            revision=revision,
            filing_repository=filing_repository,
            observation_repository=observation_repository,
        )

    assert projection.election is PriorDomiciliationElection.CANCEL_OR_MODIFY
    assert projection.baseline_filing_record_id == baseline.filing_record_id
    assert projection.baseline_evidence_reference_id == _EVIDENCE_REFERENCE
    assert projection.baseline_result_disposition is ResultDisposition.DOMICILIACION
    assert projection.baseline_source_header_locator == _DECLARATION_TYPE_LOCATOR
    assert "iban" not in projection.model_dump_json().casefold()
