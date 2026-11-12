"""Errors raised while addressing and selecting Modelo work units and calculation revisions.

Each class is a registered refusal. The selector classes state the door of the
cause: an unmatched or ambiguous selector opens the work list, an operator
token the registry refuses opens the listing that states valid choices, and an
internally inconsistent revision pick is terminal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.errors import ModeloError
from ..operator_actions.models import PreconditionVerdict
from .action_errors import ModeloPreconditionErrorMixin
from .lifecycle_view_refusal_doors import work_list_verdict
from .work_lifecycle_refusal_failures import selector_contradiction_failure

if TYPE_CHECKING:
    from .work_selection import ModeloWorkUnitCandidate


class ModeloWorkSelectorError(ModeloError):
    """Base error for Modelo work-selection refusals."""


class ModeloWorkNoActiveBucketError(ModeloWorkSelectorError):
    """Raised when an implicit selector cannot capture an active bucket."""


class ModeloWorkUnitNotFoundError(ModeloWorkSelectorError):
    """Raised when an exact work identifier resolves no all-state unit."""


class ModeloWorkSelectorContradictionError(ModeloPreconditionErrorMixin, ModeloWorkSelectorError):
    """Raised when an exact selector contradicts supplied coordinates.

    The work list shows the coordinates each unit holds, from which the
    operator states a consistent selector. A raise site that finds the
    application's own resolution incoherent carries its own terminal failure.
    """

    @property
    @override
    def terminal_precondition_verdict(self) -> PreconditionVerdict:
        """Expose the carried verdict, or the work list door of a contradictory selector."""
        failure = self.precondition_failure
        return (failure or selector_contradiction_failure()).verdict


class ModeloWorkVisibleTargetAmbiguousError(ModeloWorkSelectorError):
    """Raised after the deterministic complete candidate set has cardinality > 1."""

    def __init__(self, candidates: tuple[ModeloWorkUnitCandidate, ...], *, selector: str | None = None) -> None:
        """Retain the full candidate set and optional exact-id token."""
        self.candidates = candidates
        self.selector = selector
        super().__init__(
            translated_message="errors.refused.modelo_work_selector_ambiguous",
            context={"candidate_count": len(candidates), "exact_id_selector": selector is not None},
            precondition_verdict=work_list_verdict("work_selector_ambiguous"),
        )


class ModeloWorkRevisionConflictError(ModeloWorkSelectorError):
    """Raised only after a singleton natural candidate fails its revision assertion."""

    def __init__(
        self,
        *,
        requested_revision_id: RevisionId,
        existing: ModeloWorkUnitCandidate,
        precondition_verdict: PreconditionVerdict,
    ) -> None:
        """Retain the failed revision assertion and existing work candidate."""
        self.requested_revision_id = requested_revision_id
        self.existing = existing
        super().__init__(
            translated_message="errors.refused.modelo_work_selector_revision_conflict",
            context={"requested_revision": requested_revision_id, "work_unit_id": existing.work_unit_id},
            precondition_verdict=precondition_verdict,
        )


class ModeloRevisionPickError(ModeloError):
    """Raised when a calculation-revision selector is internally inconsistent."""


class ModeloWorkAddressNotFoundError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a natural modelo work address resolves no work unit."""


class ModeloWorkRegistryYearMismatchError(ModeloError):
    """Raised when an explicit revision diverges from the law-determined one."""


class ModeloWorkPeriodTokenError(ModeloError):
    """Raised when an operator-facing period token cannot be normalized."""

    def __init__(
        self,
        *,
        year: int,
        token: str,
        modelo: str | None,
        declared_tokens: tuple[str, ...],
        precondition_verdict: PreconditionVerdict,
    ) -> None:
        """Record the rejected token and the declared alternatives for its target."""
        context = {
            "year": year,
            "token": token,
            "modelo": modelo or "",
            "tokens": ", ".join(declared_tokens),
        }
        super().__init__(
            context=context,
            translated_message=(
                "application.modelo.errors.work_period_token_invalid"
                if declared_tokens
                else "application.modelo.errors.work_period_token_unrecognised"
            ),
            precondition_verdict=precondition_verdict,
        )


__all__ = [
    "ModeloRevisionPickError",
    "ModeloWorkAddressNotFoundError",
    "ModeloWorkNoActiveBucketError",
    "ModeloWorkPeriodTokenError",
    "ModeloWorkRegistryYearMismatchError",
    "ModeloWorkRevisionConflictError",
    "ModeloWorkSelectorContradictionError",
    "ModeloWorkSelectorError",
    "ModeloWorkUnitNotFoundError",
    "ModeloWorkVisibleTargetAmbiguousError",
]
