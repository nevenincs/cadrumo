"""The link result accepts only a linked outcome matching its request or a complete closed refusal."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import override_settings
from ....core.operations import profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.models import OperationRequest
from ..action_ports import LedgerActionPorts
from ..link_operation import (
    LedgerLinkExecutionResult,
    LedgerLinkOperationResult,
    LedgerLinkProjection,
    LedgerLinkRequest,
    build_ledger_link_definition,
)
from .bulk_classify_operation_support import PROFILE_ID
from .export_link_operation_support import Subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIFFERS = "ledger linkage outcome differs from its exact request"
_INCOMPLETE = "ledger linkage refusal is incomplete"
_CANDIDATES = "ambiguous invoice linkage requires distinct candidates"
_ONLY_AMBIGUOUS = "only an ambiguous invoice selector carries candidates"


@pytest.fixture
def linked(authority_operation: PinnedAuthorityOperation) -> Iterator[LedgerLinkOperationResult]:
    """A linked result the real executor produced for a synthetic transaction and invoice."""
    with override_settings(cadrumo_active_profile=str(PROFILE_ID)):
        subject = Subject(authority_operation)

        def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
            del bucket_id, operation
            return subject.ports

        definition = build_ledger_link_definition(factory)
        request = OperationRequest[BaseModel](
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
            payload=LedgerLinkRequest(
                profile_id=PROFILE_ID,
                transaction_id=subject.transaction.transaction_id,
                invoice_id=subject.invoice.invoice_id,
            ),
        )
        asyncio.run(definition.executor_factory.create().execute(request, subject.context(definition.definition_id)))
        retained = subject.operands.values[0]
        assert isinstance(retained, LedgerLinkExecutionResult)
        yield retained.result


def _linked(result: LedgerLinkOperationResult, **changes: object) -> LedgerLinkOperationResult:
    fields: dict[str, object] = {
        "profile_id": result.profile_id,
        "transaction_id": result.transaction_id,
        "invoice_id": result.invoice_id,
        "outcome": "linked",
        "projection": result.projection,
    }
    return LedgerLinkOperationResult.model_validate({**fields, **changes})


def _refused(**changes: object) -> LedgerLinkOperationResult:
    fields: dict[str, object] = {
        "profile_id": PROFILE_ID,
        "transaction_id": "a" * 12,
        "invoice_id": "b" * 12,
        "outcome": "refused",
    }
    return LedgerLinkOperationResult.model_validate({**fields, **changes})


def _projection(result: LedgerLinkOperationResult) -> LedgerLinkProjection:
    assert result.projection is not None
    return result.projection


def test_a_linked_result_matching_its_request_is_accepted(linked: LedgerLinkOperationResult) -> None:
    assert _linked(linked) == linked
    transaction_id = _projection(linked).transaction_id
    assert _linked(linked, transaction_id=f"  {transaction_id[:12].upper()} ").outcome == "linked"


@pytest.mark.parametrize(
    "change",
    [
        "reason",
        "no_projection",
        "other_profile",
        "other_invoice",
        "candidates",
        "other_transaction",
    ],
)
def test_a_linked_result_that_departs_from_its_request_is_refused(
    linked: LedgerLinkOperationResult, change: str
) -> None:
    projection = _projection(linked)
    changes: dict[str, dict[str, object]] = {
        "reason": {"reason": "missing_invoice"},
        "no_projection": {"projection": None},
        "other_profile": {"profile_id": uuid4()},
        "other_invoice": {"invoice_id": "f" * 12 if not projection.invoice_id.startswith("f") else "e" * 12},
        "candidates": {"candidate_invoice_ids": ("c" * 12, "d" * 12)},
        "other_transaction": {
            "transaction_id": "0" * 12 if not projection.transaction_id.startswith("0") else "1" * 12
        },
    }[change]

    with pytest.raises(ValidationError, match=_DIFFERS):
        _linked(linked, **changes)


def test_a_refusal_needs_a_reason_and_carries_no_projection(linked: LedgerLinkOperationResult) -> None:
    with pytest.raises(ValidationError, match=_INCOMPLETE):
        _refused()
    with pytest.raises(ValidationError, match=_INCOMPLETE):
        _refused(reason="missing_invoice", projection=linked.projection)
    with pytest.raises(ValidationError, match=_INCOMPLETE):
        _refused(projection=linked.projection)


@pytest.mark.parametrize("candidates", [(), ("c" * 12,), ("c" * 12, "c" * 12), ("c" * 12, "d" * 12, "c" * 12)])
def test_an_ambiguous_refusal_needs_distinct_candidates(candidates: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError, match=_CANDIDATES):
        _refused(reason="ambiguous_invoice", candidate_invoice_ids=candidates)


def test_an_ambiguous_refusal_names_its_distinct_candidates() -> None:
    result = _refused(reason="ambiguous_invoice", candidate_invoice_ids=("c" * 12, "d" * 12))
    assert result.candidate_invoice_ids == ("c" * 12, "d" * 12)


@pytest.mark.parametrize("reason", ["missing_invoice", "cross_bucket_invoice", "transaction_takes_no_invoice"])
def test_only_an_ambiguous_refusal_carries_candidates(reason: str) -> None:
    assert _refused(reason=reason).reason == reason
    with pytest.raises(ValidationError, match=_ONLY_AMBIGUOUS):
        _refused(reason=reason, candidate_invoice_ids=("c" * 12, "d" * 12))
