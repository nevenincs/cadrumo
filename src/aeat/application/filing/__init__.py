"""Typed filing draft API guarded by registry-backed runtime providers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from ...core.logging import get_logger
from ...domain.filing import (
    APPROVAL_BASIS_VERSION,
    QUARTERLY_303_INPUT_KEY,
    SCHEMA_VERSION_DEFAULT,
    AmendmentKind,
    CasillaChange,
    CasillaCollection,
    CasillaDelta,
    CasillaInputs,
    CasillaSchema,
    CasillaSchemaProvider,
    DeadlineChecker,
    DeadlineStatus,
    FilingAmendment,
    FilingAmendmentError,
    FilingAmendmentValidationError,
    FilingApprovalBasis,
    FilingBuilder,
    FilingBuilderError,
    FilingComputationError,
    FilingDraft,
    FilingDraftError,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingImportError,
    FilingInputs,
    FilingProfile,
    FilingScalar,
    FilingValidationError,
    FilingValidationFinding,
    FilingValidator,
    FilingValue,
    FilingValueKind,
    ModeloCode,
    ModeloIdentity,
    apply_validation,
    compute_draft_id,
    derive_validation_status,
    make_amendment_id,
)
from ._calculate import (
    DeclarationCalculateNextAction,
    DeclarationCalculateSummary,
    summarise_calculation,
)
from ._complementaria import build_complementaria, list_amendments, load_amendment
from ._export import (
    DeclarationExportFormat,
    DeclarationExportResult,
    DeclarationVerifyResult,
    DeclarationVerifyVerdict,
    export_draft,
    verify_export,
)
from ._import import JustificanteImportResult, import_filing_from_justificante
from ._review import (
    FilingApprovalStaleReason,
    approval_stale_reasons,
    approve_draft,
    compute_current_approval_basis,
    compute_review_checksum,
    describe_stale_reason,
    refresh_review_status,
    unapprove_draft,
)
from .runtime import (
    FilingOperatorProfile,
    build_runtime_schema_provider,
    filing_profile_from_autonomo,
    load_default_filing_profile,
)

_logger = get_logger(__name__)


def _extract_quarterly_303(
    modelo: str,
    inputs: FilingInputs,
) -> tuple[FilingDraft, ...] | None:
    """Return the four quarterly 303 drafts, if the caller supplied them.

    The helper returns ``None`` for every modelo other than 390,
    and also when the reserved ``_quarterly_303`` key is absent.
    Shape validation lives in the validated registry snapshot — this
    function only pulls the tuple out of the inputs mapping so
    the validator can be wired at :func:`build_draft` call time.
    """
    if modelo != "390":
        return None
    raw = inputs.get(QUARTERLY_303_INPUT_KEY)
    if raw is None:
        return None
    if not isinstance(raw, tuple):
        _logger.warning(
            "quarterly_303 input has unexpected type %s; expected tuple — skipping",
            type(raw).__name__,
        )
        return None
    filtered: list[FilingDraft] = []
    for entry in raw:
        if isinstance(entry, FilingDraft):
            filtered.append(entry)
    if not filtered:
        _logger.warning(
            "quarterly_303 input tuple contained no FilingDraft entries — skipping",
        )
        return None
    return tuple(filtered)


def build_draft(
    *,
    modelo: str,
    period: str,
    profile: FilingProfile,
    inputs: FilingInputs,
    schema_provider: CasillaSchemaProvider,
    deadline_checker: DeadlineChecker | None = None,
    fail_on_warning: bool = False,
) -> FilingDraft:
    """Reject draft construction until validated registry snapshots exist.

    Args:
        modelo: Stable modelo string ID.
        period: Period identifier.
        profile: Taxpayer profile the draft would be built for.
        inputs: Raw filing inputs.
        schema_provider: Registry-backed casilla schema provider placeholder.
        deadline_checker: Optional deadline checker placeholder.
        fail_on_warning: Retained for API compatibility; ignored while the
            registry-backed builder is unavailable.

    Raises:
        FilingBuilderError: Always, until a validated registry snapshot builder
            replaces the legacy Python filing builders.
    """

    _ = (
        modelo,
        period,
        profile,
        inputs,
        schema_provider,
        deadline_checker,
        fail_on_warning,
    )
    raise FilingBuilderError(
        "filing draft construction requires a validated registry snapshot; "
        "legacy Python filing builders are disabled"
    )


def validate_draft(
    draft: FilingDraft,
    *,
    schema_provider: CasillaSchemaProvider,
    deadline_checker: DeadlineChecker | None = None,
) -> FilingDraft:
    """Re-run validation against an existing draft.

    The returned draft preserves ``draft_id`` because the hash
    excludes findings, status, ``updated_at`` and ``notes``.

    Args:
        draft: The draft to re-validate.
        schema_provider: Resolves the casilla collection for the
            draft's modelo.
        deadline_checker: Optional deadline check Protocol implementation.

    Returns:
        A new :class:`FilingDraft` with refreshed findings, status
        and ``updated_at``.
    """
    validator = FilingValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
        quarterly_303_drafts=None,
    )
    findings = validator.validate(draft)
    refreshed = apply_validation(draft, findings)
    refreshed = refresh_review_status(
        refreshed,
        schema_provider=schema_provider,
    )
    # Defensive sanity check: re-validation must never change identity.
    assert refreshed.draft_id == draft.draft_id, "validate_draft must preserve draft_id"
    return refreshed


_SEVERITY_RANK: dict[str, int] = {
    FilingFindingSeverity.INFO: 0,
    FilingFindingSeverity.WARNING: 1,
    FilingFindingSeverity.ERROR: 2,
}


def iter_findings(
    draft: FilingDraft,
    *,
    severity_at_least: str = "WARNING",
) -> Iterator[FilingValidationFinding]:
    """Yield findings filtered by minimum severity.

    Args:
        draft: The draft to scan.
        severity_at_least: Minimum severity to yield, one of
            ``"INFO"``, ``"WARNING"``, ``"ERROR"``. Defaults to
            ``"WARNING"``.

    Yields:
        Each :class:`FilingValidationFinding` whose severity meets
        or exceeds the threshold, in declaration order.

    Raises:
        ValueError: When ``severity_at_least`` is not a known
            severity name.
    """
    try:
        threshold = _SEVERITY_RANK[FilingFindingSeverity(severity_at_least)]
    except ValueError as exc:
        raise FilingBuilderError(f"Unknown severity {severity_at_least!r}; expected INFO, WARNING, or ERROR") from exc
    for finding in draft.findings:
        if _SEVERITY_RANK[finding.severity] >= threshold:
            yield finding


def utc_now() -> datetime:
    """Return the current UTC time, used by tests for determinism hooks."""
    return datetime.now(tz=UTC)


__all__ = [
    "APPROVAL_BASIS_VERSION",
    "QUARTERLY_303_INPUT_KEY",
    "SCHEMA_VERSION_DEFAULT",
    "AmendmentKind",
    "CasillaChange",
    "CasillaCollection",
    "CasillaDelta",
    "CasillaInputs",
    "CasillaSchema",
    "CasillaSchemaProvider",
    "DeadlineChecker",
    "DeadlineStatus",
    "DeclarationCalculateNextAction",
    "DeclarationCalculateSummary",
    "DeclarationExportFormat",
    "DeclarationExportResult",
    "DeclarationVerifyResult",
    "DeclarationVerifyVerdict",
    "FilingAmendment",
    "FilingAmendmentError",
    "FilingAmendmentValidationError",
    "FilingApprovalBasis",
    "FilingApprovalStaleReason",
    "FilingBuilder",
    "FilingBuilderError",
    "FilingComputationError",
    "FilingDraft",
    "FilingDraftError",
    "FilingDraftStatus",
    "FilingFindingSeverity",
    "FilingImportError",
    "FilingInputs",
    "FilingOperatorProfile",
    "FilingProfile",
    "FilingScalar",
    "FilingValidationError",
    "FilingValidationFinding",
    "FilingValidator",
    "FilingValue",
    "FilingValueKind",
    "JustificanteImportResult",
    "ModeloCode",
    "ModeloIdentity",
    "apply_validation",
    "approval_stale_reasons",
    "approve_draft",
    "build_complementaria",
    "build_draft",
    "build_runtime_schema_provider",
    "compute_current_approval_basis",
    "compute_draft_id",
    "compute_review_checksum",
    "derive_validation_status",
    "describe_stale_reason",
    "export_draft",
    "filing_profile_from_autonomo",
    "import_filing_from_justificante",
    "iter_findings",
    "list_amendments",
    "load_amendment",
    "load_default_filing_profile",
    "make_amendment_id",
    "refresh_review_status",
    "summarise_calculation",
    "unapprove_draft",
    "verify_export",
]
