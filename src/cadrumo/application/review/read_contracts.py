"""Request and port contracts for authenticated review reads."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Protocol, Self
from uuid import UUID

from pydantic import Field, model_validator

from ...core.config import Settings
from ...core.external_constants import OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.unit_proportion import is_unit_proportion
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..filing.draft_review_ports import DraftReviewPorts
from ..operations.models import CredentialFreeOperationRequest
from ..operations.public_scalar import PublicDecimal
from .enums import ReviewState

REVIEW_QUEUE_OPERATION_DEFINITION_ID = "app.review.queue"


REVIEW_VIEW_OPERATION_DEFINITION_ID = "app.review.view"


_MAX_SELECTOR_COUNT = 128


_ReviewSelectors = Annotated[tuple[str, ...], Field(max_length=_MAX_SELECTOR_COUNT)]


class ReviewReadPortsFactory(Protocol):
    """Create the canonical review reader capabilities under the worker pin."""

    def __call__(
        self,
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
    ) -> DraftReviewPorts:
        """Return the encrypted source readers for this exact profile and pin."""
        ...


@dataclass(frozen=True, slots=True)
class ReviewReadOperationPorts:
    """Dependencies shared by the two immutable review reads."""

    settings: Settings
    draft_review_ports_factory: ReviewReadPortsFactory


class ReviewQueueReadRequest(CredentialFreeOperationRequest):
    """One ordered, profile-wide queue query."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kinds: _ReviewSelectors = ()
    source_kinds: _ReviewSelectors = ()
    state: ReviewState = ReviewState.PENDING
    modelo: str | None = None
    confidence_below: PublicDecimal | None = None
    output_language: OutputLanguage

    @model_validator(mode="after")
    def _confidence_threshold(self) -> Self:
        if self.confidence_below is not None and not is_unit_proportion(Decimal(self.confidence_below.decimal)):
            raise ValueError("review confidence threshold must be between zero and one")
        return self


class ReviewViewReadRequest(CredentialFreeOperationRequest):
    """One exact review item lookup in the active profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    item_id: str = Field(min_length=1)
    output_language: OutputLanguage


__all__ = [
    "REVIEW_QUEUE_OPERATION_DEFINITION_ID",
    "REVIEW_VIEW_OPERATION_DEFINITION_ID",
    "ReviewQueueReadRequest",
    "ReviewReadOperationPorts",
    "ReviewReadPortsFactory",
    "ReviewViewReadRequest",
]
