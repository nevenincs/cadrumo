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

from collections.abc import Iterator

from ...core.errors.severity import BaseSeverity as _BaseSeverity
from ...domain.filing.protocols import CasillaSchemaProvider as _CasillaSchemaProvider
from ...domain.filing.protocols import DeadlineChecker as _DeadlineChecker
from ...domain.filing.schema import ModeloDraft as _ModeloDraft
from ...domain.filing.schema import ModeloValidationFinding as _ModeloValidationFinding
from ...domain.filing.validator import ModeloValidator as _ModeloValidator
from ...domain.filing.validator import apply_validation as _apply_validation
from .draft_review import (
    refresh_review_status,
)
from .errors import ModeloApplicationError as ModeloApplicationError
from .errors import ModeloCalculateError


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
