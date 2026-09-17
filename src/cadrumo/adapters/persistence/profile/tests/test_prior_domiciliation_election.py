"""Real-storage proof for Modelo 303 prior-domiciliation election authority."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.calculations.m303_carry_ingress import M303CarryIngressError, m303_declaration_type_header_key
from .....application.calculations.observations_repository import ObservationSourceKind, ResultDispositionProjection
from .....application.modelo.action_errors import ModeloPriorDomiciliationElectionRefusedError
from .....application.modelo.prior_domiciliation import resolveprior_domiciliation_election
from .....core.casilla_id import validated_casilla_id
from .....core.observed_header_fact import ObservedHeaderFact
from .....core.period import Period
from .....core.prior_domiciliation_election import PriorDomiciliationElection
from .....core.result_disposition import ResultDisposition
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from .....domain.calculations.registry.casilla_membership import casillas_by_id
from .....domain.calculations.registry.schema_references import RegistrySnapshotRef
from .....domain.calculations.registry.tests.registry_observations import revision_id_for_observation
from .....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .....domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentIdentity,
    CalculationRevisionAmendmentKind,
)
from .....domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from .....domain.modelos.filing_repository import upsert_filing_record
from .....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..modelos_filing import ModeloRecordCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "21000000-0000-4000-8000-000000000021"
_WHEN = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
_EVIDENCE_REFERENCE = "CSV-303-2025-1T-S21"
_DECLARATION_TYPE_LOCATOR = "modelo-303-page-01:declaration-type:13:1"
#: A positive result: the only sign a domiciliation (or ingreso) disposition admits.
_POSITIVE_RESULT = Decimal("100.00")


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _submitted_file_declaration_type(
    value: str,
    *,
    locator: str = _DECLARATION_TYPE_LOCATOR,
) -> ObservedHeaderFact:
    with bundled_indexed_authority().operation() as operation:
        header_key = m303_declaration_type_header_key(filing_year=2025, period="1T", operation=operation)
    return ObservedHeaderFact(
        header_key=header_key,
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


def _filed_observation() -> RegistryModeloObservation:
    """The filed M303 result the declaration-type header must agree with."""
    period = Period.from_year_and_code(2025, "1T")
    snapshot = published_authority_operation().snapshot(
        "303", filing_year=period.filing_year, period=period.registry_token
    )
    result_casilla = validated_casilla_id("iva.resultado")
    definition = casillas_by_id(snapshot.revision)[result_casilla]
    return RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=result_casilla,
                value=_POSITIVE_RESULT,
                legal_refs=tuple(definition.legal_refs),
                source_refs=tuple(definition.source_refs),
            ),
        ),
    )


def _work_unit(*, modelo: str = "303") -> WorkUnit:
    period = Period.from_year_and_code(2025, "1T")
    revision_id = (
        published_authority_operation()
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
    # A rectificativa revision validates against its whole amendment evidence
    # chain; the election resolver reads only the amendment identity, so the
    # rectificativa shape is constructed without that out-of-scope aggregate.
    build = (
        CalculationRevision.model_construct
        if amendment_kind is CalculationRevisionAmendmentKind.RECTIFICATIVA
        else CalculationRevision
    )
    return build(
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
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
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
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
            reference_id=_EVIDENCE_REFERENCE,
            imported_at=_WHEN,
        ),
    )


def test_keep_is_neutral_and_needs_no_filing_evidence(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The default is a safe no-op rather than an inferred change request."""
    work_unit = _work_unit()
    revision = _revision(work_unit, amendment_kind=None)

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        projection = resolveprior_domiciliation_election(
            election=PriorDomiciliationElection.KEEP,
            work_unit=work_unit,
            revision=revision,
            filing_repository=ModeloRecordCatalogueRepository(objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
            operation=authority_operation,
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
    authority_operation: PinnedAuthorityOperation,
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
        resolveprior_domiciliation_election(
            election=election,
            work_unit=work_unit,
            revision=revision,
            filing_repository=ModeloRecordCatalogueRepository(objects=profile.repository),
            observation_repository=CalculationObservationRepository(objects=profile.repository),
            operation=authority_operation,
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
    ],
)
def test_cancel_or_modify_refuses_every_missing_baseline_u_link(
    tmp_path: Path,
    source_kind: ObservationSourceKind,
    source_headers: tuple[ObservedHeaderFact, ...],
    result_disposition: ResultDispositionProjection,
    metadata_csv: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A persisted observation is insufficient unless its whole official U chain joins.

    A broken link is refused either where the observation is admitted to storage
    or where the election is resolved; neither boundary may accept it.
    """
    with (
        isolated_runtime_profile(tmp_path=tmp_path) as profile,
        pytest.raises((M303CarryIngressError, ModeloPriorDomiciliationElectionRefusedError)),
    ):
        work_unit = _work_unit()
        baseline = _baseline_filing(work_unit)
        filing_repository = ModeloRecordCatalogueRepository(objects=profile.repository)
        filing_repository.save(upsert_filing_record(filing_repository.load(), baseline))
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                _filed_observation(),
                source_kind=source_kind,
                captured_at=_WHEN,
                source_metadata={"aeat_justificante_csv": metadata_csv},
                source_headers=source_headers,
                result_disposition=result_disposition,
                stamped_revision_id=revision_id_for_observation(_filed_observation()),
            )
        )
        revision = _revision(
            work_unit,
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            baseline_filing_record_id=baseline.filing_record_id,
        )

        resolveprior_domiciliation_election(
            election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
            work_unit=work_unit,
            revision=revision,
            filing_repository=filing_repository,
            observation_repository=observation_repository,
            operation=authority_operation,
        )


@pytest.mark.parametrize(
    "supplied",
    [
        pytest.param(
            ResultDispositionProjection(
                disposition=ResultDisposition.DOMICILIACION,
                provenance_kind="app_filing",
                provenance_locator=_DECLARATION_TYPE_LOCATOR,
            ),
            id="non-header-disposition",
        ),
        pytest.param(
            _source_header_disposition(
                ResultDisposition.DOMICILIACION,
                locator="modelo-303-page-01:declaration-type:forged-locator",
            ),
            id="projection-header-locator-disagreement",
        ),
    ],
)
def test_official_evidence_stores_the_header_projection_not_the_supplied_one(
    tmp_path: Path,
    supplied: ResultDispositionProjection,
) -> None:
    """A forged provenance on official evidence never reaches storage.

    The observed declaration-type header is the sole authority for official
    evidence, so what persists is the projection derived from it; the U link the
    election later joins is therefore the header's, not the caller's.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                _filed_observation(),
                source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
                captured_at=_WHEN,
                source_metadata={"aeat_justificante_csv": _EVIDENCE_REFERENCE},
                source_headers=(_submitted_file_declaration_type("U"),),
                result_disposition=supplied,
                stamped_revision_id=revision_id_for_observation(_filed_observation()),
            )
        )
        loaded = observation_repository.load_observation("303", Period.from_year_and_code(2025, "1T"))

    assert loaded is not None
    assert loaded.result_disposition == _source_header_disposition(ResultDisposition.DOMICILIACION)


def test_cancel_or_modify_persists_only_join_safe_baseline_u_provenance(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The accepted route uses real encrypted storage and exposes no account material."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        work_unit = _work_unit()
        baseline = _baseline_filing(work_unit)
        filing_repository = ModeloRecordCatalogueRepository(objects=profile.repository)
        filing_repository.save(upsert_filing_record(filing_repository.load(), baseline))
        observation_repository = CalculationObservationRepository(objects=profile.repository)
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                _filed_observation(),
                source_kind=ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
                captured_at=_WHEN,
                source_metadata={"aeat_justificante_csv": _EVIDENCE_REFERENCE},
                source_headers=(_submitted_file_declaration_type("U"),),
                result_disposition=_source_header_disposition(ResultDisposition.DOMICILIACION),
                stamped_revision_id=revision_id_for_observation(_filed_observation()),
            )
        )
        revision = _revision(
            work_unit,
            amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            baseline_filing_record_id=baseline.filing_record_id,
        )

        projection = resolveprior_domiciliation_election(
            election=PriorDomiciliationElection.CANCEL_OR_MODIFY,
            work_unit=work_unit,
            revision=revision,
            filing_repository=filing_repository,
            observation_repository=observation_repository,
            operation=authority_operation,
        )

    assert projection.election is PriorDomiciliationElection.CANCEL_OR_MODIFY
    assert projection.baseline_filing_record_id == baseline.filing_record_id
    assert projection.baseline_evidence_reference_id == _EVIDENCE_REFERENCE
    assert projection.baseline_result_disposition is ResultDisposition.DOMICILIACION
    assert projection.baseline_source_header_locator == _DECLARATION_TYPE_LOCATOR
    assert "iban" not in projection.model_dump_json().casefold()
