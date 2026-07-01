"""Public facade for modelo filing domain records and repository boundaries.

The public surface exposes :class:`ModeloCode`, :class:`WorkUnit`,
:class:`CalculationRevision`, :class:`ModeloRecord`, :class:`VerificationReport`,
their in-memory catalogues, encrypted repository boundaries, repository
protocols, row DTOs, derivation and upsert helpers, :class:`ExternalEvidence`,
and ``WorkUnitId``. :class:`ModeloCode` validates identifier shape only; filing
availability and revision targeting are resolved through registry-aware flows
anchored on :class:`ModeloRevision`.

These records are the domain aggregate carried by :mod:`aeat.application.modelo`:
a :class:`WorkUnit` fixes the bucket/modelo/year/period/registry-revision target
and carries current/filed pointers, while a :class:`CalculationRevision` is
content-addressed, stateful, source-transaction aware, and records
:class:`CasillaObservation` values plus ``ModeloDetailRow`` rows. A
:class:`ModeloRecord` is the durable filing-record receipt paired with a filed
revision. Local filing writes keep ``aeat_accepted=False`` and no
:class:`ExternalEvidence`; only the external import path may stamp
AEAT-attested evidence, validated against
:class:`aeat.domain.justificante.Justificante` metadata for receipt-bound
evidence kinds, and turn that record into an amendment baseline.

The package also owns the transaction participation index. A
:class:`TransactionRevisionParticipationIndex` is a rebuildable read-side cache
keyed by ledger transaction id; verified and filed writes co-emit
:class:`TransactionRevisionParticipation` entries, and the index can be rebuilt
from the calculation-revision, work-unit, and filing-record catalogues. The live
catalogues remain the source of truth.

Informational-declaration row models also live here:
:class:`Modelo184MemberRow`, :class:`Modelo232VinculadaRow`,
:class:`Modelo347ContraparteRow`, :class:`Modelo349OperadorRow`,
:class:`Modelo349RectificacionRow`, and ``ModeloDetailRow``, plus the
Modelo 349 NIF and country-prefix validators exposed by this root facade.
Regulatory constants such as the Modelo 347 declarability threshold remain in
:mod:`aeat.core.external_constants`.

See Also:
    :mod:`aeat.application.modelo`
        Application facade that creates, calculates, verifies, files, exports,
        reconciles, and rebuilds this aggregate.
    :class:`CalculationRevision`
        Immutable calculation attempt with lifecycle state, source transaction
        ids, typed casilla observations, and content-addressed identity.
    :class:`ModeloRecord`
        Filing event record paired with the filed calculation revision.
    :class:`ExternalEvidence`
        Official evidence metadata carried only by imported AEAT-attested
        filing records.
    :func:`aeat.application.modelo.file_modelo_revision`
        Application service that records a verified revision as local/internal
        filed state without AEAT acceptance.
    :func:`aeat.application.modelo.import_external_filing_evidence`
        Application service that imports AEAT-attested evidence into a current
        filing record.
    :func:`aeat.application.modelo.amend_modelo_revision`
        Application service that consumes an externally evidenced current
        filing record as the amendment baseline.
    :mod:`aeat.domain.justificante`
        Receipt metadata domain referenced by justificante PDF, CSV-register,
        and live-capture evidence kinds.
    :class:`TransactionRevisionParticipationIndex`
        Rebuildable inverse index from ledger transaction ids to finalized
        calculation revisions and filing records.
    :mod:`aeat.domain.calculations.registry`
        Registry snapshots, formulas, bindings, and observation types that
        produce the calculation payload stored on a revision.
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
from ._ids import WorkUnitId
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
    Modelo349CountryPrefixContextError,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloDetailRow,
    validate_m349_country_prefix_context,
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
    "Modelo349CountryPrefixContextError",
    "Modelo349OperadorRow",
    "Modelo349RectificacionRow",
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
    "TransactionParticipationIndexPersistenceError",
    "TransactionParticipationIndexRepository",
    "TransactionRevisionParticipation",
    "TransactionRevisionParticipationIndex",
    "VerificationCompletenessStatus",
    "VerificationReport",
    "VerificationReportCatalogue",
    "VerificationReportCatalogueRepository",
    "VerificationReportCatalogueRepositoryProtocol",
    "WorkUnit",
    "WorkUnitCatalogue",
    "WorkUnitCatalogueRepository",
    "WorkUnitCatalogueRepositoryProtocol",
    "WorkUnitId",
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
    "validate_m349_country_prefix_context",
    "validate_m349_nif_format",
)
