"""Filing draft generation engine for AEAT modelos.

The :mod:`aeat.application.filing` subpackage owns the typed public API for
building, validating, and inspecting :class:`FilingDraft`
records — the project's single answer to *"what does the system
actually produce?"*.

Public API discipline: callers from outside this subpackage MUST
import only from :mod:`aeat.application.filing`. The concrete builders under
:mod:`aeat.domain.filing._builders` are private; consumers select a
builder via :func:`build_draft` instead.

Example:
    ```python
    from decimal import Decimal

    from . import (
        FilingDraft,
        FilingDraftStatus,
        build_draft,
        iter_findings,
    )
    from .runtime import (
        FilingOperatorProfile,
        build_runtime_schema_provider,
    )

    profile = FilingOperatorProfile(
        tax_id="00000000T",
        display_name="Autónomo Demo",
        applicable_modelos=("130",),
    )
    inputs = {
        "01": Decimal("12500.00"),  # Ingresos
        "02": Decimal("3500.00"),   # Gastos
        "05": Decimal("400.00"),    # Retenciones
        "06": Decimal("0.00"),      # Pagos fraccionados anteriores
    }
    draft: FilingDraft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=profile,
        inputs=inputs,
        schema_provider=build_runtime_schema_provider(),
    )
    assert draft.status is FilingDraftStatus.READY_TO_SUBMIT
    for finding in iter_findings(draft, severity_at_least="ERROR"):
        ...
    ```
"""

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
    Modelo130Builder,
    Modelo303Builder,
    Modelo390Builder,
    ModeloCode,
    ModeloIdentity,
    apply_validation,
    compute_draft_id,
    derive_validation_status,
    get_builder,
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
    Shape validation lives in :class:`Modelo390Builder` — this
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
    """Build, validate, and return a :class:`FilingDraft`.

    Args:
        modelo: Stable modelo string ID (e.g. ``"130"``).
        period: Period identifier (e.g. ``"2026Q1"``).
        profile: Taxpayer profile the draft is built for.
        inputs: Mapping of casilla ID → raw input value.
        schema_provider: Resolves the casilla collection for
            ``modelo``.
        deadline_checker: Optional deadline check Protocol implementation
            forwarded to the validator.
        fail_on_warning: When ``True``, the call raises
            :class:`FilingValidationError` if any finding is at
            ``WARNING`` severity or above. Defaults to ``False``;
            callers can also opt in via the
            ``AEAT_DRAFT_FAIL_ON_WARNING`` setting.

    Returns:
        A frozen :class:`FilingDraft` with findings populated and
        the status promoted by :func:`apply_validation`.

    Raises:
        FilingBuilderError: When no builder is registered for
            ``modelo``.
        FilingValidationError: When ``fail_on_warning`` is true
            and the validator surfaces a non-INFO finding.
    """
    builder = get_builder(modelo)
    raw_draft = builder.build(
        period=period,
        profile=profile,
        inputs=inputs,
        schema_provider=schema_provider,
    )
    quarterly_303_drafts = _extract_quarterly_303(modelo, inputs)
    validator = FilingValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
        quarterly_303_drafts=quarterly_303_drafts,
    )
    findings = validator.validate(raw_draft)
    draft = apply_validation(raw_draft, findings)
    if fail_on_warning and any(f.severity is not FilingFindingSeverity.INFO for f in findings):
        raise FilingValidationError(f"Draft {draft.draft_id} has {len(findings)} blocking findings")
    _logger.info(
        "built draft draft_id=%s modelo=%s period=%s status=%s findings=%d",
        draft.draft_id,
        draft.modelo,
        draft.period,
        draft.status.value,
        len(findings),
    )
    return draft


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
    "Modelo130Builder",
    "Modelo303Builder",
    "Modelo390Builder",
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
    "get_builder",
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
