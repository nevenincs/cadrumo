"""Modelo identity codes and informational-declaration row models.

The public surface exposes ``ModeloCode`` (the closed set of AEAT modelo
identifiers) together with the typed per-row records for the informational
declarations: ``Modelo184MemberRow``, ``Modelo232VinculadaRow``,
``Modelo347ContraparteRow``, ``Modelo349OperadorRow``, and ``ModeloDetailRow``
(plus ``validate_m349_nif_format``). The Modelo 347 declarability threshold is a
regulatory constant owned by ``core.external_constants`` (``M347_THRESHOLD_EUR``),
consumed directly from there.

This module uses :class:`CalculationRevision` and :class:`ModeloRecord`
for persistence operations.

The package also hosts, as submodules imported by their consumers directly, the
domain-layer modelo persistence and identity core: the calculation, filing, and
verification repositories, calculation revisions, filing records, verification
reports, and work units.

Use of :class:`CalculationRevision`, :class:`ModeloRecord` for compliance.
"""

from __future__ import annotations

from ._calculation_repository import CalculationRevisionCatalogueRepository, upsert_calculation_revision
from ._calculation_revision import (
    CalculationRevision,
    CalculationRevisionAmendmentKind,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ._codes import ModeloCode
from ._filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from ._filing_repository import ModeloRecordCatalogueRepository, upsert_filing_record
from ._participation_index import (
    PARTICIPATION_INDEX_NAMESPACE,
    PARTICIPATION_INDEX_SCHEMA_VERSION,
    TransactionParticipationIndexPersistenceError,
    TransactionParticipationIndexRepository,
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
    derive_participation_index_id,
    upsert_transaction_participation,
)
from ._protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
    WorkUnitCatalogueRepositoryProtocol,
)
from ._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ._row_models import (
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    ModeloDetailRow,
    validate_m349_nif_format,
)
from ._verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    VerificationReportCatalogue,
    derive_verification_report_id,
)
from ._verification_repository import VerificationReportCatalogueRepository, upsert_verification_report
from ._work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id

__all__ = (
    "PARTICIPATION_INDEX_NAMESPACE",
    "PARTICIPATION_INDEX_SCHEMA_VERSION",
    "CalculationRevision",
    "CalculationRevisionAmendmentKind",
    "CalculationRevisionCatalogue",
    "CalculationRevisionCatalogueRepository",
    "CalculationRevisionCatalogueRepositoryProtocol",
    "CalculationRevisionState",
    "ExternalEvidence",
    "ExternalEvidenceKind",
    "Modelo184MemberRow",
    "Modelo232VinculadaRow",
    "Modelo347ContraparteRow",
    "Modelo349OperadorRow",
    "ModeloCode",
    "ModeloDetailRow",
    "ModeloRecord",
    "ModeloRecordCatalogue",
    "ModeloRecordCatalogueRepository",
    "ModeloRecordCatalogueRepositoryProtocol",
    "ModeloRecordStatus",
    "ModeloVerificationFinding",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "VerificationCompletenessStatus",
    "VerificationReport",
    "VerificationReportCatalogue",
    "TransactionParticipationIndexPersistenceError",
    "TransactionParticipationIndexRepository",
    "TransactionRevisionParticipation",
    "TransactionRevisionParticipationIndex",
    "VerificationReportCatalogueRepository",
    "VerificationReportCatalogueRepositoryProtocol",
    "WorkUnit",
    "WorkUnitCatalogue",
    "WorkUnitCatalogueRepository",
    "WorkUnitCatalogueRepositoryProtocol",
    "derive_calculation_revision_id",
    "derive_filing_record_id",
    "derive_participation_index_id",
    "derive_verification_report_id",
    "derive_work_unit_id",
    "upsert_calculation_revision",
    "upsert_filing_record",
    "upsert_transaction_participation",
    "upsert_verification_report",
    "upsert_work_unit",
    "validate_m349_nif_format",
)
