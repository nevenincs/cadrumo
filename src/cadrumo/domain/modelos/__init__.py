"""Public facade for modelo filing domain records and repository boundaries.

The public surface exposes :class:`ModeloCode`, :class:`WorkUnit`,
:class:`CalculationRevision`, :class:`ModeloRecord`, :class:`VerificationReport`,
their in-memory catalogues, encrypted repository boundaries, repository
protocols, row DTOs, derivation and upsert helpers, and
:class:`ExternalEvidence`. The record identities themselves are not exported
here: they are consumed across package boundaries and live at
:mod:`core.identity`, aliased from the one canonical hex-64 primitive.
:class:`ModeloCode` validates identifier shape only;
filing availability and revision targeting are resolved through registry-aware
flows anchored on :class:`domain.calculations.registry.ModeloRevision`.

These records are the domain aggregate carried by
:mod:`application.modelo`:
a :class:`WorkUnit` fixes the bucket/modelo/year/period/registry-revision target
and carries current/filed pointers, while a :class:`CalculationRevision` is
content-addressed, stateful, source-transaction aware, and records
:class:`domain.calculations.registry.CasillaObservation` values plus
:obj:`ModeloDetailRow` rows. A :class:`ModeloRecord` is the durable
filing-record receipt paired with a filed revision. Local filing writes keep
``aeat_accepted=False`` and no
:class:`ExternalEvidence`; only the external import path may stamp
AEAT-attested evidence, validated against
:class:`domain.justificante.Justificante` metadata for receipt-bound
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
:class:`Modelo349RectificacionRow`, :class:`Modelo210AgrupacionRentaRow`, and
:obj:`ModeloDetailRow`, plus the
Modelo 349 NIF and country-prefix validators exposed by this root facade.
Regulatory constants such as the Modelo 347 declarability threshold remain in
:mod:`core.external_constants`.

See Also:
    :mod:`application.modelo`
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
    :func:`application.modelo.file_modelo_revision`
        Application service that records a verified revision as local/internal
        filed state without AEAT acceptance.
    :func:`application.modelo.import_external_filing_evidence`
        Application service that imports AEAT-attested evidence into a current
        filing record.
    :func:`application.modelo.amend_modelo_revision`
        Application service that consumes an externally evidenced current
        filing record as the amendment baseline.
    :mod:`domain.justificante`
        Receipt metadata domain referenced by justificante PDF, CSV-register,
        and live-capture evidence kinds.
    :class:`TransactionRevisionParticipationIndex`
        Rebuildable inverse index from ledger transaction ids to finalized
        calculation revisions and filing records.
    :mod:`domain.calculations.registry`
        Registry snapshots, formulas, bindings, and observation types that
        produce the calculation payload stored on a revision.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._calculation_repository import CalculationRevisionPersistenceError, upsert_calculation_revision
    from ._calculation_revision import (
        CURRENT_SEALED_REVISION_STATES,
        M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS,
        SEALED_REVISION_STATES,
        CalculationRevision,
        CalculationRevisionAmendmentIdentity,
        CalculationRevisionAmendmentKind,
        CalculationRevisionCatalogue,
        CalculationRevisionState,
        CalculationSourceIssue,
        CalculationSourceRef,
        FilingInstanceEvidence,
        M303DANA2024EligibilityEvidence,
        M303DANA2024ReductionResult,
        M303Exonerado390ActivityRowEvidence,
        M303Exonerado390EndpointEvidence,
        M303Exonerado390FilingEvidence,
        M303FilingInstanceEvidence,
        M303InsolvencyFilingFact,
        M303InsolvencyFilingSubtype,
        M303RectificativaMotive,
        M303RegimenSimplificadoActivityCalculationResult,
        M303RegimenSimplificadoAnnualSummaryHandoff,
        M303RegimenSimplificadoCalculationResult,
        M303RegimenSimplificadoFilingEvidence,
        M303RegimenSimplificadoModuleCalculationResult,
        assert_revision_snapshot_evidence_coverage,
        calculation_revision_identity_inputs,
        calculation_revision_identity_inputs_from_revision,
        derive_calculation_revision_id,
        derive_calculation_revision_id_from_revision,
    )
    from ._calculation_revision_aggregate import (
        CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY,
        CalculationRevisionAggregateContext,
        ValidatedM303RectificativaEvidence,
        validate_calculation_revision_aggregate,
    )
    from ._calculation_revision_amendment import (
        m303_rectificativa_motive_is_applicable,
        m303_rectificativa_record_design_from_snapshot,
    )
    from ._codes import ModeloCode
    from ._dt12_reduccion import (
        Dt12WindowEligibility,
        compute_dt12_reduccion_plan_pensiones,
        dt12_regime_window_eligibility,
    )
    from ._filing_record import (
        ExternalEvidence,
        ExternalEvidenceKind,
        ModeloRecord,
        ModeloRecordCatalogue,
        ModeloRecordStatus,
        derive_filing_record_id,
        is_justificante_backed_external_evidence,
        is_receipt_bound_external_evidence,
    )
    from ._filing_repository import ModeloRecordPersistenceError, upsert_filing_record
    from ._iae_exemption import (
        Modelo840IaeExemptionAssessment,
        Modelo840IaeExemptionStatus,
        assess_modelo_840_iae_cifra_negocios_exemption,
    )
    from ._ledger_filing_snapshot import (
        LedgerEvidenceRow,
        LedgerFilingEvidence,
        LedgerFilingSnapshot,
        LedgerFilingStalenessVerdict,
        LedgerRowFingerprint,
        ManualFactBasisEntry,
        diff_ledger_fingerprints,
        snapshot_fingerprint,
    )
    from ._m232_row_materialisation import (
        M232_MAX_RELATED_PARTY_ROWS,
        m232_related_party_row_casilla_values,
    )
    from ._participation_index import (
        TransactionParticipationIndexPersistenceError,
        TransactionRevisionParticipation,
        TransactionRevisionParticipationIndex,
        derive_participation_index_id,
        upsert_transaction_participation,
    )
    from ._protocols import (
        CalculationRevisionCatalogueRepositoryProtocol,
        ModeloRecordCatalogueRepositoryProtocol,
        TransactionParticipationIndexRepositoryProtocol,
        VerificationReportCatalogueRepositoryProtocol,
    )
    from ._repository import WorkUnitPersistenceError, upsert_work_unit
    from ._row_models import (
        M184Clave,
        M184ClaveDeclarado,
        M184NaturalezaInmueble,
        M184SituacionInmueble,
        M184Subclave,
        Modelo184MemberRow,
        Modelo184ShareSumError,
        Modelo210AgrupacionRentaRow,
        Modelo210AgrupacionRentaRowsError,
        Modelo232VinculadaRow,
        Modelo347ContraparteRow,
        Modelo347ThresholdError,
        Modelo349CountryPrefixContextError,
        Modelo349OperadorRow,
        Modelo349RectificacionRow,
        ModeloDetailRow,
        m349_nif_number_for_export,
        validate_m184_member_share_sum,
        validate_m210_agrupacion_renta_rows,
        validate_m347_threshold,
        validate_m349_country_prefix_context,
        validate_m349_nif_format,
    )
    from ._sal_reserva_especial import compute_sal_reserva_especial_dotacion
    from ._verification_report import (
        OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND,
        ModeloVerificationFinding,
        ModeloVerificationFindingKind,
        ModeloVerificationFindingSeverity,
        VerificationCompletenessStatus,
        VerificationReport,
        VerificationReportCatalogue,
        derive_verification_report_id,
    )
    from ._verification_repository import VerificationReportPersistenceError, upsert_verification_report
    from ._work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id

_LAZY_EXPORTS: dict[str, str] = {
    "CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY": "._calculation_revision_aggregate",
    "CURRENT_SEALED_REVISION_STATES": "._calculation_revision",
    "CalculationRevision": "._calculation_revision",
    "CalculationRevisionAggregateContext": "._calculation_revision_aggregate",
    "CalculationRevisionAmendmentIdentity": "._calculation_revision",
    "CalculationRevisionAmendmentKind": "._calculation_revision",
    "CalculationRevisionCatalogue": "._calculation_revision",
    "CalculationRevisionCatalogueRepositoryProtocol": "._protocols",
    "CalculationRevisionPersistenceError": "._calculation_repository",
    "CalculationRevisionState": "._calculation_revision",
    "CalculationSourceIssue": "._calculation_revision",
    "CalculationSourceRef": "._calculation_revision",
    "Dt12WindowEligibility": "._dt12_reduccion",
    "ExternalEvidence": "._filing_record",
    "ExternalEvidenceKind": "._filing_record",
    "FilingInstanceEvidence": "._calculation_revision",
    "LedgerEvidenceRow": "._ledger_filing_snapshot",
    "LedgerFilingEvidence": "._ledger_filing_snapshot",
    "LedgerFilingSnapshot": "._ledger_filing_snapshot",
    "LedgerFilingStalenessVerdict": "._ledger_filing_snapshot",
    "LedgerRowFingerprint": "._ledger_filing_snapshot",
    "M184Clave": "._row_models",
    "M184ClaveDeclarado": "._row_models",
    "M184NaturalezaInmueble": "._row_models",
    "M184SituacionInmueble": "._row_models",
    "M184Subclave": "._row_models",
    "M232_MAX_RELATED_PARTY_ROWS": "._m232_row_materialisation",
    "M303DANA2024EligibilityEvidence": "._calculation_revision",
    "M303DANA2024ReductionResult": "._calculation_revision",
    "M303Exonerado390ActivityRowEvidence": "._calculation_revision",
    "M303Exonerado390EndpointEvidence": "._calculation_revision",
    "M303Exonerado390FilingEvidence": "._calculation_revision",
    "M303FilingInstanceEvidence": "._calculation_revision",
    "M303InsolvencyFilingFact": "._calculation_revision",
    "M303InsolvencyFilingSubtype": "._calculation_revision",
    "M303RectificativaMotive": "._calculation_revision",
    "M303RegimenSimplificadoActivityCalculationResult": "._calculation_revision",
    "M303RegimenSimplificadoAnnualSummaryHandoff": "._calculation_revision",
    "M303RegimenSimplificadoCalculationResult": "._calculation_revision",
    "M303RegimenSimplificadoFilingEvidence": "._calculation_revision",
    "M303RegimenSimplificadoModuleCalculationResult": "._calculation_revision",
    "M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS": "._calculation_revision",
    "ManualFactBasisEntry": "._ledger_filing_snapshot",
    "Modelo184MemberRow": "._row_models",
    "Modelo184ShareSumError": "._row_models",
    "Modelo210AgrupacionRentaRow": "._row_models",
    "Modelo210AgrupacionRentaRowsError": "._row_models",
    "Modelo232VinculadaRow": "._row_models",
    "Modelo347ContraparteRow": "._row_models",
    "Modelo347ThresholdError": "._row_models",
    "Modelo349CountryPrefixContextError": "._row_models",
    "Modelo349OperadorRow": "._row_models",
    "Modelo349RectificacionRow": "._row_models",
    "Modelo840IaeExemptionAssessment": "._iae_exemption",
    "Modelo840IaeExemptionStatus": "._iae_exemption",
    "ModeloCode": "._codes",
    "ModeloDetailRow": "._row_models",
    "ModeloRecord": "._filing_record",
    "ModeloRecordCatalogue": "._filing_record",
    "ModeloRecordCatalogueRepositoryProtocol": "._protocols",
    "ModeloRecordPersistenceError": "._filing_repository",
    "ModeloRecordStatus": "._filing_record",
    "ModeloVerificationFinding": "._verification_report",
    "ModeloVerificationFindingKind": "._verification_report",
    "ModeloVerificationFindingSeverity": "._verification_report",
    "OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND": "._verification_report",
    "SEALED_REVISION_STATES": "._calculation_revision",
    "TransactionParticipationIndexPersistenceError": "._participation_index",
    "TransactionParticipationIndexRepositoryProtocol": "._protocols",
    "TransactionRevisionParticipation": "._participation_index",
    "TransactionRevisionParticipationIndex": "._participation_index",
    "ValidatedM303RectificativaEvidence": "._calculation_revision_aggregate",
    "VerificationCompletenessStatus": "._verification_report",
    "VerificationReport": "._verification_report",
    "VerificationReportCatalogue": "._verification_report",
    "VerificationReportCatalogueRepositoryProtocol": "._protocols",
    "VerificationReportPersistenceError": "._verification_repository",
    "WorkUnit": "._work_unit",
    "WorkUnitCatalogue": "._work_unit",
    "WorkUnitPersistenceError": "._repository",
    "WorkUnitState": "._work_unit",
    "assert_revision_snapshot_evidence_coverage": "._calculation_revision",
    "assess_modelo_840_iae_cifra_negocios_exemption": "._iae_exemption",
    "calculation_revision_identity_inputs": "._calculation_revision",
    "calculation_revision_identity_inputs_from_revision": "._calculation_revision",
    "compute_dt12_reduccion_plan_pensiones": "._dt12_reduccion",
    "compute_sal_reserva_especial_dotacion": "._sal_reserva_especial",
    "derive_calculation_revision_id": "._calculation_revision",
    "derive_calculation_revision_id_from_revision": "._calculation_revision",
    "derive_filing_record_id": "._filing_record",
    "derive_participation_index_id": "._participation_index",
    "derive_verification_report_id": "._verification_report",
    "derive_work_unit_id": "._work_unit",
    "diff_ledger_fingerprints": "._ledger_filing_snapshot",
    "dt12_regime_window_eligibility": "._dt12_reduccion",
    "is_justificante_backed_external_evidence": "._filing_record",
    "is_receipt_bound_external_evidence": "._filing_record",
    "m232_related_party_row_casilla_values": "._m232_row_materialisation",
    "m303_rectificativa_motive_is_applicable": "._calculation_revision_amendment",
    "m303_rectificativa_record_design_from_snapshot": "._calculation_revision_amendment",
    "m349_nif_number_for_export": "._row_models",
    "snapshot_fingerprint": "._ledger_filing_snapshot",
    "upsert_calculation_revision": "._calculation_repository",
    "upsert_filing_record": "._filing_repository",
    "upsert_transaction_participation": "._participation_index",
    "upsert_verification_report": "._verification_repository",
    "upsert_work_unit": "._repository",
    "validate_calculation_revision_aggregate": "._calculation_revision_aggregate",
    "validate_m184_member_share_sum": "._row_models",
    "validate_m210_agrupacion_renta_rows": "._row_models",
    "validate_m347_threshold": "._row_models",
    "validate_m349_country_prefix_context": "._row_models",
    "validate_m349_nif_format": "._row_models",
}

# Every loader target is a closed literal from the map above.  The attribute
# name selects one of these pre-bound loaders; it never becomes an import path.
_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve one public name by importing only the submodule that owns it.

    The resolved value is written into module globals, so only the first
    access to a name goes through this hook; every later one is an ordinary
    global lookup with no import machinery in the path.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_name)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_name!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


__all__ = (
    "CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY",
    "CURRENT_SEALED_REVISION_STATES",
    "M232_MAX_RELATED_PARTY_ROWS",
    "M390_REGIMEN_SIMPLIFICADO_ANNUAL_SUMMARY_CASILLA_IDS",
    "OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND",
    "SEALED_REVISION_STATES",
    "CalculationRevision",
    "CalculationRevisionAggregateContext",
    "CalculationRevisionAmendmentIdentity",
    "CalculationRevisionAmendmentKind",
    "CalculationRevisionCatalogue",
    "CalculationRevisionCatalogueRepositoryProtocol",
    "CalculationRevisionPersistenceError",
    "CalculationRevisionState",
    "CalculationSourceIssue",
    "CalculationSourceRef",
    "Dt12WindowEligibility",
    "ExternalEvidence",
    "ExternalEvidenceKind",
    "FilingInstanceEvidence",
    "LedgerEvidenceRow",
    "LedgerFilingEvidence",
    "LedgerFilingSnapshot",
    "LedgerFilingStalenessVerdict",
    "LedgerRowFingerprint",
    "M184Clave",
    "M184ClaveDeclarado",
    "M184NaturalezaInmueble",
    "M184SituacionInmueble",
    "M184Subclave",
    "M303DANA2024EligibilityEvidence",
    "M303DANA2024ReductionResult",
    "M303Exonerado390ActivityRowEvidence",
    "M303Exonerado390EndpointEvidence",
    "M303Exonerado390FilingEvidence",
    "M303FilingInstanceEvidence",
    "M303InsolvencyFilingFact",
    "M303InsolvencyFilingSubtype",
    "M303RectificativaMotive",
    "M303RegimenSimplificadoActivityCalculationResult",
    "M303RegimenSimplificadoAnnualSummaryHandoff",
    "M303RegimenSimplificadoCalculationResult",
    "M303RegimenSimplificadoFilingEvidence",
    "M303RegimenSimplificadoModuleCalculationResult",
    "ManualFactBasisEntry",
    "Modelo184MemberRow",
    "Modelo184ShareSumError",
    "Modelo210AgrupacionRentaRow",
    "Modelo210AgrupacionRentaRowsError",
    "Modelo232VinculadaRow",
    "Modelo347ContraparteRow",
    "Modelo347ThresholdError",
    "Modelo349CountryPrefixContextError",
    "Modelo349OperadorRow",
    "Modelo349RectificacionRow",
    "Modelo840IaeExemptionAssessment",
    "Modelo840IaeExemptionStatus",
    "ModeloCode",
    "ModeloDetailRow",
    "ModeloRecord",
    "ModeloRecordCatalogue",
    "ModeloRecordCatalogueRepositoryProtocol",
    "ModeloRecordPersistenceError",
    "ModeloRecordStatus",
    "ModeloVerificationFinding",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "TransactionParticipationIndexPersistenceError",
    "TransactionParticipationIndexRepositoryProtocol",
    "TransactionRevisionParticipation",
    "TransactionRevisionParticipationIndex",
    "ValidatedM303RectificativaEvidence",
    "VerificationCompletenessStatus",
    "VerificationReport",
    "VerificationReportCatalogue",
    "VerificationReportCatalogueRepositoryProtocol",
    "VerificationReportPersistenceError",
    "WorkUnit",
    "WorkUnitCatalogue",
    "WorkUnitPersistenceError",
    "WorkUnitState",
    "assert_revision_snapshot_evidence_coverage",
    "assess_modelo_840_iae_cifra_negocios_exemption",
    "calculation_revision_identity_inputs",
    "calculation_revision_identity_inputs_from_revision",
    "compute_dt12_reduccion_plan_pensiones",
    "compute_sal_reserva_especial_dotacion",
    "derive_calculation_revision_id",
    "derive_calculation_revision_id_from_revision",
    "derive_filing_record_id",
    "derive_participation_index_id",
    "derive_verification_report_id",
    "derive_work_unit_id",
    "diff_ledger_fingerprints",
    "dt12_regime_window_eligibility",
    "is_justificante_backed_external_evidence",
    "is_receipt_bound_external_evidence",
    "m232_related_party_row_casilla_values",
    "m303_rectificativa_motive_is_applicable",
    "m303_rectificativa_record_design_from_snapshot",
    "m349_nif_number_for_export",
    "snapshot_fingerprint",
    "upsert_calculation_revision",
    "upsert_filing_record",
    "upsert_transaction_participation",
    "upsert_verification_report",
    "upsert_work_unit",
    "validate_calculation_revision_aggregate",
    "validate_m184_member_share_sum",
    "validate_m210_agrupacion_renta_rows",
    "validate_m347_threshold",
    "validate_m349_country_prefix_context",
    "validate_m349_nif_format",
)
