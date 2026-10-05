"""Contract tests for authenticated read-only review operations."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core.config import Settings
from ....core.errors.error_codes import get_registered_error_code
from ....core.external_constants import OutputLanguage
from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...filing.draft_review_ports import DraftReviewPorts
from ...operations.public_scalar import PublicDecimal
from ...operations.registry import OperationRegistry
from ..enums import ReviewState
from ..errors import ReviewItemNotFoundError
from ..read_contracts import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewReadOperationPorts,
    ReviewViewReadRequest,
)
from ..read_operation import (
    ReviewQueueReadExecutor,
    ReviewViewReadExecutor,
)
from ..read_registration import (
    build_review_read_definitions,
    build_review_read_registrations,
)
from .draft_review_test_support import draft_review_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("23232323-2323-4232-8232-232323232323")


class _RecordingPortsFactory:
    def __init__(self) -> None:
        self.calls: list[tuple[str, PinnedAuthorityOperation]] = []
        self.ports = draft_review_ports()

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> DraftReviewPorts:
        self.calls.append((bucket_id, operation))
        return self.ports


def test_review_queue_capture_uses_profile_and_worker_pin_before_canonical_reader(
    operation: PinnedAuthorityOperation,
) -> None:
    factory = _RecordingPortsFactory()
    ports = ReviewReadOperationPorts(settings=Settings(), draft_review_ports_factory=factory)
    request = ReviewQueueReadRequest(
        profile_id=_PROFILE_ID,
        kinds=("ledger_transaction", "modelo_finding"),
        source_kinds=("modelo_finding", "ledger_transaction"),
        state=ReviewState.ALL,
        output_language=OutputLanguage.EN,
    )

    result = ReviewQueueReadExecutor(ports)._capture(request, operation)

    assert result.profile_id == _PROFILE_ID
    assert result.request == request
    assert result.rows == ()
    assert factory.calls == [(str(_PROFILE_ID), operation)]


def test_review_view_capture_preserves_not_found_error_without_echoing_item_id(
    operation: PinnedAuthorityOperation,
) -> None:
    factory = _RecordingPortsFactory()
    ports = ReviewReadOperationPorts(settings=Settings(), draft_review_ports_factory=factory)
    private_item_id = "tax-id-12345678Z-private-review-item"
    request = ReviewViewReadRequest(
        profile_id=_PROFILE_ID,
        item_id=private_item_id,
        output_language=OutputLanguage.EN,
    )

    with pytest.raises(ReviewItemNotFoundError) as exc_info:
        ReviewViewReadExecutor(ports)._capture(request, operation)

    assert exc_info.value.translated_message == "review.operator.errors.item_not_found"
    assert get_registered_error_code(exc_info.value).code == "REFUSED_REVIEW_ITEM_NOT_FOUND"
    assert exc_info.value.context is None
    assert private_item_id not in str(exc_info.value)
    assert factory.calls == [(str(_PROFILE_ID), operation)]


def test_queue_request_preserves_ordered_filters_and_bounds_confidence() -> None:
    request = ReviewQueueReadRequest(
        profile_id=_PROFILE_ID,
        kinds=("modelo_finding", "ledger_transaction"),
        source_kinds=("ledger_transaction", "modelo_finding"),
        confidence_below=PublicDecimal(decimal="0.50"),
        output_language=OutputLanguage.ES,
    )

    assert request.kinds == ("modelo_finding", "ledger_transaction")
    assert request.source_kinds == ("ledger_transaction", "modelo_finding")
    assert request.confidence_below is not None
    assert Decimal(request.confidence_below.decimal) == Decimal("0.50")

    with pytest.raises(ValidationError, match="confidence threshold"):
        ReviewQueueReadRequest(
            profile_id=_PROFILE_ID,
            confidence_below=PublicDecimal(decimal="1.01"),
            output_language=OutputLanguage.ES,
        )


def test_review_read_operations_bind_both_closed_public_schemas() -> None:
    ports = ReviewReadOperationPorts(settings=Settings(), draft_review_ports_factory=_RecordingPortsFactory())
    definitions = build_review_read_definitions(ports)
    registrations = build_review_read_registrations(definitions)

    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)

    assert tuple(definition.definition_id for definition in registry.definitions) == (
        REVIEW_QUEUE_OPERATION_DEFINITION_ID,
        REVIEW_VIEW_OPERATION_DEFINITION_ID,
    )
    assert {
        registry.lookup_public_contract(definition_id).definition_id
        for definition_id in (REVIEW_QUEUE_OPERATION_DEFINITION_ID, REVIEW_VIEW_OPERATION_DEFINITION_ID)
    } == {REVIEW_QUEUE_OPERATION_DEFINITION_ID, REVIEW_VIEW_OPERATION_DEFINITION_ID}
    assert all(
        OperationEffect.NONE in registry.lookup(definition_id).capabilities.permitted_effects
        for definition_id in (REVIEW_QUEUE_OPERATION_DEFINITION_ID, REVIEW_VIEW_OPERATION_DEFINITION_ID)
    )
