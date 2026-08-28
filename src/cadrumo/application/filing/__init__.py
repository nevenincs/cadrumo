"""Public application facade for registry-backed filing drafts.

This package builds, reviews, approves, exports, verifies, imports, and
summarises local filing artefacts. All draft creation and validation consume
a :class:`RegistrySnapshot` to resolve the
active :class:`ModeloRevision`, its casilla
schema, relation inputs, and formula graph.

Major entry points:

* :func:`build_draft` constructs a validated
  :class:`ModeloDraft` from registry-backed inputs.
* :func:`approve_draft`, :func:`unapprove_draft`, and
  :func:`refresh_review_status` manage local review state and approval basis.
* :func:`export_draft` writes a local fichero-BOE artefact, and
  :func:`verify_export` re-reads that file through the registry export parser.
* :func:`import_filing_from_justificante` reconstructs a draft-level local
  receipt baseline and companion
  :class:`ModeloPresentado` audit record from a
  justificante PDF without treating the receipt as a casilla-value authority.
* :func:`build_complementaria`, :func:`list_amendments`, and
  :func:`load_amendment` build and read governed
  :class:`ModeloComplementaria` and
  :class:`ModeloSustitutiva` amendment records.
* :class:`ModeloHistoryRepository` persists encrypted lightweight
  :class:`ModeloHistory` summaries for local
  filing-history views.
* :func:`build_runtime_schema_provider` supplies the runtime registry view used
  by draft construction, review, export, and verification.

The facade deliberately separates local filing state from live submission.
Remote AEAT submission is not exposed here; attempted live writes are refused
by :class:`LiveSubmitForbiddenError`.

Imports from external PDFs stay evidence-scoped. A justificante import creates a
local draft plus submission-audit baseline, while casilla-complete declaration
and borrador parsing enter through the inbound adapter surfaces before
application services decide how that evidence participates in a work-unit
workflow.

Work-unit filing records for calculation revisions live in
:mod:`modelo` and :mod:`domain.modelos`. This package owns
draft-level construction, review, export, verification, justificante import,
local amendment construction, and lightweight local history; it does not create
:class:`ModeloRecord` entries or stamp :class:`ExternalEvidence`.

See Also:
    :mod:`modelo`
        Operator-facing modelo facade that carries calculation revisions into
        this filing surface.
    :func:`file_modelo_revision`
        Work-unit action that records a verified calculation revision as a
        current local :class:`ModeloRecord`.
    :func:`import_external_filing_evidence`
        External-evidence import path that creates an evidenced
        :class:`ModeloRecord` baseline for amendments.
    :mod:`domain.justificante`
        Receipt-metadata domain used by justificante PDF imports and
        receipt-bound external evidence.
    :mod:`domain.filing`
        Canonical draft records, values, provenance, validation findings, and
        review helpers.
    :mod:`domain.submission`
        Local-only submission audit records populated by justificante import;
        this is not an AEAT live-submit path.
    :mod:`domain.calculations.registry`
        Registry authority, snapshots, export layouts, and formula execution
        used by this application facade.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

from ...core.errors import BaseSeverity as _BaseSeverity
from ...domain.filing import (
    CasillaSchemaProvider as _CasillaSchemaProvider,
)
from ...domain.filing import (
    DeadlineChecker as _DeadlineChecker,
)
from ...domain.filing import (
    ModeloDraft as _ModeloDraft,
)
from ...domain.filing import (
    ModeloValidationFinding as _ModeloValidationFinding,
)
from ...domain.filing import (
    ModeloValidator as _ModeloValidator,
)
from ...domain.filing import (
    apply_validation as _apply_validation,
)
from ._calculate import (
    DeclaracionCalculateSummary,
    summarise_calculation,
)
from ._draft_construction import build_draft
from ._export_parity import did_page_required, required_applicable_casilla_ids
from ._export_producer import m303_rectificativa_motive_producer_values
from ._history_models import ModeloHistory, ModeloHistoryEntry
from ._history_repository import ModeloHistoryRepository
from ._import import JustificanteImportResult, import_filing_from_justificante
from ._m303_exonerado_390 import project_m303_exonerado_390_value_arrival
from ._m303_export_applicability import validate_m303_export_applicability
from ._producer_snapshot import (
    M202_UNSUPPORTED_PRODUCER_IDS,
    AmendmentEvidence,
    ChargeAccountSelection,
    DeclarationContactFacts,
    FilingElectionFacts,
    FilingModelProfileFacts,
    FilingProducerSnapshot,
    FilingProducerSnapshotError,
    GeneralFilingProfileFacts,
    M202UnsupportedProducerId,
    M303FilingFacts,
    M303InsolvencyFilingFact,
    M303InsolvencyFilingSubtype,
    Modelo111ProfileFacts,
    Modelo202ActivityFacts,
    Modelo202ProducerProfile,
    PresenterIdentity,
    RefundAccountSelection,
    SelectedFilingAccount,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    resolve_m303_filing_facts,
)
from ._profile_filing_retention import (
    FilingRetentionAuthority,
    try_record_filing_retention_snapshot,
)
from ._projection import FilingProjectionValue, FilingRecordRenderContext
from ._review import (
    ModeloApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    compute_current_approval_basis,
    compute_review_checksum,
    describe_stale_reason,
    empty_prior_filing_observations_fingerprint,
    empty_profile_activity_fingerprint,
    refresh_review_status,
    unapprove_draft,
)
from ._runtime_repository import modelo_record_repository_for_application
from .errors import ModeloApplicationError as ModeloApplicationError
from .errors import ModeloCalculateError
from .runtime import (
    ModeloOperatorProfile,
    build_runtime_schema_provider,
    filing_profile_from_taxpayer,
    load_default_filing_profile,
)

if TYPE_CHECKING:
    from ._complementaria import build_complementaria, list_amendments, load_amendment
    from ._export import (
        DeclaracionExportFormat,
        DeclaracionExportResult,
        DeclaracionVerifyResult,
        DeclaracionVerifyVerdict,
        FilingEnvelopeOccurrence,
        FilingEnvelopeRenderRequest,
        FilingEnvelopeRenderResult,
        FilingExportConsumedResult,
        FilingExportPayloadConsumer,
        FilingExportValidatedPayload,
        assert_export_artifact_matches_receipt,
        export_draft,
        export_layout_renderability_reason,
        render_envelope_prefix_field,
        render_filing_envelope,
        verify_export,
    )
    from ._export_proof import (
        FilingExportConformanceAuthority,
        FilingExportConformanceReceipt,
        FilingExportConformanceRenderInputs,
        FilingExportConformanceRequest,
        FilingExportConformanceVectorEvidence,
        FilingExportDictionaryValue,
        FilingExportGeneratedOutput,
        FilingExportOfficialProbe,
        FilingExportProof,
        FilingExportProofAssessment,
        FilingExportProofAuthority,
        FilingExportProofChannel,
        FilingExportProofCoordinate,
        FilingExportProofRefusal,
        FilingExportProofRefusalReason,
        FilingExportPublicProvenance,
        FilingExportSecureCustodyRecord,
        FilingExportSecureReplayCustody,
        FilingExportSecureReplayEvidence,
        FilingExportSecureReplayReceipt,
        FilingExportSecureReplayRequest,
        FilingExportSecureReplaySourceAuthority,
        FilingExportSourcePinnedProbeExpectation,
        prove_export_conformance,
        prove_secure_export_replay,
    )

_LAZY_EXPORTS: dict[str, str] = {
    "DeclaracionExportFormat": "._export",
    "DeclaracionExportResult": "._export",
    "DeclaracionVerifyResult": "._export",
    "DeclaracionVerifyVerdict": "._export",
    "FilingEnvelopeOccurrence": "._export",
    "FilingEnvelopeRenderRequest": "._export",
    "FilingEnvelopeRenderResult": "._export",
    "FilingExportConformanceAuthority": "._export_proof",
    "FilingExportConformanceReceipt": "._export_proof",
    "FilingExportConformanceRenderInputs": "._export_proof",
    "FilingExportConformanceRequest": "._export_proof",
    "FilingExportConformanceVectorEvidence": "._export_proof",
    "FilingExportConsumedResult": "._export",
    "FilingExportDictionaryValue": "._export_proof",
    "FilingExportGeneratedOutput": "._export_proof",
    "FilingExportOfficialProbe": "._export_proof",
    "FilingExportPayloadConsumer": "._export",
    "FilingExportProof": "._export_proof",
    "FilingExportProofAssessment": "._export_proof",
    "FilingExportProofAuthority": "._export_proof",
    "FilingExportProofChannel": "._export_proof",
    "FilingExportProofCoordinate": "._export_proof",
    "FilingExportProofRefusal": "._export_proof",
    "FilingExportProofRefusalReason": "._export_proof",
    "FilingExportPublicProvenance": "._export_proof",
    "FilingExportSecureCustodyRecord": "._export_proof",
    "FilingExportSecureReplayCustody": "._export_proof",
    "FilingExportSecureReplayEvidence": "._export_proof",
    "FilingExportSecureReplayReceipt": "._export_proof",
    "FilingExportSecureReplayRequest": "._export_proof",
    "FilingExportSecureReplaySourceAuthority": "._export_proof",
    "FilingExportSourcePinnedProbeExpectation": "._export_proof",
    "FilingExportValidatedPayload": "._export",
    "assert_export_artifact_matches_receipt": "._export",
    "build_complementaria": "._complementaria",
    "export_draft": "._export",
    "export_layout_renderability_reason": "._export",
    "list_amendments": "._complementaria",
    "load_amendment": "._complementaria",
    "prove_export_conformance": "._export_proof",
    "prove_secure_export_replay": "._export_proof",
    "render_envelope_prefix_field": "._export",
    "render_filing_envelope": "._export",
    "verify_export": "._export",
}
"""Names this package re-exports, resolved on first access.

Bounded exception, not a whole-namespace facade: only ``._complementaria``,
``._export``, and ``._export_proof`` stay lazy. Measured 2026-08-28 with a
fresh interpreter (``uv run --no-sync python``), eagerly importing every
_LAZY_EXPORTS target in turn against a base ``import cadrumo.application.filing``
of 749 modules / 1.745s:

    ._complementaria   +259 modules, 0.569s
    ._export           +152 modules, 0.913s

``._export_proof`` measured only +1 module in that same run, which looked
cheap enough to retire -- but that number was an artifact of measurement
order: ``._export`` had already been imported by an earlier target in the
same interpreter, so ``._export_proof``'s OWN cost (it imports ``._export`` at
its own top level, `._export_proof.py:31`) was silently paid by ``._export``'s
entry instead of its own. Retiring ``._export_proof`` to an eager import
verified this the hard way: a fresh-interpreter run showed `._export` fully
loaded as soon as the package was imported at all, even before ``export_draft``
was ever touched -- the bounded exception for ``._export`` was structurally
dead the moment ``._export_proof`` stopped deferring, because nothing can
import ``._export_proof`` without also paying for ``._export``. So
``._export_proof`` stays lazy alongside its dependency; every other prior
lazy target has no such edge back into ``._complementaria`` or ``._export``
(checked by grep against all fifteen retired submodules) and is imported
eagerly above.

``__getattr__`` runs only for names absent from module globals, so the
module's own definitions -- and now every eagerly re-imported name -- stay
untouched; only these three submodules' names still defer.
"""

_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve one re-exported name by importing only the sibling that owns it."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_LAZY_MODULE_LOADERS[module_name](), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


def validate_draft(
    draft: _ModeloDraft,
    *,
    bucket_id: str,
    schema_provider: _CasillaSchemaProvider,
    deadline_checker: _DeadlineChecker | None = None,
) -> _ModeloDraft:
    """Re-run validation against an existing draft.

    The returned draft preserves ``draft_id`` because the hash
    excludes findings, status, ``updated_at`` and ``notes``.

    Args:
        draft: The :class:`ModeloDraft` to re-validate.
        bucket_id: Stable bucket identifier; forwarded to
            :func:`refresh_review_status` after validation.
        schema_provider: :class:`CasillaSchemaProvider`
            resolving the casilla collection for the draft's modelo.
        deadline_checker: Optional :class:`DeadlineChecker`
            Protocol implementation.

    Returns:
        A new :class:`ModeloDraft` with refreshed findings,
        status and ``updated_at``.
    """
    validator = _ModeloValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
    )
    findings = validator.validate(draft)
    refreshed = _apply_validation(draft, findings)
    refreshed = refresh_review_status(
        refreshed,
        bucket_id=bucket_id,
        schema_provider=schema_provider,
    )
    # Defensive sanity check: re-validation must never change identity.
    assert refreshed.draft_id == draft.draft_id, "validate_draft must preserve draft_id"
    return refreshed


_SEVERITY_RANK: dict[str, int] = {
    _BaseSeverity.INFO: 0,
    _BaseSeverity.WARNING: 1,
    _BaseSeverity.ERROR: 2,
}


def iter_findings(
    draft: _ModeloDraft,
    *,
    severity_at_least: str = "WARNING",
) -> Iterator[_ModeloValidationFinding]:
    """Yield findings filtered by minimum severity.

    Args:
        draft: The :class:`ModeloDraft` to scan for
            validation findings.
        severity_at_least: Minimum severity to yield, one of
            ``"INFO"``, ``"WARNING"``, ``"ERROR"``. Defaults to
            ``"WARNING"``.

    Yields:
        Each :class:`ModeloValidationFinding` whose severity
        meets or exceeds the threshold, in declaration order.

    Raises:
        ModeloCalculateError: When ``severity_at_least`` is not a known
            severity name (``"INFO"``, ``"WARNING"``, or ``"ERROR"``).
    """
    try:
        threshold = _SEVERITY_RANK[_BaseSeverity[severity_at_least]]
    except KeyError as exc:
        raise ModeloCalculateError(
            translated_message="application.filing.errors.unknown_severity_threshold",
            context={
                "severity_at_least": severity_at_least,
                "accepted_severities": tuple(member.name for member in _BaseSeverity),
            },
        ) from exc
    for finding in draft.findings:
        if _SEVERITY_RANK[finding.severity] >= threshold:
            yield finding


__all__ = [
    "M202_UNSUPPORTED_PRODUCER_IDS",
    "AmendmentEvidence",
    "ChargeAccountSelection",
    "DeclaracionCalculateSummary",
    "DeclaracionExportFormat",
    "DeclaracionExportResult",
    "DeclaracionVerifyResult",
    "DeclaracionVerifyVerdict",
    "DeclarationContactFacts",
    "FilingElectionFacts",
    "FilingEnvelopeOccurrence",
    "FilingEnvelopeRenderRequest",
    "FilingEnvelopeRenderResult",
    "FilingExportConformanceAuthority",
    "FilingExportConformanceReceipt",
    "FilingExportConformanceRenderInputs",
    "FilingExportConformanceRequest",
    "FilingExportConformanceVectorEvidence",
    "FilingExportConsumedResult",
    "FilingExportDictionaryValue",
    "FilingExportGeneratedOutput",
    "FilingExportOfficialProbe",
    "FilingExportPayloadConsumer",
    "FilingExportProof",
    "FilingExportProofAssessment",
    "FilingExportProofAuthority",
    "FilingExportProofChannel",
    "FilingExportProofCoordinate",
    "FilingExportProofRefusal",
    "FilingExportProofRefusalReason",
    "FilingExportPublicProvenance",
    "FilingExportSecureCustodyRecord",
    "FilingExportSecureReplayCustody",
    "FilingExportSecureReplayEvidence",
    "FilingExportSecureReplayReceipt",
    "FilingExportSecureReplayRequest",
    "FilingExportSecureReplaySourceAuthority",
    "FilingExportSourcePinnedProbeExpectation",
    "FilingExportValidatedPayload",
    "FilingModelProfileFacts",
    "FilingProducerSnapshot",
    "FilingProducerSnapshotError",
    "FilingProjectionValue",
    "FilingRecordRenderContext",
    "FilingRetentionAuthority",
    "GeneralFilingProfileFacts",
    "JustificanteImportResult",
    "M202UnsupportedProducerId",
    "M303FilingFacts",
    "M303InsolvencyFilingFact",
    "M303InsolvencyFilingSubtype",
    "Modelo111ProfileFacts",
    "Modelo202ActivityFacts",
    "Modelo202ProducerProfile",
    "ModeloApplicationError",
    "ModeloApprovalStaleReason",
    "ModeloCalculateError",
    "ModeloHistory",
    "ModeloHistoryEntry",
    "ModeloHistoryRepository",
    "ModeloOperatorProfile",
    "PresenterIdentity",
    "RefundAccountSelection",
    "SelectedFilingAccount",
    "TaxpayerIdentityFacts",
    "approval_stale_reasons",
    "approve_draft",
    "assert_export_artifact_matches_receipt",
    "build_complementaria",
    "build_draft",
    "build_filing_producer_snapshot",
    "build_runtime_schema_provider",
    "compute_current_approval_basis",
    "compute_review_checksum",
    "describe_stale_reason",
    "did_page_required",
    "empty_prior_filing_observations_fingerprint",
    "empty_profile_activity_fingerprint",
    "export_draft",
    "export_layout_renderability_reason",
    "filing_profile_from_taxpayer",
    "import_filing_from_justificante",
    "iter_findings",
    "list_amendments",
    "load_amendment",
    "load_default_filing_profile",
    "m303_rectificativa_motive_producer_values",
    "modelo_record_repository_for_application",
    "project_m303_exonerado_390_value_arrival",
    "prove_export_conformance",
    "prove_secure_export_replay",
    "refresh_review_status",
    "render_envelope_prefix_field",
    "render_filing_envelope",
    "required_applicable_casilla_ids",
    "resolve_m303_filing_facts",
    "summarise_calculation",
    "try_record_filing_retention_snapshot",
    "unapprove_draft",
    "validate_m303_export_applicability",
    "verify_export",
]
