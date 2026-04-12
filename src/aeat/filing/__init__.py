"""Filing draft generation engine for AEAT modelos.

The :mod:`aeat.filing` subpackage owns the typed public API for
building, validating, and inspecting :class:`FilingDraft`
records — the project's single answer to *"what does the system
actually produce?"*.

Public API discipline: callers from outside this subpackage MUST
import only from :mod:`aeat.filing`. The concrete builders under
:mod:`aeat.filing._builders` are private; consumers select a
builder via :func:`build_draft` instead.

Example:
    ```python
    from decimal import Decimal

    from aeat.filing import (
        FilingDraft,
        FilingDraftStatus,
        build_draft,
        iter_findings,
    )
    from aeat.filing.testing import (
        SyntheticProfile,
        default_schema_provider,
    )

    profile = SyntheticProfile(
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
        schema_provider=default_schema_provider(),
    )
    assert draft.status is FilingDraftStatus.READY_TO_SUBMIT
    for finding in iter_findings(draft, severity_at_least="ERROR"):
        ...
    ```
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from aeat.logging import get_logger

from ._builder import FilingBuilder
from ._builders import Modelo130Builder, get_builder
from ._errors import (
    FilingBuilderError,
    FilingComputationError,
    FilingDraftError,
    FilingValidationError,
)
from ._protocols import (
    CasillaCollection,
    CasillaSchema,
    CasillaSchemaProvider,
    DeadlineChecker,
    DeadlineStatus,
    FilingInputs,
    FilingProfile,
    ModeloIdentity,
)
from ._schema import (
    SCHEMA_VERSION_DEFAULT,
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingScalar,
    FilingValidationFinding,
    FilingValue,
    FilingValueKind,
    compute_draft_id,
)
from ._validator import FilingValidator, apply_validation

_logger = get_logger(__name__)


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
        deadline_checker: Optional deadline check Protocol stub
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
    validator = FilingValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
    )
    findings = validator.validate(raw_draft)
    draft = apply_validation(raw_draft, findings)
    if fail_on_warning and any(f.severity is not FilingFindingSeverity.INFO for f in findings):
        raise FilingValidationError(f"Draft {draft.draft_id} has {len(findings)} blocking findings")
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
        deadline_checker: Optional deadline check Protocol stub.

    Returns:
        A new :class:`FilingDraft` with refreshed findings, status
        and ``updated_at``.
    """
    validator = FilingValidator(
        schema_provider=schema_provider,
        deadline_checker=deadline_checker,
    )
    findings = validator.validate(draft)
    refreshed = apply_validation(draft, findings)
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
        raise ValueError(f"Unknown severity {severity_at_least!r}; expected INFO, WARNING, or ERROR") from exc
    for finding in draft.findings:
        if _SEVERITY_RANK[finding.severity] >= threshold:
            yield finding


def utc_now() -> datetime:
    """Return the current UTC time, used by tests for determinism hooks."""
    return datetime.now(tz=UTC)


__all__ = [
    "SCHEMA_VERSION_DEFAULT",
    "CasillaCollection",
    "CasillaSchema",
    "CasillaSchemaProvider",
    "DeadlineChecker",
    "DeadlineStatus",
    "FilingBuilder",
    "FilingBuilderError",
    "FilingComputationError",
    "FilingDraft",
    "FilingDraftError",
    "FilingDraftStatus",
    "FilingFindingSeverity",
    "FilingInputs",
    "FilingProfile",
    "FilingScalar",
    "FilingValidationError",
    "FilingValidationFinding",
    "FilingValidator",
    "FilingValue",
    "FilingValueKind",
    "Modelo130Builder",
    "ModeloIdentity",
    "apply_validation",
    "build_draft",
    "compute_draft_id",
    "get_builder",
    "iter_findings",
    "utc_now",
    "validate_draft",
]
